"""
Knob state detector using white dot stickers on stove knobs.

Uses hardcoded dot positions (calibrated with knobs in OFF position).
Checks if the white dot is still at its known OFF position.
If the dot has moved away → the knob has been turned → burner is ON.
"""

import cv2
import numpy as np
import logging
from typing import List

logger = logging.getLogger(__name__)

# Hardcoded from successful detection with all knobs OFF.
# Each entry: knob name, knob center (cx, cy), dot position when OFF (dx, dy)
# All coordinates in full frame pixel space (2304x1296).
KNOBS = [
    {"name": "Knob 1", "cx": 1043, "cy": 558, "dot_x": 1038, "dot_y": 566},
    {"name": "Knob 2", "cx": 1077, "cy": 554, "dot_x": 1072, "dot_y": 562},
    {"name": "Knob 3", "cx": 1298, "cy": 548, "dot_x": 1289, "dot_y": 549},
    {"name": "Knob 4", "cx": 1335, "cy": 540, "dot_x": 1327, "dot_y": 551},
    {"name": "Knob 5", "cx": 1373, "cy": 541, "dot_x": 1365, "dot_y": 551},
]

# The dot sticker is ~3-5 pixels across.
DOT_RADIUS = 3       # tiny region at the dot center
SURROUND_RADIUS = 12  # larger region around the dot (knob surface)

# The dot must be this much brighter than the surrounding knob surface.
# This is RELATIVE so it works regardless of lighting conditions.
BRIGHTNESS_DIFF_THRESHOLD = 30


def _check_dot_present(
    frame: np.ndarray, dot_x: int, dot_y: int, cx: int, cy: int
) -> dict:
    """Check if the white dot sticker is at the expected position.

    Compares brightness at the dot center vs the surrounding knob surface.
    The dot is always brighter than the dark knob, regardless of lighting.
    """
    h, w = frame.shape[:2]
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    v_full = hsv[:, :, 2]

    # Average brightness at the dot center (tiny area)
    r = DOT_RADIUS
    y1, y2 = max(0, dot_y - r), min(h, dot_y + r)
    x1, x2 = max(0, dot_x - r), min(w, dot_x + r)
    dot_v = float(np.mean(v_full[y1:y2, x1:x2]))

    # Average brightness of the knob surface (ring around center, excluding dot)
    sr = SURROUND_RADIUS
    sy1, sy2 = max(0, cy - sr), min(h, cy + sr)
    sx1, sx2 = max(0, cx - sr), min(w, cx + sr)
    surround = v_full[sy1:sy2, sx1:sx2].copy()

    # Mask out the dot area from the surround to get pure knob surface
    local_dy = dot_y - (cy - sr)
    local_dx = dot_x - (cx - sr)
    mask = np.ones(surround.shape, dtype=bool)
    dr = DOT_RADIUS + 2
    mask_y1 = max(0, local_dy - dr)
    mask_y2 = min(surround.shape[0], local_dy + dr)
    mask_x1 = max(0, local_dx - dr)
    mask_x2 = min(surround.shape[1], local_dx + dr)
    mask[mask_y1:mask_y2, mask_x1:mask_x2] = False

    surround_v = float(np.mean(surround[mask])) if np.any(mask) else dot_v

    brightness_diff = dot_v - surround_v
    dot_present = brightness_diff >= BRIGHTNESS_DIFF_THRESHOLD

    return {
        "dot_v": dot_v,
        "surround_v": surround_v,
        "brightness_diff": brightness_diff,
        "dot_present": dot_present,
    }


def detect_knob_states(frame: np.ndarray) -> List[dict]:
    """Detect ON/OFF state of each knob.

    Checks if the white dot is still at its calibrated OFF position.
    If yes → OFF. If the dot has moved away → ON.
    """
    results = []
    for knob in KNOBS:
        check = _check_dot_present(frame, knob["dot_x"], knob["dot_y"], knob["cx"], knob["cy"])
        # Dot present at OFF position → knob is OFF
        # Dot NOT present → knob has been turned → ON
        is_on = not check["dot_present"]

        results.append({
            "name": knob["name"],
            "cx": knob["cx"],
            "cy": knob["cy"],
            "dot_x": knob["dot_x"],
            "dot_y": knob["dot_y"],
            "dot_v": check["dot_v"],
            "brightness_diff": check["brightness_diff"],
            "is_on": is_on,
        })
        status = "ON" if is_on else "OFF"
        logger.debug("%s: %s (diff=%.0f)", knob["name"], status, check["brightness_diff"])

    return results


def draw_knob_states(frame: np.ndarray, states: List[dict]) -> np.ndarray:
    """Draw knob detection results on frame."""
    annotated = frame.copy()
    r = DOT_RADIUS

    for s in states:
        cx, cy = s["cx"], s["cy"]
        dx, dy = s["dot_x"], s["dot_y"]

        if s["is_on"]:
            color = (0, 0, 255)  # red — ON
            label = f"{s['name']}: ON"
        else:
            color = (0, 255, 0)  # green — OFF
            label = f"{s['name']}: OFF"

        # Draw knob circle
        cv2.circle(annotated, (cx, cy), 22, color, 2)
        # Draw dot check region
        cv2.rectangle(annotated, (dx - r, dy - r), (dx + r, dy + r), color, 2)
        # Draw label
        cv2.putText(annotated, label, (cx - 50, cy - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        # Show debug info
        cv2.putText(annotated, f"diff={s['brightness_diff']:.0f}",
                    (dx - r - 10, dy + r + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, color, 1)

    return annotated


if __name__ == "__main__":
    import sys
    import yaml
    import urllib.parse

    # Grab a frame
    if len(sys.argv) > 1:
        frame = cv2.imread(sys.argv[1])
    else:
        with open("config.yaml") as f:
            cfg = yaml.safe_load(f)["camera"]
        user = urllib.parse.quote(cfg["username"], safe="")
        pwd = urllib.parse.quote(cfg["password"], safe="")
        url = f"rtsp://{user}:{pwd}@{cfg['ip']}:{cfg.get('port', 554)}/{cfg.get('stream', 'stream1')}"
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("Failed to grab frame from camera.")
            sys.exit(1)

    states = detect_knob_states(frame)
    for s in states:
        status = "ON" if s["is_on"] else "OFF"
        print(f"{s['name']}: {status}  (diff={s['brightness_diff']:.0f})")

    annotated = draw_knob_states(frame, states)
    cv2.imwrite("knob_status.jpg", annotated)

    crop = annotated[460:620, 960:1450]
    crop_big = cv2.resize(crop, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    cv2.imwrite("knob_status_zoom.jpg", crop_big)
    print("\nSaved knob_status.jpg and knob_status_zoom.jpg")
