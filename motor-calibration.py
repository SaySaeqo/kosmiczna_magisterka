#!/bin/python

import motor
import RPi.GPIO as GPIO
import math
from time import sleep


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

def calibrate_wheel_inertia():
    acceleration = math.pi
    start_frequency = 100
    start_speed = motor.ROTATION_PER_STEP * start_frequency
    t = 1
    impulses = motor.accelerated_impulse_durations(acceleration, t, 1/start_frequency)
    theoretical_final_speed = start_speed + acceleration * t
    final_frequency = 1/impulses[-1]
    final_speed = motor.ROTATION_PER_STEP * final_frequency

    print(f"Theoretical final speed: {theoretical_final_speed:.3f} rad/s")
    print(f"Final speed: {final_speed:.3f} rad/s")

    for state in motor.generate_sine_wave(start_frequency, t):
        GPIO.output(motor.PINS["STEP"], statet)

    for wt in [i/2 for i in impulses]:
        GPIO.output(motor.PINS["STEP"], GPIO.HIGH)
        sleep(wt)
        GPIO.output(motor.PINS["STEP"], GPIO.LOW)
        sleep(wt)

    print("Acceleration completed!")

    for state in motor.generate_sine_wave(final_frequency, 10):
        GPIO.output(motor.PINS["STEP"], state)


if __name__ == "__main__":
    try:
        motor.setup()
        motor.reset()

        calibrate_wheel_inertia()
        

    except KeyboardInterrupt: ...
    finally:
        motor.reset()
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)