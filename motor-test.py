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

test_acceleration_of_accelerated_impulse()
    
