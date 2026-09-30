from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageStat, ImageFilter
import base64, math
from io import BytesIO
import numpy as np

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

    # ENGINE 1: ELA at 90 and 95 - AI is too perfect at both
    b90 = BytesIO(); orig.save(b90,format="JPEG",quality=90); b90.seek(0)
    e90 = Image.open(b90)
    d90 = ImageChops.difference(orig, e90)
    mean90 = sum(ImageStat.Stat(d90).mean)/3
    max90 = max([e[1] for e in d90.getextrema()]) if d90.getextrema() else 0

    b95 = BytesIO(); orig.save(b95,format="JPEG",quality=95); b95.seek(0)
    e95 = Image.open(b95)
    d95 = ImageChops.difference(orig, e95)
    mean95 = sum(ImageStat.Stat(d95).mean)/3
    max95 = max([e[1] for e in d95.getextrema()]) if d95.getextrema() else 0

    # ENGINE 2: Sensor noise - real camera has grain everywhere, AI is smooth
    blur = orig.filter(ImageFilter.GaussianBlur(1))
    noise = sum(ImageStat.Stat(ImageChops.difference(orig, blur)).mean)/3

    # ENGINE 3: Edge sharpness - real crash has sharp jagged metal, AI has smooth dents
    edges = orig.filter(ImageFilter.FIND_EDGES)
    edge_sharp = sum(ImageStat.Stat(edges).mean)/3

    # ENGINE 4: Frequency - AI lacks high-frequency detail (use numpy FFT)
    gray = np.array(orig.convert("L"), dtype=np.float32)
    f = np.fft.fft2(gray)
    fshift = np.fft.fftshift(f)
    # high freq = outer 75% of spectrum
    rows, cols = gray.shape
    crow, ccol = rows//2, cols//2
    mask_low = np.zeros((rows, cols))
    mask_low[crow-30:crow+30, ccol-30:ccol+30] = 1
    high_freq = np.sum(np.abs(fshift) * (1-mask_low)) / np.sum(np.abs(fshift))

    # ENGINE 5: Noise consistency - real noise is uniform, edited has patches
    # split into 4 quadrants and check noise variance
    q1 = orig.crop((0,0,w//2,h//2))
    q2 = orig.crop((w//2,0,w,h//2))
    q3 = orig.crop((0,h//2,w//2,h))
    q4 = orig.crop((w//2,h//2,w,h))
    noises = []
    for q in [q1,q2,q3,q4]:
        b = q.filter(ImageFilter.GaussianBlur(1))
        n = sum(ImageStat.Stat(ImageChops.difference(q,b)).mean)/3
        noises.append(n)
    noise_var = np.std(noises) # high var = inconsistent = fake edit

    thumb = orig.copy(); thumb.thumbnail((500,500))
    ib = BytesIO(); thumb.save(ib,format="JPEG",quality=70)
    hb = BytesIO(); d90.point(lambda p: min(255,p*15)).save(hb,format="JPEG")

    # V16 SCORING - NO COLORS!
    risk = 0
    log = []

    # AI is too perfect
    if mean90 < 0.3: risk+=50; log.append(f"Perfect ELA {mean90:.2f}")
    elif mean90 < 0.8: risk+=25; log.append(f"Low ELA {mean90:.2f}")

    if max90 < 20: risk+=20; log.append(f"Max {max90}")

    # Double compression check - real has big jump 90->95, AI small
    ratio = mean95/(mean90+0.001)
    if ratio > 0.7: risk+=20; log.append(f"Double JPEG {ratio:.2f}")

    if noise < 1.5: risk+=35; log.append(f"Plastic {noise:.1f}")
    elif noise < 2.5: risk+=15

    if edge_sharp < 10: risk+=20; log.append(f"Soft edges {edge_sharp:.1f}")

    if high_freq < 0.65: risk+=25; log.append(f"No detail {high_freq:.2f}")

    if noise_var > 2.5: risk+=20; log.append(f"Patchy noise {noise_var:.1f}")

    # Real bonuses
    if noise > 4 and edge_sharp > 15: risk-=30; log.append("Real grain")
    if high_freq > 0.75: risk-=15
    if kb < 180: risk-=20

    risk = max(0,min(98,risk))

    if risk >= 55:
        status,col = f"🤖 FAKE/AI - REJECT ({risk}% Risk)", "#ef4444"
    else:
        status,col = f"✅ AUTHENTIC ({100-risk}% Real)", "#22c55e"

    desc = " | ".join(log)

    html = f"""<html><body style="background:#0f172a;color:white;text-align:center;font-family:sans-serif;padding:20px">
    <h2 style="color:{col};border:3px solid {col};padding:15px;border-radius:12px">{status}</h2>
    <p>{kb:.0f}KB | ELA {mean90:.2f}/{max90} | Noise {noise:.1f} (var {noise_var:.1f}) | Edge {edge_sharp:.1f} | Freq {high_freq:.2f}</p>
    <p style="background:#1e293b;padding:10px;border-radius:8px;font-size:12px">{desc}</p>
    <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap">
    <img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:280px;border-radius:10px">
    <img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:280px;border-radius:10px;border:2px solid {col}">
    </div><br><a href="/" style="color:#60a5fa">← Another</a></body></html>"""
    return HTMLResponse(html)
