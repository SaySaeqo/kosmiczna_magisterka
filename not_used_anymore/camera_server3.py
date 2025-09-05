import socket
import requests
import struct
import time

# Settings
STREAM_URL = "http://localhost:8080/?action=stream"
DEST_IP = "192.168.0.126"
DEST_PORT = 5000
CHUNK_SIZE = 1024
FRAME_ID = 0

sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

with requests.get(STREAM_URL, stream=True) as r:
    buffer = b""
    for chunk in r.iter_content(1024):
        buffer += chunk
        start = buffer.find(b'\xff\xd8')
        end = buffer.find(b'\xff\xd9')
        if start != -1 and end != -1 and end > start:
            jpeg = buffer[start:end+2]
            buffer = buffer[end+2:]

            FRAME_ID = (FRAME_ID + 1) % 256
            total_parts = (len(jpeg) + CHUNK_SIZE - 1) // CHUNK_SIZE

            for i in range(total_parts):
                part = jpeg[i * CHUNK_SIZE:(i + 1) * CHUNK_SIZE]
                header = struct.pack("!BHH", FRAME_ID, i, total_parts)
                sock.sendto(header + part, (DEST_IP, DEST_PORT))

            time.sleep(0.001)

