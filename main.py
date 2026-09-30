from fastapi import FastAPI, File, UploadFile
from fastapi.responses import HTMLResponse
import os

app = FastAPI()

def get_index_html():
    with open("index.html", "r", encoding="utf-8") as f:
        return f.read()

@app.get("/", response_class=HTMLResponse)
async def home():
    return get_index_html()

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    # Mock analysis for now - makes site work, you add real AI later
    contents = await file.read()
    size = len(contents)
    html = get_index_html()
    # Inject result at bottom
    result_box = f"""
    <div style="margin:20px;padding:20px;background:#d4edda;border:2px solid #28a745;border-radius:10px;">
    <h3>✅ Analysis Complete: {file.filename}</h3>
    <p><b>File Size:</b> {size} bytes</p>
    <p><b>Result:</b> No tampering detected - 95% Authentic</p>
    <p><b>Status:</b> Image looks genuine</p>
    </div>
    """
    # Insert before </body>
    if "</body>" in html:
        html = html.replace("</body>", result_box + "</body>")
    else:
        html += result_box
    return HTMLResponse(content=html)
