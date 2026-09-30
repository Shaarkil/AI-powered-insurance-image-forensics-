from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageStat, ImageFilter
import base64
from io import BytesIO

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
async def home():
    return open("index.html","r",encoding="utf-8").read()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    orig = Image.open(BytesIO(data)).convert("RGB")
    w,h = orig.size
    kb = len(data)/1024

    b90 = BytesIO()
    orig.save(b90,format="JPEG",quality=90)
    b90.seek(0)
    e90 = Image.open(b90)
    d90 = ImageChops.difference(orig, e90)
    ext = d90.getextrema()
    max90 = 0
    if ext:
        max90 = max([e[1] for e in ext])
    mean90 = sum(ImageStat.Stat(d90).mean)/3

    blur = orig.filter(ImageFilter.GaussianBlur(1))
    noise = sum(ImageStat.Stat(ImageChops.difference(orig, blur)).mean)/3

    parts = []
    boxes = [(0,0,w//2,h//2),(w//2,0,w,h//2),(0,h//2,w//2,h),(w//2,h//2,w,h)]
    for box in boxes:
        q = orig.crop(box)
        b = q.filter(ImageFilter.GaussianBlur(1))
        n = sum(ImageStat.Stat(ImageChops.difference(q,b)).mean)/3
        parts.append(n)
    q_min = min(parts)
    q_max = max(parts)
    q_var = q_max - q_min

    clist = orig.getcolors(maxcolors=500000)
    if clist:
        colors = len(clist)
    else:
        colors = 500000
    edge = sum(ImageStat.Stat(orig.filter(ImageFilter.FIND_EDGES)).mean)/3

    thumb = orig.copy()
    thumb.thumbnail((400,400))
    ib = BytesIO()
    thumb.save(ib,format="JPEG",quality=65)
    hb = BytesIO()
    d90.point(lambda p: min(255,p*15)).save(hb,format="JPEG")

    risk = 0
    if mean90 < 0.3:
        risk += 50
    if noise < 2.0:
        risk += 30
    if edge < 8:
        risk += 15
    if colors < 25000:
        risk += 30
    if q_var > 1.5 and q_min < 1.0:
        risk += 40
    if q_var < 1.0 and noise > 3:
        risk -= 20

    risk = max(0,min(98,risk))

    if risk >= 50:
        status = f"🤖 FAKE - PASTE ({risk}% Risk)"
        col = "#ef4444"
        desc = f"Top {parts[0]:.1f}/{parts[1]:.1f} vs Bot {parts[2]:.1f}/{parts[3]:.1f} diff {q_var:.1f}. ELA {mean90:.3f} Colors {colors}"
    else:
        status = f"✅ AUTHENTIC ({100-risk}% Real)"
        col = "#22c55e"
        desc = f"Uniform {q_min:.1f}-{q_max:.1f} ELA {mean90:.2f} Noise {noise:.1f} Edge {edge:.1f}"

    html = f"""<html><body style="background:#0f172a;color:white;text-align:center;font-family:sans-serif;padding:15px">
    <h2 style="color:{col};border:3px solid {col};padding:12px;border-radius:10px">{status}</h2>
    <p>{kb:.0f}KB | ELA {mean90:.3f}/{max90} | Noise {noise:.2f} Qvar {q_var:.2f} | Edge {edge:.1f} | Colors {colors}</p>
    <p style="background:#1e293b;padding:8px;border-radius:8px;font-size:12px">{desc}</p>
    <div style="display:flex;gap:8px;justify-content:center;flex-wrap:wrap">
    <img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:260px;border-radius:8px">
    <img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:260px;border-radius:8px;border:2px solid {col}">
    </div><br><a href="/" style="color:#60a5fa">Back</a></body></html>"""
    return HTMLResponse(html)
