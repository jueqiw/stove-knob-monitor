# Stove Knob Monitor

A safety system that watches a kitchen stove via a Tapo camera and alerts you when a **burner is ON but no pot/pan is on it**.

## How It Works

```
1. Grab a frame from the Tapo camera

2. Check knob positions (local, free)
   - White dot stickers on knobs — compare brightness at dot vs surrounding knob
   - Dot brighter than knob → OFF | Same brightness → knob turned → ON

3. Any burner ON?
   ├── NO  → Sleep 1 hour, repeat
   └── YES → Send stove image to Groq API (Llama 4 vision)
             Compare current image vs empty stove reference
             ├── Pot detected    → Safe, no alert
             └── No pot detected → ALERT! Save snapshot + send email
```

## Quick Start

```bash
pip install opencv-python numpy pyyaml openai  # openai SDK also used for Groq API

cp config.example.yaml config.yaml  # fill in your credentials

python3 main.py          # run continuous monitoring
python3 main.py --once   # single check (for testing)
```

## Configuration

See `config.example.yaml` — you need:
- **Tapo camera** RTSP credentials (set in Tapo App → Advanced Settings → Camera Account)
- **Groq API key** (free at https://console.groq.com/)
- **Gmail app password** for email alerts (https://myaccount.google.com/apppasswords)

## Calibration

1. Place white dot stickers on each knob at the indicator mark (knobs in OFF position)
2. Run `click_position.py snapshot.jpg` to get dot pixel coordinates
3. Update the `KNOBS` list in `knob_detector.py`
4. Save an empty stove reference image as `empty_stove_ref.jpg`

## Project Structure

```
main.py              # Monitoring loop
knob_detector.py     # Knob ON/OFF detection (OpenCV)
pot_detector.py      # Pot detection (Groq vision API)
alert.py             # Email alerts with cooldown
video_source.py      # RTSP/file/webcam capture
config.example.yaml  # Example config (copy to config.yaml)
```
