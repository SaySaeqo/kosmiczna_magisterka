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
pigpio_stub = types.ModuleType("pigpio")
sys.modules["pigpio"] = pigpio_stub
class pi_stub:
    def __init__(self):
        self.hardware_PWM = lambda gpio, frequency, dutycycle: None
        self.set_mode = lambda gpio, mode: None
        self.write = lambda gpio, value: None
        self.read = lambda gpio: 0
pigpio_stub.pi = lambda: pi_stub()

import motor
motor.get_step_resolution = lambda: 1/16

from motor import *
import math
import types
import matplotlib.pyplot as plt
import time
import pprint
import json
import webcam

def sum_times(times):
    return [sum(times[:i+1]) for i in range(len(times))]

def test_negation_of_accelerated_impulse():
    """Test the accelerated impulse durations generator."""
    duration = 1
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * (math.pi) / duration / duration
    impulses = accelerated_impulse_durations(acceleration, duration, 1/100)
    n_impulses = accelerated_impulse_durations(-acceleration, duration, impulses[-1])

    r_impulses = list(reversed(impulses))
    plt.plot(impulses, label="acceleration")
    # plt.xscale("log")
    # plt.plot(sum_times(n_impulses), n_impulses, label="deceleration")
    plt.xlabel("Cumulative time (s)")
    plt.ylabel("Impulse duration (s)")
    plt.title("Accelerated Impulse Durations")
    plt.legend()
    plt.grid()
    plt.show()

def test_acceleration_of_accelerated_impulse():
    """Test the acceleration of the accelerated impulse durations generator."""
    duration = 0.5
    acceleration = INERTIA_PLATFORM2WHEEL_RATIO * 1.6 / duration / duration
    start_impulse = 1/300
    start = time.perf_counter()
    impulses = accelerated_impulse_durations(acceleration, duration, start_impulse)
    end = time.perf_counter()
    print(f"Impulse generation took {end - start:.6f} seconds")

    # Speeds of the flywheel
    final_speed = (ROTATION_PER_STEP * get_step_resolution()) / (impulses[-1])
    theoretical_final_speed = (ROTATION_PER_STEP * get_step_resolution())/start_impulse + acceleration * duration
    print(f"Computed: {final_speed:.2f} rad/s, Theoretical: {theoretical_final_speed:.2f} rad/s")
    print(f"Computed final frequency: {1.0/impulses[-1]} Hz, Theoretical: {theoretical_final_speed / ROTATION_PER_STEP/get_step_resolution()} Hz")
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

def test_new_impulse_duration_formula():
    duration = 1
    radians = math.pi
    acceleration = 2* INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
    t0 = 1/300

    a = 300
    b = acceleration/ROTATION_PER_STEP/get_step_resolution()
    a1 = (-b*t0*t0)/(a+b*t0)
    k = (1/(a+b*(2*t0+a1)) - t0 - a1)/a1

    impulses = [t0]
    t_sum = t0
    ax = a1
    tx = t0 + ax
    t_sum += tx
    impulses.append(tx)
    while t_sum < duration:
        ax *= k
        tx += ax
        impulses.append(tx)
        t_sum += tx


    impulses2 = accelerated_impulse_durations(acceleration, duration, t0)
    impulses3 = [t0]
    t_sum = t0
    while t_sum < duration:
        tx = 1/(a+b*t_sum)
        impulses3.append(tx)
        t_sum += tx

    # print(f"{a1=} {impulses_true[1]-impulses_true[0]=}")
    # a2 = impulses_true[2]-impulses_true[1]
    # print(f"{k=} {a1*k=} {a2=}")
    a_n_2 = a1
    for i in range(2, len(impulses3)):
        a_n = impulses3[i]-impulses3[i-1]
        a_n_2 = a_n_2 * k
        a_n = round(a_n, 6)
        a_n_2 = round(a_n_2, 6)
        if a_n != a_n_2:
            print(f"Discrepancy found ({i}): {a_n=} {a_n_2=}")
            break

    for i in range(len(impulses2)):
        im1 = round(impulses2[i], 6)
        im2 = round(impulses3[i], 6)
        if im1 != im2:
            print(f"Discrepancy found (impulses2 vs impulses3) ({i}): {im1=} {im2=}")

    plt.plot(impulses, label="tx = tx-1 + ax")
    plt.plot(impulses2, label="tx = tx-1/(1 + alfa*tx-1/L)")
    plt.plot(impulses3, label="tx = 1/(a + b*sum_x-1)")
    plt.xlabel("Cumulative time (s)")
    plt.ylabel("Impulse frequency (Hz)")
    plt.title("Accelerated Impulse Frequency")
    plt.legend()
    plt.grid()
    plt.show()

def test_pigpio_parameters():
    angle = math.pi
    duration = 1
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * angle / duration / duration
    start_frequency = 300

    acceleration_constant = acceleration / ROTATION_PER_STEP / get_step_resolution()

    a = start_frequency # x.0
    b = round(acceleration_constant * 4096)  # x.12
    duration = round(duration * 1048576)  # x.20
    t0 = round(1/start_frequency * 1048576)  # x.20

    print(f"{acceleration=}, {acceleration_constant=}")
    print(f"{a=}, {b=}, {duration=}, {t0=}")
    print(f"Last impulse duration: {accelerated_impulse_durations(acceleration, 1, 1/start_frequency)[-1] * 1000_000} us")

def test_accelerated_impulses_unique_values():
    angle = math.pi
    duration = 1
    acceleration = 2 * INERTIA_PLATFORM2WHEEL_RATIO * angle / duration / duration
    start_frequency = 300

    impulses = accelerated_impulse_durations(acceleration, duration, 1/start_frequency)
    impulses_len = len(impulses)
    impulses = map(lambda x: int(x * 1000_000), impulses)
    unique_impulses = []
    last_impulse = 1
    for idx, impulse in enumerate(impulses):
        if impulse != last_impulse:
            unique_impulses.append((idx, impulse))
            last_impulse = impulse
    
    pprint.pprint(unique_impulses)
    print(f"Number of unique impulses: {len(unique_impulses)}")
    print(f"Total impulses: {impulses_len}")

def test_quest_input():
    with open("webcam.log", "r") as f:
        lines = f.readlines()
        data = list(map(json.loads, lines))
        prev_time = data[0]["time"]- 1 
        prev_now = time.clock_gettime(time.CLOCK_MONOTONIC)
        for i in range(len(data)): 
            orientation = data[i]["orientation"]
            time_diff = data[i]["time"] - prev_time
            prev_time = data[i]["time"]
            now = time.clock_gettime(time.CLOCK_MONOTONIC)
            real_time_diff = now - prev_now
            prev_now = now
            if time_diff > real_time_diff:
                time.sleep(time_diff - real_time_diff)
            else:
                pass
                #print(f"Warning: processing is too slow! {time_diff=} {real_time_diff=}")
            #some func
            test_now = time.clock_gettime(time.CLOCK_MONOTONIC)
            result = webcam.get_cmotor_parameters(orientation, time_diff)
            test_time_passed = time.clock_gettime(time.CLOCK_MONOTONIC) - test_now
            if time_diff < test_time_passed:
                print(f"Warning: processing is too slow! {time_diff=} {test_time_passed=}")

            with open("webcam_test_output.log", "a") as of:
                of.write(json.dumps({
                    "input": i+1,
                    "output": result,
                    "real_time_diff": test_time_passed
                }) + "\n")


logging.basicConfig(level=logging.DEBUG)
test_quest_input()
