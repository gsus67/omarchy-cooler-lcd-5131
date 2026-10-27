# Credits and license

Omarchy Cooler LCD, author **gsus**, is licensed under **GPL-3.0-or-later**;
see [LICENSE](LICENSE) for the GPL version 3 text.

- [YehanKD/csm-cooler-lcd](https://github.com/YehanKD/csm-cooler-lcd):
  reverse engineering and documentation of the CSM / Alseye / COOLMOON 0x40 HID
  protocol and the misleading 5131:2007 USB database label.
- [ZarateBM/thermax-pulsar-linux](https://github.com/ZarateBM/thermax-pulsar-linux):
  related Linux work for THERMAX 6 Pulsar cooler displays.
- [gsus67/omarchy-trcc](https://github.com/gsus67/omarchy-trcc), GPL-3.0-or-later:
  plugin conventions, bootstrap and installer patterns, CI action pins,
  GPL license text and the copied QML security test.

The daemon is restructured from the local Python standard-library prototype
verified on the CyberPowerPC GMA6000BSTV6 ARGB Air Cool (CPU 42 °C). It uses the
verified byte layout in this project's task; it does not include the TRCC C++
engine or the unsupported 0x00/0x01/0x02 firmware protocol.
