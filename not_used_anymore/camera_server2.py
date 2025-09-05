import cv2
import time
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
import uvicorn
import asyncio

app = FastAPI()

# Try to open stereo camera
camera_index = 0
camera = cv2.VideoCapture(camera_index, cv2.CAP_V4L2)
camera.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)  # stereo width (e.g. 2×640)
camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)  # height of one camera

FPS = 60

def generate_mjpeg():
    while camera.isOpened():
        time.sleep(1.0/FPS)

        ret, frame = camera.read()
        if not ret or frame is None:
            print("Can't receive frame (stream end?). Exiting ...")
            camera.release()
            continue

        # Optionally: resize or preprocess here
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            print("Can't convert to jpg. Exiting ...")
            camera.release()
            continue

        frame_bytes = jpeg.tobytes()
        yield (
            b"--frame\r\n"
            b"Content-Type: image/jpeg\r\n"
            + f"Content-Length: {len(frame_bytes)}\r\n".encode()
            + b"\r\n"
            + frame_bytes
            + b"\r\n"
        )


@app.get("/", response_class=HTMLResponse)
def index():
    return """
    <html>
        <head><title>Stereo VR 180 Stream</title></head>
        <body style="background:#000; text-align:center; color:white;">
            <h1>Stereo VR 180 Camera Stream</h1>
            <img src="/video" style="width:100%; max-width:1280px;" />
        </body>
    </html>
    """


@app.get("/video")
def video_feed():
    return StreamingResponse(
        generate_mjpeg(),
        media_type="multipart/x-mixed-replace; boundary=frame"
    )


@app.on_event("shutdown")
def shutdown():
    camera.release()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)

