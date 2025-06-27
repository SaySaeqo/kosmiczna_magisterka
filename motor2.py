import RPi.GPIO as GPIO
from time import sleep, perf_counter

FULL_ROTATION = 200

M1 = 17
M2 = 27
M3 = 22
DIR = 6
STEP = 5
EN = 26
SLP = 21
RST = 20

# Setup pin layout on PI
GPIO.setmode(GPIO.BCM)

# Establish Pins in software
GPIO.setup(M1, GPIO.OUT)
GPIO.setup(M2, GPIO.OUT)
GPIO.setup(M3, GPIO.OUT)
GPIO.setup(DIR, GPIO.OUT)
GPIO.setup(STEP, GPIO.OUT)
GPIO.setup(EN, GPIO.OUT)
GPIO.setup(SLP, GPIO.OUT)
GPIO.setup(RST, GPIO.OUT)

def reset():
    GPIO.output(M1, GPIO.LOW)
    GPIO.output(M2, GPIO.LOW)
    GPIO.output(M3, GPIO.LOW)
    GPIO.output(DIR, GPIO.LOW)
    GPIO.output(STEP, GPIO.LOW)
    GPIO.output(EN, GPIO.LOW)
    GPIO.output(SLP, GPIO.LOW)
    GPIO.output(RST, GPIO.LOW)

def step(count, direction=GPIO.LOW):
    """Rotate count steps. direction = -1 means backwards"""
    #for x in range(count):
    while True:
        #GPIO.output(DIR, direction)
        GPIO.output(STEP, GPIO.HIGH) 
        sleep(.01)
        #GPIO.output(DIR, direction)
        GPIO.output(STEP, GPIO.LOW) 
        sleep(.01)

def press(pin, seconds=5):
    GPIO.output(pin, GPIO.HIGH)
    sleep(seconds)
    GPIO.output(pin, GPIO.LOW)
    sleep(seconds)

if __name__ == "__main__":
    try:
        reset()
        #start = perf_counter()
        step(FULL_ROTATION)
        #one_rot = perf_counter() - start
        #print(f"{one_rot} seconds")

    # Once finished clean everything up
    except KeyboardInterrupt:
        print("cleanup")
        GPIO.cleanup()
