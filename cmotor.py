import kosmiczna_magisterka.fast_motor as fast_motor
from time import perf_counter
import motor

def c_generate_signal(pin: int, acc: float, freq: int, duration: float):
    acc_const = acc / motor.ROTATION_PER_STEP / motor.get_step_resolution()
    fast_motor.generate_signal(pin, acc_const, freq, duration)

def c_generate_signal2(pin: int, acc: float, freq: int, duration: float):
    acc_const = acc / motor.ROTATION_PER_STEP / motor.get_step_resolution()
    fast_motor.generate_signal2(pin, acc_const, freq, duration)

def c_generate_signal3(pin: int, acc: float, freq: int, duration: float):
    acc_const = acc / motor.ROTATION_PER_STEP / motor.get_step_resolution()
    fast_motor.generate_signal3(pin, acc_const, freq, duration)