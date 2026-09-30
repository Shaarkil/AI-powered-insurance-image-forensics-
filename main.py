from flask import Flask, request, jsonify, render_template_string
from PIL import Image
import io, numpy as np, base64, os, time

app = Flask(__name__)

# Load AI detector once (slow first time)
print("Loading AI detector model...")
try:
    from transformers import pipeline
    ai_pipe = pipeline("image-classification", model="umm-maybe/AI-image-detector", top_k=2)
    HAS_ML = True
    print("AI model loaded")
except Exception as e:
    print(f"ML not loaded: {e}")
    ai_pipe = None
    HAS_ML = False

def forensic_score(pil_img):
    if max(pil_img.size) > 800:
        pil_img.thumbnail((800,800))
    arr = np.array(pil_img.resize((256,256)))
    noise = float(np.std(arr))
    # ELA
    buf = io.BytesIO()
    pil_img.save(buf, 'JPEG', quality=90)
    buf.seek(0)
    recomp = Image.open(buf).resize(pil_img.size)
    diff = np.abs(np.array(pil_img).astype(int) - np.array(recomp).astype(int))
    ela_var = float(np.std(diff))
    # sharpness
    gray = np.mean(arr, axis=2)
    sharp = float(np.var(np.diff(gray, axis=0)) + np.var(np.diff(gray, axis=1)))

    score = 0
    if noise < 12: score += 30
    if ela_var < 5: score += 25
    if sharp < 20: score += 20
    if noise > 22: score -= 15
    if ela_var > 10: score -= 10
    return max(5, min(90, score)), {"ELA":ela_var, "Noise":noise, "Sharp":sharp}

def ml_score(pil_img):
    if not HAS_ML or ai_pipe is None:
        return 50, "No ML"
    try:
        # Resize for model
        img = pil_img.resize((512,512))
        res = ai_pipe(img)
        # res = [{'label':'artificial','score':0.9}, {'label':'real',...}]
        ai_score = 0
        for r in res:
            if 'artificial' in r['label'].lower() or 'ai' in r['label'].lower() or 'fake' in r['label'].lower():
                ai_score = r['score']*100
            if 'real' in r['label'].lower():
                ai_score = (1 - r['score'])*100 if ai_score==0 else ai_score
        # If model returns only artificial
        if len(res)==1 and res[0]['label']=='artificial':
            ai_score = res[0]['score']*100
        return ai_score, str(res)
    except Exception as e:
        return 50, f"ML error {e}"

@app.route('/')
def home():
    with open('index.html') as f:
        return render_template_string(f.read())

@app.route('/analyze', methods=['POST'])
def analyze():
    t0 = time.time()
    file = request.files.get('image')
    if not file:
        return jsonify({"error":"No image"}),400
    data = file.read()
    pil = Image.open(io.BytesIO(data)).convert('RGB')

    f_score, f_metrics = forensic_score(pil)
    m_score, m_raw = ml_score(pil)

    # ENSEMBLE - weighted
    if HAS_ML:
        final_fake = (f_score*0.35 + m_score*0.65) # ML is more accurate
    else:
        final_fake = f_score

    final_fake = max(5, min(95, final_fake))
    real = 100 - final_fake

    if final_fake >= 75:
        tier, verdict = "HIGH", f"AI GENERATED - {final_fake:.1f}% fake"
    elif final_fake >= 45:
        tier, verdict = "MEDIUM", f"SUSPICIOUS - {final_fake:.1f}% - needs original"
    else:
        tier, verdict = "LOW", f"LIKELY REAL - {real:.1f}% real"

    took = time.time() - t0
    return jsonify({
        "verdict": verdict,
        "risk_tier": tier,
        "real_percent": round(real,1),
        "fake_percent": round(final_fake,1),
        "metrics": {**f_metrics, "ML_AI_score": round(m_score,1), "Time_sec": round(took,1)},
        "flags": [f"Forensic {f_score:.1f}% fake", f"ML {m_score:.1f}% fake", f"ML raw: {m_raw[:200]}"],
        "accurate_mode": True
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
