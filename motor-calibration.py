#!/bin/python

import motor
import RPi.GPIO as GPIO
import math
import time
import logging
import threading


def calibrate_inertia_ratio():
    unit, tenths, hundredths = 11, 0.9, 0.09

    for u in range(1, 11):
        motor.INERTIA_PLATFORM2WHEEL_RATIO = u
        motor.rotate_platform2(math.pi, 1, 100)
        next_step = input(f"Is {u} to much? (y/n): ").strip().lower()
        if next_step == "y":
            unit = u - 1
            break
    
    for t in range(1, 10):
        t = t / 10.0
        motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + t
        motor.rotate_platform2(math.pi, 1, 100)
        next_step = input(f"Is {unit + t} to much? (y/n): ").strip().lower()
        if next_step == "y":
            tenths = t - 0.1
            break

    for h in range(1, 10):
        h = h / 100.0
        motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + tenths + h
        motor.rotate_platform2(math.pi, 1, 100)
        next_step = input(f"Is {unit + tenths + h} to much? (y/n): ").strip().lower()
        if next_step == "y":
            hundredths = h - 0.01
            break
    
    print(f"Final inertia ratio: {unit + tenths + hundredths}")

def calibrate_decay_time():
    active = True
    start = None
    def accelerate_then_stay():
        nonlocal active, start
        freq =  motor.rotate_platform(2, 1, 50)
        wait_time = 1 / (2 * freq)
        start = time.perf_counter()
        while active:
            GPIO.output(motor.PINS["STEP"], GPIO.HIGH)
            time.sleep(wait_time)
            GPIO.output(motor.PINS["STEP"], GPIO.LOW)
            time.sleep(wait_time)

    thread = threading.Thread(target=accelerate_then_stay)
    thread.start()
    input("Press Enter to stop the motor...")
    end = time.perf_counter()
    active = False
    decay_time = end - start
    print(f"Decay time: {decay_time:.3f} seconds")
    thread.join()
    return decay_time


if __name__ == "__main__":
    try:
        motor.setup()
        motor.reset()
        logging.basicConfig(level=logging.DEBUG, filemode="w", filename="motor-calibration.log")

        decay_times = []
        for _ in range(20):
            decay_time = calibrate_decay_time()
            decay_times.append(decay_time)
        print(f"Average decay time: {sum(decay_times) / len(decay_times):.3f} seconds")
        print(f"{decay_times=}")

    except KeyboardInterrupt: ...
    finally:
        motor.reset()
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)