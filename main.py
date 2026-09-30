from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageEnhance, ImageStat
import io, base64

app = FastAPI()

def get_html():
    try:
        return open("index.html", encoding="utf-8").read()
    except:
        return "<html><body><h1>App running</h1></body></html>"

@app.get("/", response_class=HTMLResponse)
async def home():
    return get_html()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    try:
        data = await file.read()
        orig = Image.open(io.BytesIO(data)).convert("RGB")
        img = orig.copy()
        img.thumbnail((400, 400))

        # ELA
        buf = io.BytesIO()
        img.save(buf, "JPEG", quality=90)
        buf.seek(0)
        comp = Image.open(buf)
        diff = ImageChops.difference(img, comp)

        extrema = diff.getextrema()
        max_d = max([e[1] for e in extrema]) if extrema else 0
        mean_d = sum(ImageStat.Stat(diff).mean)/3

        # SAFE exif check
        try:
            has_exif = orig.getexif() and len(orig.getexif()) > 0
        except:
            has_exif = False

        # Detection
        if not has_exif and mean_d < 8 and max_d < 22:
            status, score, color, desc = "🤖 FULL AI-GENERATED CAR", 20, "#ef4444", "No EXIF + too smooth = AI made whole car"
        elif max_d > 50:
            status, score, color, desc = "🚨 PARTIAL TAMPER - Edited", 40, "#ef4444", "Bright areas = edited damage"
        elif max_d > 28:
            status, score, color, desc = "⚠️ SUSPICIOUS", 70, "#eab308", "Needs manual review"
        else:
            status, score, color, desc = "✅ AUTHENTIC REAL CAR", 95, "#22c55e", "Real camera photo - natural noise"

        # Heatmap
        enhance_factor = 4.0 if max_d > 0 else 1.0
        heat = ImageEnhance.Brightness(diff).enhance(enhance_factor)
        hb = io.BytesIO(); heat.save(hb, "JPEG")
        ib = io.BytesIO(); img.save(ib, "JPEG", quality=75)

        box = f"""
        <div style="margin:15px;padding:18px;background:#0f172a;border:3px solid {color};border-radius:14px;color:white;text-align:center">
          <h2 style="color:{color}">{status}</h2>
          <h3>{score}% Real | Max:{max_d} Mean:{mean_d:.1f} | EXIF:{'Yes' if has_exif else 'No (AI sign)'}</h3>
          <p>{desc}</p>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:12px">
            <div><p>Original</p><img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:250px;border-radius:10px"></div>
            <div><p>🔥 Heatmap (Bright=Fake)</p><img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:250px;border-radius:10px;border:2px solid {color}"></div>
          </div>
          <p>Action: {'APPROVE' if score>85 else 'REVIEW' if score>60 else 'REJECT - Fraud'}</p>
        </div>
        """
        html = get_html()
        if "</body>" in html:
            html = html.replace("</body>", box + "</body>")
        else:
            html = html + box
        return HTMLResponse(html)

    except Exception as e:
        return HTMLResponse(f"<h2 style='color:red'>Error: {str(e)}</h2><a href='/'>Go Back</a>")
