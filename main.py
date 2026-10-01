import os
import base64
from fastapi import FastAPI, UploadFile, File, Header, HTTPException, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from forensics import verify_3d_perspective_shift, blur_privacy_regions

app = FastAPI(title="Vehicle Fraud Prevention Engine")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

VALID_API_KEYS = {"lease_client_demo_key_9981", "fleet_manager_prod_4421"}

HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Damage Inspection</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #121212; color: #fff; text-align: center; margin: 0; padding: 20px; }
        .camera-container { position: relative; max-width: 500px; margin: 20px auto; border-radius: 12px; overflow: hidden; border: 2px solid #333; background: #000; min-height: 280px; display: flex; align-items: center; justify-content: center; }
        video { width: 100%; height: auto; display: none; }
        .hud-overlay { position: absolute; top: 0; left: 0; width: 100%; height: 100%; pointer-events: none; border: 4px dashed rgba(255, 255, 255, 0.4); box-sizing: border-box; display: none; }
        .hud-overlay::after { content: "ALIGN CAR DAMAGE WITHIN BOX"; position: absolute; top: 10px; width: 100%; text-align: center; font-size: 12px; color: #00ff88; font-weight: bold; }
        .btn { background: #007aff; color: white; border: none; padding: 14px 28px; font-size: 16px; font-weight: bold; border-radius: 8px; cursor: pointer; margin-top: 15px; width: 100%; max-width: 500px; }
        .btn:disabled { background: #444; cursor: not-allowed; }
        #status { margin-top: 20px; font-weight: bold; color: #aaa; }
        .passed { color: #00ff88; }
        .rejected { color: #ff3b30; }
        .placeholder-text { color: #666; font-size: 14px; padding: 20px; }
    </style>
</head>
<body>
    <h2>Live Vehicle Inspection</h2>
    <p style="font-size: 13px; color: #aaa;">Hardware locked live capture engine</p>

    <div class="camera-container" id="camBox">
        <span class="placeholder-text" id="placeholder">Tap 'Start Camera' to enable live scanner</span>
        <video id="webcam" autoplay playsinline></video>
        <div class="hud-overlay" id="hud"></div>
    </div>

    <!-- Initial Action Button -->
    <button id="mainBtn" class="btn" onclick="handleMainAction()">START CAMERA & INSPECTION</button>
    <div id="status">Awaiting camera authorization...</div>

    <script>
        let video = document.getElementById('webcam');
        let hud = document.getElementById('hud');
        let placeholder = document.getElementById('placeholder');
        let statusDiv = document.getElementById('status');
        let mainBtn = document.getElementById('mainBtn');
        let isVirtualCamDetected = false;
        let isCameraActive = false;

        async function handleMainAction() {
            if (!isCameraActive) {
                // User intentionally requested camera activation
                await initWebRTC();
            } else {
                // Camera is running, execute scan
                await captureAndVerify();
            }
        }

        async function initWebRTC() {
            statusDiv.innerHTML = "Requesting hardware camera access...";
            mainBtn.disabled = true;

            try {
                const stream = await navigator.mediaDevices.getUserMedia({ video: { facingMode: { exact: "environment" } } });
                handleStream(stream);
            } catch (err) {
                try {
                    const stream = await navigator.mediaDevices.getUserMedia({ video: true });
                    handleStream(stream);
                } catch (e) {
                    statusDiv.innerHTML = "<span class='rejected'>Error: Camera access denied or hardware missing.</span>";
                    mainBtn.disabled = false;
                }
            }
        }

        function handleStream(stream) {
            video.srcObject = stream;
            video.style.display = "block";
            hud.style.display = "block";
            placeholder.style.display = "none";
            
            const track = stream.getVideoTracks()[0];
            const label = track.label.toLowerCase();

            if (label.includes("obs") || label.includes("virtual") || label.includes("software")) {
                isVirtualCamDetected = true;
                statusDiv.innerHTML = "<span class='rejected'>SECURITY ALERT: Virtual Camera / Software Injection Blocked!</span>";
                mainBtn.disabled = true;
                return;
            }

            isCameraActive = true;
            mainBtn.disabled = false;
            mainBtn.innerText = "SCAN DAMAGE (STEP 1: TILT PHONE)";
            mainBtn.style.background = "#28a745";
            statusDiv.innerHTML = "Camera active. Target vehicle area and click Scan.";
        }

        async function captureAndVerify() {
            statusDiv.innerHTML = "Capturing Frame 1... Tilt phone slightly now...";
            mainBtn.disabled = true;

            const canvas = document.createElement('canvas');
            canvas.width = video.videoWidth;
            canvas.height = video.videoHeight;
            const ctx = canvas.getContext('2d');

            ctx.drawImage(video, 0, 0);
            const frame1Blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg'));

            setTimeout(async () => {
                statusDiv.innerHTML = "Capturing Frame 2 & Auditing 3D Perspective...";
                ctx.drawImage(video, 0, 0);
                const frame2Blob = await new Promise(res => canvas.toBlob(res, 'image/jpeg'));

                const formData = new FormData();
                formData.append('frame1', frame1Blob, 'frame1.jpg');
                formData.append('frame2', frame2Blob, 'frame2.jpg');
                formData.append('is_virtual_camera', isVirtualCamDetected);

                try {
                    const response = await fetch('/api/v1/verify-stream', {
                        method: 'POST',
                        headers: { 'X-API-KEY': 'lease_client_demo_key_9981' },
                        body: formData
                    });

                    const data = await response.json();

                    if (data.authenticity_verdict === "PASSED") {
                        statusDiv.innerHTML = `<span class='passed'>PASSED: Authenticity Confirmed (Risk Score: ${data.risk_score}/100)</span>`;
                    } else {
                        statusDiv.innerHTML = `<span class='rejected'>REJECTED: ${data.reason}</span>`;
                    }
                } catch (err) {
                    statusDiv.innerHTML = "<span class='rejected'>Server error processing verification.</span>";
                }
                mainBtn.disabled = false;
            }, 800);
        }
    </script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
async def read_root():
    return HTMLResponse(content=HTML_CONTENT, status_code=200)

@app.post("/api/v1/verify-stream")
async def verify_stream(
    frame1: UploadFile = File(...),
    frame2: UploadFile = File(...),
    is_virtual_camera: bool = Form(False),
    x_api_key: str = Header(None)
):
    if x_api_key and x_api_key not in VALID_API_KEYS:
        raise HTTPException(status_code=401, detail="Unauthorized X-API-KEY header.")

    if is_virtual_camera:
        return JSONResponse(status_code=400, content={
            "authenticity_verdict": "REJECTED",
            "risk_score": 100,
            "reason": "Virtual camera / software injection detected."
        })

    frame1_bytes = await frame1.read()
    frame2_bytes = await frame2.read()

    liveness_result = verify_3d_perspective_shift(frame1_bytes, frame2_bytes)
    processed_bytes, redaction_info = blur_privacy_regions(frame1_bytes)
    base64_processed = base64.b64encode(processed_bytes).decode('utf-8')

    if not liveness_result["is_3d_valid"]:
        return {
            "authenticity_verdict": "FLAGGED",
            "risk_score": 85,
            "security_checks": {"2d_screen_spoof_detected": True},
            "reason": liveness_result["reason"],
            "processed_image_base64": f"data:image/jpeg;base64,{base64_processed}"
        }

    return {
        "authenticity_verdict": "PASSED",
        "risk_score": 5,
        "security_checks": {"2d_screen_spoof_detected": False},
        "liveness_metrics": liveness_result,
        "processed_image_base64": f"data:image/jpeg;base64,{base64_processed}"
    }
