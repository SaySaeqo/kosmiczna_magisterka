#!/usr/bin/env python

from __future__ import division
import cv2
import socket
import struct
import math
import sys


class FrameSegment(object):
    """ 
    Object to break down image frame segment
    if the size of image exceed maximum datagram size 
    """
    MAX_DGRAM = 2**16
    MAX_IMAGE_DGRAM = MAX_DGRAM - 64 # extract 64 bytes in case UDP frame overflown
    def __init__(self, sock, port, addr="127.0.0.1"):
        self.s = sock
        self.port = port
        self.addr = addr

    def udp_frame(self, img):
        """ 
        Compress image and Break down
        into data segments 
        """
        compress_img = cv2.imencode('.jpg', img)[1]
        dat = compress_img.tobytes()
        size = len(dat)
        count = math.ceil(size/(self.MAX_IMAGE_DGRAM))
        array_pos_start = 0
        while count:
            array_pos_end = min(size, array_pos_start + self.MAX_IMAGE_DGRAM)
            self.s.sendto(struct.pack("B", count) +
                dat[array_pos_start:array_pos_end], 
                (self.addr, self.port)
                )
            array_pos_start = array_pos_end
            count -= 1


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Use: udp_camera_sender.py <addr> <port>")
        sys.exit()

    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    addr, port = sys.argv[1], int(sys.argv[2])
    fs = FrameSegment(s, port, addr)

    cap = cv2.VideoCapture(0, cv2.CAP_V4L2)
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 3840)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    print (f"Frames are being sent to {fs.addr}:{fs.port}")
    try:
        while (cap.isOpened()):
            _, frame = cap.read()
            fs.udp_frame(frame)
    except KeyboardInterrupt: ...
    finally:
        print("Closing...")
        cap.release()
        cv2.destroyAllWindows()
        s.close()

