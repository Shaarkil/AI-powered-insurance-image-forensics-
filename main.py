from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageEnhance, ImageStat, ImageFilter
import io, base64

app = FastAPI()
def get_html():
    try: return open("index.html", encoding="utf-8").read()
    except: return "<body></body>"

@app.get("/", response_class=HTMLResponse)
async def home(): return get_html()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    try:
        data = await file.read()
        orig = Image.open(io.BytesIO(data)).convert("RGB")
        img = orig.copy()
        img.thumbnail((500,500))

        # 1. ELA
        buf = io.BytesIO(); img.save(buf, "JPEG", quality=90); buf.seek(0)
        diff = ImageChops.difference(img, Image.open(buf))
        max_d = max([e[1] for e in diff.getextrema()]) if diff.getextrema() else 0
        mean_d = sum(ImageStat.Stat(diff).mean)/3

        # 2. NOISE CHECK - AI is too clean
        blurred = img.filter(ImageFilter.GaussianBlur(1))
        noise_diff = ImageChops.difference(img, blurred)
        noise_level = sum(ImageStat.Stat(noise_diff).mean)/3

        # 3. EXIF
        try: has_exif = len(orig.getexif()) > 0
        except: has_exif = False

        # --- NEW SMART LOGIC ---
        # Real camera: mean 8-30, noise >3
        # AI Full: mean <5, noise <2, too smooth

        if mean_d < 5.0 and noise_level < 3.5:
            status, score, color, desc = "🤖 FULLY AI-GENERATED CAR!", 15, "#ef4444", f"AI Proof: Mean ELA {mean_d:.1f} too low (real is 10+), Noise {noise_level:.1f} too clean. This car never existed!"
        elif mean_d < 6 and max_d < 45:
            status, score, color, desc = "🤖 AI-GENERATED SUSPECTED", 30, "#ef4444", f"Very smooth texture, low noise {noise_level:.1f} = Midjourney/DALL-E style"
        elif max_d > 55:
            status, score, color, desc = "🚨 PARTIAL TAMPER - Edited Damage", 40, "#ef4444", f"Bright ELA {max_d} = photoshopped dent"
        elif max_d > 35 or mean_d < 7:
            status, score, color, desc = "⚠️ SUSPICIOUS - Likely AI", 55, "#eab308", "Unnatural smoothness, needs review"
        else:
            status, score, color, desc = "✅ AUTHENTIC REAL CAR", 96, "#22c55e", "Natural camera noise, ELA consistent"

        heat = ImageEnhance.Brightness(diff).enhance(5)
        hb = io.BytesIO(); heat.save(hb, "JPEG")
        ib = io.BytesIO(); img.save(ib, "JPEG", quality=75)

        box = f"""
        <div style="margin:15px;padding:18px;background:#0f172a;border:3px solid {color};border-radius:14px;color:white;text-align:center">
          <h2 style="color:{color}">{status}</h2>
          <h3>{score}% Real</h3>
          <p><b>ELA Max:{max_d} Mean:{mean_d:.1f} | Noise:{noise_level:.1f} | EXIF:{'Yes' if has_exif else 'No'}</b></p>
          <p>{desc}</p>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:12px">
            <div><p>Original</p><img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:250px;border-radius:10px"></div>
            <div><p>🔥 Heatmap (Dark=AI/Smooth)</p><img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:250px;border-radius:10px;border:2px solid {color}"></div>
          </div>
          <p style="margin-top:10px;font-size:12px">REAL: noisy heatmap + high mean | AI: black heatmap + low mean ({mean_d:.1f})</p>
        </div>
        """
        return HTMLResponse(get_html().replace("</body>", box+"</body>"))
    except Exception as e:
        return HTMLResponse(f"<h2>Error {e}</h2><a href='/'>Back</a>")
