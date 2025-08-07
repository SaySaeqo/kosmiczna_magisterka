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