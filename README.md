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

Copy the example config and fill in your credentials:

```bash
cp config.example.yaml config.yaml
```

### Tapo Camera (RTSP)

1. Open Tapo App → tap your camera → gear icon → **Advanced Settings** → **Camera Account**
2. Create a username and password
3. Find your camera's IP address in the Tapo App (Settings → Device Info)
4. Fill in `config.yaml`:
   ```yaml
   camera:
     ip: "192.168.1.xxx"
     username: "your-camera-username"
     password: "your-camera-password"
   ```

### Groq API Key (free)

1. Go to https://console.groq.com/ and sign up (Google account works)
2. Go to **API Keys** → **Create API Key**
3. Copy the key and add to `config.yaml`:
   ```yaml
   groq:
     api_key: "gsk_your_key_here"
   ```

### Gmail Email Alerts

1. Go to https://myaccount.google.com/security and enable **2-Step Verification**
2. Go to https://myaccount.google.com/apppasswords
3. Create an app password (name it `stove-monitor`)
4. Copy the 16-character code and add to `config.yaml`:
   ```yaml
   alert:
     email_to: "recipient@gmail.com"
     email_from: "sender@gmail.com"
     app_password: "xxxx xxxx xxxx xxxx"
   ```

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
