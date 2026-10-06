from fastapi import FastAPI, File, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details, damage, plates, color and helps flag potential fraud for Kenyan insurance claims",
    version="0.1.0"
)

# Allow CORS (useful during testing)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Serve static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Serve the new professional frontend as the homepage
@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    return FileResponse("static/index.html")


# Keep your existing /assess endpoint exactly as it is
@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    # ⬇️ KEEP YOUR EXISTING ANALYSIS CODE HERE ⬇️
    # (whatever you currently have that processes the image
    # and returns the JSON with plate, damage, risk etc.)
    
    # Example placeholder (replace with your real logic):
    # result = your_analysis_function(file)
    # return result
    
    pass   # ← delete this line and put your real code
