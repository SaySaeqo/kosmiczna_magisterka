import RPi.GPIO as GPIO
from time import sleep, perf_counter

HIGH = 1
LOW = 0

HALF_STEP = [
    [LOW, LOW, LOW, HIGH],
    [LOW, LOW, HIGH, HIGH],
    [LOW, LOW, HIGH, LOW],
    [LOW, HIGH, HIGH, LOW],
    [LOW, HIGH, LOW, LOW],
    [HIGH, HIGH, LOW, LOW],
    [HIGH, LOW, LOW, LOW],
    [HIGH, LOW, LOW, HIGH],
]

FULL_STEP = [
    [HIGH, LOW, HIGH, LOW],
    [LOW, HIGH, HIGH, LOW],
    [LOW, HIGH, LOW, HIGH],
    [HIGH, LOW, LOW, HIGH]
]

FULL_ROTATION = int(4075.7728395061727 / 8)

IN1 = 17
IN2 = 27
IN3 = 22
IN4 = 26

# Setup pin layout on PI
GPIO.setmode(GPIO.BCM)

# Establish Pins in software
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

def reset():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)

def step(step, count, direction=1):
    """Rotate count steps. direction = -1 means backwards"""
    for x in range(count):
        for bit in step[::direction]:
            GPIO.output(IN1, bit[0]) 
            GPIO.output(IN2, bit[1]) 
            GPIO.output(IN3, bit[2]) 
            GPIO.output(IN4, bit[3]) 
            sleep(.001)
    reset()

if __name__ == "__main__":
    try:
        reset()
        start = perf_counter()
        step(HALF_STEP, FULL_ROTATION)
        one_rot = perf_counter() - start
        print(f"{one_rot} seconds")

    # Once finished clean everything up
    except KeyboardInterrupt:
        print("cleanup")
        GPIO.cleanup()
