from flask import Flask, request, jsonify, render_template_string
from PIL import Image, ExifTags
import io, numpy as np, os, time, base64

app = Flask(__name__)

def fast_accurate(pil_img):
    # Shrink first - fast on phone
    if max(pil_img.size) > 700:
        pil_img.thumbnail((700,700))
    
    small = pil_img.resize((256,256))
    arr = np.array(small)
    noise = float(np.std(arr))
    gray = np.mean(arr, axis=2)
    sharp = float(np.var(np.diff(gray, axis=0)) + np.var(np.diff(gray, axis=1)))
    
    # ELA
    buf = io.BytesIO()
    pil_img.save(buf, 'JPEG', quality=90)
    buf.seek(0)
    recomp = Image.open(buf).resize(pil_img.size)
    diff = np.abs(np.array(pil_img).astype(int) - np.array(recomp).astype(int))
    ela_var = float(np.std(diff))
    ela_mean = float(np.mean(diff))
    
    try:
        exif = pil_img._getexif()
        has_make = 1 if exif and any(ExifTags.TAGS.get(k)=='Make' for k in exif) else 0
        has_exif = 1 if exif and len(exif)>3 else 0
    except:
        has_make = 0
        has_exif = 0

    # Tuned on many cars
    fake = 0
    if noise < 11: fake += 30
    elif noise < 15: fake += 15
    if ela_var < 5: fake += 25
    elif ela_var < 8: fake += 10
    if sharp < 20: fake += 20
    if has_exif == 0: fake += 10
    if has_make: fake -= 20
    if noise > 28: fake -= 15
    if ela_var > 12: fake -= 10
    if sharp > 80: fake -= 10

    fake = max(8, min(92, fake))
    
    # heatmap for UI
    heat = (diff*10).clip(0,255).astype(np.uint8)
    b = io.BytesIO()
    Image.fromarray(heat).save(b, format='PNG')
    h64 = base64.b64encode(b.getvalue()).decode()
    
    return fake, {
        "Noise": round(noise,1),
        "ELA_var": round(ela_var,2),
        "ELA_mean": round(ela_mean,2),
        "Sharpness": round(sharp,1),
        "EXIF": has_exif,
        "Camera": has_make
    }, f"data:image/png;base64,{h64}"

@app.route('/')
def home():
    with open('index.html') as f:
        return render_template_string(f.read())

@app.route('/analyze', methods=['POST'])
def analyze():
    f = request.files.get('image')
    if not f:
        return jsonify({"error":"No image"}),400
    data = f.read()
    if len(data) > 7*1024*1024:
        return jsonify({"error":"Image too big >7MB"}),413
    pil = Image.open(io.BytesIO(data)).convert('RGB')
    fake, metrics, heat = fast_accurate(pil)
    real = 100-fake
    tier = "HIGH" if fake>=70 else "MEDIUM" if fake>=45 else "LOW"
    verdict = f"{'AI FAKE' if tier=='HIGH' else 'SUSPICIOUS COPY' if tier=='MEDIUM' else 'LIKELY REAL'} - {fake:.0f}%"
    return jsonify({
        "verdict": verdict,
        "risk_tier": tier,
        "real_percent": round(real,1),
        "fake_percent": round(fake,1),
        "metrics": metrics,
        "heatmap": heat,
        "flags": [f"{k}: {v}" for k,v in metrics.items()]
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
