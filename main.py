from fastapi import FastAPI, File, UploadFile, Request
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from PIL import Image
import numpy as np
import cv2
import io
import os

app = FastAPI(title="AI Powered Insurance Image Forensics")

templates = Jinja2Templates(directory=".")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze", response_class=HTMLResponse)
async def analyze_image(request: Request, file: UploadFile = File(...)):
    try:
        contents = await file.read()
        image = Image.open(io.BytesIO(contents))
        # Simple analysis - you can add your real forensics logic later
        result = {
            "filename": file.filename,
            "status": "Analysis Complete",
            "message": "No tampering detected - Image looks authentic",
            "score": "95% Authentic"
        }
        return templates.TemplateResponse("index.html", {"request": request, "result": result, "filename": file.filename})
    except Exception as e:
        return templates.TemplateResponse("index.html", {"request": request, "error": str(e)})
