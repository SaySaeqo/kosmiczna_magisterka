#!/bin/python

import motor
import RPi.GPIO as GPIO
import math
import time
import logging
import threading
import kosmiczna_magisterka.fast_motor as cmotor

def rotate_platform(angle, dur=0.5):
    GPIO.output(motor.MPINS, GPIO.HIGH)
    GPIO.output(motor.PINS["M3"],GPIO.LOW)
    duration = dur
    acceleration = (angle / motor.ROTATION_PER_STEP / motor.get_step_resolution()) * motor.INERTIA_PLATFORM2WHEEL_RATIO / duration / duration
    #acceleration = 2*(angle / motor.ROTATION_PER_STEP / motor.get_step_resolution()) * motor.INERTIA_PLATFORM2WHEEL_RATIO / duration / duration
    print(acceleration)
    cmotor.generate_signal_prep(acceleration,200,duration)
    #cmotor.generate_signal((acceleration,200,duration))
    #time.sleep(0.1)
    # cmotor.generate_signal((0, -400, 0.1))
                           
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
        rotate_platform(math.pi/2)
        next_step = input(f"Is {unit + t} to much? (y/n): ").strip().lower()
        if next_step == "y":
            tenths = t - 0.1
            break

    for h in range(1, 10):
        h = h / 100.0
        motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + tenths + h
        rotate_platform(math.pi/2)
        next_step = input(f"Is {unit + tenths + h} to much? (y/n): ").strip().lower()
        if next_step == "y":
            hundredths = h - 0.01
            break
    
    print(f"Final inertia ratio: {unit + tenths + hundredths}")

    motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + tenths + hundredths
    time.sleep(3)
    rotate_platform(math.pi/4)
    time.sleep(1)
    rotate_platform(math.pi/2)
    time.sleep(1)
    rotate_platform(math.pi)


def final_rotation_test():
    print("Setting INERTIA")
    time.sleep(3)
    motor.INERTIA_PLATFORM2WHEEL_RATIO = 6.9
    print("PI/4 rotate")
    time.sleep(3)
    rotate_platform(math.pi/4)
    print("PI/2 rotate")
    time.sleep(3)
    rotate_platform(math.pi/2)
    print("PI rotate")
    time.sleep(3)
    rotate_platform(math.pi)
    print("PI/4 rotate")
    time.sleep(3)
    rotate_platform(math.pi/4, 0.25)
    print("PI/2 rotate")
    time.sleep(3)
    rotate_platform(math.pi/2, 0.25)
    print("PI rotate")
    time.sleep(3)
    rotate_platform(math.pi, 0.25)


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

        CALLIBRATION_TYPE = 0

        if CALLIBRATION_TYPE == 0:
            final_rotation_test()
        elif CALLIBRATION_TYPE == 1:
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
