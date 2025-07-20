import RPi.GPIO as GPIO
from time import sleep, perf_counter

FULL_ROTATION = 200

PINS = {
    "M1": 14,
    "M2": 15,
    "M3": 18,
    "DIR": 3,
    "STEP": 2,
    "EN": 17,
    "SLP": 27,
    "RST": 4
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
    while perf_counter() - start_time < duration:
        yield GPIO.HIGH
        sleep(1 / (2 * frequency))
        yield GPIO.LOW
        sleep(1 / (2 * frequency))

def step(count, direction=GPIO.LOW):
    """Rotate count steps. direction = 1 means backwards"""
    GPIO.output(PINS["DIR"], direction)
    for state, _ in zip(generate_sine_wave(200), range(200)):
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
