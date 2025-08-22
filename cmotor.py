import kosmiczna_magisterka.fast_motor as fast_motor
from time import perf_counter

def c_test_signal(pin, how_much):
    start = perf_counter()
    fast_motor.generate_signal(pin, how_much)
    end = perf_counter()
    print(f"Generated {how_much / (end - start):.6f} impulses per second")