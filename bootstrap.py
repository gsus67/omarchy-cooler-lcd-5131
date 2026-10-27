#!/usr/bin/env python3
"""Install and enable the user unit when Omarchy loads this plugin."""
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys

from cooler_lcd.device import send

UNIT = "omarchy-cooler-lcd-5131.service"


def unit_path(value):
    """A literal path for WorkingDirectory=, which takes it unquoted."""
    value = str(value)
    if not value.startswith("/") or any(ord(c) < 32 or c in '\\"' for c in value):
        raise ValueError("Invalid installation path.")
    return value.replace("%", "%%")


def unit_content(source):
    return "\n".join([
        "[Unit]", "Description=Omarchy Cooler LCD 5131 — 5131:2007 HID display",
        "After=graphical-session.target", "PartOf=graphical-session.target", "",
        "[Service]", "Type=simple", "WorkingDirectory=" + unit_path(source),
        "ExecStart=/usr/bin/python3 -B -m cooler_lcd",
        "Restart=on-failure", "RestartSec=3", "UMask=0077",
        "NoNewPrivileges=true", "ProtectSystem=strict", "ProtectHome=read-only",
        "PrivateTmp=true", "RestrictAddressFamilies=AF_UNIX",
        "ProtectKernelTunables=true", "ProtectKernelModules=true", "ProtectControlGroups=true",
        "CapabilityBoundingSet=", "RestrictSUIDSGID=true", "RestrictRealtime=true",
        "RestrictNamespaces=true", "LockPersonality=true", "SystemCallArchitectures=native", "",
        "[Install]", "WantedBy=graphical-session.target", "",
    ])


def run(*command):
    reply = subprocess.run(command, capture_output=True, text=True, timeout=30)
    if reply.returncode:
        raise RuntimeError(reply.stderr.strip() or reply.stdout.strip() or "Command failed: " + command[0])


def ensure(source):
    if os.geteuid() == 0:
        raise ValueError("Run the plugin as your desktop user, never as root.")
    source = Path(source).resolve()
    if not (source / "cooler_lcd/__main__.py").is_file():
        raise ValueError("Plugin daemon not found.")
    config = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    unit = config / "systemd/user" / UNIT
    content = unit_content(source)
    changed = not unit.exists() or unit.read_text() != content
    if changed:
        unit.parent.mkdir(parents=True, exist_ok=True)
        temporary = unit.with_suffix(".tmp")
        temporary.write_text(content)
        temporary.replace(unit)
        run("systemctl", "--user", "daemon-reload")
    run("systemctl", "--user", "enable", "--now", UNIT)
    # Pick up Python changes on a plugin update or a shell reload.
    run("systemctl", "--user", "restart", UNIT)
    return {"ok": True, "needsSetup": send(None) == "no_permission",
            "setupCommand": "sudo bash " + shlex.quote(str(source / "setup.sh"))}


if __name__ == "__main__":
    try:
        print(json.dumps(ensure(sys.argv[1] if len(sys.argv) > 1 else Path(__file__).parent)))
    except (OSError, RuntimeError, ValueError, subprocess.TimeoutExpired) as error:
        print(json.dumps({"ok": False, "message": str(error)}))
        sys.exit(1)
