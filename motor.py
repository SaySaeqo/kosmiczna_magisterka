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
    try:
        setup()
        while True:
            cmd = input("Enter command: ").strip().lower()
            if cmd == "rot":
                print("Rotating...")
                for state in generate_sine_wave(100,2):
                    GPIO.output(PINS["STEP"], state)
            elif cmd in PINS:
                state = int(input(f"Set {cmd} state (0/1): ").strip())
                if state not in (0, 1):
                    print("Invalid state. Use 0 or 1.")
                    continue
                GPIO.output(PINS[cmd], state)
                print(f"{cmd} set to {'HIGH' if state else 'LOW'}")
            elif cmd == "reset":
                print("Resetting all pins...")
                reset()
    except KeyboardInterrupt: ...
    finally:
        print("cleanup")
        GPIO.cleanup()
