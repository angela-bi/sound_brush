import cv2
import numpy as np
import bpy

cap = cv2.VideoCapture(0, cv2.CAP_AVFOUNDATION)

cv2.namedWindow("Webcam Brightness Tracker", cv2.WINDOW_NORMAL)
arr = []

while True:
    ret, frame = cap.read()
    if not ret:
        print("failed to read frame.")
        break

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    brightness = np.mean(gray)
    arr.append(brightness)

    cv2.putText(frame, f"Brightness: {brightness:.2f}", (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    cv2.imshow("Webcam Brightness Tracker", frame)

    key = cv2.waitKey(1)
    if key == ord('q'):
        print("exiting")
        break

cap.release()
cv2.destroyAllWindows()

normalized_arr = (arr - np.min(arr)) / (np.max(arr) - np.min(arr))
sampled_brightness = np.random.choice(normalized_arr)

print('sampled brightness:', sampled_brightness)
brush = bpy.data.brushes.get("Tint")
r,g,b = brush.color
print('old brush color:', brush.color)
brush.color = sampled_brightness, g, b
print('new brush color:', brush.color)