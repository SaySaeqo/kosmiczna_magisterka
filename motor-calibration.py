import motor
import RPi.GPIO as GPIO
import math

if __name__ == "__main__":
    try:
        motor.setup()
        motor.reset()

        unit, tenths, hundredths = 0, 0, 0

        for u in range(1, 11):
            motor.INERTIA_PLATFORM2WHEEL_RATIO = u
            motor.rotate_platform(math.pi, 1, 100)
            next_step = input(f"Is {u} to much? (y/n): ").strip().lower()
            if next_step == "y":
                unit = u - 1
                break
        
        for t in range(0.1, 1, 0.1):
            motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + t
            motor.rotate_platform(math.pi, 1, 100)
            next_step = input(f"Is {unit + t} to much? (y/n): ").strip().lower()
            if next_step == "y":
                tenths = t - 0.1
                break
        
        for h in range(0.01, 0.1, 0.01):
            motor.INERTIA_PLATFORM2WHEEL_RATIO = unit + tenths + h
            motor.rotate_platform(math.pi, 1, 100)
            next_step = input(f"Is {unit + tenths + h} to much? (y/n): ").strip().lower()
            if next_step == "y":
                hundredths = h - 0.01
                break
        
        print(f"Final inertia ratio: {unit + tenths + hundredths}")

    except KeyboardInterrupt: ...
    finally:
        motor.reset()
        GPIO.output(motor.PINS["EN"], GPIO.HIGH)