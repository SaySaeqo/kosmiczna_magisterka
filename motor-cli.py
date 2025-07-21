import RPi.GPIO as GPIO
import motor

if __name__ == "__main__":
    try:
        motor.setup()
        motor.reset()
        while True:
            cmd = input("Enter command: ").strip()
            if cmd == "rot":
                print("Rotating...")
                for state in motor.generate_sine_wave(100,2):
                    GPIO.output(motor.PINS["STEP"], state)
            elif cmd in motor.PINS:
                state = int(input(f"Set {cmd} state (0/1): ").strip())
                if state not in (0, 1):
                    print("Invalid state. Use 0 or 1.")
                    continue
                GPIO.output(motor.PINS[cmd], state)
                print(f"{cmd} set to {'HIGH' if state else 'LOW'}")
            elif cmd == "reset":
                print("Resetting all pins...")
                motor.reset()
            elif cmd == "pins":
                print("Current pin states:")
                for name, pin in motor.PINS.items():
                    print(f"{name}: {GPIO.input(pin)}")
    except KeyboardInterrupt: ...
    finally:
        motor.reset()
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)
