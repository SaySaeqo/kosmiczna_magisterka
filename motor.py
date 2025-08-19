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

PINS = {
    "M1": 17,
    "M2": 27,
    "M3": 22,
    "DIR": 23,
    "STEP": 24,
    # These below are negated on the driver
    "EN": 4,
    #"SLP": NOT_ASSIGNED,
    #"RST": NOT_ASSIGNED,
}
MPINS = (PINS["M1"], PINS["M2"], PINS["M3"])
MPINS_SETTINGS = {
    1/16: (GPIO.HIGH, GPIO.HIGH, GPIO.HIGH),
    1/8: (GPIO.HIGH, GPIO.HIGH, GPIO.LOW),
    1/4: (GPIO.LOW, GPIO.HIGH, GPIO.LOW),
    1/2: (GPIO.HIGH, GPIO.LOW, GPIO.LOW),
    1: (GPIO.LOW, GPIO.LOW, GPIO.LOW)
}
LOG = logging.getLogger(__name__)

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(PINS.values(), GPIO.OUT, initial=GPIO.LOW)

def reset():
    GPIO.output(PINS.values(), GPIO.LOW)
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

def STEP_signal(wait_times: list[float]):
    """Trigger steps based on the provided wait times."""
    for wt in wait_times:
        GPIO.output(PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(PINS["STEP"], GPIO.LOW)
        sleep(wt)

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

def get_step_resolution():
    """Get the current step resolution."""
    for resolution, settings in MPINS_SETTINGS.items():
        if all(x == y for x, y in zip((GPIO.input(pin) for pin in MPINS), settings)):
            return resolution
    raise Exception("Current step resolution not found in MPINS_SETTINGS.")


def accelerated_impulse_durations_with_cond(acceleration, t0=1/100, condition = lambda durations: sum(durations) < 1):
    acceleration_constant = acceleration / ROTATION_PER_STEP / get_step_resolution()
    impulse_durations = [t0]
    while condition(impulse_durations):
        impulse_durations += [impulse_durations[-1] / (1 + acceleration_constant * impulse_durations[-1]**2)]
    else:
        LOG.debug(f"Last impuls time: {impulse_durations[-1]:.6f} s or {1/impulse_durations[-1]:.2f} Hz")
    return impulse_durations

def accelerated_impulse_durations(acceleration, duration=1, t0=1/100):
    """Generate an accelerated sine wave for the given frequency and duration."""
    return accelerated_impulse_durations_with_cond(acceleration, t0, lambda durations: sum(durations) < duration)


def rotate_platform(radians, duration=1, start_frequency=100):
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, duration, 1/start_frequency)]
    STEP_signal(wait_times)
    return 1/wait_times[-1]/2  # Return the final frequency

def accelerate(start_frequency=100, final_frequency=200, duration=1):
    """Accelerate the motor to a given frequency over a specified duration."""
    acceleration = ROTATION_PER_STEP * (final_frequency - start_frequency) / duration / duration
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, duration, 1/start_frequency)]
    STEP_signal(wait_times)
    return 1/wait_times[-1]/2  # Return the final frequency

def rotate_platform_deceleration(radians, duration=1, start_frequency=50):
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(-acceleration, duration, 1/start_frequency)]
    STEP_signal(wait_times)
    return 1/wait_times[-1]/2  # Return the final frequency

def rotate_platform2(radians, duration=1, start_frequency=50):
    """Rotate the platform by a specified angle in radians."""
    dur= duration/2
    acceleration = INERTIA_PLATFORM2WHEEL_RATIO*radians/dur/dur
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, dur, 1/start_frequency)]
    negated_wait_times = [impulse/2 for impulse in accelerated_impulse_durations(-acceleration, dur, wait_times[-1]*2)]

    STEP_signal(wait_times)           # Accelerate
    STEP_signal(negated_wait_times)   # Decelerate

def rotate_platform3(radians, duration=1):
    """
    Rotate the platform by a specified angle (radians) with acceleration and deceleration.
    Uses M1-M3 pins to halve the step count for smoother transitions at the start and end.
    """
    # Preparations

    dur = duration / 2
    acceleration = INERTIA_PLATFORM2WHEEL_RATIO * radians / dur / dur

    # formula is: t= (wk - wp)/acc, for current L (ROTATION_PER_STEP):
    # part_duration = math.pi / acceleration

    part_wait_times = []
    first_impulse_time = MAX_IMPULSE_DURATION
    for _ in range(len(MPINS_SETTINGS)-1):
        part_wait_times += [[impulse/2 for impulse in accelerated_impulse_durations_with_cond(acceleration, first_impulse_time, lambda durations: durations[-1] > 1/200)]]
        first_impulse_time = part_wait_times[-1][-1]*2*2  # Next part
    
    dur -= sum(sum(pwts) for pwts in part_wait_times)*2  # Subtract the time used by M1-M3 halving
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, dur, first_impulse_time)]
    negated_wait_times = [impulse/2 for impulse in accelerated_impulse_durations_with_cond(-acceleration, wait_times[-1]*2, lambda durations: durations[-1] < 1/100)]

    negated_part_wait_times = []
    first_impulse_time = negated_wait_times[-1]
    for _ in range(len(MPINS_SETTINGS)-1):
        negated_part_wait_times += [[impulse/2 for impulse in accelerated_impulse_durations_with_cond(-acceleration, first_impulse_time, lambda durations: durations[-1] < 1/100)]]
        first_impulse_time = negated_part_wait_times[-1][-1]  # Next part

    part_wait_times_zip = zip(MPINS_SETTINGS[:-1], part_wait_times)
    negated_part_wait_times_zip = zip(reversed(MPINS_SETTINGS[:-1]), negated_part_wait_times)

    # Halve steps at start using M1-M3
    for settings, pwts in part_wait_times_zip:
        GPIO.output(MPINS, settings)
        STEP_signal(pwts)

    # Full steps in middle
    GPIO.output(MPINS, GPIO.LOW)
    STEP_signal(wait_times)
    STEP_signal(negated_wait_times)

    # Halve steps at end using M1-M3
    for settings, pwts in negated_part_wait_times_zip:
        GPIO.output(MPINS, settings)
        STEP_signal(pwts)

    # Reset M1-M3 pins
    GPIO.output(MPINS, GPIO.LOW)

if __name__ == "__main__":
    setup()
    GPIO.output(PINS["EN"], GPIO.HIGH)  # DISABLE motor