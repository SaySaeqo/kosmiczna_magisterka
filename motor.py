import RPi.GPIO as GPIO
from time import sleep
from threading import Thread
import math
import logging
from functools import cache

FULL_ROTATION = 200
ROTATION_PER_STEP = 2*math.pi / FULL_ROTATION
INERTIA_PLATFORM2WHEEL_RATIO = 3.72

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
    wait_time = 1 / (2 * frequency)
    how_many_steps = int(duration / (2*wait_time))
    for _ in range(how_many_steps):
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
        self.rotate_job = Thread(target=rotate, args=(self,))
        self.rotate_job.start()

    def set_frequency(self, frequency):
        self.frequency = frequency
        print(f"Frequency set to {self.frequency} Hz")

    def stop(self):
        print("Stopping motor...")
        self.active = False
        self.rotate_job.join()

@cache
def accelerated_impulse_durations(acceleration=2*math.pi, duration=1, t0=1/100):
    """Generate an accelerated sine wave for the given frequency and duration."""
    acceleration_constant = acceleration / ROTATION_PER_STEP
    impulse_durations=[t0]
    duration -= impulse_durations[0]
    # Next impuls times
    while duration > 0:
        impulse_durations += [impulse_durations[-1] / (1 + acceleration_constant * impulse_durations[-1]**2)]
        duration -= impulse_durations[-1]
    else:
        LOG.debug(f"Last impuls time: {impulse_durations[-1]:.6f} s or {1/impulse_durations[-1]:.2f} Hz")
    return impulse_durations

def rotate_platform(radians, duration=1, start_frequency=100):
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, duration, 1/start_frequency)]
    for wt in wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    return 1/wt/2  # Return the final frequency

def rotate_platform_deceleration(radians, duration=1, start_frequency=100):
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(-acceleration, duration, 1/start_frequency)]
    for wt in wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    return 1/wt/2  # Return the final frequency

def rotate_platform2(radians, duration=1, start_frequency=100):
    """Rotate the platform by a specified angle in radians."""
    dur= duration/2
    acceleration = INERTIA_PLATFORM2WHEEL_RATIO*radians/dur
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, dur, 1/start_frequency)]
    negated_wait_times = [impulse/2 for impulse in accelerated_impulse_durations(-acceleration, dur, wait_times[-1]*2)]
    for wt in wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    
    # Deaccelerate
    for wt in negated_wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)


if __name__ == "__main__":
    setup()
    reset()
    GPIO.output(PINS["EN"], GPIO.HIGH)  # DISABLE motor