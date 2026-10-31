#!/usr/bin/env bash
set -euo pipefail
if (( EUID == 0 )); then
  echo 'Run uninstall.sh as your desktop user; sudo is requested only to remove system files.' >&2
  exit 1
fi

config_root="${XDG_CONFIG_HOME:-$HOME/.config}"
omarchy plugin disable io.github.gsus67.omarchy-cooler-lcd-5131 2>/dev/null || true
systemctl --user disable --now omarchy-cooler-lcd-5131.service 2>/dev/null || true
rm -f -- "$config_root/systemd/user/omarchy-cooler-lcd-5131.service"
systemctl --user daemon-reload
if [[ -f /etc/udev/rules.d/70-omarchy-cooler-lcd-5131.rules ]]; then
  sudo rm -f /etc/udev/rules.d/70-omarchy-cooler-lcd-5131.rules
  sudo udevadm control --reload-rules
  sudo udevadm trigger --subsystem-match=hidraw
fi
if [[ -f /etc/modules-load.d/omarchy-cooler-lcd-5131.conf ]]; then
  sudo rm -f /etc/modules-load.d/omarchy-cooler-lcd-5131.conf
fi
echo 'Cooler display service removed. The panel keeps the last values sent.'
