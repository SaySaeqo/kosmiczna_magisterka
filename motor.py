import RPi.GPIO as GPIO
from time import sleep, perf_counter
from threading import Thread
import math
import logging
from functools import cache
import pigpio
import re

FULL_ROTATION = 200
ROTATION_PER_STEP = 2*math.pi / FULL_ROTATION
INERTIA_PLATFORM2WHEEL_RATIO = 2.74
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


PI = None
SCRIPT_ID = None
# about 250 commands per loop
# with current clock set to 10MHz it is 16 us per loop
# TODO: can b be negative? YES but then b accuraccy is only 19 bits before comma
# TODO: is b really lower that 2^20? YES (needs to be shown in paper why)
PIGPIO_SCRIPT = f"""
// p0 = a (x.0)
// p1 = b (x.12)
// p2 = duration (x.20)
// p3 = t0 (x.20)
// p4 = pin

W p4 1

LD v0 p3 // v0 -> sum (x.20)
LD v1 p3 // v1 -> tx (x.20)

LD v10 500000 
LD v12 v1
CALL 200 // v10,v11 = tx * 1_000_000 / 2
RL v10 12
LDA v11
RRA 20
AND 4095
ADD v10 // A = total part (x.20 * x.0)
SUB 9
STA v3 // v3 = sleep time - 9 us (aproximated time of above calculations)
SUB 1
STA v4 // v4 = sleep time - 10 us (aproximated time of one loop below)

JMP 110

TAG 100

W p4 1
TAG 110
MICS v3
W p4 0
MICS v4

LD v10 p1
LD v12 v0
CALL 200 // v10,v11 = b*Sx-1
LDA p0
ADD v10 // A,v11 = a+b*Sx-1 (32.32) (no overflow for my data)
RLA 12
STA v5
LDA v11
RRA 20
AND 4095
ADD v5 // increasing accuracy (x.12)
STA v5
LDA 2048000000 // 2^12 * 500_000
DIV v5 // A = tx/2 (microseconds) (max 11 bits) -> sleep time
STA v3 // v3 = sleep time
SUB 10
STA v4 // v4 = sleep time - 10 us (aproximated time of one loop calculations)
ADD 10

RLA 15
DIV 15625 // 500_000 * 2^-5
STA v1 // v1 = tx (seconds) (x.20)

ADD v0
STA v0 // v0 = sum (x.20)

CMP p2
JM 100
JMP 999 // End of script


TAG 200 // 2 register mul (args: v10, v12)

LDA v10
AND 65535
STA v11    // v11 = lower 16-bits
LDA v10
RRA 16
AND 65535
STA v10 // v10 = higher 16-bits

LDA v12
AND 65535
STA v13
LDA v12
RRA 16
AND 65535
STA v12 // as above but for argument v12 (higher part), v13 (lower part)

MLT v10
STA v14 // v14 = v10 * v12 (higher parts)

LDA v13
MLT v11
STA v17 // v17 = v13 * v11 (lower part)

LDA v12
MLT v11
STA v15 // v15 = v12 * v11 (middle part)

LDA v10
MLT v13
STA v16 // v16 = v10 * v13 (middle part)

AND 65535
STA v18
LDA v15
AND 65535
ADD v18
STA v18 // v18 = sum of lower parts of middle parts
RRA 16
STA v19 // v19 = carry
RL v18 16
LD v20 v18
LD v21 v17
CALL 300
LD v11 v20 // v11 = lower part of mul
LDA v16
RRA 16
AND 65535
STA v16
LDA v15
RRA 16
AND 65535
ADD v19
ADD v21
ADD v16
ADD v14 // will never overflow because result of mul is guaranteed to fit into 64 bits
STA v10 // v10 = higher part of mul

RET


TAG 300 // ADD with carry (args: v20, v21)

LDA v20
RRA 31
AND 1
STA v22
LDA v21
RRA 31
AND 1
STA v23
RL v20 1
RR v20 1
RL v21 1
RR v21 1 // extract MSB from args

LDA v20
ADD v21
STA v20 // Add lower part (without MSB)
RRA 31
AND 1
ADD v22
ADD v23 
STA v21 // v21 = Summed MSBs and carry
RLA 31
STA v22
LDA v20
RLA 1
RRA 1
ADD v22
STA v20 // v20 = Result
RR v21 1 // v21 = carry

RET


TAG 999
"""
PIGPIO_SCRIPT = re.sub(r"//.*","", PIGPIO_SCRIPT)
PIGPIO_SCRIPT = re.sub(r"\s+"," ", PIGPIO_SCRIPT)
PIGPIO_SCRIPT = PIGPIO_SCRIPT.strip().encode()

def setup():
    GPIO.setmode(GPIO.BCM)
    GPIO.setup(list(PINS.values()), GPIO.OUT, initial=GPIO.LOW)

def reset():
    GPIO.output(list(PINS.values()), GPIO.LOW)
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
            LOG.debug(f"Step resolution: {resolution}")
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

def pigpio_init():
    global PI, SCRIPT_ID
    PI = pigpio.pi()
    PI.hardware_clock(4, 10_000_000)
    SCRIPT_ID = PI.store_script(PIGPIO_SCRIPT)

    return PI

def pigpio_cleanup():
    global PI, SCRIPT_ID
    if PI is not None:
        if SCRIPT_ID is not None:
            PI.stop_script(SCRIPT_ID)
            PI.delete_script(SCRIPT_ID)
            SCRIPT_ID = None
        PI.stop()
        PI = None

def pigpio_accelerated_signal(acceleration: float, start_frequency: int, duration: float):
    acceleration_constant = acceleration / ROTATION_PER_STEP / get_step_resolution()

    a = start_frequency # x.0
    b = round(acceleration_constant * 4096)  # x.12
    duration = round(duration * 1048576)  # x.20
    t0 = round(1/start_frequency * 1048576)  # x.20

    PI.run_script(SCRIPT_ID, [a, b, duration, t0, PINS["STEP"]])
    # run_script is non-blocking operation.

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
