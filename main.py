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
            print("Downloading 90MB ONNX detector...")
            r = requests.get(MODEL_URL, stream=True, timeout=120)
            r.raise_for_status()
            with open(MODEL_PATH, 'wb') as f:
                for chunk in r.iter_content(chunk_size=8192):
                    if chunk:
                        f.write(chunk)
            print("Download done")
        onnx_sess = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
        onnx_input_name = onnx_sess.get_inputs()[0].name
        print(f"ONNX loaded: {onnx_input_name}")
    except Exception as e:
        print(f"ONNX load failed, heuristic only: {e}")
        onnx_sess = None

def onnx_predict(pil_img):
    if onnx_sess is None:
        return None
    try:
        img = pil_img.resize((224, 224)).convert('RGB')
        arr = np.array(img).astype(np.float32) / 255.0
        arr = arr.transpose(2, 0, 1)
        arr = np.expand_dims(arr, axis=0)
        mean = np.array([0.485, 0.456, 0.406], dtype=np.float32).reshape(1, 3, 1, 1)
        std = np.array([0.229, 0.224, 0.225], dtype=np.float32).reshape(1, 3, 1, 1)
        arr = (arr - mean) / std
        inputs = {onnx_input_name: arr}
        out = onnx_sess.run(None, inputs)[0]
        # output is [batch, 2] -> prob fake is index 1
        if out.shape[-1] == 2:
            prob_fake = float(out[0][1])
        else:
            prob_fake = float(out[0][0])
        # convert 0-1 to 0-100
        if prob_fake <= 1.0:
            prob_fake = prob_fake * 100.0
        return max(0, min(98, prob_fake))
    except Exception as e:
        print(f"ONNX infer error: {e}")
        return None

def get_prnu(pil_img):
    gray = np.array(pil_img.resize((256, 256)).convert('L'), dtype=np.float32)
    blur = np.array(pil_img.resize((256, 256)).filter(ImageFilter.GaussianBlur(radius=2)).convert('L'), dtype=np.float32)
    res = gray - blur
    energy = float(np.var(res))
    fft = np.abs(np.fft.fftshift(np.fft.fft2(res)))
    h, w = fft.shape
    center = fft[h//4:3*h//4, w//4:3*w//4].mean()
    hf = float(fft.mean() / (center + 1e-6))
    has = energy > 12 and hf > 1.4
    return energy, hf, has

def analyze(pil_img, file_bytes, filename):
    W, H = pil_img.size
    if max(W, H) > 800:
        pil_img.thumbnail((800, 800))
        W, H = pil_img.size

    ext = filename.split('.')[-1].lower() if '.' in filename else 'jpg'
    size_kb = len(file_bytes) / 1024
    try:
        exif = pil_img._getexif()
        exif_len = len(exif) if exif else 0
    except:
        exif_len = 0

    small = pil_img.resize((256, 256))
    arr = np.array(small)
    noise = float(np.std(arr))
    gray_mean = np.mean(arr, axis=2)
    sharp = float(np.var(np.diff(gray_mean, axis=0)) + np.var(np.diff(gray_mean, axis=1)))

    buf = io.BytesIO()
    pil_img.save(buf, 'JPEG', quality=90)
    buf.seek(0)
    recomp = Image.open(buf).resize((W, H))
    diff = np.abs(np.array(pil_img).astype(int) - np.array(recomp).astype(int))
    ela_var = float(np.std(diff))

    prnu_e, prnu_hf, has_prnu = get_prnu(pil_img)
    has_c2pa = b'c2pa' in file_bytes[:60000] or b'jumbf' in file_bytes[:60000]

    plate_crop = pil_img.crop((int(W*0.2), int(H*0.45), int(W*0.8), int(H*0.85))).resize((200, 100))
    plate_sharp = float(np.var(np.mean(np.array(plate_crop), axis=2)))

    def tread_score(c):
        g = np.mean(np.array(c.resize((128, 128))), axis=2)
        return float(np.std(np.diff(g, axis=1)))

    tread = (tread_score(pil_img.crop((0, int(H*0.6), int(W*0.4), H))) + tread_score(pil_img.crop((int(W*0.6), int(H*0.6), W, H)))) / 2.0

    fake_h = 0
    reasons = []
    if not has_prnu:
        fake_h += 30
        reasons.append("NO_PRNU")
    else:
        fake_h -= 20
    if noise < 9:
        fake_h += 25
        reasons.append("PLASTIC")
    elif noise < 13:
        fake_h += 15
    if ela_var < 4.5:
        fake_h += 25
        reasons.append("FLAT_ELA")
    elif ela_var < 7:
        fake_h += 12
    if exif_len == 0:
        fake_h += 18
        reasons.append("NO_EXIF")
    if ext == 'png' and exif_len == 0:
        fake_h += 12
        reasons.append("SCREENSHOT")
    if plate_sharp < 350:
        fake_h += 10
        reasons.append("MELTED_PLATE")
    if tread < 7.5:
        fake_h += 10
        reasons.append("NO_TREAD")
    fake_h = max(5, min(97, fake_h))

    fake_onnx = onnx_predict(pil_img)
    if fake_onnx is not None:
        final_fake = fake_h * 0.45 + fake_onnx * 0.55
        reasons.append(f"ONNX_{fake_onnx:.0f}%")
    else:
        final_fake = fake_h
        reasons.append("ONNX_OFFLINE")

    final_fake = max(5, min(97, final_fake))

    heat = (diff * 12).clip(0, 255).astype(np.uint8)
    b = io.BytesIO()
    Image.fromarray(heat).save(b, format='PNG')
    h64 = base64.b64encode(b.getvalue()).decode()

    chain = "WHATSAPP" if exif_len == 0 and size_kb < 350 else "SCREENSHOT" if ext == 'png' and exif_len == 0 else "DOCUMENT" if exif_len > 0 else "COMPRESSED"
    metrics = {"Noise": round(noise, 1), "ELA": round(ela_var, 2), "PRNU_E": round(prnu_e, 1), "EXIF": exif_len, "ONNX": round(fake_onnx, 1) if fake_onnx else "OFF"}

    return final_fake, fake_h, fake_onnx, metrics, "data:image/png;base64," + h64, chain, reasons, has_prnu, has_c2pa

load_onnx()

@app.route('/')
def home():
    return render_template_string(open('index.html').read())

@app.route('/analyze', methods=['POST'])
def analyze_route():
    f = request.files.get('image')
    fb = f.read()
    pil = Image.open(io.BytesIO(fb)).convert('RGB')
    final_fake, fake_h, fake_onnx, metrics, heat, chain, reasons, has_prnu, has_c2pa = analyze(pil, fb, f.filename or "image.jpg")
    tier = "HIGH" if final_fake >= 65 else "MEDIUM" if final_fake >= 40 else "LOW"
    verdict = "AI GENERATED - REJECT" if tier == "HIGH" else "SUSPICIOUS" if tier == "MEDIUM" else "LIKELY REAL"
    return jsonify({
        "verdict": f"{verdict} {final_fake:.0f}%",
        "risk_tier": tier,
        "real_percent": round(100 - final_fake, 1),
        "fake_percent": round(final_fake, 1),
        "heuristic_percent": round(fake_h, 1),
        "onnx_percent": round(fake_onnx, 1) if fake_onnx else None,
        "metrics": metrics,
        "chain_of_custody": chain,
        "c2pa_status": "PRESENT" if has_c2pa else "MISSING",
        "prnu_status": "PRNU FOUND" if has_prnu else "NO PRNU",
        "heatmap": heat,
        "flags": reasons
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
