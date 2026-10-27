"""Send one Celsius report per second for the lifetime of the user service."""
import logging
import os
import time

from .device import send
from .protocol import build_frame
from .sensors import Sensors


def main():
    if os.geteuid() == 0:
        raise SystemExit("Run Omarchy Cooler LCD as your desktop user, never as root.")
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sensors = Sensors()
    previous_status = None
    while True:
        started = time.monotonic()
        status = send(build_frame(sensors.sample()))
        if status != previous_status:
            logging.info("Cooler display: %s", status)
            previous_status = status
        time.sleep(max(0, 1 - (time.monotonic() - started)))


if __name__ == "__main__":
    main()
