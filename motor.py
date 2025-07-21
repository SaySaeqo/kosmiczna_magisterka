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

def press(pin, seconds=0.1):
    """Press a pin for a given number of seconds."""
    GPIO.output(pin, GPIO.HIGH)
    sleep(seconds)
    GPIO.output(pin, GPIO.LOW)

def reset():
    for pin in PINS.values():
        GPIO.output(pin, GPIO.LOW)
    press(PINS["RST"])

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