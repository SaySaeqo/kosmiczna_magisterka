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

    dur = duration / 2
    acceleration = motor.INERTIA_PLATFORM2WHEEL_RATIO * radians / dur / dur
    impulses = motor.accelerated_impulse_durations(acceleration, dur, motor.MAX_IMPULSE_DURATION)
    up_to_200hz_impulses = [wt for wt in impulses if wt > 1/200]
    up_to_200hz_wait_times = [impulse/2 for impulse in up_to_200hz_impulses]
    up_to_200hz_total_time = sum(up_to_200hz_impulses)
    dur -= up_to_200hz_total_time * 4
    wait_times = [impulse/2 for impulse in motor.accelerated_impulse_durations(acceleration, dur, motor.MAX_IMPULSE_DURATION)]
    negated_wait_times = [impulse/2 for impulse in motor.accelerated_impulse_durations(-acceleration, dur, wait_times[-1]*2)]
    down_to_100hz_wait_times = [wt for wt in negated_wait_times if wt > 1/400]

test_rotate_platform3_calculations()
