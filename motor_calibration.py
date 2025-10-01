#!/bin/python

import motor
import RPi.GPIO as GPIO
import math
import time
import logging
import threading
import kosmiczna_magisterka.fast_motor as cmotor

def rotate_platform(angle):
    GPIO.output(motor.MPINS, GPIO.HIGH)
    acceleration = 2*motor.INERTIA_PLATFORM2WHEEL_RATIO*angle *4
    cmotor.generate_signal_prep(acceleration,300,0.5)

def calibrate_inertia_ratio():
    unit, tenths, hundredths = 11, 0.9, 0.09

    for u in range(1, 11):
        motor.INERTIA_PLATFORM2WHEEL_RATIO = u
        rotate_platform(math.pi)
        next_step = input(f"Is {u} to much? (y/n): ").strip().lower()
        if next_step == "y":
            unit = u - 1
            break
    
    for t in range(1, 10):
        t = t / 10.0
        motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + t
        rotate_platform(math.pi)
        next_step = input(f"Is {unit + t} to much? (y/n): ").strip().lower()
        if next_step == "y":
            tenths = t - 0.1
            break

    for h in range(1, 10):
        h = h / 100.0
        motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + tenths + h
        rotate_platform(math.pi)
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

        CALLIBRATION_TYPE = 1

        if CALLIBRATION_TYPE == 1:
            calibrate_inertia_ratio()
        elif CALLIBRATION_TYPE == 2:
            calibrate_decay_time()
            decay_times = []
            for _ in range(20):
                decay_time = calibrate_decay_time()
                decay_times.append(decay_time)
                input("Press Enter to continue to the next decay time...")
            print(f"Average decay time: {sum(decay_times) / len(decay_times):.3f} seconds")
            print(f"{decay_times=}")
            # Average decay time: 2.966 seconds
            # decay_times=[4.29820970500009, 3.8321442379999553, 2.6101399949998267, 3.9040863259999696, 2.604079805000083, 2.5939705389998835, 2.1244751449999058, 2.5221408759998667, 3.583803927999952, 3.6725272829999085, 3.216739906000157, 3.1135998590000327, 3.5238182850000612, 2.698659054000018, 2.28576684199993, 2.3034265280000454, 2.5562098079999487, 2.5932729310000013, 2.4178872039999533, 2.8656973120000657]

    except KeyboardInterrupt: ...
    finally:
        motor.reset()
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)
