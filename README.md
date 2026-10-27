# omarchy-cooler-lcd-5131 · v0.0.1

**English** · [Español](README.es.md)

Omarchy service for the small temperature display on CPU air coolers with USB
**5131:2007**, using the **0x40 HID protocol**. Python 3 standard library only;
no compiler, pip packages or configuration file. There is no bar widget, panel
or icon.

Verified with the stock **ARGB Air Cool** in a CyberPowerPC **GMA6000BSTV6**
(ASRock B840M-C, Ryzen 7 8700F, RX 9060); the prototype lit the display at 42 °C.

## Identify the device

```sh
lsusb | grep 5131:2007
```

The device has no USB string descriptors. `lsusb` may call it **MSR-101U magnetic
card reader** because of its USB ID database entry.

Only the **0x40 family** (CSM / Alseye / COOLMOON / THERMAX 6 Pulsar) is supported.
Other firmware with the same USB ID uses **0x00/0x01/0x02 opcodes** and is not
supported. The USB ID cannot distinguish them; this driver never probes or
switches protocols. Use it only with the verified family.

## Install

Requires Omarchy Shell with service plugins, Python 3 and systemd. `lsusb` and
`notify-send` are the usual Omarchy tools; `nvidia-smi` is optional.

```sh
omarchy plugin add https://github.com/gsus67/omarchy-cooler-lcd-5131 --enable
```

On load, the plugin installs and enables
`~/.config/systemd/user/omarchy-cooler-lcd-5131.service`, pointing at its checkout.
It runs as your desktop user and never installs packages.

The display needs one permission, granted once and never asked again. If it is
missing, the plugin shows a notification: click it and enter your password in
Omarchy's prompt. Or run the same step from a terminal:

```sh
sudo bash ~/.config/omarchy/plugins/io.github.gsus67.omarchy-cooler-lcd-5131/setup.sh
```

This idempotently installs the root-owned, mode 0644 rule
`/etc/udev/rules.d/70-omarchy-cooler-lcd-5131.rules`, reloads udev and triggers hidraw:

```udev
SUBSYSTEM=="hidraw", ATTRS{idVendor}=="5131", ATTRS{idProduct}=="2007", TAG+="uaccess"
```

Access belongs to the active local session; no world-writable device mode or
extra group is used. Reconnect USB if needed.

## What the display receives

Once per second: CPU and GPU temperature in **°C**, usage %, frequency MHz,
fan RPM, power W, and the local date and time. The firmware controls the layout
and decides which fields are visible. Missing or unreadable values are **0**.

- CPU: `k10temp` Tctl, `coretemp` package or `zenpower`; usage from `/proc/stat`,
  frequency from cpufreq. Only explicitly CPU-labelled fans are used. Power
  comes from readable CPU hwmon values or package RAPL counters.
- GPU: `amdgpu` hwmon and `gpu_busy_percent`; optional `nvidia-smi` for NVIDIA;
  best-effort Intel `i915`/`xe` sysfs readings. One GPU is used. NVIDIA fan RPM
  is unavailable and remains 0.
- CPU fan and power frequently remain 0 without accessible sensors. No
  permission is widened and no RAPL counter is chmodded.

The service rediscovers the HID device by `HID_ID` each second, including after
unplug or suspend. It never assumes a fixed `/dev/hidrawN`. The hardened user
unit has a read-only filesystem, private temporary directory, no new privileges
and only Unix sockets; it keeps access to the real USB devices. When stopped,
the panel latches the last frame. There are no options; Celsius and one second
are fixed. The Fahrenheit protocol bit is documented in the frame builder but
is never sent.

```sh
systemctl --user status omarchy-cooler-lcd-5131.service
journalctl --user -u omarchy-cooler-lcd-5131.service
omarchy plugin update io.github.gsus67.omarchy-cooler-lcd-5131
```

Disabling the shell plugin alone does not stop the independent user unit.
To stop it, use `systemctl --user stop omarchy-cooler-lcd-5131.service`.

## Remove

Run as your desktop user. The script disables the plugin, stops and removes
the user unit and any old plugin configuration, and asks for sudo only to
remove the udev rule. Then remove the checkout:

```sh
bash ~/.config/omarchy/plugins/io.github.gsus67.omarchy-cooler-lcd-5131/uninstall.sh
omarchy plugin remove io.github.gsus67.omarchy-cooler-lcd-5131
```

The user unit respects `XDG_CONFIG_HOME`. No daemon state or settings are stored.

## Development

```sh
python -m unittest discover -s tests
omarchy plugin validate .
```

Tests use temporary sysfs trees and mocked system commands, without touching
hardware. CI also checks the generated user unit with `systemd-analyze verify`,
all shell scripts with ShellCheck, workflows with zizmor, and Python/actions
with CodeQL. See [SECURITY.md](SECURITY.md).

License **GPL-3.0-or-later**. Thanks to
[YehanKD/csm-cooler-lcd](https://github.com/YehanKD/csm-cooler-lcd),
[ZarateBM/thermax-pulsar-linux](https://github.com/ZarateBM/thermax-pulsar-linux)
and [omarchy-trcc](https://github.com/gsus67/omarchy-trcc).
Protocol and code credits are in [NOTICE.md](NOTICE.md).
