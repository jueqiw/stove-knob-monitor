"""
Alert system for stove monitor.

Sends email with snapshot when a dangerous condition is detected.
Includes cooldown to avoid spamming.
"""

import cv2
import logging
import smtplib
import time
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional

logger = logging.getLogger(__name__)


class AlertManager:
    """Manages alert sending with cooldown."""

    def __init__(self, config: dict):
        self._cfg = config.get("alert", {})
        self._last_alert_time: float = 0
        self._cooldown = self._cfg.get("cooldown_seconds", 300)

    def _in_cooldown(self) -> bool:
        return (time.time() - self._last_alert_time) < self._cooldown

    def send_alert(self, frame, message: str) -> bool:
        """Send an alert with snapshot image.

        Returns True if alert was sent, False if in cooldown.
        """
        if self._in_cooldown():
            remaining = self._cooldown - (time.time() - self._last_alert_time)
            logger.info("Alert cooldown active (%.0fs remaining), skipping.", remaining)
            return False

        # Save snapshot
        snapshot_path = "alert_snapshot.jpg"
        cv2.imwrite(snapshot_path, frame)
        logger.warning("ALERT: %s (snapshot saved to %s)", message, snapshot_path)

        # Try email
        if self._cfg.get("app_password"):
            self._send_email(frame, message)
        else:
            logger.info("Email not configured (no app_password). Alert logged only.")

        self._last_alert_time = time.time()
        return True

    def _send_email(self, frame, message: str) -> None:
        """Send email with snapshot attachment."""
        try:
            msg = MIMEMultipart()
            msg["From"] = self._cfg["email_from"]
            msg["To"] = self._cfg["email_to"]
            msg["Subject"] = "⚠️ Stove Alert: Burner ON without pot!"

            body = f"{message}\n\nSee attached snapshot from the kitchen camera."
            msg.attach(MIMEText(body, "plain"))

            # Attach snapshot
            _, buf = cv2.imencode(".jpg", frame)
            img = MIMEImage(buf.tobytes(), name="stove_alert.jpg")
            msg.attach(img)

            with smtplib.SMTP(self._cfg["smtp_server"], self._cfg["smtp_port"]) as server:
                server.starttls()
                server.login(self._cfg["email_from"], self._cfg["app_password"])
                server.send_message(msg)

            logger.info("Alert email sent to %s", self._cfg["email_to"])
        except Exception as e:
            logger.error("Failed to send alert email: %s", e)
