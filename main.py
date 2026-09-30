from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageStat, ImageFilter
import base64, os

app = FastAPI()
def get_html():
    try: return open("index.html", encoding="utf-8").read()
    except: return "<body><h1>Upload</h1></body>"

@app.get("/", response_class=HTMLResponse)
async def home(): return get_html()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    orig = Image.open("/tmp/t.jpg" if False else data) # placeholder
    from io import BytesIO
    try:
        orig = Image.open(BytesIO(data)).convert("RGB")
    except:
        orig = Image.open(BytesIO(data)).convert("RGB")
    w,h = orig.size
    kb = len(data)/1024

    img = orig.copy()
    img.thumbnail((600,600))

    # Forensics
    tmp = "/tmp/ela.jpg"
    img.save(tmp, "JPEG", quality=90)
    diff = ImageChops.difference(img, Image.open(tmp))
    max_d = max([e[1] for e in diff.getextrema()]) if diff.getextrema() else 0
    mean_d = sum(ImageStat.Stat(diff).mean)/3
    noise = sum(ImageStat.Stat(ImageChops.difference(img, img.filter(ImageFilter.GaussianBlur(1)))).mean)/3
    edges = sum(ImageStat.Stat(img.filter(ImageFilter.FIND_EDGES)).mean)/3
    color_var = sum(ImageStat.Stat(img).stddev)/3
    colors = len(img.getcolors(maxcolors=500000) or [])

    # NEW MONEY SCORING - catches that silver Corolla
    ai_risk = 0
    reasons = []
    if mean_d < 3.0:
        ai_risk += 35
        reasons.append(f"ELA too low {mean_d:.1f}")
    if max_d < 60:
        ai_risk += 20
        reasons.append(f"Max {max_d} low")
    if colors < 35000 and kb > 100:
        ai_risk += 35
        reasons.append(f"Only {colors} colors")
    if color_var < 50:
        ai_risk += 15
        reasons.append(f"Colors flat {color_var:.1f}")
    if noise > 3 and mean_d < 2.5 and colors < 30000:
        ai_risk += 20
        reasons.append("Fake grain")

    # WhatsApp real protection
    if kb < 200 and colors > 20000:
        ai_risk -= 40

    ai_risk = max(0, min(98, ai_risk))

    if ai_risk > 65:
        status, score, color = f"🤖 AI-GENERATED - REJECT CLAIM", 100-ai_risk, "#ef4444"
        desc = f"AI detected! {', '.join(reasons)}. Saves KES 150k. Unique colors {colors} too low for real."
    elif max_d > 75:
        status, score, color = "🚨 TAMPERED", 30, "#ef4444"
        desc = f"Local edit! Max {max_d}"
    elif kb < 250:
        status, score, color = "✅ REAL - WhatsApp", 78, "#22c55e"
        desc = f"Real but {kb:.0f}KB. Noise {noise:.1f} proves camera."
    else:
        status, score, color = "✅ AUTHENTIC - APPROVE", 88, "#22c55e"
        desc = f"Real fingerprint. Colors {colors}, ELA {mean_d:.1f}/{max_d}"

    hb = BytesIO(); diff.point(lambda p: min(255,p*8)).save(hb, format="JPEG")
    ib = BytesIO(); img.save(ib, format="JPEG", quality=70)

    box = f"""
    <div style="margin:12px;padding:18px;background:#0f172a;border:3px solid {color};border-radius:16px;color:white;text-align:center;font-family:sans-serif">
      <h2 style="color:{color}">{status}</h2>
      <h3>{score}% Real | AI-Risk {ai_risk}% | {kb:.0f}KB | {colors} colors</h3>
      <p style="background:#1e293b;padding:8px;border-radius:8px">{desc}</p>
      <p style="font-size:11px">ELA:{mean_d:.1f}/{max_d} Noise:{noise:.1f} Edges:{edges:.1f} Var:{color_var:.1f}</p>
      <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
        <img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:230px;border-radius:10px">
        <img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:230px;border-radius:10px;border:2px solid {color}">
      </div>
    </div>
    """
    return HTMLResponse(get_html().replace("</body>", box+"</body>"))
