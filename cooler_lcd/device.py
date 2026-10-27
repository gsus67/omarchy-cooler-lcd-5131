"""Discover by HID identity on every tick, including after unplug or resume."""
import errno
import os
from pathlib import Path

HID_ID = "0003:00005131:00002007"


def discover(sys_root=Path("/sys"), dev_root=Path("/dev")):
    devices = []
    for path in sorted((Path(sys_root) / "class/hidraw").glob("hidraw*")):
        try:
            fields = dict(line.split("=", 1) for line in (path / "device/uevent").read_text().splitlines() if "=" in line)
            if fields.get("HID_ID", "").upper() == HID_ID:
                devices.append(Path(dev_root) / path.name)
        except (OSError, ValueError):
            continue
    return devices


def send(frame, sys_root=Path("/sys"), dev_root=Path("/dev")):
    """Open only matched nodes; None probes permission without sending.

    Opening afresh avoids stale handles after suspend or hidraw number reuse.
    Never send a partial report's remainder as a second HID report.
    """
    status = "not_found"
    for path in discover(sys_root, dev_root):
        try:
            descriptor = os.open(path, os.O_WRONLY | os.O_NONBLOCK | os.O_CLOEXEC)
            try:
                if frame is not None and os.write(descriptor, frame) != len(frame):
                    raise OSError(errno.EIO, "short HID report")
            finally:
                os.close(descriptor)
            return "found"
        except PermissionError:
            status = "no_permission"
        except OSError:
            if status != "no_permission":
                status = "disconnected"
    return status
