import sys, os, base64, time
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI()
os.makedirs("chelsy_uploads", exist_ok=True)

# This fixes your black screen
app.mount("/chelsy_uploads", StaticFiles(directory="chelsy_uploads"), name="chelsy_uploads")

@app.get("/")
def home():
    # Try all possible places for index.html
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return HTMLResponse("<h1>Upload index.html to GitHub root</h1>", status_code=404)

@app.post("/api/save-chelsy-selfie")
async def save_chelsy(request: Request):
    data = await request.json()
    img_data = data.get("image", "")
    if "," in img_data:
        img_data = img_data.split(",")[1]
    filename = f"chelsy_uploads/chelsy_{int(time.time())}.jpg"
    with open(filename, "wb") as f:
        f.write(base64.b64decode(img_data))
    print(f"New selfie: {filename}")
    return {"ok": True}

@app.get("/my-chelsy-gallery")
def gallery():
    files = [f for f in os.listdir("chelsy_uploads") if f.endswith(".jpg")] if os.path.exists("chelsy_uploads") else []
    html = "<h2>Chelsy's Photos 💖</h2><div style='display:flex;flex-wrap:wrap;gap:12px'>"
    for f in sorted(files, reverse=True):
        html += f"<div><img src='/chelsy_uploads/{f}' style='width:180px;border-radius:16px'><br><a href='/chelsy_uploads/{f}' download>Download</a></div>"
    html += "</div>"
    return HTMLResponse(html)
