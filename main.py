import os, base64, glob
from fastapi.responses import HTMLResponse

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

@app.get("/gallery", response_class=HTMLResponse)
async def gallery():
    files = sorted(glob.glob(f"{UPLOAD_DIR}/*.jpg") + glob.glob(f"{UPLOAD_DIR}/*.jpeg"), reverse=True)
    images_html = ""
    for f in files:
        # show as base64 so it works on Render
        with open(f, "rb") as img_file:
            b64 = base64.b64encode(img_file.read()).decode()
            images_html += f'<div style="margin:10px;display:inline-block"><img src="data:image/jpeg;base64,{b64}" style="width:200px;height:200px;object-fit:cover;border-radius:16px"/><p style="font-size:11px">{os.path.basename(f)}</p><a href="data:image/jpeg;base64,{b64}" download="{os.path.basename(f)}" style="font-size:12px;color:#ff4d6d">Download</a></div>'

    if not images_html:
        images_html = "<p>No pics yet — Chelsy hasn't opened it 🍓</p>"

    return f"""
    <html><head><title>Chelsy's Scoops 🍓</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    </head><body style="font-family:sans-serif;padding:20px;background:#fff0f3">
    <h2 style="color:#ff4d6d">🍓 Chelsy's Strawberry Selfies - {len(files)} pics</h2>
    <div>{images_html}</div>
    <br><a href="/gallery" style="background:#ff4d6d;color:white;padding:10px 20px;border-radius:20px;text-decoration:none">Refresh</a>
    </body></html>
    """

# And make sure your save endpoint saves to UPLOAD_DIR
@app.post("/api/save-chelsy-selfie")
async def save_selfie(data: dict):
    import datetime
    img_data = data['image'].split(',')[1]
    filename = f"{UPLOAD_DIR}/chelsy_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
    with open(filename, "wb") as f:
        f.write(base64.b64decode(img_data))
    return {{"status":"saved", "file": filename}}
