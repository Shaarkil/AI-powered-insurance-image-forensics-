from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image, ImageChops, ImageEnhance
import io, os, hashlib
import numpy as np

app = FastAPI()

def get_index_html():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

def analyze_ela(image: Image.Image):
    """Real Error Level Analysis"""
    try:
        # Save at 90% quality and compare
        buffer = io.BytesIO()
        image.save(buffer, 'JPEG', quality=90)
        buffer.seek(0)
        compressed = Image.open(buffer)

        diff = ImageChops.difference(image, compressed)
        extrema = diff.getextrema()
        max_diff = max([ex[1] for ex in extrema])

        # Higher diff = more tampering possibility
        if max_diff > 50:
            return f"High ELA ({max_diff}) - Possible editing", 60
        elif max_diff > 20:
            return f"Medium ELA ({max_diff}) - Check needed", 80
        else:
            return f"Low ELA ({max_diff}) - Likely authentic", 95
    except Exception as e:
        return f"ELA Error: {str(e)}", 70

def check_metadata(image: Image.Image):
    exif = image._getexif()
    if exif is None:
        return "No EXIF - Could be screenshot/AI-generated", 65
    else:
        return f"EXIF found ({len(exif)} tags) - Original camera likely", 90

@app.get("/", response_class=HTMLResponse)
async def home():
    return get_index_html()

@app.post("/analyze", response_class=HTMLResponse)
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    pil_img = Image.open(io.BytesIO(contents)).convert('RGB')

    ela_msg, ela_score = analyze_ela(pil_img)
    meta_msg, meta_score = check_metadata(pil_img)

    final_score = int((ela_score + meta_score) / 2)
    status = "✅ AUTHENTIC" if final_score > 85 else "⚠️ SUSPICIOUS" if final_score > 70 else "🚨 POSSIBLE TAMPERING"

    result_box = f"""
    <div style="margin:20px;padding:20px;background:#0f172a;border:2px solid {'#22c55e' if final_score>85 else '#eab308' if final_score>70 else '#ef4444'};border-radius:12px;color:white;">
    <h3>{status} - {file.filename}</h3>
    <p><b>Authenticity Score:</b> {final_score}%</p>
    <p><b>ELA Check:</b> {ela_msg}</p>
    <p><b>Metadata Check:</b> {meta_msg}</p>
    <p><b>File:</b> {len(contents)} bytes | {pil_img.size[0]}x{pil_img.size[1]}</p>
    <p style="margin-top:10px;font-size:12px;opacity:0.7;">For insurance: {'>85% = Approve, 70-85% = Manual review, <70% = Investigate' }</p>
    </div>
    """

    html = get_index_html()
    if "</body>" in html:
        html = html.replace("</body>", result_box + "</body>")
    else:
        html += result_box
    return HTMLResponse(content=html)
