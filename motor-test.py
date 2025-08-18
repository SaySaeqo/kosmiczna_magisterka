# stub GPIO module
import types
import sys
gpio_stub = types.ModuleType("GPIO")
sys.modules["GPIO"] = gpio_stub
rpi_gpio_stub = types.ModuleType("RPi.GPIO")
sys.modules["RPi.GPIO"] = rpi_gpio_stub
rpi_stub = types.ModuleType("RPi")
sys.modules["RPi"] = rpi_stub


import motor
import math
import types
import matplotlib.pyplot as plt

def test_negation_of_accelerated_impulse():
    """Test the accelerated impulse durations generator."""
    duration = 1
    acceleration = 2 * motor.INERTIA_PLATFORM2WHEEL_RATIO * (math.pi) / duration / duration
    impulses = motor.accelerated_impulse_durations(acceleration, duration, 1/100)
    n_impulses = motor.accelerated_impulse_durations(-acceleration, duration, impulses[-1])

    def sum_times(times):
        return [sum(times[:i+1]) for i in range(len(times))]

    r_impulses = list(reversed(impulses))
    plt.plot(sum_times(r_impulses), r_impulses, label="acceleration")
    plt.plot(sum_times(n_impulses), n_impulses, label="deceleration")
    plt.xlabel("Cumulative time (s)")
    plt.ylabel("Impulse duration (s)")
    plt.title("Accelerated Impulse Durations")
    plt.legend()
    plt.grid()
    plt.show()

def test_acceleration_of_accelerated_impulse():
    """Test the acceleration of the accelerated impulse durations generator."""
    duration = 1
    acceleration = 2 * motor.INERTIA_PLATFORM2WHEEL_RATIO * (math.pi) / duration / duration
    start_impulse = 1/100
    impulses = motor.accelerated_impulse_durations(acceleration, duration, start_impulse)

    # Speeds of the flywheel
    final_speed = motor.ROTATION_PER_STEP/ (impulses[-1])
    theoretical_final_speed = motor.ROTATION_PER_STEP/start_impulse + acceleration * duration
    print(f"Computed: {final_speed:.2f} rad/s, Theoretical: {theoretical_final_speed:.2f} rad/s")
    print(f"Number of impulses: {len(impulses)}")


def test_frequency_grow_over_time():
    duration = 1
    acceleration = 2 * motor.INERTIA_PLATFORM2WHEEL_RATIO * (math.pi) / duration / duration
    impulses = motor.accelerated_impulse_durations(acceleration, duration, 1/100)

    def sum_times(times):
        return [sum(times[:i+1]) for i in range(len(times))]

    plt.plot(sum_times(impulses), list(map(lambda x: 1/x, impulses)), label="acceleration")
    plt.xlabel("Cumulative time (s)")
    plt.ylabel("Impulse frequency (Hz)")
    plt.title("Accelerated Impulse Frequency")
    plt.legend()
    plt.grid()
    plt.show()

def test_rotate_platform3_calculations():
    """Test the rotate_platform3 function."""
    duration = 1
    radians = math.pi
    motor.GPIO.HIGH = 1
    motor.GPIO.LOW = 0

    # Preparations
    MPINS_SETTINGS = [
        (motor.GPIO.HIGH, motor.GPIO.HIGH, motor.GPIO.HIGH), # 1/16
        (motor.GPIO.HIGH, motor.GPIO.HIGH, motor.GPIO.LOW),  # 1/8
        (motor.GPIO.LOW, motor.GPIO.HIGH, motor.GPIO.LOW),   # 1/4
        (motor.GPIO.HIGH, motor.GPIO.LOW, motor.GPIO.LOW)    # 1/2
    ]

    dur = duration / 2
    acceleration = motor.INERTIA_PLATFORM2WHEEL_RATIO * radians / dur / dur
    # formula is: t= (wk - wp)/acc, for current L (ROTATION_PER_STEP):
    part_duration = math.pi / acceleration
    part_wait_times = []
    first_impulse_time = motor.MAX_IMPULSE_DURATION

    for _ in range(len(MPINS_SETTINGS)):
        part_wait_times += [[impulse/2 for impulse in motor.accelerated_impulse_durations(acceleration, part_duration, first_impulse_time)]]
        first_impulse_time = part_wait_times[-1][-1]  # Next part
    
    dur -= part_duration * len(MPINS_SETTINGS) 
    wait_times = [impulse/2 for impulse in motor.accelerated_impulse_durations(acceleration, dur, part_wait_times[-1][-1]*2)]
    negated_wait_times = [impulse/2 for impulse in motor.accelerated_impulse_durations(-acceleration, dur, wait_times[-1]*2)]

    negated_part_wait_times = []
    first_impulse_time = negated_wait_times[-1]*2*2
    for _ in range(len(MPINS_SETTINGS)):
        negated_part_wait_times += [[impulse/2 for impulse in motor.accelerated_impulse_durations(-acceleration, part_duration, first_impulse_time)]]
        first_impulse_time = negated_part_wait_times[-1][-1] *2*2  # Next part

    part_wait_times_zip = zip(MPINS_SETTINGS, part_wait_times)
    negated_part_wait_times_zip = zip(reversed(MPINS_SETTINGS), negated_part_wait_times)

test_rotate_platform3_calculations()
