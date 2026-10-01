from flask import Flask, request, jsonify, render_template_string
from PIL import Image, ExifTags, ImageFilter
import io, numpy as np, os, base64

app = Flask(__name__)

# ---------- C2PA + CHAIN ----------
def get_c2pa(file_bytes):
    head = file_bytes[:60000]
    return b'c2pa' in head or b'jumbf' in head

def get_prnu(pil_img):
    gray = np.array(pil_img.resize((256,256)).convert('L'), dtype=np.float32)
    blur = np.array(pil_img.resize((256,256)).filter(ImageFilter.GaussianBlur(2)).convert('L'), dtype=np.float32)
    res = gray - blur
    energy = float(np.var(res))
    fft = np.abs(np.fft.fftshift(np.fft.fft2(res)))
    h,w = fft.shape
    center = fft[h//4:3*h//4, w//4:3*w//4].mean()
    edge = fft.mean()
    hf = float(edge/(center+1e-6))
    has_prnu = energy > 12 and hf > 1.4
    return has_prnu, energy, hf

def detect_chain(pil_img, file_bytes, filename):
    W,H = pil_img.size
    ext = (filename.split('.')[-1] if '.' in filename else 'jpg').lower()
    try:
        exif = pil_img._getexif()
        exif_len = len(exif) if exif else 0
    except:
        exif_len=0
    
    size_kb = len(file_bytes)/1024
    is_raw = ext in ['dng','arw','cr2','nef','raw','tiff','tif']
    is_png = ext=='png'
    is_screenshot = False
    channel="UNKNOWN"
    
    if is_png and exif_len==0 and (W in [1080,720,1440] or H in [2400,2340,1920] or W*H>1500000):
        is_screenshot=True
        channel="SCREENSHOT - LOSSY COPY, C2PA STRIPPED"
    elif is_raw:
        channel=f"RAW .{ext.upper()} - BEST EVIDENCE"
    elif is_png and exif_len>5:
        channel="PNG DOCUMENT UPLOAD - PRESERVED"
    elif is_png:
        channel="PNG SCREENSHOT/CROP - CHECK"
    else:
        if exif_len==0 and max(W,H)<=1600 and size_kb<350:
            channel="WHATSAPP / TELEGRAM COMPRESSED"
        elif exif_len==0 and size_kb<500:
            channel="SOCIAL COMPRESSED"
        elif exif_len>0 and size_kb>600:
            channel="ORIGINAL JPEG / DOCUMENT - PRESERVED"
        else:
            channel="COMPRESSED JPEG"
    
    has_c2pa = get_c2pa(file_bytes)
    c2pa_status = "C2PA PRESENT" if has_c2pa else "C2PA MISSING - STRIPPED"
    
    has_prnu, prnu_e, prnu_hf = get_prnu(pil_img)
    prnu_flag = "REAL SENSOR PRNU FOUND" if has_prnu else "NO PRNU - AI OR SCREENSHOT"
    
    return channel, c2pa_status, prnu_flag, has_c2pa, has_prnu, prnu_e, prnu_hf, exif_len, size_kb, ext.upper(), is_screenshot, is_raw

# ---------- MAIN ANALYZER V26 ----------
def analyze_v26(pil_img, file_bytes, filename):
    W,H = pil_img.size
    if max(W,H)>800:
        pil_img.thumbnail((800,800))
        W,H = pil_img.size
    
    small = pil_img.resize((256,256))
    arr = np.array(small)
    noise = float(np.std(arr))
    gray = np.mean(arr, axis=2)
    sharp = float(np.var(np.diff(gray,axis=0)) + np.var(np.diff(gray,axis=1)))
    
    # ELA
    buf=io.BytesIO()
    pil_img.save(buf,'JPEG',quality=90)
    buf.seek(0)
    recomp=Image.open(buf).resize((W,H))
    diff=np.abs(np.array(pil_img).astype(int)-np.array(recomp).astype(int))
    ela_var=float(np.std(diff))
    
    # CHAIN + PRNU
    channel,c2pa_status,prnu_flag,has_c2pa,has_prnu,prnu_e,prnu_hf,exif_len,size_kb,ext,is_screenshot,is_raw = detect_chain(pil_img,file_bytes,filename)
    
    # PLATE CHECK
    px0,px1 = int(W*0.2), int(W*0.8)
    py0,py1 = int(H*0.45), int(H*0.85)
    plate = np.array(pil_img.crop((px0,py0,px1,py1)).resize((200,100)))
    plate_sharp = float(np.var(np.mean(plate,axis=2)))
    plate_flag = "FAKE_PLATE" if plate_sharp<400 else "OK_PLATE"
    
    # TIRE CHECK
    def tread_score(crop):
        g=np.mean(np.array(crop.resize((128,128))),axis=2)
        return float(np.std(np.diff(g,axis=1)))
    tl = pil_img.crop((0,int(H*0.6),int(W*0.4),H))
    tr = pil_img.crop((int(W*0.6),int(H*0.6),W,H))
    tread = (tread_score(tl)+tread_score(tr))/2
    tire_flag = "FAKE_TIRE" if tread<8 else "OK_TIRE"
    
    # REFLECTION SYMMETRY
    left = np.array(pil_img.crop((0,0,W//2,H)).resize((128,128))).astype(int)
    right = np.array(pil_img.crop((W//2,0,W,H)).resize((128,128))).astype(int)
    sym = float(np.mean(np.abs(left - np.fliplr(right))))
    refl_flag = "FAKE_REFLECTION" if sym<18 else "OK_REFLECTION"
    
    # FINAL SCORE - keeps yesterday + today
    fake=0
    if noise<11: fake+=18
    elif noise<15: fake+=8
    if ela_var<5: fake+=12
    elif ela_var<8: fake+=6
    if sharp<20: fake+=10
    if exif_len==0: fake+=8
    if plate_sharp<400: fake+=8
    if tread<8: fake+=8
    if sym<18: fake+=6
    if not has_prnu: fake+=15
    if is_screenshot: fake+=12
    if not has_c2pa: fake+=4
    if is_raw: fake-=28
    if has_prnu: fake-=18
    
    fake=max(5,min(96,fake))
    
    # heatmap
    heat = (diff*10).clip(0,255).astype(np.uint8)
    b=io.BytesIO()
    Image.fromarray(heat).save(b,format='PNG')
    h64=base64.b64encode(b.getvalue()).decode()
    
    metrics={
        "Noise": round(noise,1),
        "ELA": round(ela_var,2),
        "Sharp": round(sharp,1),
        "Plate": round(plate_sharp,1),
        "Tread": round(tread,1),
        "Sym": round(sym,1),
        "PRNU_E": round(prnu_e,1),
        "PRNU_HF": round(prnu_hf,2),
        "EXIF": exif_len,
        "SizeKB": round(size_kb,1)
    }
    flags=[plate_flag,tire_flag,refl_flag,channel,c2pa_status,prnu_flag]
    
    return fake, metrics, f"data:image/png;base64,{h64}", channel, c2pa_status, prnu_flag, is_screenshot, is_raw, ext, flags

@app.route('/')
def home():
    return render_template_string(open('index.html').read())

@app.route('/analyze', methods=['POST'])
def analyze():
    f=request.files.get('image')
    file_bytes=f.read()
    pil=Image.open(io.BytesIO(file_bytes)).convert('RGB')
    fake,metrics,heat,channel,c2pa,prnu,is_ss,is_raw,ext,flags = analyze_v26(pil,file_bytes,f.filename or "image.jpg")
    tier="HIGH" if fake>=70 else "MEDIUM" if fake>=45 else "LOW"
    return jsonify({
        "verdict": f"{'AI FAKE' if tier=='HIGH' else 'SUSPICIOUS' if tier=='MEDIUM' else 'LIKELY REAL'} {fake:.0f}%",
        "risk_tier": tier,
        "real_percent": round(100-fake,1),
        "fake_percent": round(fake,1),
        "metrics": metrics,
        "chain_of_custody": channel,
        "c2pa_status": c2pa,
        "prnu_status": prnu,
        "is_screenshot": is_ss,
        "is_raw": is_raw,
        "file_type": ext,
        "heatmap": heat,
        "flags": flags
    })

if __name__=="__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
