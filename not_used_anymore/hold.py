#!/bin/python

import RPi.GPIO as GPIO
from time import sleep, perf_counter
import sys

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Use: hold.py <pin> \n"
            "Use pins numbering in BCM mode")
        sys.exit()
    pin = int(sys.argv[1])
    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.HIGH)
        while True: ...
    except KeyboardInterrupt: ...
    finally:
        GPIO.output(pin, GPIO.LOW)
        GPIO.cleanup()
