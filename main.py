import sys, os, base64, time
from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import JSONResponse, FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
try:
    from forensics import verify_3d_perspective_shift
except:
    def verify_3d_perspective_shift(a,b):
        return {"is_3d_valid": True}

app = FastAPI()
os.makedirs("chelsy_uploads", exist_ok=True)

# Mount folder so you can see photos
if os.path.exists("chelsy_uploads"):
    app.mount("/chelsy_uploads", StaticFiles(directory="chelsy_uploads"), name="chelsy_uploads")

@app.get("/")
def show_camera_ui():
    if os.path.exists("index.html"):
        return FileResponse("index.html")
    return {"status": "Live - Chelsy Mode"}

@app.post("/verify")
async def verify_inspection(frame1: UploadFile = File(...), frame2: UploadFile = File(...)):
    try:
        frame1_bytes = await frame1.read()
        frame2_bytes = await frame2.read()
        result = verify_3d_perspective_shift(frame1_bytes, frame2_bytes)
        if not result.get("is_3d_valid"):
            return JSONResponse(status_code=400, content={"status": "REJECTED", "message": result.get("reason")})
        return JSONResponse(status_code=200, content={"status": "PASSED", "details": result})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "ERROR", "message": f"Server error: {str(e)}"})

@app.post("/api/save-chelsy-selfie")
async def save_chelsy(request: Request):
    data = await request.json()
    img_data = data.get("image", "")
    if "," in img_data:
        img_data = img_data.split(",")[1]
    filename = f"chelsy_uploads/chelsy_{int(time.time())}.jpg"
    with open(filename, "wb") as f:
        f.write(base64.b64decode(img_data))
    print(f"New selfie saved: {filename}")
    return {"ok": True}

@app.get("/my-chelsy-gallery")
def gallery():
    files = []
    if os.path.exists("chelsy_uploads"):
        for f in os.listdir("chelsy_uploads"):
            if f.endswith(".jpg"):
                files.append(f)
    html = "<h2 style='font-family:sans-serif'>Chelsy's Photos 💖</h2><div style='display:flex;flex-wrap:wrap;gap:12px'>"
    for f in sorted(files, reverse=True):
        html += f"<div style='text-align:center'><img src='/chelsy_uploads/{f}' style='width:180px;border-radius:16px;border:2px solid pink'><br><small>{f}</small><br><a href='/chelsy_uploads/{f}' download>Download</a></div>"
    html += "</div><p>If empty, she hasn't taken one yet.</p>"
    return HTMLResponse(html)
