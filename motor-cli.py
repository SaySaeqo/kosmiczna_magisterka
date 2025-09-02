#!/bin/python

import RPi.GPIO as GPIO
import motor
import math
import logging
import functools
import cmotor

rotator = None

def with_arg(func):
    return lambda x: func()

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG, filemode="w", filename="motor.log")
    try:
        motor.setup()
        motor.reset()
        GPIO.output(motor.MPINS, GPIO.HIGH)  # Set 1/16 step
        #motor.pigpio_init()
        next_cmd = None
        commands = []
        while True:
            # Command chaining and input handling
            if not next_cmd and commands:
                last_result = None
                for command in commands:
                    last_result = command(last_result)
                commands.clear()
            if next_cmd:
                cmd = next_cmd
                next_cmd = None
            else:
                if rotator is None:
                    GPIO.output(motor.PINS["EN"], GPIO.HIGH)  # Disable motor driver
                cmd = input("Enter command: ").strip().split(" ")
                if rotator is None:
                    GPIO.output(motor.PINS["EN"], GPIO.LOW)  # Enable motor driver
            if "+" in cmd:
                plus_idx = cmd.index("+")
                next_cmd = cmd[plus_idx + 1:] if plus_idx + 1 < len(cmd) else None
                cmd = cmd[:plus_idx]


            if cmd[0] == "rot":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Rotating...")
                try:
                    if len(cmd) > 1 and cmd[1] == "-":
                        freq = None
                    else:
                        freq = int(cmd[1]) if len(cmd) > 1 else 150
                    seconds = float(cmd[2]) if len(cmd) > 2 else 1
                except ValueError:
                    print("Usage: rot [frequency] [seconds]")
                    continue
                def rot(*args):
                    for state in motor.generate_sine_wave(args[1], args[0]):
                        GPIO.output(motor.PINS["STEP"], state)
                if freq:
                    commands.append(functools.partial(rot, seconds, freq))
                else:
                    commands.append(functools.partial(rot, seconds))
            elif cmd[0] == "acc":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Accelerating flywheel...")
                try:
                    if len(cmd) > 1 and cmd[1] == "-":
                        start_frequency = None
                    else:
                        start_frequency = int(cmd[1]) if len(cmd) > 1 else 100
                    if len(cmd) > 2 and cmd[2] == "-":
                        final_frequency = None
                    else:
                        final_frequency = int(cmd[2]) if len(cmd) > 2 else 200
                    seconds = float(cmd[3]) if len(cmd) > 3 else 1
                except ValueError:
                    print("Usage: acc [start_frequency] [final_frequency] [seconds]")
                    continue
                if start_frequency is None:
                    commands.append(functools.partial(motor.accelerate, final_frequency=final_frequency, duration=seconds))
                elif final_frequency is None:
                    commands.append(functools.partial(motor.accelerate, start_frequency=start_frequency, duration=seconds))
                else:
                    commands.append(with_arg(functools.partial(motor.accelerate, start_frequency, final_frequency, seconds)))
            elif cmd[0] == "rotacc":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Rotating with acceleration...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    seconds = float(cmd[2]) if len(cmd) > 2 else 1
                    if len(cmd) > 3 and cmd[3] == "-":
                        start_frequency = None
                    else:
                        start_frequency = int(cmd[3]) if len(cmd) > 3 else 50
                except ValueError:
                    print("Usage: rotacc [radians] [seconds] [start_frequency]")
                    continue
                if start_frequency is None:
                    commands.append(functools.partial(motor.rotate_platform, radians, seconds))
                else:
                    commands.append(with_arg(functools.partial(motor.rotate_platform, radians, seconds, start_frequency)))
            elif cmd[0] == "rotdec":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Rotating with deceleration...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    seconds = float(cmd[2]) if len(cmd) > 2 else 1
                    if len(cmd) > 3 and cmd[3] == "-":
                        start_frequency = None
                    else:
                        start_frequency = int(cmd[3]) if len(cmd) > 3 else 50
                except ValueError:
                    print("Usage: rotdec [radians] [seconds] [start_frequency]")
                    continue
                if start_frequency is None:
                    commands.append(functools.partial(motor.rotate_platform_deceleration, radians, seconds))
                else:
                    commands.append(with_arg(functools.partial(motor.rotate_platform_deceleration, radians, seconds, start_frequency)))
            elif cmd[0] == "rotacc2":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Rotating with acceleration (experimental)...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    seconds = float(cmd[2]) if len(cmd) > 2 else 1
                    if len(cmd) > 3 and cmd[3] == "-":
                        start_frequency = None
                    else:
                        start_frequency = int(cmd[3]) if len(cmd) > 3 else 50
                except ValueError:
                    print("Usage: rotacc2 [radians] [seconds] [start_frequency]")
                    continue
                if start_frequency is None:
                    commands.append(functools.partial(motor.rotate_platform2, radians, seconds))
                else:
                    commands.append(with_arg(functools.partial(motor.rotate_platform2, radians, seconds, start_frequency)))
            elif cmd[0] == "rotacc3":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Rotating with acceleration with m1-3 pins usage...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    seconds = float(cmd[2]) if len(cmd) > 2 else 1
                except ValueError:
                    print("Usage: rotacc3 [radians] [seconds]")
                    continue

                commands.append(with_arg(functools.partial(motor.rotate_platform3, radians, seconds)))
            elif cmd[0] == "crotacc":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Running crotacc...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    duration = float(cmd[2]) if len(cmd) > 2 else 1
                    frequency = int(cmd[3]) if len(cmd) > 3 else 300
                except ValueError:
                    print("Usage: crotacc [radians] [seconds] [frequency]")
                    continue

                acceleration = 2 * motor.INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
                commands.append(with_arg(functools.partial(cmotor.c_generate_signal, motor.PINS["STEP"], acceleration, frequency, duration)))
            elif cmd[0] == "crotacc2":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Running crotacc2...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    duration = float(cmd[2]) if len(cmd) > 2 else 1
                    frequency = int(cmd[3]) if len(cmd) > 3 else 300
                except ValueError:
                    print("Usage: crotacc2 [radians] [seconds] [frequency]")
                    continue

                acceleration = 2 * motor.INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
                commands.append(with_arg(functools.partial(cmotor.c_generate_signal2, motor.PINS["STEP"], acceleration, frequency, duration)))
            elif cmd[0] == "crotacc3":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Running crotacc3...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    duration = float(cmd[2]) if len(cmd) > 2 else 1
                    frequency = int(cmd[3]) if len(cmd) > 3 else 300
                except ValueError:
                    print("Usage: crotacc3 [radians] [seconds] [frequency]")
                    continue

                acceleration = 2 * motor.INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
                commands.append(with_arg(functools.partial(cmotor.c_generate_signal3, motor.PINS["STEP"], acceleration, frequency, duration)))
            elif cmd[0] == "protacc":
                if rotator is not None:
                    print("Motor is already rotating. Use 'freq 0' to stop it first.")
                    continue
                print("Running protacc...")
                try:
                    radians = float(cmd[1]) if len(cmd) > 1 else math.pi
                    duration = float(cmd[2]) if len(cmd) > 2 else 1.0
                    frequency = int(cmd[3]) if len(cmd) > 3 else 300
                except ValueError:
                    print("Usage: protacc [radians] [seconds] [frequency]")
                    continue
                acceleration = 2 * motor.INERTIA_PLATFORM2WHEEL_RATIO * radians / duration / duration
                commands.append(with_arg(functools.partial(motor.pigpio_accelerated_signal, acceleration, frequency, duration)))
            elif cmd[0] == "freq":
                try:
                    if len(cmd) > 1 and cmd[1] == "-":
                        freq = None
                    else:
                        freq = int(cmd[1]) if len(cmd) > 1 else 100
                except ValueError:
                    print("Usage: freq [frequency]")
                    continue
                def set_freq(*args):
                    global rotator
                    if args[0] <= 0:
                        if rotator:
                            rotator.stop()
                        rotator = None
                    elif rotator is None:
                        rotator = motor.MotorRotator(args[0])
                    else:
                        rotator.set_frequency(args[0])
                if freq is None:
                    commands.append(set_freq)
                else:
                    commands.append(functools.partial(set_freq, freq))
            elif cmd[0] in motor.PINS:
                if len(cmd) == 1:
                    cmd.append(input(f"Set {cmd} state (0/1): ").strip())
                if cmd[1] not in ("0", "1"):
                    print("Invalid state. Use 0 or 1.")
                    continue
                state = int(cmd[1])
                print(f"{cmd[0]} set to {'HIGH' if state else 'LOW'}")

                commands.append(with_arg(functools.partial(GPIO.output, motor.PINS[cmd[0]], state)))
            elif cmd[0] == "reset":
                print("Resetting all pins...")
                commands.append(motor.reset)
            elif cmd[0] == "pins":
                def show_pins(*args):
                    print("Current pin states:")
                    for name, pin in motor.PINS.items():
                        print(f"{name}: {GPIO.input(pin)}")
                commands.append(show_pins)
    except KeyboardInterrupt: print()
    finally:
        motor.reset()
        if rotator:
            rotator.stop()
            rotator = None
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)
        #motor.pigpio_cleanup()
