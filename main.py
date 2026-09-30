from fastapi import FastAPI, File, UploadFile, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
import uvicorn
from forensics import analyze_image
from ml_detector import detect_ai_generated
import os

app = FastAPI(title="Insurance Forensics")
templates = Jinja2Templates(directory=".")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/analyze")
async def analyze(file: UploadFile = File(...)):
    contents = await file.read()
    forensics_result = analyze_image(contents)
    ai_result = detect_ai_generated(contents)
    return {
        "forensics": forensics_result,
        "ai_detection": ai_result,
        "filename": file.filename
    }
