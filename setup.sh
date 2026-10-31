#!/usr/bin/env bash
# The only privileged installation step. Run once with sudo from a terminal.
set -euo pipefail
if (( EUID != 0 )); then
  echo 'Run: sudo bash setup.sh' >&2
  exit 1
fi

rule='SUBSYSTEM=="hidraw", ATTRS{idVendor}=="5131", ATTRS{idProduct}=="2007", TAG+="uaccess"'
temporary=$(mktemp)
trap 'rm -f "$temporary"' EXIT
printf '%s\n' "$rule" > "$temporary"
install -o root -g root -m 644 "$temporary" /etc/udev/rules.d/70-omarchy-cooler-lcd-5131.rules
udevadm control --reload-rules
udevadm trigger --subsystem-match=hidraw

# Only boards whose CPU fan header was measured; keep in sync with CPU_FAN_HEADERS in cooler_lcd/sensors.py.
board=$(cat /sys/class/dmi/id/board_name 2>/dev/null || true)
case "$board" in
  'B840M-C') driver=nct6775 ;;
  *) driver= ;;
esac
if [[ -n "$driver" ]]; then
  printf '%s\n' "$driver" > "$temporary"
  install -D -o root -g root -m 644 "$temporary" /etc/modules-load.d/omarchy-cooler-lcd-5131.conf
  modprobe "$driver" || echo "Could not load $driver now; it will be retried at boot." >&2
fi
echo 'Cooler display session access configured. Reconnect USB if permission is still denied.'
