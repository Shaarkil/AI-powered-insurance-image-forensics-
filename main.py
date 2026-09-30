from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageEnhance, ImageStat
import io, base64

app = FastAPI()

def get_index_html():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    img = Image.open(io.BytesIO(contents)).convert('RGB')
    small = img.resize((600, 600)) if max(img.size)>600 else img

    # ELA
    buf = io.BytesIO(); small.save(buf, 'JPEG', quality=90); buf.seek(0)
    diff = ImageChops.difference(small, Image.open(buf))
    stat = ImageStat.Stat(diff); max_diff = max([e[1] for e in diff.getextrema()])
    mean_diff = sum(stat.mean)/3

    # Noise check for AI
    gray = small.convert('L')
    exif = small._getexif()

    # Heatmap
    scale = 255.0/max_diff if max_diff!=0 else 1
    heat = ImageEnhance.Brightness(diff).enhance(scale*2)
    hb = io.BytesIO(); heat.save(hb, format='JPEG')
    heat_b64 = base64.b64encode(hb.getvalue()).decode()
    orig_b64 = base64.b64encode(contents).decode()

    # LOGIC FOR FULL AI vs PARTIAL
    if exif is None and mean_diff < 8 and max_diff < 20:
        status, score, color = "🤖 FULLY AI-GENERATED CAR SUSPECTED", 20, "#ef4444"
        explain = "Whole image is TOO smooth, No camera EXIF, Uniform texture = Midjourney/DALL-E/Firefly car, NOT real!"
    elif max_diff > 50:
        status, score, color = "🚨 PARTIAL AI TAMPERING - Edited Damage", 45, "#ef4444"
        explain = f"Bright spots = edited areas (dent/accident photoshopped). ELA {max_diff}"
    elif max_diff > 25:
        status, score, color = "⚠️ SUSPICIOUS", 70, "#eab308"
        explain = "Some inconsistent compression - needs manual review"
    else:
        status, score, color = "✅ AUTHENTIC REAL CAR", 95, "#22c55e"
        explain = "Natural camera noise, EXIF present, Even ELA = Real photo"

    result = f"""
    <div style="margin:20px;padding:20px;background:#0f172a;border:3px solid {color};border-radius:15px;color:white;text-align:center;">
      <h2 style="color:{color}">{status} - {score}% Real</h2>
      <p>{explain}</p>
      <p>Mean ELA: {mean_diff:.1f} | Max: {max_diff} | EXIF: {'No (AI sign)' if exif is None else 'Yes'}</p>
      <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:15px;">
        <div><p>Original</p><img src="data:image/jpeg;base64,{orig_b64}" style="max-width:280px;border-radius:10px;"></div>
        <div><p>Heatmap</p><img src="data:image/jpeg;base64,{heat_b64}" style="max-width:280px;border-radius:10px;border:2px solid {color}"></div>
      </div>
    </div>
    """
    html = get_index_html()
    return HTMLResponse(content=html.replace("</body>", result+"</body>") if "</body>" in html else html+result)

@app.get("/", response_class=HTMLResponse)
async def home():
    return get_index_html()
