# Security

Please report vulnerabilities privately through
[GitHub security advisories](https://github.com/gsus67/omarchy-cooler-lcd-5131/security/advisories/new)
instead of a public issue.

The daemon and bootstrap run as the desktop user, never root. Only `setup.sh`
needs sudo to install a root-owned udev rule restricted to hidraw 5131:2007 and,
on boards with a measured CPU fan header, a fixed entry in
`/etc/modules-load.d` for the matching in-tree sensor driver; `uninstall.sh`
requests sudo to remove them. There are no world-writable device modes, extra
groups, privileged power helpers or changes to RAPL permissions.

`setup.sh` runs as root from the plugin checkout, which the desktop user can
write, after an explicit click and password prompt or a manual `sudo`. A process
already running as that user could alter it before it is approved, as it could
with the plugin's other files. Run it only on a checkout you trust.
The user unit restricts privileges, filesystem writes and socket families,
while retaining the device access needed for HID and optional `nvidia-smi`.

Every change runs, in CI:

- Python tests for frames, sensors, USB discovery, bootstrap and the manifest;
- the QML security checks copied from omarchy-trcc: plain text and no remote URLs;
- `systemd-analyze verify` for the generated user unit;
- ShellCheck for all shell scripts and zizmor for workflows;
- CodeQL `security-extended` analysis for Python and GitHub Actions.
