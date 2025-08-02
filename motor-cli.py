#!/bin/python

import RPi.GPIO as GPIO
import motor
import math
import logging
from time import sleep

rotator = None

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filemode="w", filename="motor.log")
    try:
        motor.setup()
        motor.reset()
        while True:
            cmd = input("Enter command: ").strip().split(" ")

            if cmd[0] == "rot":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Rotating...")
                try:
                    freq = int(cmd[1]) if len(cmd) > 1 else 150
                    seconds = int(cmd[2]) if len(cmd) > 2 else 1
                except ValueError:
                    print("Usage: rot [frequency] [seconds]")
                    continue
                for state in motor.generate_sine_wave(freq, seconds):
                    GPIO.output(motor.PINS["STEP"], state)
            elif cmd[0] == "rotacc":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Rotating with acceleration...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    seconds = float(cmd[2]) if len(cmd) > 2 else 1
                    start_frequency = int(cmd[3]) if len(cmd) > 3 else 100
                except ValueError:
                    print("Usage: rotacc [radians] [seconds] [start_frequency]")
                    continue
                motor.rotate_platform(radians, seconds, start_frequency)
                # end_wait_time *= 1.1
                # STAY_SECONDS = 3
                # while STAY_SECONDS > 0:
                #     GPIO.output(motor.PINS["STEP"], GPIO.HIGH)
                #     sleep(end_wait_time)
                #     GPIO.output(motor.PINS["STEP"], GPIO.LOW)
                #     sleep(end_wait_time)
                #     STAY_SECONDS -= end_wait_time * 2
            elif cmd[0] == "freq":
                try:
                    freq = float(cmd[1]) if len(cmd) > 1 else 0.75
                    if freq <= 0:
                        rotator.stop()
                        rotator = None
                    elif rotator is None:
                        rotator = motor.MotorRotator(freq)
                    else:
                        rotator.set_frequency(freq)
                except ValueError:
                    print("Usage: freq [frequency]")
            elif cmd[0] in motor.PINS:
                if len(cmd) == 1:
                    cmd.append(input(f"Set {cmd} state (0/1): ").strip())
                if cmd[1] not in ("0", "1"):
                    print("Invalid state. Use 0 or 1.")
                    continue
                state = int(cmd[1])
                GPIO.output(motor.PINS[cmd[0]], state)
                print(f"{cmd} set to {'HIGH' if state else 'LOW'}")
            elif cmd[0] == "reset":
                print("Resetting all pins...")
                motor.reset()
            elif cmd[0] == "pins":
                print("Current pin states:")
                for name, pin in motor.PINS.items():
                    print(f"{name}: {GPIO.input(pin)}")
    except KeyboardInterrupt: print()
    finally:
        motor.reset()
        if rotator:
            rotator.stop()
            rotator = None
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)
