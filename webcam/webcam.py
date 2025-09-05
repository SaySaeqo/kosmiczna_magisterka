import argparse
import asyncio
import json
import logging
import os
import platform
import ssl
from typing import Optional
import math
import time
import motor
import threading
import queue as thread_queue

from aiohttp import web
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCRtpSender,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaPlayer, MediaRelay

ROOT = os.path.dirname(__file__)

pcs = set()
relay = None
webcam = None
disable_motor = True
ctx = None
queue = None
motor_thread = None

def cmotor_worker(q):
    try:
        import kosmiczna_magisterka.fast_motor as cmotor
        motor.setup()
        motor.reset()
        motor.GPIO.output(motor.MPINS, motor.GPIO.HIGH) # setting 1/16 step
        motor.GPIO.output(motor.PINS["EN"], motor.GPIO.LOW)  # Enable the motor
        for task in iter(q.get, None):
            print(".",end="", flush=True)
            dir_pin, acceleration, start_freq, duration = task
            motor.GPIO.output(motor.PINS["DIR"], dir_pin)
            cmotor.generate_signal(acceleration, int(start_freq), duration)
            q.task_done()
        motor.GPIO.output(motor.PINS["EN"], motor.GPIO.HIGH)  # Disable the m   ootor
    except KeyboardInterrupt: 
        motor.GPIO.output(motor.PINS["EN"], motor.GPIO.HIGH)  # Disable the m   ootor

def cmotor_worker_mock(q):
    for task in iter(q.get, None):
        dir_pin, acceleration, start_freq, duration = task
        print(f"Mock motor: dir={dir_pin} acc={acceleration:.2f} start_freq={start_freq} duration={duration:.2f}")
        time.sleep(duration + 0.1)
        q.task_done()


def create_local_tracks(
    play_from: str, decode: bool
) -> tuple[Optional[MediaStreamTrack], Optional[MediaStreamTrack]]:
    global relay, webcam

    if play_from:
        # If a file name was given, play from that file.
        player = MediaPlayer(play_from, decode=decode)
        return player.audio, player.video
    else:
        # Otherwise, play from the system's default webcam.
        #
        # In order to serve the same webcam to multiple users we make use of
        # a `MediaRelay`. The webcam will stay open, so it is our responsability
        # to stop the webcam when the application shuts down in `on_shutdown`.
        options = {
            "framerate": "10",
            "video_size": "1280x480",
            "input_format": "yuv420p",
            "thread_queue_size": "1024",
            "c:v": "h264_v4l2m2m"
        }
        if relay is None:
            if platform.system() == "Darwin":
                webcam = MediaPlayer(
                    "default:none", format="avfoundation", options=options
                )
            elif platform.system() == "Windows":
                webcam = MediaPlayer(
                    "video=Integrated Camera", format="dshow", options=options
                )
            else:
                webcam = MediaPlayer("/dev/video0", format="v4l2", options=options)
            relay = MediaRelay()
        return None, relay.subscribe(webcam.video)


def force_codec(pc: RTCPeerConnection, sender: RTCRtpSender, forced_codec: str) -> None:
    kind = forced_codec.split("/")[0]
    codecs = RTCRtpSender.getCapabilities(kind).codecs
    transceiver = next(t for t in pc.getTransceivers() if t.sender == sender)
    transceiver.setCodecPreferences(
        [codec for codec in codecs if codec.mimeType == forced_codec]
    )


