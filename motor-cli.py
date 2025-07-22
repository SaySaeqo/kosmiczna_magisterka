import RPi.GPIO as GPIO
import motor

if __name__ == "__main__":
    try:
        motor.setup()
        motor.reset()
        while True:
            cmd = input("Enter command: ").strip().split(" ")

            if cmd[0] == "rot":
                print("Rotating...")
                try:
                    freq = int(cmd[1]) if len(cmd) > 1 else 150
                    seconds = int(cmd[2]) if len(cmd) > 2 else 1
                except ValueError:
                    print("Usage: rot [frequency] [seconds]")
                    continue
                for state in motor.generate_sine_wave(freq, seconds):
                    GPIO.output(motor.PINS["STEP"], state)
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
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)
