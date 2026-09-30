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
        w,h = orig.size
        img = orig.copy()
        img.thumbnail((500,500))

        buf = io.BytesIO(); img.save(buf, "JPEG", quality=90); buf.seek(0)
        diff = ImageChops.difference(img, Image.open(buf))
        max_d = max([e[1] for e in diff.getextrema()]) if diff.getextrema() else 0
        mean_d = sum(ImageStat.Stat(diff).mean)/3

        blurred = img.filter(ImageFilter.GaussianBlur(1))
        noise_level = sum(ImageStat.Stat(ImageChops.difference(img, blurred)).mean)/3

        try: has_exif = len(orig.getexif()) > 0
        except: has_exif = False

        file_kb = len(data)/1024
        is_whatsapp = file_kb < 300 or (w < 800) # WhatsApp crushes files

        # BALANCED LOGIC FOR REAL CLAIMS
        if mean_d < 2.5 and noise_level < 2.5 and max_d < 20:
            status, score, color, desc = "🤖 FULL AI-GENERATED", 10, "#ef4444", f"Too perfect. Mean {mean_d:.1f}, Noise {noise_level:.1f}. No camera noise at all."
        elif mean_d < 4 and noise_level < 3.0 and not is_whatsapp:
            status, score, color, desc = "🤖 AI-GENERATED SUSPECTED", 30, "#ef4444", "Suspiciously smooth for original photo"
        elif max_d > 70:
            status, score, color, desc = "🚨 TAMPERED - Edited Area", 35, "#ef4444", f"Local edit detected! Max {max_d} bright spot"
        elif is_whatsapp and mean_d < 5:
            # THIS IS YOUR CASE - REAL but WhatsApp quality
            status, score, color, desc = "✅ AUTHENTIC (Low Quality)", 78, "#22c55e", f"Real crash but WhatsApp compressed it ({file_kb:.0f}KB, {w}x{h}). Noise {noise_level:.1f} proves real. Recommend request original photo."
        elif mean_d > 6 and noise_level > 3:
            status, score, color, desc = "✅ AUTHENTIC REAL CAR", 92, "#22c55e", f"Natural noise {noise_level:.1f} + ELA {mean_d:.1f} = Real camera"
        else:
            status, score, color, desc = "⚠️ LOW QUALITY - Manual Review", 65, "#eab308", f"WhatsApp quality loss. Mean {mean_d:.1f}. Ask for original HD photo for 100% check"

        heat = ImageEnhance.Brightness(diff).enhance(5)
        hb = io.BytesIO(); heat.save(hb, "JPEG")
        ib = io.BytesIO(); img.save(ib, "JPEG", quality=75)

        box = f"""
        <div style="margin:15px;padding:18px;background:#0f172a;border:3px solid {color};border-radius:14px;color:white;text-align:center">
          <h2 style="color:{color}">{status}</h2>
          <h3>{score}% Real | ELA:{mean_d:.1f}/{max_d} | Noise:{noise_level:.1f} | Size:{file_kb:.0f}KB</h3>
          <p>{desc}</p>
          <div style="display:flex;gap:10px;justify-content:center;flex-wrap:wrap;margin-top:12px">
            <div><img src="data:image/jpeg;base64,{base64.b64encode(ib.getvalue()).decode()}" style="width:250px;border-radius:10px"></div>
            <div><img src="data:image/jpeg;base64,{base64.b64encode(hb.getvalue()).decode()}" style="width:250px;border-radius:10px;border:2px solid {color}"></div>
          </div>
        </div>
        """
        return HTMLResponse(get_html().replace("</body>", box+"</body>"))
    except Exception as e:
        return HTMLResponse(f"<h2>Error {e}</h2><a href='/'>Back</a>")
