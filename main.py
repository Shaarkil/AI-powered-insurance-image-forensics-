import base64
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from forensics import verify_3d_perspective_shift, blur_privacy_regions

app = FastAPI(
    title="Vehicle Damage Fraud Prevention Engine",
    version="1.0.0",
    description="Enterprise REST API for liveness verification and image tamper auditing."
)

templates = Jinja2Templates(directory="templates")

# Mock database of authorized enterprise B2B API keys
VALID_API_KEYS = {"lease_client_demo_key_9981", "fleet_manager_prod_4421"}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/api/v1/verify-stream")
async def verify_stream(
    frame1: UploadFile = File(...),
    frame2: UploadFile = File(...),
    is_virtual_camera: bool = Form(False),
    x_api_key: str = Header(None)
):
    # API Authentication Gate for B2B Clients
    if x_api_key and x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Invalid or unauthorized X-API-KEY header.")

    if is_virtual_camera:
        return JSONResponse(status_code=400, content={
            "authenticity_verdict": "REJECTED",
            "risk_score": 100,
            "security_checks": {
                "virtual_camera_detected": True,
                "2d_screen_spoof_detected": False,
            },
            "reason": "Virtual camera/OBS injection detected on client side."
        })

    frame1_bytes = await frame1.read()
    frame2_bytes = await frame2.read()

    # Perform 3D depth and displacement check
    liveness_result = verify_3d_perspective_shift(frame1_bytes, frame2_bytes)

    # Perform privacy blurring on primary frame
    processed_bytes, redaction_info = blur_privacy_regions(frame1_bytes)
    base64_processed = base64.b64encode(processed_bytes).decode('utf-8')

    if not liveness_result["is_3d_valid"]:
        return {
            "authenticity_verdict": "FLAGGED",
            "risk_score": 85,
            "security_checks": {
                "virtual_camera_detected": False,
                "2d_screen_spoof_detected": True,
            },
            "reason": liveness_result["reason"],
            "processed_image_base64": f"data:image/jpeg;base64,{base64_processed}"
        }

    return {
        "authenticity_verdict": "PASSED",
        "risk_score": 5,
        "security_checks": {
            "virtual_camera_detected": False,
            "2d_screen_spoof_detected": False,
        },
        "liveness_metrics": liveness_result,
        "privacy_redaction": redaction_info,
        "processed_image_base64": f"data:image/jpeg;base64,{base64_processed}"
    }
