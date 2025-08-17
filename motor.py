import RPi.GPIO as GPIO
from time import sleep
from threading import Thread
import math
import logging
from functools import cache

FULL_ROTATION = 200
ROTATION_PER_STEP = 2*math.pi / FULL_ROTATION
INERTIA_PLATFORM2WHEEL_RATIO = 4.92
MIN_FREQUENCY = 100
MAX_IMPULSE_DURATION = 1/MIN_FREQUENCY

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
    def __init__(self, frequency=100):
        self.frequency = frequency
        self.active = True
        self.wait_time = 1 / (2 * self.frequency)
        def rotate(self):
            print("Rotating...")
            while self.active:
                GPIO.output(PINS["STEP"], GPIO.HIGH)
                sleep(self.wait_time)
                GPIO.output(PINS["STEP"], GPIO.LOW)
                sleep(self.wait_time)
        self.rotate_job = Thread(target=rotate, args=(self,))
        self.rotate_job.start()

    def set_frequency(self, frequency):
        if frequency <= 0:
            self.stop()
            return
        self.frequency = frequency
        self.wait_time = 1 / (2 * self.frequency)
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

def accelerate(start_frequency=100, final_frequency=200, duration=1):
    """Accelerate the motor to a given frequency over a specified duration."""
    acceleration = ROTATION_PER_STEP * (final_frequency - start_frequency) / duration / duration
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, duration, 1/start_frequency)]
    for wt in wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    return 1/wt/2  # Return the final frequency

def rotate_platform_deceleration(radians, duration=1, start_frequency=50):
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(-acceleration, duration, 1/start_frequency)]
    for wt in wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    return 1/wt/2  # Return the final frequency

def rotate_platform2(radians, duration=1, start_frequency=50):
    """Rotate the platform by a specified angle in radians."""
    dur= duration/2
    acceleration = INERTIA_PLATFORM2WHEEL_RATIO*radians/dur/dur
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

def rotate_platform3(radians, duration=1):
    """
    Rotate the platform by a specified angle (radians) with acceleration and deceleration.
    Uses M1-M3 pins to halve the step count for smoother transitions at the start and end.
    """
    dur = duration / 2
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * radians / dur / dur
    impulses = accelerated_impulse_durations(acceleration, dur, MAX_IMPULSE_DURATION)
    up_to_200hz_impulses = [wt for wt in impulses if wt > 1/200]
    up_to_200hz_wait_times = [impulse/2 for impulse in up_to_200hz_impulses]
    up_to_200hz_total_time = sum(up_to_200hz_impulses)
    dur -= up_to_200hz_total_time * 4
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, dur, MAX_IMPULSE_DURATION)]
    negated_wait_times = [impulse/2 for impulse in accelerated_impulse_durations(-acceleration, dur, wait_times[-1]*2)]
    down_to_100hz_wait_times = [wt for wt in negated_wait_times if wt > 1/400]
    MPINS_SETTINGS = [
        (GPIO.HIGH, GPIO.HIGH, GPIO.HIGH),
        (GPIO.HIGH, GPIO.HIGH, GPIO.LOW),
        (GPIO.LOW, GPIO.HIGH, GPIO.LOW),
        (GPIO.HIGH, GPIO.LOW, GPIO.LOW)
    ]
    # Halve steps at start using M1-M3
    for m1, m2, m3 in MPINS_SETTINGS:
        GPIO.output(PINS["M1"], m1)
        GPIO.output(PINS["M2"], m2)
        GPIO.output(PINS["M3"], m3)
        for wt in up_to_200hz_wait_times:
            GPIO.output(PINS["STEP"], GPIO.HIGH)
            sleep(wt)
            GPIO.output(PINS["STEP"], GPIO.LOW)
            sleep(wt)
    # Full steps in middle
    GPIO.output(PINS["M1"], GPIO.LOW)
    GPIO.output(PINS["M2"], GPIO.LOW)
    GPIO.output(PINS["M3"], GPIO.LOW)
    for wt in wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    for wt in negated_wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)
    # Halve steps at end using M1-M3
    for m1, m2, m3 in reversed(MPINS_SETTINGS):
        GPIO.output(PINS["M1"], m1)
        GPIO.output(PINS["M2"], m2)
        GPIO.output(PINS["M3"], m3)
        for wt in down_to_100hz_wait_times:
            GPIO.output(PINS["STEP"], GPIO.HIGH)
            sleep(wt)
            GPIO.output(PINS["STEP"], GPIO.LOW)
            sleep(wt)

if __name__ == "__main__":
    setup()
    reset()
    GPIO.output(PINS["EN"], GPIO.HIGH)  # DISABLE motor