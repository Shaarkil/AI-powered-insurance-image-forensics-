from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageStat, ImageFilter
import base64, os
from io import BytesIO

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    except:
        return "<h1>Insurance Forensics - Upload at /</h1>"

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    img_orig = Image.open(BytesIO(data)).convert("RGB")
    kb = len(data)/1024
    w,h = img_orig.size

    img = img_orig.copy()
    img.thumbnail((600,600))

    # Forensics
    buf = BytesIO()
    img.save(buf, format="JPEG", quality=90)
    buf.seek(0)
    ela_img = Image.open(buf)
    diff = ImageChops.difference(img, ela_img)
    ext = diff.getextrema()
    max_d = max([e[1] for e in ext]) if ext else 0
    mean_d = sum(ImageStat.Stat(diff).mean)/3
    noise = sum(ImageStat.Stat(ImageChops.difference(img, img.filter(ImageFilter.GaussianBlur(1)))).mean)/3
    edges = sum(ImageStat.Stat(img.filter(ImageFilter.FIND_EDGES)).mean)/3
    cvar = sum(ImageStat.Stat(img).stddev)/3
    clist = img.getcolors(maxcolors=500000)
    colors = len(clist) if clist else 500000

    ai_risk = 0
    if mean_d < 3: ai_risk += 35
    if max_d < 60: ai_risk += 20
    if colors < 35000: ai_risk += 35
    if cvar < 50: ai_risk += 10
    if kb < 200: ai_risk -= 40
    ai_risk = max(0, min(95, ai_risk))

    if ai_risk > 65:
        status, col = f"🤖 AI-GENERATED - REJECT ({ai_risk}% AI-Risk)", "#ef4444"
    elif max_d > 75:
        status, col = "🚨 TAMPERED", "#ef4444"
    elif kb < 250:
        status, col = "✅ REAL - WhatsApp Quality", "#22c55e"
    else:
        status, col = "✅ AUTHENTIC - APPROVE", "#22c55e"

    hb = BytesIO()
    diff.point(lambda p: min(255, p*8)).save(hb, format="JPEG")
    ib = BytesIO()
    img.save(ib, format="JPEG", quality=70)

    result = f"""
    <html><body style="background:#0f172a;color:white;text-align:center;font-family:sans-serif;padding:20px">
    <h2 style="color:{col};border:3px solid {col};padding:15px;border-radius:12px">{status}</h2>
    <p>{100-ai_risk}% Real | {kb:.0f}KB | {colors} colors | ELA {mean_d:.1f}/{max_d} | Noise {noise:.1f}</p>
    <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
    <img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:280px;border-radius:10px">
    <img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:280px;border-radius:10px;border:2px solid {col}">
    </div>
    <br><a href="/" style="color:#3b82f6">← Analyze another</a>
    <p style="color:#94a3b8;font-size:12px">Saves KES 150k per fraud caught</p>
    </body></html>
    """
    return HTMLResponse(result)
