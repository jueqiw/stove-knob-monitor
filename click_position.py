"""Click on the image to get pixel coordinates. Press any key to quit."""

import cv2
import sys

image_path = sys.argv[1] if len(sys.argv) > 1 else "snapshot.jpg"
frame = cv2.imread(image_path)
if frame is None:
    print(f"Cannot read {image_path}")
    sys.exit(1)

h, w = frame.shape[:2]
scale = 1.0
max_dim = 2000
if max(h, w) > max_dim:
    scale = max_dim / max(h, w)
    display = cv2.resize(frame, None, fx=scale, fy=scale)
else:
    display = frame.copy()

clicks = []


def on_click(event, x, y, flags, param):
    if event == cv2.EVENT_LBUTTONDOWN:
        orig_x = int(x / scale)
        orig_y = int(y / scale)
        clicks.append((orig_x, orig_y))
        print(f"Click {len(clicks)}: ({orig_x}, {orig_y})")
        cv2.circle(display, (x, y), 8, (0, 255, 0), 2)
        cv2.putText(display, f"({orig_x},{orig_y})", (x + 12, y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        cv2.imshow(win, display)


win = "Click on white dots - press any key to quit"
cv2.namedWindow(win, cv2.WINDOW_NORMAL)
cv2.resizeWindow(win, min(w, 2000), min(h, 1200))
cv2.imshow(win, display)
cv2.setMouseCallback(win, on_click)

print("Click on the white dots. Press any key to quit.")
cv2.waitKey(0)
cv2.destroyAllWindows()

print(f"\nAll clicks: {clicks}")
