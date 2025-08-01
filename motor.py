import RPi.GPIO as GPIO
from time import sleep, perf_counter
import threading
import math
import logging

FULL_ROTATION = 200
INERTIA_PLATFORM2WHEEL_RATIO = 7.61

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
LOG = logging.getLogger(__name__)

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
                wait_time = 1 / (2 * self.frequency)
                GPIO.output(PINS["STEP"], GPIO.HIGH)
                sleep(wait_time)
                GPIO.output(PINS["STEP"], GPIO.LOW)
                sleep(wait_time)
        self.rotate_job = threading.Thread(target=rotate, args=(self,))
        self.rotate_job.start()

    def set_frequency(self, frequency):
        self.frequency = frequency
        print(f"Frequency set to {self.frequency} Hz")

    def stop(self):
        print("Stopping motor...")
        self.active = False
        self.rotate_job.join()

def accelerated_wait_times(acceleration=2*math.pi, duration=1, start_frequency=100):
    """Generate an accelerated sine wave for the given frequency and duration."""
    rotation_per_step = 2*math.pi / FULL_ROTATION
    acceleration_constant = acceleration / rotation_per_step
    def k(step_time):
        return acceleration_constant * step_time * step_time + 1
    last = 1 / (2 * start_frequency)
    wait_times=[last]
    duration -= last * 2
    while duration > 0:
        last = last / k(last*2)
        wait_times.append(last)
        duration -= last * 2
        LOG.debug(f"Impuls time: {last*2:.6f} seconds which is {1/last/2:.2f} Hz")
    return wait_times

def rotate_platform(radians, duration=1, start_frequency=100):
    """Rotate the platform by a specified angle in radians."""
    acceleration = INERTIA_PLATFORM2WHEEL_RATIO*(2*radians)/(duration*duration)
    for wt in accelerated_wait_times(acceleration, duration, start_frequency):
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    else:
        rotation_per_step = 2*math.pi / FULL_ROTATION
        final = acceleration*duration/rotation_per_step + start_frequency
        LOG.debug(f"Final frequency should be: {final:.2f} Hz but is: {1/(2*wt):.2f} Hz")
        return wt

if __name__ == "__main__":
    setup()
    reset()
    GPIO.output(PINS["EN"], GPIO.HIGH)  # DISABLE motor