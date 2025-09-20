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

from aiohttp import web
from aiortc import (
    MediaStreamTrack,
    RTCPeerConnection,
    RTCRtpSender,
    RTCSessionDescription,
)
from aiortc.contrib.media import MediaPlayer, MediaRelay
import kosmiczna_magisterka.fast_motor as cmotor

ROOT = os.path.dirname(__file__)
cert_path = os.path.join("/etc/ssl/mycerts", "server_rsa.crt")
key_path = os.path.join("/etc/ssl/mycerts", "server_rsa.key")

pcs = set()
relay = None
webcam = None
disable_motor = True

def LOG2FILE(json):
    with open("webcam.log", "a") as f:
        f.write(json + "\n")

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
        #options = {
            #"framerate": "10",
            #"video_size": "1280x480",
            #"input_format": "yuv420p",
            #"thread_queue_size": "1024",
            #"c:v": "h264_v4l2m2m"
        #}
        options = {
            "framerate": "30",
            "video_size": "2560x720",
            "input_format": "mjpeg",
            "thread_queue_size": "1024",
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
    content = open(os.path.join(ROOT, "client.html"), "r").read()
    return web.Response(content_type="text/html", text=content)

CLAMP_FLAG = True

def _clamp(v, lo=-1.0, hi=1.0):
    if not CLAMP_FLAG:
        return v
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

last_orientation = None
last_rot_time = time.clock_gettime(time.CLOCK_MONOTONIC)
last_speed = 0.0
MESSAGE_INTERVAL = 0.1
MIN_FREQ = 300
MIN_SPEED = MIN_FREQ*motor.ROTATION_PER_STEP / 16 
MAX_ACCELERATION = 50
MAX_FREQ = 15000
MAX_SPEED = MAX_FREQ*motor.ROTATION_PER_STEP / 16
last_number = -1
accumulated_angle = 0.0
MIN_ANGLE = MIN_SPEED * MESSAGE_INTERVAL

def get_cmotor_parameters(current_orientation, time_diff) -> list[tuple[float, float, float]]:
    global last_orientation, last_speed, accumulated_angle
    if last_orientation is None:
        last_orientation = current_orientation
        return []
    angle = relative_y_axis_rotation(last_orientation, current_orientation)
    accumulated_angle += angle
    last_orientation = current_orientation
    # print(f"{current_orientation=} {orientation=} {angle=}")
    current_speed = accumulated_angle / time_diff
    current_speed = _clamp(current_speed, -MAX_SPEED, MAX_SPEED)
    acceleration = (current_speed - last_speed) / time_diff
    acceleration = _clamp(acceleration, -MAX_ACCELERATION, MAX_ACCELERATION)
    start_frequency = last_speed / motor.ROTATION_PER_STEP * 16
    accumulated_angle -= last_speed*time_diff + acceleration * time_diff * time_diff / 2
    if accumulated_angle < MIN_ANGLE and accumulated_angle > -MIN_ANGLE:
        accumulated_angle = 0.0

    if last_speed == 0.0 and abs(current_speed) < MIN_SPEED:
        # Both speeds are very low, no need to move
        last_speed = 0.0
        return []
    elif last_speed == 0.0:
        start_frequency = MIN_FREQ * (1 if current_speed >= 0 else -1)
        time_diff = _clamp((current_speed - math.copysign(MIN_SPEED, current_speed)) / acceleration, -MESSAGE_INTERVAL, MESSAGE_INTERVAL)
    elif abs(current_speed) < MIN_SPEED:
        current_speed = 0.0
        time_diff = _clamp((math.copysign(MIN_SPEED, last_speed) - last_speed) / acceleration, -MESSAGE_INTERVAL, MESSAGE_INTERVAL)
    elif last_speed*current_speed < 0:
        time_to_decelerate = (math.copysign(MIN_SPEED, last_speed) - last_speed) / acceleration
        time_to_accelerate = (current_speed - math.copysign(MIN_SPEED, current_speed)) / acceleration
        last_speed = current_speed

        if time_to_decelerate > time_diff:
            return [(acceleration, start_frequency, time_diff)]
        elif time_to_decelerate + time_to_accelerate > time_diff:
            return [(acceleration, start_frequency, time_to_decelerate),
                    (acceleration, math.copysign(MIN_FREQ, acceleration), time_diff - time_to_decelerate)]
        else:
            return [(acceleration, start_frequency, time_to_decelerate),
                    (acceleration, math.copysign(MIN_FREQ, acceleration), time_to_accelerate)]

    last_speed = current_speed

    return [(acceleration, start_frequency, time_diff)]

def handle_rotate(json_params):
    current_number = json_params["number"]
    global last_number
    if current_number <= last_number:
        print(f"Out of order packet: {current_number=} {last_number=}")
        return
    last_number = current_number


    current_orientation = json_params["orientation"]
    #now = time.clock_gettime(time.CLOCK_MONOTONIC)
    #json_params["monotonic"] = now
    #json_params["realtime"] = time.time()
    #LOG2FILE(json.dumps(json_params))

    x,y,z,w = current_orientation["x"], current_orientation["y"], current_orientation["z"], current_orientation["w"]
    if not disable_motor:
        cmotor.rotation_client(x,y,z,w)

async def rotate(request: web.Request) -> web.Response:
    # Get parameters
    params = await request.json()
    handle_rotate(params)
    return web.Response(status=200)


async def print_queue_size(request: web.Request):
    cmotor.print_globals()
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

    @pc.on("datachannel")
    def on_datachannel(channel) -> None:
        print(f"Data channel created: {channel.label}")
        
        @channel.on("message")
        def on_message(message) -> None:
            handle_rotate(json.loads(message))

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

    if args.cert_file:
        cert_file = args.cert_file
        key_file = args.key_file
        cert_path, key_path = os.path.join(ROOT, cert_file),os.path.join(ROOT,key_file)
    ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    ssl_context.set_ciphers('ECDHE+AESGCM') 
    print(cert_path, key_path)
    ssl_context.load_cert_chain(cert_path,key_path)
 
    app = web.Application()
    app.on_shutdown.append(on_shutdown)
    app.router.add_get("/", index)
    #app.router.add_get("/client.js", javascript)
    app.router.add_post("/print_queue_size", print_queue_size)
    app.router.add_post("/offer", offer)
    app.router.add_post("/rotate", rotate)

    if not args.disable_motor:
        disable_motor = args.disable_motor
        cmotor.setup()
        cmotor.rotation_server()

    web.run_app(app, host=args.host, port=args.port, ssl_context=ssl_context)
