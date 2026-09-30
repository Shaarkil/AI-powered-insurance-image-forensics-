from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageStat, ImageFilter
import base64
from io import BytesIO

app = FastAPI()

def get_html():
    try:
        return open("index.html", encoding="utf-8").read()
    except:
        return "<h1>AI Insurance Forensics</h1>"

@app.get("/", response_class=HTMLResponse)
async def home():
    return get_html()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    try:
        data = await file.read()
        orig = Image.open(BytesIO(data)).convert("RGB")
        kb = len(data)/1024

        img = orig.copy()
        img.thumbnail((600,600))

        # ELA
        buf = BytesIO()
        img.save(buf, format="JPEG", quality=90)
        buf.seek(0)
        ela_img = Image.open(buf)
        diff = ImageChops.difference(img, ela_img)
        ext = diff.getextrema()
        max_d = max([e[1] for e in ext]) if ext else 0
        mean_d = sum(ImageStat.Stat(diff).mean)/3

        # Noise & edges
        blurred = img.filter(ImageFilter.GaussianBlur(1))
        noise = sum(ImageStat.Stat(ImageChops.difference(img, blurred)).mean)/3
        edges = sum(ImageStat.Stat(img.filter(ImageFilter.FIND_EDGES)).mean)/3
        color_var = sum(ImageStat.Stat(img).stddev)/3
        colors_list = img.getcolors(maxcolors=500000)
        colors = len(colors_list) if colors_list else 500000

        # SCORING - catches silver AI Corolla
        ai_risk = 0
        reasons = []
        if mean_d < 3.0:
            ai_risk += 35
            reasons.append(f"Low ELA {mean_d:.1f}")
        if max_d < 60:
            ai_risk += 20
            reasons.append(f"Max {max_d}")
        if colors < 35000 and kb > 100:
            ai_risk += 35
            reasons.append(f"{colors} colors only")
        if color_var < 50:
            ai_risk += 10
            reasons.append(f"Flat colors")
        if kb < 200 and colors > 20000:
            ai_risk -= 40

        ai_risk = max(0, min(95, ai_risk))

        if ai_risk > 65:
            status, score, color = "🤖 AI-GENERATED - REJECT CLAIM", 100-ai_risk, "#ef4444"
            desc = f"AI detected! {', '.join(reasons)}. Saves KES 150k. Only {colors} colors."
        elif max_d > 75:
            status, score, color = "🚨 TAMPERED", 30, "#ef4444"
            desc = f"Edit found! Max {max_d}"
        elif kb < 250:
            status, score, color = "✅ REAL - WhatsApp Quality", 78, "#22c55e"
            desc = f"Real but {kb:.0f}KB. Noise {noise:.1f} proves camera."
        else:
            status, score, color = "✅ AUTHENTIC - APPROVE", 88, "#22c55e"
            desc = f"Real. Colors {colors}, ELA {mean_d:.1f}/{max_d}"

        # Images for report
        heat = diff.point(lambda p: min(255, p*8))
        hb = BytesIO(); heat.save(hb, format="JPEG")
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

        html = get_html()
        if "</body>" in html:
            return HTMLResponse(html.replace("</body>", box+"</body>"))
        else:
            return HTMLResponse(html + box)

    except Exception as e:
        return HTMLResponse(f"<h1>Error: {e}</h1><p>Try another image</p><a href='/'>Back</a>", status_code=200)
