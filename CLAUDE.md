# Stove Knob Monitor

## Project Overview
A Python application that monitors a kitchen stove via a Tapo security camera to detect a dangerous condition: a burner is on (knob rotated) but no pot/pan is on it. Sends email alerts when this is detected.

## Tech Stack
- Python 3.10+
- OpenCV (cv2) — video capture, image processing, HSV filtering
- NumPy — array operations
- smtplib / email — alert delivery
- Optional: Ultralytics YOLOv8 — pot/pan detection

## Project Structure
```
code/
├── CLAUDE.md
├── requirements.txt
├── config.yaml              # User configuration (SMTP, camera, thresholds)
├── config.example.yaml      # Example config (committed, no secrets)
├── main.py                  # Entry point — arg parsing, mode dispatch
├── calibration.py           # Interactive calibration (knob centers, OFF angles, burner ROIs)
├── knob_detector.py         # White-dot HSV filtering, angle calculation, ON/OFF state
├── pot_detector.py          # Pot/pan presence detection (YOLO or contour-based)
├── alert.py                 # Email/notification sending with cooldown logic
├── video_source.py          # RTSP, file, or webcam capture abstraction
├── tuner.py                 # --tune mode: interactive HSV trackbar UI
├── utils.py                 # Shared helpers (drawing, geometry, logging)
├── calibration_data.json    # Generated: saved knob centers, OFF angles, burner ROIs
└── tests/
    └── test_knob_detector.py
```

## Key Concepts

### Knob Detection (pure OpenCV, no ML)
- White dot stickers (5-8mm) on black knobs at the indicator mark
- HSV color filter: H=[0,179], S=[0,50], V=[200,255]
- Detect white dot position → compute angle from calibrated knob center
- Compare angle to calibrated OFF angle → determine ON/OFF + intensity

### Pot/Pan Detection
- Per-burner ROI (region of interest) defined during calibration
- Primary approach: YOLOv8 object detection for pots/pans/cookware
- Fallback: contour/edge detection within the burner ROI
- Each burner ROI is mapped to its corresponding knob

### Alert Logic
- Trigger: burner ON AND no pot/pan detected
- Email alert with snapshot image attached
- Cooldown: configurable window (default 5 min) to avoid spam
- Extended duration alert: burner on 30+ min regardless of pot presence

## Video Sources
- Tapo RTSP: `rtsp://user:pass@ip:554/stream1`
- Local file: path to `.mp4`/`.avi`
- Webcam: integer device index (e.g. `0`)

## Run Modes
```bash
# Calibration: position knobs to OFF, press 'c', click knob centers
python main.py --source rtsp://user:pass@ip:554/stream1 --calibrate

# HSV tuner: interactive trackbars to find white dot color range
python main.py --source video.mp4 --tune

# Monitor: continuous detection + alerting
python main.py --source rtsp://user:pass@ip:554/stream1

# Test with webcam
python main.py --source 0
```

## Configuration (config.yaml)
```yaml
camera:
  source: "rtsp://user:pass@ip:554/stream1"

hsv:
  h_min: 0
  h_max: 179
  s_min: 0
  s_max: 50
  v_min: 200
  v_max: 255

alert:
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  sender: "you@gmail.com"
  password: ""            # use app password
  recipient: "alert@example.com"
  cooldown_seconds: 300
  extended_duration_minutes: 30

detection:
  pot_method: "yolo"      # "yolo" or "contour"
  yolo_model: "yolov8n.pt"
  confidence_threshold: 0.5
  knob_angle_threshold: 15  # degrees from OFF to count as ON
```

## Build & Run
```bash
pip install -r requirements.txt
python main.py --source 0 --tune          # tune HSV first
python main.py --source 0 --calibrate     # calibrate knobs
python main.py --source 0                 # run monitor
```

## Testing
```bash
pytest tests/
```

## Development Guidelines
- Keep knob detection pure OpenCV — no ML models
- All coordinates and angles use OpenCV conventions (origin top-left, clockwise angles)
- Config secrets (passwords) go in `config.yaml` which is gitignored
- `config.example.yaml` is committed with placeholder values
- Use logging module (not print) for operational output
- Type hints on all function signatures
- Each module should be independently testable
