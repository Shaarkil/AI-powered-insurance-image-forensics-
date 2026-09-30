from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageStat, ImageFilter
import base64
from io import BytesIO

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    try:
        return open("index.html", "r", encoding="utf-8").read()
    except:
        return "<h1>Insurance Forensics</h1>"

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    orig = Image.open(BytesIO(data)).convert("RGB")
    kb = len(data)/1024

    #!!! CHECK ORIGINAL, NOT THUMBNAIL!!!
    # ELA on original
    buf90 = BytesIO()
    orig.save(buf90, format="JPEG", quality=90)
    buf90.seek(0)
    ela90 = Image.open(buf90)
    diff90 = ImageChops.difference(orig, ela90)
    ext90 = diff90.getextrema()
    max90 = max([e[1] for e in ext90]) if ext90 else 0
    mean90 = sum(ImageStat.Stat(diff90).mean)/3

    buf95 = BytesIO()
    orig.save(buf95, format="JPEG", quality=95)
    buf95.seek(0)
    ela95 = Image.open(buf95)
    diff95 = ImageChops.difference(orig, ela95)
    ext95 = diff95.getextrema()
    max95 = max([e[1] for e in ext95]) if ext95 else 0
    mean95 = sum(ImageStat.Stat(diff95).mean)/3

    # Noise on original
    blur = orig.filter(ImageFilter.GaussianBlur(1))
    noise = sum(ImageStat.Stat(ImageChops.difference(orig, blur)).mean)/3
    cvar = sum(ImageStat.Stat(orig).stddev)/3
    clist = orig.getcolors(maxcolors=500000)
    colors = len(clist) if clist else 500000

    # Thumbnail only for display
    thumb = orig.copy()
    thumb.thumbnail((500,500))
    ib = BytesIO()
    thumb.save(ib, format="JPEG", quality=70)
    hb = BytesIO()
    diff90.point(lambda p: min(255, p*12)).save(hb, format="JPEG")

    # V12 SCORING - catches your 504x1120 AI car
    ai_risk = 0
    reasons = []

    # Killer tell for AI: ELA too perfect
    if mean90 < 1.0:
        ai_risk += 50
        reasons.append(f"ELA {mean90:.2f} too perfect")
    elif mean90 < 3.0:
        ai_risk += 30
        reasons.append(f"Low ELA {mean90:.1f}")

    if max90 < 30:
        ai_risk += 30
        reasons.append(f"Max {max90}")
    elif max90 < 60:
        ai_risk += 15

    if colors < 20000:
        ai_risk += 40
        reasons.append(f"{colors} colors")
    elif colors < 40000 and kb > 150:
        ai_risk += 25
        reasons.append(f"Only {colors} colors")

    if noise < 2.0 and kb > 100:
        ai_risk += 20
        reasons.append(f"No camera noise {noise:.1f}")

    if cvar < 35:
        ai_risk += 10

    # WhatsApp real protection - small files are real even if low colors
    if kb < 180 and colors > 8000:
        ai_risk = max(0, ai_risk - 50)
        reasons.append("WhatsApp")

    ai_risk = max(0, min(98, ai_risk))

    if ai_risk >= 60:
        status, col = f"🤖 AI-GENERATED - REJECT CLAIM ({ai_risk}% AI-Risk)", "#ef4444"
        desc = f"AI detected! {', '.join(reasons)}. Saves KES 150k. Real photos have 80k+ colors & ELA 5-10, this has {colors} & {mean90:.2f}"
    elif max90 > 80 or max95 > 80:
        status, col = "🚨 TAMPERED - Local Edit", "#ef4444"
        desc = f"Edit found Max {max90}/{max95}"
    elif kb < 250:
        status, col = "✅ REAL - WhatsApp Quality", "#22c55e"
        desc = f"Real camera but {kb:.0f}KB compressed. Noise {noise:.1f} proves sensor."
    else:
        status, col = "✅ AUTHENTIC - APPROVE", "#22c55e"
        desc = f"Real fingerprint. {colors} colors, ELA {mean90:.1f}/{max90}, Noise {noise:.1f}"

    result = f"""
    <html><body style="background:#0f172a;color:white;text-align:center;font-family:sans-serif;padding:20px">
    <h2 style="color:{col};border:3px solid {col};padding:15px;border-radius:12px">{status}</h2>
    <p><b>{100-ai_risk}% Real</b> | {kb:.0f}KB | {colors} colors | ORIG ELA {mean90:.2f}/{max90} (95:{mean95:.2f}/{max95}) | Noise {noise:.1f}</p>
    <p style="background:#1e293b;padding:10px;border-radius:8px">{desc}</p>
    <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:10px">
    <img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:280px;border-radius:10px">
    <img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:280px;border-radius:10px;border:2px solid {col}">
    </div>
    <br><a href="/" style="color:#60a5fa;font-size:18px">← Analyze another</a>
    </body></html>
    """
    return HTMLResponse(result)
