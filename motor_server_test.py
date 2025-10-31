import kosmiczna_magisterka.fast_motor2 as cmotor2
import time



if __name__ == "__main__":
    cmotor2.setup()
    #cmotor2.rotation_server()
    cmotor2.rotation_server_simple()

    print("Motor server is running. Enter angle to rotate. Type 'q' to quit.")
    cmd = ""
    try:
        while cmd != "q":
            cmd = input("Angle: ").strip().lower()
            if cmd == "globals":
                cmotor2.print_globals()
            elif cmd.startswith("stream"):
                cmd = cmd.removeprefix("stream")
                angle = int(cmd)
                time_sec = 5
                interval = 0.1
                print(f"Pushing {angle} angle every {interval}s for {time_sec}s")
                for _ in range(int(time_sec / interval)):
                    cmotor2.rotation_client(angle)
                    time.sleep(interval)
            else:
                angle = int(cmd)
                cmotor2.rotation_client(angle)
    except KeyboardInterrupt:
        pass
    except ValueError:
        print("Wrong angle value. Exiting...")
