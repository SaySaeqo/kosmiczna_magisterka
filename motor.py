import RPi.GPIO as GPIO
from time import sleep, perf_counter
import threading

FULL_ROTATION = 200
NOT_ASSIGNED = 26
PINS = {
    "M1": 17,
    "M2": 27,
    "M3": 22,
    "DIR": 23,
    "STEP": 24,
    "EN": 4,
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
    # These 2 are reversed in the motor driver:
    # GPIO.output(PINS["SLP"], GPIO.HIGH)
    # GPIO.output(PINS["RST"], GPIO.HIGH)

def generate_sine_wave(frequency=1, duration=1):
    """Generate a sine wave for the given frequency and duration."""
    start_time = perf_counter()
    wait_time = 1 / (2 * frequency)
    while perf_counter() - start_time < duration:
        yield GPIO.HIGH
        sleep(wait_time)
        yield GPIO.LOW
        sleep(wait_time)

class MotorRotator:
    def __init__(self, frequency=0.75):
        self.frequency = frequency
        self.active = True
        def rotate(self):
            print("Rotating...")
            while self.active:
                wait_time = 1 / (2 * self.steps_per_second())
                GPIO.output(PINS["STEP"], GPIO.HIGH)
                sleep(wait_time)
                GPIO.output(PINS["STEP"], GPIO.LOW)
                sleep(wait_time)
        self.rotate_job = threading.Thread(target=rotate, args=(self,))
        self.rotate_job.start()

    def steps_per_second(self):
        return self.frequency * FULL_ROTATION
    
    def set_frequency(self, frequency):
        self.frequency = frequency
        print(f"Frequency set to {self.frequency} Hz")

    def __del__(self):
        print("Stopping motor...")
        self.active = False
        self.rotate_job.join()

if __name__ == "__main__":
    setup()
    reset()
    GPIO.output(PINS["EN"], GPIO.HIGH)  # DISABLE motor