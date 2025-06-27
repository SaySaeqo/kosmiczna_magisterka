from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse, HTMLResponse, JSONResponse
from picamera2 import Picamera2
from threading import Thread
from io import BytesIO
from PIL import Image
import time
import motor

app = FastAPI()
picam2 = None
frame = None
frame_thread = None
monitor_thread = None
running = False
camera_active = False
last_access_time = time.time()
INACTIVITY_TIMEOUT = 60  # seconds
app_running = True

def capture_frames():
    global frame
    while running:
        try:
            img_array = picam2.capture_array()
            img = Image.fromarray(img_array)
            buf = BytesIO()
            img.save(buf, format="JPEG")
            frame = buf.getvalue()
            time.sleep(0.1)
        except Exception as e:
            print(f"Frame capture error: {e}")
            time.sleep(0.5)

def monitor_activity():
    global running, camera_active
    while app_running:
        time.sleep(5)
        if camera_active and (time.time() - last_access_time > INACTIVITY_TIMEOUT):
            print("No access detected. Auto-stopping camera.")
            stop_camera()

@app.on_event("startup")
def initialize():
    global picam2, monitor_thread
    picam2 = Picamera2()
    picam2.configure(picam2.create_video_configuration(main={"format": "RGB888", "size": (640, 480)}))
    monitor_thread = Thread(target=monitor_activity, daemon=True)
    monitor_thread.start()

@app.on_event("shutdown")
def cleanup():
    stop_camera()
    app_running = False

def start_camera():
    global running, frame_thread, camera_active
    if not camera_active:
        print("Starting camera.")
        picam2.start()
        running = True
        frame_thread = Thread(target=capture_frames, daemon=True)
        frame_thread.start()
        camera_active = True

def stop_camera():
    global running, camera_active
    if camera_active:
        print("Stopping camera.")
        running = False
        time.sleep(0.2)
        picam2.stop()
        camera_active = False

def mjpeg_generator():
    boundary = "--frame"
    while running:
        if frame:
            yield (
                f"{boundary}\r\n"
                "Content-Type: image/jpeg\r\n"
                f"Content-Length: {len(frame)}\r\n\r\n"
            ).encode() + frame + b"\r\n"
        time.sleep(0.1)

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    return """
    <html>
        <head>
            <title>Camera Control</title>
        </head>
        <body>
            <h1>Raspberry Pi MJPEG Stream</h1>
            <div>
                <button onclick="startCamera()">Start Camera</button>
                <button onclick="stopCamera()">Stop Camera</button>
                <button onclick="runMotor()">Run Motor</button>
            </div>
            <div id="status" style="margin-top: 10px; font-weight: bold;">Checking camera status...</div>
            <br />
            <img id="stream" src="/stream" width="640" height="480" />
            <script>
                function startCamera() {
                    fetch('/start', { method: 'POST' }).then(() => {
                        document.getElementById("stream").src = "/stream?" + new Date().getTime();
                    });
                }
                function stopCamera() {
                    fetch('/stop', { method: 'POST' }).then(() => {
                        document.getElementById("stream").src = "";
                    });
                }

                function runMotor() {
                    fetch('/motor')
                        .then(response => response.json())
                        .then(data => {
                            document.getElementById("status").innerText = 
                                `Motor status: ${data.motor_status}`;
                        });
                }

                function updateStatus() {
                    fetch('/status')
                        .then(response => response.json())
                        .then(data => {
                            const secs = data.time_remaining;
                            if (secs > 0) {
                                document.getElementById("status").innerText = 
                                    `Camera will auto-stop in ${secs} second${secs === 1 ? '' : 's'}`;
                            } else {
                                document.getElementById("status").innerText = 
                                    "Camera is inactive or about to stop.";
                                document.getElementById("stream").src = "";
                            }
                        });
                }

                setInterval(updateStatus, 3000);
                updateStatus();
            </script>
        </body>
    </html>
    """

@app.get("/stream")
def stream():
    global last_access_time
    last_access_time = time.time()
    if not camera_active:
        return JSONResponse({"error": "Camera not active"}, status_code=400)
    return StreamingResponse(mjpeg_generator(), media_type="multipart/x-mixed-replace; boundary=frame")

@app.post("/start")
def start():
    global last_access_time
    last_access_time = time.time()
    start_camera()
    return {"status": "started"}

@app.post("/stop")
def stop():
    stop_camera()
    return {"status": "stopped"}

@app.get("/status")
def status():
    global last_access_time 
    time_left = max(0, int(INACTIVITY_TIMEOUT - (time.time() - last_access_time))) if camera_active else 0
    return {"time_remaining": time_left}

motor_is_running = False
@app.get("/motor")
def run_motor():
    return {"motor_status":"no motor yet"}
    global motor_is_running
    if motor_is_running:
        return {"motor_status": "already running"}
    motor_is_running = True
    motor.reset()
    motor.step(motor.HALF_STEP, motor.FULL_ROTATION)
    motor_is_running = False
    return {"motor_status": "motor has run successfuly"}



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)

