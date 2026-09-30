from fastapi import FastAPI, File, UploadFile, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from PIL import Image
import numpy as np
import cv2
import io
import os

app = FastAPI(title="AI Powered Insurance Image Forensics")

templates = Jinja2Templates(directory="templates")

# Create templates folder if not exists
if not os.path.exists("templates"):
    os.makedirs("templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_image(request: Request, file: UploadFile = File(...)):
    try:
        # Read image
        contents = await file.read()
        nparr = np.frombuffer(contents, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        
        pil_img = Image.open(io.BytesIO(contents))
        
        # Simple Forensics Analysis
        width, height = pil_img.size
        format_type = pil_img.format
        mode = pil_img.mode
        
        # ELA Simulation - check compression artifacts
        # Convert to grayscale and check variance
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        variance = np.var(gray)
        
        # Simple fraud detection logic
        if variance < 100:
            risk = "HIGH - Possible tampering detected (Low variance)"
            score = "85% Suspicious"
        elif variance < 500:
            risk = "MEDIUM - Needs manual review"
            score = "45% Suspicious"
        else:
            risk = "LOW - Image appears authentic"
            score = "10% Suspicious"
        
        result = {
            "filename": file.filename,
            "dimensions": f"{width} x {height}",
            "format": format_type,
            "mode": mode,
            "variance": f"{variance:.2f}",
            "risk": risk,
            "score": score
        }
        
        return templates.TemplateResponse("index.html", {"request": request, "result": result})
    
    except Exception as e:
        error_result = {
            "filename": file.filename if file else "Unknown",
            "risk": f"Error analyzing image: {str(e)}",
           