async def index(request: web.Request) -> web.Response:
    content = open(os.path.join(ROOT, "../client5.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

def _clamp(v, lo=-1.0, hi=1.0):
    return hi if v > hi else lo if v < lo else v

def y_axis_rotation(q: dict) -> float:
    x, y, z, w = q["x"], q["y"], q["z"], q["w"]
    return math.atan2(2*(w*y + x*z), 1 - 2*(y*y + z*z))

def relative_y_axis_rotation(q_from: dict, q_to: dict) -> float:
    """
    Rotation about Y to go from q_from to q_to.
    """
    # conjugate of q_from (unit quaternion inverse)
    cf = { "x": -q_from["x"], "y": -q_from["y"], "z": -q_from["z"], "w": q_from["w"] }
    # quaternion multiply q_to * cf
    q = {
        "x": q_to["w"]*cf["x"] + q_to["x"]*cf["w"] + q_to["y"]*cf["z"] - q_to["z"]*cf["y"],
        "y": q_to["w"]*cf["y"] - q_to["x"]*cf["z"] + q_to["y"]*cf["w"] + q_to["z"]*cf["x"],
        "z": q_to["w"]*cf["z"] + q_to["x"]*cf["y"] - q_to["y"]*cf["x"] + q_to["z"]*cf["w"],
        "w": q_to["w"]*cf["w"] - q_to["x"]*cf["x"] - q_to["y"]*cf["y"] - q_to["z"]*cf["z"],
    }
    return y_axis_rotation(q)

last_orientation = { "x": 0, "y": 0, "z": 0, "w": 1 }
last_rot_time = time.perf_counter()
last_speed = 0.0
last_frequency = 0.0
MIN_FREQ = 300
MIN_SPEED = MIN_FREQ*motor.ROTATION_PER_STEP / 16 


async def rotate(request: web.Request) -> web.Response:
    # Get parameters
    params = await request.json()
    current_orientation = params["orientation"]

    # Calculate time_diff, angle and save new position
    global last_orientation, last_rot_time, last_speed, last_frequency
    now = time.perf_counter()
    time_diff = now - last_rot_time
    if time_diff < 0.1:  # Prevent too frequent updates
        return web.Response(status=200)
    else:
        last_rot_time = now
    angle = relative_y_axis_rotation(last_orientation, current_orientation)
    # print(f"{current_orientation=} {orientation=} {angle=}")
    current_speed = angle / time_diff
    current_frequency = current_speed / motor.ROTATION_PER_STEP * 16  # 1/16 step
    acceleration = (current_speed - last_speed) / time_diff

    if abs(last_frequency) < MIN_FREQ and abs(current_frequency) < MIN_FREQ:
        # Both speeds are very low, no need to move
        last_speed = 0.0
        last_frequency = 0.0
        last_orientation = current_orientation
        return web.Response(status=200)
    elif abs(last_frequency) < MIN_FREQ:
        last_frequency = MIN_FREQ * (1 if current_frequency >= 0 else -1)
        time_diff = abs((MIN_SPEED - current_speed) / acceleration)
    elif abs(current_frequency) < MIN_FREQ:
        current_frequency = 0.0
        current_speed = 0.0
        time_diff = abs((MIN_SPEED - last_speed) / acceleration)
    elif last_frequency*current_frequency < 0:
        time_to_decelerate = abs((MIN_SPEED - last_speed)/ acceleration)
        acc_time = abs((MIN_SPEED - current_speed) / acceleration)
        next_dir = motor.GPIO.HIGH if last_frequency >= 0 else motor.GPIO.LOW
        current_dir = motor.GPIO.LOW if next_dir == motor.GPIO.HIGH else motor.GPIO.HIGH
        acceleration = abs(acceleration) * motor.INERTIA_PLATFORM2WHEEL_RATIO
        queue.put((current_dir, -acceleration, int(abs(last_frequency)), time_to_decelerate))
        queue.put((next_dir, acceleration, MIN_FREQ, acc_time))
        last_orientation = current_orientation
        last_speed = current_speed
        last_frequency = current_frequency
        return web.Response(status=200)

    # Adjust DIR pin
    dir_pin = 0
    if current_frequency > 0 or last_frequency > 0:
        dir_pin = motor.GPIO.LOW
    else:
        dir_pin = motor.GPIO.HIGH
        acceleration = -acceleration
        last_frequency = -last_frequency

    # Rotate
    queue.put((dir_pin, acceleration*motor.INERTIA_PLATFORM2WHEEL_RATIO, int(last_frequency), time_diff))

    # Update last values
    last_orientation = current_orientation
    last_speed = current_speed
    last_frequency = current_frequency
    return web.Response(status=200)

async def javascript(request: web.Request) -> web.Response:
    content = open(os.path.join(ROOT, "client.js"), "r").read()
    return web.Response(content_type="application/javascript", text=content)


async def offer(request: web.Request) -> web.Response:
    params = await request.json()
    offer = RTCSessionDescription(sdp=params["sdp"], type=params["type"])

    pc = RTCPeerConnection()
    pcs.add(pc)

    @pc.on("connectionstatechange")
    async def on_connectionstatechange() -> None:
        print("Connection state is %s" % pc.connectionState)
        if pc.connectionState == "failed":
            await pc.close()
            pcs.discard(pc)

    # open media source
    audio, video = create_local_tracks(
        args.play_from, decode=not args.play_without_decoding
    )

    if audio:
        audio_sender = pc.addTrack(audio)
        if args.audio_codec:
            force_codec(pc, audio_sender, args.audio_codec)
        elif args.play_without_decoding:
            raise Exception("You must specify the audio codec using --audio-codec")

    if video:
        video_sender = pc.addTrack(video)
        if args.video_codec:
            force_codec(pc, video_sender, args.video_codec)
        elif args.play_without_decoding:
            raise Exception("You must specify the video codec using --video-codec")

    await pc.setRemoteDescription(offer)

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    return web.Response(
        content_type="application/json",
        text=json.dumps(
            {"sdp": pc.localDescription.sdp, "type": pc.localDescription.type}
        ),
    )


async def on_shutdown(app: web.Application) -> None:
    # Close peer connections.
    coros = [pc.close() for pc in pcs]
    await asyncio.gather(*coros)
    pcs.clear()

    # If a shared webcam was opened, stop it.
    if webcam is not None:
        webcam.video.stop()
    
    global motor_thread, queue
    if queue is not None:
        queue.put(None)          # sentinel
    if motor_thread is not None:
        motor_thread.join(timeout=2.0)
        motor_thread = None
    queue = None



if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="WebRTC webcam demo")
    parser.add_argument("--cert-file", help="SSL certificate file (for HTTPS)")
    parser.add_argument("--key-file", help="SSL key file (for HTTPS)")
    parser.add_argument("--play-from", help="Read the media from a file and sent it.")
    parser.add_argument(
        "--play-without-decoding",
        help=(
            "Read the media without decoding it (experimental). "
            "For now it only works with an MPEGTS container with only H.264 video."
        ),
        action="store_true",
    )
    parser.add_argument(
        "--host", default="0.0.0.0", help="Host for HTTP server (default: 0.0.0.0)"
    )
    parser.add_argument(
        "--port", type=int, default=8080, help="Port for HTTP server (default: 8080)"
    )
    parser.add_argument("--verbose", "-v", action="count")
    parser.add_argument(
        "--audio-codec", help="Force a specific audio codec (e.g. audio/opus)"
    )
    parser.add_argument(
        "--video-codec", help="Force a specific video codec (e.g. video/H264)"
    )
    parser.add_argument(
        "--disable-motor", action="store_true", help="Disable motor control"
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.INFO)
    else:
        logging.basicConfig(level=logging.WARNING)
    cert_file = "server_rsa.crt"
    key_file = "server_rsa.key"
    if args.cert_file:
      cert_file = args.cert_file
      key_file = args.key_file
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.set_ciphers('ECDHE+AESGCM') 
    a, b = os.path.join(ROOT, cert_file),os.path.join(ROOT,key_file)
    #print(a,b)
    ssl_context.load_cert_chain(a,b)
 
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    app.router.add_get("/client.js", javascript)
    app.router.add_post("/offer", offer)
    app.router.add_post("/rotate", rotate)

    queue = thread_queue.Queue()
    if not args.disable_motor:
        disable_motor = args.disable_motor
        motor_thread = threading.Thread(target=cmotor_worker, args=(queue,), daemon=True)
        motor_thread.start()
    else:
        # keep mock version threaded too
        motor_thread = threading.Thread(target=cmotor_worker_mock, args=(queue,), daemon=True)
        motor_thread.start()

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
