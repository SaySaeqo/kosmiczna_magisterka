import RPi.GPIO as GPIO
from time import sleep, perf_counter

FULL_ROTATION = 200
NOT_ASSIGNED = 26
PINS = {
    "M1": 17,
    "M2": 27,
    "M3": 22,
    "DIR": 23,
    "STEP": 24,
    "EN": 25,
    "SLP": 8,
    "RST": 7
}

def setup():
    GPIO.setmode(GPIO.BCM)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.OUT)

def reset():
    for pin in PINS.values():
        GPIO.output(pin, GPIO.LOW)
    # These 2 are reversed in the motor driver:
    GPIO.output(PINS["SLP"], GPIO.HIGH)
    GPIO.output(PINS["RST"], GPIO.HIGH)
    # Reseting driver itself just to be sure:
    sleep(0.1)
    GPIO.output(PINS["RST"], GPIO.LOW)
    sleep(0.1)
    GPIO.output(PINS["RST"], GPIO.HIGH)

def generate_sine_wave(frequency=1, duration=1):
    """Generate a sine wave for the given frequency and duration."""
    start_time = perf_counter()
    wait_time = 1 / (2 * frequency)
    while perf_counter() - start_time < duration:
        yield GPIO.HIGH
        sleep(wait_time)
        yield GPIO.LOW
        sleep(wait_time)

if __name__ == "__main__":
    setup()
    reset()
    GPIO.output(PINS["EN"], GPIO.HIGH)  # DISABLE motor