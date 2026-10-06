from fastapi import FastAPI, UploadFile, File, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from datetime import datetime
import uuid
import hashlib
import tempfile
import os
from ultralytics import YOLO

app = FastAPI(title="AI Insurance Image Forensics", version="0.3.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load YOLO once
model = YOLO("yolov8n.pt")

ALLOWED_CLASSES = {
    2: "car",
    3: "motorcycle",
    5: "bus",
    7: "truck"
}

def generate_unique_id(image_bytes: bytes) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    img_hash = hashlib.sha256(image_bytes).hexdigest()[:8]
    return f"{timestamp}_{img_hash}_{str(uuid.uuid4())[:6]}"
