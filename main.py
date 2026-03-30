"""
Stove Knob Monitor — Main monitoring loop.

Watches the kitchen stove via a Tapo camera and detects a dangerous
condition: a burner is ON but no pot/pan is on the stove.
Sends an alert when this is detected.
"""

import argparse
import logging
import time
import urllib.parse
import cv2
import yaml

from alert import AlertManager
from knob_detector import detect_knob_states, draw_knob_states
from pot_detector import detect_pots, any_pot_present, person_present

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def build_rtsp_url(cam: dict) -> str:
    user = urllib.parse.quote(cam["username"], safe="")
    pwd = urllib.parse.quote(cam["password"], safe="")
    return f"rtsp://{user}:{pwd}@{cam['ip']}:{cam.get('port', 554)}/{cam.get('stream', 'stream1')}"


def grab_frame(source):
    """Grab a single frame from RTSP, file, or webcam."""
    cap = cv2.VideoCapture(source, cv2.CAP_FFMPEG)
    ret, frame = cap.read()
    cap.release()
    if not ret or frame is None:
        return None
    return frame


POT_CHECK_INTERVAL = 3600  # seconds — check pots via API every 1 hour
_last_pot_check: float = 0
_last_pot_result: bool = False  # True if pot was present last check
_last_person_result: bool = False  # True if person was detected last check
_burner_was_off: bool = True  # Track if burners were previously all OFF


def check_stove(frame, config: dict, alert_mgr: AlertManager) -> None:
    """Run one detection cycle: check knobs, check pots, alert if needed.

    Knob detection runs every cycle (local, free).
    Pot detection via API runs:
      - Immediately when a burner first turns ON
      - Then every POT_CHECK_INTERVAL (1 hour) while burner stays ON
    """
    global _last_pot_check, _last_pot_result, _burner_was_off, _last_person_result

    now = time.time()
    time_since_last_check = now - _last_pot_check
    need_api_check = _burner_was_off or time_since_last_check >= POT_CHECK_INTERVAL

    # Step 1: Groq API check — person + pot (once at start, then every 1 hour)
    if need_api_check:
        try:
            result = detect_pots(frame, config)
            _last_person_result = person_present(result)
            _last_pot_result = any_pot_present(result)
            _last_pot_check = now
            logger.info("Groq check: person=%s, pot=%s",
                        _last_person_result, _last_pot_result)
        except Exception as e:
            logger.error("Groq check failed: %s", e)
            _last_person_result = False
            _last_pot_result = False
    else:
        remaining = POT_CHECK_INTERVAL - time_since_last_check
        logger.info("Using cached Groq result (next check in %.0f min)", remaining / 60)

    # Step 2: If person detected → safe, skip everything
    if _last_person_result:
        logger.info("Person in kitchen — no action needed.")
        return

    # Step 3: Check knob states (local, fast, every cycle)
    knob_states = detect_knob_states(frame)
    on_knobs = [s["name"] for s in knob_states if s["is_on"]]

    if not on_knobs:
        logger.info("All burners OFF.")
        _burner_was_off = True
        return

    logger.info("Burners ON: %s", ", ".join(on_knobs))
    _burner_was_off = False

    # Step 4: Alert if burner ON and no pot
    if not _last_pot_result:
        message = f"DANGER: {', '.join(on_knobs)} ON but no pot/pan detected on stove!"
        alert_mgr.send_alert(frame, message)
    else:
        logger.info("Pot detected on stove — no alert needed.")


def main():
    parser = argparse.ArgumentParser(description="Stove Knob Monitor")
    parser.add_argument("--source", default=None,
                        help="Video source: RTSP URL, file path, or webcam index. "
                             "Defaults to camera in config.yaml.")
    parser.add_argument("--interval", type=int, default=3600,
                        help="Seconds between checks when all burners OFF (default: 3600 = 1 hour)")
    parser.add_argument("--active-interval", type=int, default=10,
                        help="Seconds between checks when a burner is ON (default: 10)")
    parser.add_argument("--once", action="store_true",
                        help="Run one check and exit (for testing)")
    args = parser.parse_args()

    config = load_config()
    alert_mgr = AlertManager(config)

    # Determine source
    if args.source:
        try:
            source = int(args.source)
        except ValueError:
            source = args.source
    else:
        source = build_rtsp_url(config["camera"])

    logger.info("Starting Stove Knob Monitor (idle=%ds, active=%ds)",
                args.interval, args.active_interval)
    logger.info("Source: %s", source if not isinstance(source, str) or "://" not in source
                else source.split("@")[-1])  # hide credentials in log

    while True:
        frame = grab_frame(source)
        if frame is None:
            logger.warning("Failed to grab frame, retrying in %ds...", args.active_interval)
            time.sleep(args.active_interval)
            continue

        try:
            check_stove(frame, config, alert_mgr)
        except Exception as e:
            logger.error("Error during check: %s", e)

        if args.once:
            break

        # Sleep longer when idle, shorter when a burner is ON
        if _burner_was_off:
            time.sleep(args.interval)
        else:
            time.sleep(args.active_interval)


if __name__ == "__main__":
    main()
