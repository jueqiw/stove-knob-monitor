"""
Pot/pan presence detection using vision API.

Supports OpenAI (GPT-4o) and Google Gemini.
Sends a cropped image of the stove top and asks whether
pots/pans are present on each burner.
"""

import base64
import cv2
import json
import logging
import yaml
from typing import Optional

logger = logging.getLogger(__name__)

# Stove top crop region in full frame (2304x1296)
STOVE_TOP_REGION = (780, 500, 1450, 850)  # x1, y1, x2, y2

EMPTY_STOVE_REF = "empty_stove_ref.jpg"

PROMPT = """I'm showing you two images of a kitchen from a security camera.

Image 1: REFERENCE — this is the stove when it's EMPTY (no pots/pans).
Image 2: CURRENT — this is the kitchen right now.

Tell me:
1. Is there a person visible in the CURRENT image?
2. Is there a pot, pan, or any cookware on any burner that was NOT in the REFERENCE image?

Respond in JSON format only, no other text:
{
  "person_present": true/false,
  "burners": [
    {"position": "front-left", "has_pot": true/false, "description": "brief description"}
  ]
}"""


def _load_config() -> dict:
    with open("config.yaml") as f:
        return yaml.safe_load(f)


def _encode_image(img) -> str:
    """Encode an image as base64 JPEG."""
    _, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return base64.b64encode(buf.tobytes()).decode()


def _get_images(frame) -> tuple:
    """Return (reference_b64, current_b64).

    Reference is the empty stove crop. Current is the full frame
    so Groq can detect both people and pots.
    """
    ref = cv2.imread(EMPTY_STOVE_REF)
    return _encode_image(ref), _encode_image(frame)


def _make_openai_messages(ref_b64: str, cur_b64: str) -> list:
    """Build OpenAI-compatible messages with reference + current images."""
    return [
        {
            "role": "user",
            "content": [
                {"type": "text", "text": PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{ref_b64}"}},
                {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{cur_b64}"}},
            ],
        }
    ]


def _call_gemini(ref_b64: str, cur_b64: str, config: dict) -> str:
    """Call Gemini API and return response text."""
    from google import genai

    gem_cfg = config["gemini"]
    client = genai.Client(api_key=gem_cfg["api_key"])

    response = client.models.generate_content(
        model=gem_cfg.get("model", "gemini-2.0-flash"),
        contents=[
            {
                "parts": [
                    {"text": PROMPT},
                    {"inline_data": {"mime_type": "image/jpeg", "data": ref_b64}},
                    {"inline_data": {"mime_type": "image/jpeg", "data": cur_b64}},
                ]
            }
        ],
    )
    return response.text.strip()


def _call_openai(ref_b64: str, cur_b64: str, config: dict) -> str:
    """Call OpenAI API and return response text."""
    from openai import OpenAI

    ai_cfg = config["openai"]
    client = OpenAI(api_key=ai_cfg["api_key"])

    response = client.chat.completions.create(
        model=ai_cfg.get("model", "gpt-4o-mini"),
        messages=_make_openai_messages(ref_b64, cur_b64),
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


def _call_groq(ref_b64: str, cur_b64: str, config: dict) -> str:
    """Call Groq API (OpenAI-compatible) and return response text."""
    from openai import OpenAI

    groq_cfg = config["groq"]
    client = OpenAI(api_key=groq_cfg["api_key"], base_url=groq_cfg["base_url"])

    response = client.chat.completions.create(
        model=groq_cfg.get("model", "meta-llama/llama-4-scout-17b-16e-instruct"),
        messages=_make_openai_messages(ref_b64, cur_b64),
        max_tokens=500,
    )
    return response.choices[0].message.content.strip()


def detect_pots(frame, config: Optional[dict] = None) -> dict:
    """Send stove top image to vision API and check for pots/pans.

    Sends both a reference (empty stove) and current image for comparison.
    Tries Groq first, then Gemini, then OpenAI as fallback.
    """
    if config is None:
        config = _load_config()

    ref_b64, cur_b64 = _get_images(frame)

    errors = []
    for name, fn in [("groq", _call_groq), ("gemini", _call_gemini), ("openai", _call_openai)]:
        if name not in config:
            continue
        try:
            text = fn(ref_b64, cur_b64, config)
            # Strip markdown code fences
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            result = json.loads(text)
            logger.info("Pot detection via %s: %s", name, result)
            return result
        except Exception as e:
            logger.warning("Failed with %s: %s", name, e)
            errors.append(f"{name}: {e}")

    raise RuntimeError(f"All vision APIs failed: {'; '.join(errors)}")


def any_pot_present(result: dict) -> bool:
    """Check if any burner has a pot/pan."""
    return any(b.get("has_pot", False) for b in result.get("burners", []))


def person_present(result: dict) -> bool:
    """Check if a person is visible."""
    return result.get("person_present", False)


if __name__ == "__main__":
    import sys
    import urllib.parse

    config = _load_config()

    if len(sys.argv) > 1:
        frame = cv2.imread(sys.argv[1])
    else:
        cam = config["camera"]
        user = urllib.parse.quote(cam["username"], safe="")
        pwd = urllib.parse.quote(cam["password"], safe="")
        url = f"rtsp://{user}:{pwd}@{cam['ip']}:{cam.get('port', 554)}/{cam.get('stream', 'stream1')}"
        cap = cv2.VideoCapture(url, cv2.CAP_FFMPEG)
        ret, frame = cap.read()
        cap.release()
        if not ret:
            print("Failed to grab frame.")
            sys.exit(1)

    # Save the stove crop for inspection
    x1, y1, x2, y2 = STOVE_TOP_REGION
    cv2.imwrite("stove_crop.jpg", frame[y1:y2, x1:x2])
    print("Saved stove_crop.jpg")

    result = detect_pots(frame, config)
    print(json.dumps(result, indent=2))

    if any_pot_present(result):
        print("\n>> POT/PAN DETECTED on stove")
    else:
        print("\n>> No pots/pans on stove")
