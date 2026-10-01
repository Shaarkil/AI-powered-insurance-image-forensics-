from flask import Flask, request, jsonify, render_template_string
from PIL import Image, ImageFilter
import io, numpy as np, os, base64, requests

app = Flask(__name__)

MODEL_URL = "https://huggingface.co/Organika/sdxl-detector/resolve/main/model.onnx"
MODEL_PATH = "detector.onnx"
onnx_sess = None
onnx_input_name = None

def load_onnx():
    global onnx_sess, onnx_input_name
    try:
        import onnxruntime as ort
        if not os.path.exists(MODEL_PATH):
            print("Downloading ONNX 90MB...")
            r = requests.get(MODEL_URL, stream=True, timeout=120)
            with open(MODEL_PATH, 'wb') as f:
                for chunk in r.iter_content(8192):
                    if chunk: f.write(chunk)
        onnx_sess = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
        onnx_input_name = onnx_sess.get_inputs()[0].name
        print("ONNX loaded")
    except Exception as e:
        print(f"ONNX off: {e}")
        onnx_sess = None

def onnx_predict(pil_img):
    if onnx_sess is None: return None
    try:
        img = pil_img.resize((224,224)).convert('RGB')
        arr = np.array(img).astype(np.float32)/255.0
        arr = arr.transpose(2,0,1)[None,...]
        mean = np.array([0.485,0.456,0.406]).reshape(1,3,1,1)
        std = np.array([0.229,0.224,0.225]).reshape(1,3,1,1)
        arr = (arr-mean)/std
        out = onnx_sess.run(None, {onnx_input_name: arr})[0]
        prob = float(out[0][1]) if out.shape[-1]==2 else float(out[0][0])
        if prob <=1: prob*=100
        return max(0,min(98,prob))
    except: return None

def get_prnu(pil_img):
    gray = np.array(pil_img.resize((256,256)).convert('L'), dtype=np.float32)
    blur = np.array(pil_img.resize((256,256)).filter(ImageFilter.GaussianBlur(radius=2)).convert('L'), dtype=np.float32)
    res = gray-blur
    energy = float(np.var(res))
    return energy, energy>12

def analyze_v30_strict(pil_img, file_bytes, filename):
    W,H = pil_img.size
    if max(W,H)>900:
        pil_img.thumbnail((900,900))
        W,H=pil_img.size

    ext = filename.split('.')[-1].lower() if '.' in filename else 'jpg'
    size_kb = len(file_bytes)/1024

    try: exif = pil_img._getexif(); exif_len=len(exif) if exif else 0
    except: exif_len=0

    small = pil_img.resize((256,256))
    arr = np.array(small)
    noise = float(np.std(arr))

    buf=io.BytesIO(); pil_img.save(buf,'JPEG',quality=90); buf.seek(0)
    recomp=Image.open(buf).resize((W,H))
    diff=np.abs(np.array(pil_img).astype(int)-np.array(recomp).astype(int))
    ela_var=float(np.std(diff))

    prnu_e, has_prnu = get_prnu(pil_img)
    has_c2pa = b'c2pa' in file_bytes[:60000]

    # ===== STRICT CHAIN OF CUSTODY =====
    fake = 0
    reasons = []
    chain = "UNKNOWN"

    # 1. INSTANT REJECT - ANY STRIPPED SOURCE
    if exif_len == 0:
        fake += 35
        reasons.append("NO_EXIF_STRIPPED_SOURCE")
        if size_kb < 350:
            fake += 15
            chain = "WHATSAPP/TELEGRAM - REJECT"
            reasons.append("WHATSAPP_TELEGRAM_REJECT")
        elif ext == 'png':
            fake += 20
            chain = "SCREENSHOT/PNG - REJECT"
            reasons.append("SCREENSHOT_REJECT")
        elif size_kb < 800:
            chain = "GOOGLE_DRIVE/DOWNLOADED - REJECT"
            fake += 15
            reasons.append("INTERNET_DOWNLOAD_REJECT")
        else:
            chain = "STRIPPED_NO_EXIF - REJECT"
    else:
        chain = "CAMERA_ORIGINAL - CHECK"
        fake -= 25
        reasons.append(f"HAS_EXIF_{exif_len}")

    # 2. DOCUMENT UPLOAD (even if has EXIF, it's not original camera capture)
    # If client sends as Document on WhatsApp, it keeps EXIF but size is original
    # We allow it ONLY if PRNU + NOISE also present
    if exif_len > 0 and not has_prnu:
        fake += 20
        reasons.append("EXIF_BUT_NO_SENSOR_POSSIBLE_EDIT")

    # 3. SENSOR CHECK
    if not has_prnu:
        fake += 25
        reasons.append("NO_PRNU_SENSOR")
    else:
        fake -= 20

    if noise < 12:
        fake += 25
        reasons.append("AI_PLASTIC_SMOOTH")
    elif noise < 18:
        fake += 10
    elif noise > 24:
        fake -= 10

    if ela_var < 5:
        fake += 15
        reasons.append("FLAT_ELA_AI")

    # 4. ONNX AI CHECK - even camera images can be AI edited
    fake_onnx = onnx_predict(pil_img)
    if fake_onnx is not None:
        if fake_onnx > 70:
            fake += 25
        reasons.append(f"AI_MODEL_{fake_onnx:.0f}%")
        final = fake*0.5 + fake_onnx*0.5
    else:
        final = fake
        reasons.append("ONNX_OFF")

    final = max(5, min(97, final))

    # Force HIGH if stripped
    if exif_len == 0 and final < 70:
        final = 75 # force reject

    heat = (diff*12).clip(0,255).astype(np.uint8)
    b=io.BytesIO(); Image.fromarray(heat).save(b,format='PNG')
    h64=base64.b64encode(b.getvalue()).decode()

    metrics = {
        "Noise": round(noise,1),
        "ELA": round(ela_var,2),
        "PRNU_E": round(prnu_e,1),
        "EXIF": exif_len,
        "SizeKB": round(size_kb,1),
        "ONNX": round(fake_onnx,1) if fake_onnx else "OFF"
    }

    return final, metrics, "data:image/png;base64,"+h64, chain, reasons, has_prnu, has_c2pa, fake_onnx

load_onnx()

@app.route('/')
def home():
    return render_template_string(open('index.html').read())

@app.route('/analyze', methods=['POST'])
def analyze_route():
    f=request.files.get('image')
    fb=f.read()
    pil=Image.open(io.BytesIO(fb)).convert('RGB')
    final, metrics, heat, chain, reasons, has_prnu, has_c2pa, fake_onnx = analyze_v30_strict(pil, fb, f.filename or "image.jpg")

    # STRICT THRESHOLDS
    if "REJECT" in chain or final >= 65:
        tier="HIGH"; verdict=f"REJECTED - {chain} {final:.0f}%"
    elif final >= 40:
        tier="MEDIUM"; verdict=f"SUSPICIOUS - MANUAL REVIEW {final:.0f}%"
    else:
        tier="LOW"; verdict=f"ACCEPTED - ORIGINAL CAMERA {final:.0f}%"

    return jsonify({
        "verdict": verdict,
        "risk_tier": tier,
        "real_percent": round(100-final,1),
        "fake_percent": round(final,1),
        "onnx_percent": round(fake_onnx,1) if fake_onnx else None,
        "metrics": metrics,
        "chain_of_custody": chain,
        "c2pa_status": "PRESENT" if has_c2pa else "MISSING",
        "prnu_status": "PRNU FOUND" if has_prnu else "NO PRNU",
        "heatmap": heat,
        "flags": reasons
    })

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
