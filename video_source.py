"""
Video source abstraction for RTSP streams, local files, and webcams.

Provides a unified interface to capture frames regardless of the source type.
Handles RTSP reconnection and frame retrieval with consistent error handling.
"""

import cv2
import logging
import time
from typing import Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


class VideoSource:
    """Unified video capture from RTSP, file, or webcam sources."""

    def __init__(
        self,
        source: str | int,
        reconnect_delay: float = 5.0,
        max_reconnect_attempts: int = 10,
    ):
        """
        Args:
            source: RTSP URL string, file path string, or webcam index int.
            reconnect_delay: Seconds to wait between RTSP reconnection attempts.
            max_reconnect_attempts: Max consecutive reconnect tries before giving up.
        """
        self.source = self._parse_source(source)
        self.reconnect_delay = reconnect_delay
        self.max_reconnect_attempts = max_reconnect_attempts
        self._cap: Optional[cv2.VideoCapture] = None
        self._is_rtsp = isinstance(self.source, str) and self.source.startswith("rtsp://")
        self._is_file = isinstance(self.source, str) and not self._is_rtsp
        self._reconnect_count = 0

    @staticmethod
    def _parse_source(source: str | int) -> str | int:
        """Convert source argument to the appropriate type."""
        if isinstance(source, int):
            return source
        # Allow passing webcam index as string (e.g. from CLI args)
        try:
            return int(source)
        except ValueError:
            return source

    def open(self) -> bool:
        """Open the video source. Returns True on success."""
        self._release_capture()

        if self._is_rtsp:
            # Use TCP transport for more reliable RTSP streaming
            self._cap = cv2.VideoCapture(self.source, cv2.CAP_FFMPEG)
            if self._cap.isOpened():
                self._cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        else:
            self._cap = cv2.VideoCapture(self.source)

        if self.is_opened:
            self._reconnect_count = 0
            w, h = self.frame_size
            logger.info("Opened video source: %s (%dx%d @ %.1f fps)", self.source, w, h, self.fps)
            return True

        logger.error("Failed to open video source: %s", self.source)
        return False

    def read(self) -> Tuple[bool, Optional[np.ndarray]]:
        """
        Read a single frame.

        For RTSP sources, automatically attempts reconnection on failure.
        Returns (success, frame) tuple.
        """
        if not self.is_opened:
            if self._is_rtsp:
                return self._try_reconnect()
            return False, None

        ret, frame = self._cap.read()

        if not ret:
            if self._is_rtsp:
                logger.warning("RTSP frame read failed, attempting reconnect...")
                return self._try_reconnect()
            if self._is_file:
                logger.info("End of video file reached.")
            return False, None

        return True, frame

    def _try_reconnect(self) -> Tuple[bool, Optional[np.ndarray]]:
        """Attempt to reconnect to an RTSP stream."""
        while self._reconnect_count < self.max_reconnect_attempts:
            self._reconnect_count += 1
            logger.info(
                "RTSP reconnect attempt %d/%d in %.1fs...",
                self._reconnect_count,
                self.max_reconnect_attempts,
                self.reconnect_delay,
            )
            time.sleep(self.reconnect_delay)

            if self.open():
                ret, frame = self._cap.read()
                if ret:
                    return True, frame

        logger.error("Exceeded max RTSP reconnect attempts (%d).", self.max_reconnect_attempts)
        return False, None

    @property
    def is_opened(self) -> bool:
        return self._cap is not None and self._cap.isOpened()

    def _get_prop(self, prop: int, default: float = 0.0) -> float:
        """Read a capture property, returning default if not opened."""
        if self.is_opened:
            return self._cap.get(prop) or default
        return default

    @property
    def fps(self) -> float:
        return self._get_prop(cv2.CAP_PROP_FPS, 30.0)

    @property
    def frame_size(self) -> Tuple[int, int]:
        """Returns (width, height)."""
        return (
            int(self._get_prop(cv2.CAP_PROP_FRAME_WIDTH)),
            int(self._get_prop(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def release(self) -> None:
        """Release the video capture resource."""
        self._release_capture()
        logger.info("Video source released.")

    def _release_capture(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
        return False
