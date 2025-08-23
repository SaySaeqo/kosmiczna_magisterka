import kosmiczna_magisterka.fast_motor as fast_motor
from time import perf_counter
import motor

def c_test_signal(pin, how_much):
    start = perf_counter()
    fast_motor.test_signal(pin, how_much)
    end = perf_counter()
    print(f"Generated {how_much / (end - start):.6f} impulses per second")

def c_generate_signal(pin: int, acc: float, freq: int, duration: float):
    acc_const = acc / motor.ROTATION_PER_STEP / motor.get_step_resolution()
    fast_motor.generate_signal(pin, acc_const, freq, duration)