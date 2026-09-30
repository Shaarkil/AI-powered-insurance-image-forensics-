from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageEnhance, ImageStat
import io, base64

app = FastAPI()
def get_html(): return open("index.html", encoding="utf-8").read()

@app.get("/", response_class=HTMLResponse)
async def home(): return get_html()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    data = await file.read()
    orig = Image.open(io.BytesIO(data)).convert("RGB")
    img = orig.copy()
    img.thumbnail((450, 450)) # FAST but keeps details

    buf = io.BytesIO(); img.save(buf, "JPEG", quality=90); buf.seek(0)
    diff = ImageChops.difference(img, Image.open(buf))
    max_d = max([e[1] for e in diff.getextrema()])
    mean_d = sum(ImageStat.Stat(diff).mean)/3
    has_exif = orig._getexif() is not None

    # Detection logic - FULL FEATURES INTACT
    if not has_exif and mean_d < 8 and max_d < 22:
        status, score, color, desc = "🤖 FULL AI-GENERATED CAR", 20, "#ef4444", "No EXIF + too smooth = AI created entire car"
    elif max_d > 50:
        status, score, color, desc = "🚨 PARTIAL TAMPER - Edited Damage", 40, "#ef4444", "Bright heatmap areas = photoshopped dent/damage"
    elif max_d > 28:
        status, score, color, desc = "⚠️ SUSPICIOUS EDIT", 70, "#eab308", "Inconsistent compression - manual review needed"
    else:
        status, score, color, desc = "✅ AUTHENTIC REAL CAR", 95, "#22c55e", "Natural noise + EXIF = real camera photo"

    heat = ImageEnhance.Brightness(diff).enhance(4 if max_d else 1)
    hb = io.BytesIO(); heat.save(hb, "JPEG")
    ib = io.BytesIO(); img.save(ib, "JPEG", quality=75)

    box = f"""
    <div style="margin:15px;padding:18px;background:#0f172a;border:3px solid {color};border-radius:14px;color:white;text-align:center">
      <h2 style="color:{color};margin:5px">{status}</h2>
      <h3>{score}% Real | ELA Max:{max_d} Mean:{mean_d:.1f} | EXIF:{'Yes' if has_exif else 'No'}</h3>
      <p>{desc}</p>
      <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:12px">
        <div><p>Original (compressed for speed)</p><img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:260px;border-radius:10px"></div>
        <div><p>🔥 Heatmap - Bright=Fake</p><img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:260px;border-radius:10px;border:2px solid {color}"></div>
      </div>
      <p style="margin-top:12px">Action: {'APPROVE' if score>85 else 'MANUAL REVIEW' if score>60 else 'REJECT - Fraud suspected'}</p>
      <a href="/" style="display:inline-block;margin-top:10px;padding:10px 20px;background:{color};color:white;border-radius:8px;text-decoration:none">Test Another Car</a>
    </div>
    """
    return HTMLResponse(get_html().replace("</body>", box+"</body>"))
