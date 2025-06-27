import numpy as np
import cv2 as cv

cap = cv.VideoCapture(0)

# Define the codec and create VideoWriter object
fourcc = cv.VideoWriter_fourcc(*'XVID')
#out = cv.VideoWriter('output.avi', fourcc, 20.0, (640,  480))

print("Starting recording")
try:
    while cap.isOpened():
        ret, frame = cap.read()
        if not ret:
            print("Can't receive frame (stream end?). Exiting ...")
            break

        #out.write(frame)
        cv.imshow('frame', frame)
except KeyboardInterrupt: ...
finally:
    cap.release()
    cv.destroyAllWindows()
    #out.release()
