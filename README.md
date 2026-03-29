# Stove Knob Monitor

A Python application that monitors a kitchen stove via a Tapo security camera to detect a dangerous condition: **a burner is ON but no pot/pan is on it**. When detected, the system sends an email alert with a snapshot.

## How It Works

```
Loop forever:

  1. Grab a frame from the Tapo camera

  2. Check each knob's white dot brightness (local, free)
     - Compare dot position brightness vs surrounding knob
     - If dot is much brighter than knob → dot still there → OFF
     - If dot is same/darker than knob → dot moved away → ON

  3. Are any burners ON?
     │
     ├── NO → All safe. Sleep 1 HOUR, go to step 1.
     │
     └── YES → Is this the first time we noticed it's ON?
               │
               ├── YES → Send image to Groq API NOW
               │         "Is there a pot on the stove?"
               │         (compares current image vs empty stove reference)
               │
               └── NO → Has it been 1 hour since last Groq check?
                         │
                         ├── YES → Send image to Groq again
                         └── NO  → Use the answer from last time

               Does Groq say there's a pot?
               │
               ├── YES → Safe. No alert. Sleep 10 SECONDS, go to step 1.
               │
               └── NO  → DANGER! Burner ON + No pot!
                         → Save snapshot
                         → Send email alert
                         → Wait 5 min cooldown (don't spam)
                         → Sleep 10 SECONDS, go to step 1.
```

## Two Detection Methods

### 1. Burner State Detection (Knob Tracking)

White dot stickers are placed on each black stove knob at the indicator mark. The system checks if the dot is still at its calibrated OFF position by comparing brightness:

- **Relative brightness comparison** — compares the dot position to the surrounding knob surface, so it works regardless of lighting conditions
- Pure OpenCV, no ML, runs locally

### 2. Pot/Pan Presence Detection (Vision AI)

When a burner is ON, a cropped image of the stove top is sent to the Groq API (Llama 4 Scout vision model) along with a reference image of the empty stove. The AI compares the two images and reports whether any cookware is present on each burner.

## Setup

### Requirements

```bash
pip install opencv-python numpy pyyaml openai
```

### Camera Setup

1. Set up a Tapo camera (tested with C110) pointing at the stove
2. Create a Camera Account in the Tapo app (Advanced Settings → Camera Account)

### Knob Stickers

1. Place small white dot stickers (5-8mm) on each knob at the indicator mark
2. Make sure all knobs are in the OFF position
3. Run `click_position.py` to identify the exact dot pixel coordinates
4. Update the `KNOBS` list in `knob_detector.py` with the coordinates

### Reference Image

With the stove empty (no pots/pans), run:

```bash
python3 -c "
import cv2, yaml, urllib.parse
with open('config.yaml') as f:
    cfg = yaml.safe_load(f)['camera']
user = urllib.parse.quote(cfg['username'], safe='')
pwd = urllib.parse.quote(cfg['password'], safe='')
url = f'rtsp://{user}:{pwd}@{cfg[\"ip\"]}:{cfg.get(\"port\",554)}/{cfg.get(\"stream\",\"stream1\")}'
cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
ret, frame = cap.read()
cap.release()
cv2.imwrite('empty_stove_ref.jpg', frame[500:850, 780:1450])
"
```

### Configuration

Edit `config.yaml`:

```yaml
camera:
  ip: "192.168.1.155"
  username: "your-camera-username"
  password: "your-camera-password"
  port: 554
  stream: "stream1"

alert:
  email_to: "recipient@gmail.com"
  email_from: "sender@gmail.com"
  smtp_server: "smtp.gmail.com"
  smtp_port: 587
  app_password: ""  # Gmail app password
  cooldown_seconds: 300

groq:
  api_key: "your-groq-api-key"
  base_url: "https://api.groq.com/openai/v1"
  model: "meta-llama/llama-4-scout-17b-16e-instruct"
```

### Gmail App Password

To enable email alerts:
1. Go to https://myaccount.google.com/apppasswords
2. Create an app password for "Mail"
3. Add it to `config.yaml` under `alert.app_password`

### Groq API Key (Free)

1. Go to https://console.groq.com/
2. Sign up and create an API key
3. Add it to `config.yaml` under `groq.api_key`

## Usage

```bash
# Run continuous monitoring
python3 main.py

# Run a single check (for testing)
python3 main.py --once

# Custom intervals
python3 main.py --interval 1800 --active-interval 30

# Run in background
python3 main.py > monitor.log 2>&1 &
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--interval` | 3600 | Seconds between checks when all burners OFF (1 hour) |
| `--active-interval` | 10 | Seconds between checks when a burner is ON |
| `--source` | config.yaml | RTSP URL, video file, or webcam index |
| `--once` | - | Run one check and exit |

## Project Structure

```
code/
├── main.py              # Entry point — monitoring loop
├── knob_detector.py     # White dot brightness detection for ON/OFF
├── pot_detector.py      # Groq vision API for pot/pan detection
├── alert.py             # Email alerts with cooldown
├── video_source.py      # RTSP/file/webcam capture abstraction
├── config.yaml          # Configuration (gitignored — contains secrets)
├── empty_stove_ref.jpg  # Reference image of empty stove
├── CLAUDE.md            # Project documentation
└── README.md            # This file
```

## Tech Stack

- Python 3, OpenCV, NumPy
- Groq API (Llama 4 Scout) for vision-based pot detection
- smtplib for email alerts
- Tapo camera RTSP stream
