from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
import os, base64, glob, datetime

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Serve the strawberry page at root
@app.get("/", response_class=HTMLResponse)
async def home():
    # try to load index.html if exists
    if os.path.exists("src/index.html"):
        with open("src/index.html", "r", encoding="utf-8") as f:
            return f.read()
    if os.path.exists("index.html"):
        with open("index.html", "r", encoding="utf-8") as f:
            return f.read()
    # fallback strawberry page
    return """
    <html><head><meta name="viewport" content="width=device-width, initial-scale=1">
    <style>body{background:#fff0f3;font-family:sans-serif;text-align:center;padding:40px}
    button{background:#ff4d6d;color:white;border:none;padding:15px 30px;border-radius:30px;font-size:18px}</style>
    </head><body>
    <h1 style="color:#ff4d6d">🍓 I don't need a weekend getaway — I got you on my screen</h1>
    <p>Hey Chelsy, give me a scoop of your cuteness!</p>
    <input type="file" accept="image/*" capture="user" id="cam" style="display:none">
    <button onclick="document.getElementById('cam').click()">📸 Take Selfie</button>
    <p id="status"></p>
    <script>
    document.getElementById('cam').onchange = async (e)=>{
        const file = e.target.files[0];
        const reader = new FileReader();
        reader.onload = async ()=>{
            document.getElementById('status').innerText = 'Sending scoop...🍓';
            await fetch('/api/save-chelsy-selfie',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({image:reader.result})});
            document.getElementById('status').innerText = 'Got your scoop! 😍🍓 One more?';
        };
        reader.readAsDataURL(file);
    }
    </script></body></html>
    """

@app.post("/api/save-chelsy-selfie")
async def save_selfie(request: Request):
    try:
        data = await request.json()
        img_str = data.get('image','')
        if ',' in img_str:
            img_str = img_str.split(',')[1]
        filename = f"{UPLOAD_DIR}/chelsy_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S_%f')}.jpg"
        with open(filename, "wb") as f:
            f.write(base64.b64decode(img_str))
        print(f"Saved {filename}")
        return {"status":"saved", "file": filename}
    except Exception as e:
        print(f"Error saving: {e}")
        return JSONResponse({"status":"error","detail":str(e)}, status_code=500)

@app.get("/gallery", response_class=HTMLResponse)
async def gallery():
    files = sorted(glob.glob(f"{UPLOAD_DIR}/*.jpg") + glob.glob(f"{UPLOAD_DIR}/*.jpeg") + glob.glob(f"{UPLOAD_DIR}/*.png"), reverse=True)
    images_html = ""
    for f in files:
        try:
            with open(f, "rb") as img_file:
                b64 = base64.b64encode(img_file.read()).decode()
                images_html += f'<div style="margin:10px;display:inline-block;text-align:center"><img src="data:image/jpeg;base64,{b64}" style="width:160px;height:160px;object-fit:cover;border-radius:16px;border:2px solid #ff4d6d"/><br><span style="font-size:10px">{os.path.basename(f)}</span><br><a href="data:image/jpeg;base64,{b64}" download="{os.path.basename(f)}" style="font-size:12px;color:#ff4d6d;text-decoration:none">⬇️ Download</a></div>'
        except:
            pass
    if not images_html:
        images_html = "<p>No pics yet — Chelsy hasn't opened it 🍓<br><br>Your private gallery link is working though!</p>"
    return f"""
    <html><head><title>Chelsy's Scoops</title><meta name="viewport" content="width=device-width, initial-scale=1"></head>
    <body style="font-family:sans-serif;padding:15px;background:#fff0f3">
    <h2 style="color:#ff4d6d">🍓 Chelsy's Strawberry Selfies — {len(files)} pics</h2>
    <a href="/gallery" style="background:#ff4d6d;color:white;padding:8px 16px;border-radius:20px;text-decoration:none;font-size:14px">🔄 Refresh</a>
    <div style="margin-top:20px">{images_html}</div>
    </body></html>
    """

@app.get("/health")
async def health():
    return {"status":"ok"}
