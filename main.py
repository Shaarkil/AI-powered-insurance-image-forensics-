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

# Allow frontend to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

def generate_unique_id(image_bytes: bytes) -> str:
    """Create a unique ID containing date + time + image hash"""
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
    """
    Main endpoint that will process the uploaded vehicle image.
    Currently returns a basic response. Real AI models will be added next.
    """
    # Validate that it is an image
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="Only image files are allowed")

    # Read the image
    image_bytes = await file.read()

    # Generate unique ID with timestamp
    unique_id = generate_unique_id(image_bytes)

    # Save temporarily (needed later for AI models)
    with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as tmp:
        tmp.write(image_bytes)
        tmp_path = tmp.name

    try:
        # -----------------------------------------------
        # PLACEHOLDER - Real logic will be added here
        # 1. Detect vehicle type (car, motorcycle, bus...)
        # 2. Read front & rear plates
        # 3. Assess damage score
        # 4. Detect color
        # -----------------------------------------------

        result = {
            "id": unique_id,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "status": "accepted",
            "message": "Image received successfully. AI models will be connected in the next step.",
            "filename": file.filename
        }

        return result

    finally:
        # Clean up temporary file
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
