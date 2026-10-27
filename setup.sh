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
echo 'Cooler display session access configured. Reconnect USB if permission is still denied.'
