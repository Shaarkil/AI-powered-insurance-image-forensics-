from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime
import uuid
import hashlib
import tempfile
import os

app = FastAPI(
    title="AI-Powered Insurance Image Forensics",
    description="Detects vehicle details, damage, plates, color and helps flag potential fraud for Kenyan insurance claims",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_unique_id(image_bytes: bytes) -> str:
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    img_hash = hashlib.sha256(image_bytes).hexdigest()[:8]
    return f"{timestamp}_{img_hash}_{str(uuid.uuid4())[:6]}"

@app.get("/")
def health_check():
    return {
        "status": "online",
        "service": "AI-Powered Insurance Image Forensics",
        "message": "Ready to receive images"
    }

@app.post("/assess")
async def assess_vehicle(file: UploadFile = File(...)):
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    image_bytes = await file.read()
    unique_id = generate_unique_id(image_bytes)

    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        result = {
            "id": unique_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "accepted",
            "message": "Image received successfully. AI models will be added next.",
            "filename": file.filename
        }
        return result
    finally:
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
