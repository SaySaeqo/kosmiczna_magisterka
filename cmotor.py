import kosmiczna_magisterka.fast_motor as fast_motor
from time import perf_counter
import motor

def c_generate_signal_prep(acc: float, freq: int, duration: float):
    acc_const = acc / motor.ROTATION_PER_STEP / motor.get_step_resolution()
    fast_motor.generate_signal_prep(acc_const, freq, duration)

def c_generate_signal(acc: float, freq: int, duration: float):
    acc_const = acc / motor.ROTATION_PER_STEP / motor.get_step_resolution()
    fast_motor.generate_signal(acc_const, freq, duration)