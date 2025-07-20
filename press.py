import RPi.GPIO as GPIO
from time import sleep, perf_counter
import sys

if __name__ == "__main__":
    try:
        if len(sys.argv) < 2:
            print("Use: python press.py <pin> [<seconds>]\n"
                  "Use pins numbering in BCM mode")
            sys.exit()
        pin = int(sys.argv[1])
        seconds = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0
            
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(pin, GPIO.OUT)
        GPIO.output(pin, GPIO.HIGH)
        sleep(seconds)
        GPIO.output(pin, GPIO.LOW)

    # Once finished clean everything up
    except KeyboardInterrupt:
        print("cleanup")
        GPIO.cleanup()
