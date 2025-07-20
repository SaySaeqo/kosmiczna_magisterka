import RPi.GPIO as GPIO
from time import sleep, perf_counter

FULL_ROTATION = 200
NOT_ASSIGNED = 26
PINS = {
    "M1": NOT_ASSIGNED,
    "M2": NOT_ASSIGNED,
    "M3": NOT_ASSIGNED,
    "DIR": 27,
    "STEP": 17,
    "EN": NOT_ASSIGNED,
    "SLP": NOT_ASSIGNED,
    "RST": NOT_ASSIGNED
}

def setup():
    GPIO.setmode(GPIO.BCM)
    for pin in PINS.values():
        GPIO.setup(pin, GPIO.OUT)

def reset():
    for pin in PINS.values():
        GPIO.output(pin, GPIO.LOW)


def generate_sine_wave(frequency=1, duration=1):
    """Generate a sine wave for the given frequency and duration."""
    start_time = perf_counter()
    wait_time = 1 / (2 * frequency)
    while perf_counter() - start_time < duration:
        yield GPIO.HIGH
        sleep(wait_time)
        yield GPIO.LOW
        sleep(wait_time)

def step(count, direction=GPIO.LOW):
    """Rotate count steps. direction = 1 means backwards"""
    GPIO.output(PINS["DIR"], direction)
    for state, _ in zip(generate_sine_wave(100,2), range(200)):
        GPIO.output(PINS["STEP"], state)

if __name__ == "__main__":
    try:
        setup()
        reset()
        step(FULL_ROTATION)
        reset()
    except KeyboardInterrupt: ...
    finally:
        print("cleanup")
        GPIO.cleanup()
