#!/usr/bin/env python

from __future__ import division
import cv2
import numpy as np
import socket
import struct
import sys

MAX_DGRAM = 2**16

def dump_buffer(s):
    """ Emptying buffer frame """
    while True:
        seg, addr = s.recvfrom(MAX_DGRAM)
        print(seg[0])
        if struct.unpack("B", seg[0:1])[0] == 1:
            print("finish emptying buffer")
            break

if __name__ == "__main__":
    """ Getting image udp frame &
    concate before decode and output image """
    if len(sys.argv) != 2:
        print("Use udp_camera_receiver <listening_port>")
        sys.exit()
    # Set up socket
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = int(sys.argv[1])
    s.bind(('0.0.0.0', port))
    dat = b''

    print(f"Listening on port {port}")
    try:
        dump_buffer(s)
        while True:
            seg, addr = s.recvfrom(MAX_DGRAM)
            if struct.unpack("B", seg[0:1])[0] > 1:
                dat += seg[1:]
            else:
                dat += seg[1:]
                img = cv2.imdecode(np.frombuffer(dat, dtype=np.uint8), 1)
                cv2.imshow('frame', img)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    break
                dat = b''
    except KeyboardInterrupt: ...
    finally:
        print("Closing...")
        cv2.destroyAllWindows()
        s.close()

