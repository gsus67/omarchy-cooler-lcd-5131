"""Pure builder for the verified 65-byte 0x40 HID output report."""
from dataclasses import dataclass
from datetime import datetime
import math

# Bit 7 requests Fahrenheit from the firmware. This plugin always sends Celsius.
FAHRENHEIT_FLAG = 0x80


@dataclass
class Readings:
    cpu_temp: float = 0
    cpu_usage: float = 0
    cpu_mhz: float = 0
    cpu_rpm: float = 0
    cpu_watts: float = 0
    gpu_temp: float = 0
    gpu_usage: float = 0
    gpu_mhz: float = 0
    gpu_rpm: float = 0
    gpu_watts: float = 0


def clamp(value, maximum):
    """Truncate and saturate readings; unusable numbers represent unavailable data."""
    try:
        return max(0, min(int(value), maximum)) if math.isfinite(value) else 0
    except (TypeError, ValueError, OverflowError):
        return 0


def build_frame(readings, now=None):
    now = now if now is not None else datetime.now()  # Local wall clock.
    frame = bytearray(65)
    frame[1] = 0x40
    frame[2] = clamp(readings.cpu_temp, FAHRENHEIT_FLAG - 1)
    frame[3] = clamp(readings.cpu_usage, 100)
    frame[10] = clamp(readings.gpu_temp, FAHRENHEIT_FLAG - 1)
    frame[11] = clamp(readings.gpu_usage, 100)
    for offset, value in (
        (4, readings.cpu_mhz), (6, readings.cpu_rpm), (8, readings.cpu_watts),
        (12, readings.gpu_mhz), (14, readings.gpu_rpm), (16, readings.gpu_watts),
        (24, now.year),
    ):
        frame[offset:offset + 2] = clamp(value, 65535).to_bytes(2, "big")
    frame[26:30] = bytes((now.month, now.day, now.hour, now.minute))
    frame[30] = sum(frame[1:30]) & 0xFF
    return bytes(frame)
