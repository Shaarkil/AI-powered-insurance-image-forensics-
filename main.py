from flask import Flask, request, jsonify, render_template_string
from PIL import Image, ImageFilter
import io, numpy as np, os, base64, requests

app = Flask(__name__)

MODEL_URL = "https://huggingface.co/Organika/sdxl-detector/resolve/main/model.onnx"
MODEL_PATH = "detector.onnx"
onnx_sess = None

def load_onnx():
    global onnx_sess
    try:
        import onnxruntime as ort
        if not os.path.exists(MODEL_PATH):
            print("Downloading AI detector 90MB...")
            r = requests.get(MODEL_URL, stream=True, timeout=60)
            with open(MODEL_PATH, 'wb') as f:
                for chunk in r.iter_content(8192):
                    f.write(chunk)
        onnx_sess = ort.InferenceSession(MODEL_PATH, providers=['CPUExecutionProvider'])
        print("ONNX loaded!")
    except Exception as e:
        print(f"ONNX not loaded, using heuristic only: {e}")
        onnx_sess = None

def onnx_predict(pil_img):
    if onnx_sess is None:
        return None
    try:
        img = pil_img.resize((224,224)).convert('RGB')
        arr = np.array(img).astype(np.float32) / 255.0
        arr = arr.transpose(2,0,1)[None, ...]  # NCHW
        # normalize imagenet
        mean = np.array([0.485,0.456,0.406]).reshape(1,3,1,1)
        std = np.array([0.229,0.224,0.225]).reshape(1,3,1,1)
        arr = (arr - mean) / std
        out = onnx_sess.run(None, {
