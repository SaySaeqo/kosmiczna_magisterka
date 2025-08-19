# stub GPIO module
import types
import sys
gpio_stub = types.ModuleType("GPIO")
sys.modules["GPIO"] = gpio_stub
rpi_gpio_stub = types.ModuleType("RPi.GPIO")
sys.modules["RPi.GPIO"] = rpi_gpio_stub
rpi_stub = types.ModuleType("RPi")
sys.modules["RPi"] = rpi_stub
rpi_gpio_stub.HIGH = 1
rpi_gpio_stub.LOW = 0


from motor import *
import math
import types
import matplotlib.pyplot as plt

def test_negation_of_accelerated_impulse():
    """Test the accelerated impulse durations generator."""
    duration = 1
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * (math.pi) / duration / duration
    impulses = accelerated_impulse_durations(acceleration, duration, 1/100)
    n_impulses = accelerated_impulse_durations(-acceleration, duration, impulses[-1])

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
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * (math.pi) / duration / duration
    start_impulse = 1/100
    impulses = accelerated_impulse_durations(acceleration, duration, start_impulse)

    # Speeds of the flywheel
    final_speed = ROTATION_PER_STEP/ (impulses[-1])
    theoretical_final_speed = ROTATION_PER_STEP/start_impulse + acceleration * duration
    print(f"Computed: {final_speed:.2f} rad/s, Theoretical: {theoretical_final_speed:.2f} rad/s")
    print(f"Number of impulses: {len(impulses)}")


def test_frequency_grow_over_time():
    duration = 1
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * (math.pi) / duration / duration
    impulses = accelerated_impulse_durations(acceleration, duration, 1/100)

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

    # Preparations
    MPINS_SETTINGS = [
        (GPIO.HIGH, GPIO.HIGH, GPIO.HIGH), # 1/16
        (GPIO.HIGH, GPIO.HIGH, GPIO.LOW),  # 1/8
        (GPIO.LOW, GPIO.HIGH, GPIO.LOW),   # 1/4
        (GPIO.HIGH, GPIO.LOW, GPIO.LOW)    # 1/2
    ]

    dur = duration / 2
    acceleration = INERTIA_PLATFORM2WHEEL_RATIO * radians / dur / dur

    # formula is: t= (wk - wp)/acc, for current L (ROTATION_PER_STEP):
    part_duration = math.pi / acceleration

    part_wait_times = []
    first_impulse_time = MAX_IMPULSE_DURATION
    for _ in range(len(MPINS_SETTINGS)):
        part_wait_times += [[impulse/2 for impulse in accelerated_impulse_durations_with_cond(acceleration, first_impulse_time, lambda durations: durations[-1] > 1/200)]]
        first_impulse_time = part_wait_times[-1][-1]*2*2  # Next part
    
    dur -= sum(sum(pwts) for pwts in part_wait_times)*2  # Subtract the time used by M1-M3 halving
    wait_times = [impulse/2 for impulse in accelerated_impulse_durations(acceleration, dur, first_impulse_time)]
    negated_wait_times = [impulse/2 for impulse in accelerated_impulse_durations_with_cond(-acceleration, wait_times[-1]*2, lambda durations: durations[-1] < 1/100)]

    negated_part_wait_times = []
    first_impulse_time = negated_wait_times[-1]
    for _ in range(len(MPINS_SETTINGS)):
        negated_part_wait_times += [[impulse/2 for impulse in accelerated_impulse_durations_with_cond(-acceleration, first_impulse_time, lambda durations: durations[-1] < 1/100)]]
        first_impulse_time = negated_part_wait_times[-1][-1]  # Next part

    part_wait_times_zip = zip(MPINS_SETTINGS, part_wait_times)
    negated_part_wait_times_zip = zip(reversed(MPINS_SETTINGS), negated_part_wait_times)

    print(f"Total time of acceleration (parts): {sum(sum(pwts) for pwts in part_wait_times)*2:.6f} s")
    print(f"Total time of acceleration: {sum(wait_times)*2:.6f} s")
    print(f"Total time of deceleration (parts): {sum(sum(pwts) for pwts in negated_part_wait_times)*2:.6f} s")
    print(f"Total time of deceleration: {sum(negated_wait_times)*2:.6f} s")
    print(f"{dur=} {duration/2=}")
    print(f"All summed: {(sum(wait_times) + sum(negated_wait_times) + sum(sum(pwts) for pwts in part_wait_times) + sum(sum(pwts) for pwts in negated_part_wait_times))*2:.6f} s")

logging.basicConfig(level=logging.DEBUG)
test_rotate_platform3_calculations()
