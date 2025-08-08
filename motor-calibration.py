#!/bin/python

import motor
import RPi.GPIO as GPIO
import math
import time
import logging


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
    freq =  motor.rotate_platform(2, 1, 50)
    freq *= 0.9
    motor.LOG.info(f"Initial frequency: {freq} Hz")

    rotator = motor.MotorRotator(freq)
    start = time.perf_counter()
    input("Press Enter to stop the motor...")
    rotator.stop()
    end = time.perf_counter()
    decay_time = end - start
    print(f"Decay time: {decay_time:.3f} seconds")
    


if __name__ == "__main__":
    try:
        motor.setup()
        motor.reset()
        logging.basicConfig(level=logging.DEBUG, filemode="w", filename="motor-calibration.log")

        calibrate_decay_time()
        

    except KeyboardInterrupt: ...
    finally:
        motor.reset()
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)