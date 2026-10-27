import json
import os
from pathlib import Path
import shlex
import tempfile
import unittest
from unittest.mock import Mock, call, patch

import bootstrap

ROOT = Path(__file__).resolve().parent.parent


class BootstrapTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.config = Path(temporary.name) / "config"
        for replacement in (patch.dict(os.environ, {"XDG_CONFIG_HOME": str(self.config)}),
                            patch("bootstrap.os.geteuid", return_value=1000)):
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_installs_and_enables_only_user_unit_idempotently(self):
        with patch("bootstrap.run") as run, patch("bootstrap.send", return_value="not_found"):
            self.assertTrue(bootstrap.ensure(ROOT)["ok"])
            unit = self.config / "systemd/user" / bootstrap.UNIT
            self.assertEqual(unit.read_text(), bootstrap.unit_content(ROOT))
            stamp = unit.stat().st_mtime_ns
            bootstrap.ensure(ROOT)
            self.assertEqual(unit.stat().st_mtime_ns, stamp)
        self.assertEqual(run.call_args_list.count(call("systemctl", "--user", "daemon-reload")), 1)
        self.assertEqual(run.call_args_list.count(call("systemctl", "--user", "enable", "--now", bootstrap.UNIT)), 2)
        self.assertEqual(run.call_args_list.count(call("systemctl", "--user", "restart", bootstrap.UNIT)), 2)
        self.assertTrue(all(item.args[:2] == ("systemctl", "--user") for item in run.call_args_list))
        self.assertEqual([path for path in self.config.rglob("*") if path.is_file()], [unit])

    def test_permission_notification_includes_literal_setup_command(self):
        source = self.config.parent / "plugin's $literal % path"
        (source / "cooler_lcd").mkdir(parents=True)
        (source / "cooler_lcd/__main__.py").touch()
        with patch("bootstrap.run"), patch("bootstrap.send", return_value="no_permission") as send:
            result = bootstrap.ensure(source)
        self.assertTrue(result["needsSetup"])
        self.assertEqual(shlex.split(result["setupCommand"]), ["sudo", "bash", str(source / "setup.sh")])
        send.assert_called_once_with(None)

    def test_accessible_or_absent_device_does_not_request_notification(self):
        for status in ("found", "not_found", "disconnected"):
            with self.subTest(status=status), patch("bootstrap.run"), patch("bootstrap.send", return_value=status):
                self.assertFalse(bootstrap.ensure(ROOT)["needsSetup"])

    def test_root_is_rejected_before_writing_or_starting_service(self):
        with patch("bootstrap.os.geteuid", return_value=0), patch("bootstrap.run") as run:
            with self.assertRaisesRegex(ValueError, "never as root"):
                bootstrap.ensure(ROOT)
        run.assert_not_called()
        self.assertFalse(self.config.exists())

    def test_unit_runs_daemon_with_required_sandbox_and_real_devices(self):
        content = bootstrap.unit_content(ROOT)
        for line in ("ExecStart=/usr/bin/python3 -B -m cooler_lcd", "NoNewPrivileges=true",
                     "ProtectSystem=strict", "PrivateTmp=true", "RestrictAddressFamilies=AF_UNIX",
                     "PartOf=graphical-session.target", "WantedBy=graphical-session.target"):
            self.assertIn(line + "\n", content)
        self.assertNotIn("PrivateDevices=true", content)
        self.assertNotIn("User=root", content)

    def test_unit_paths_escape_quotes_backslashes_and_specifiers(self):
        self.assertEqual(bootstrap.quote('/a b/"c"/d\\e%f'), '"/a b/\\"c\\"/d\\\\e%%f"')
        with self.assertRaises(ValueError):
            bootstrap.quote("/a\nb")

    def test_failed_systemctl_is_reported(self):
        with patch("bootstrap.subprocess.run", return_value=Mock(returncode=1, stderr="failed", stdout="")):
            with self.assertRaisesRegex(RuntimeError, "failed"):
                bootstrap.ensure(ROOT)

    def test_system_commands_have_timeout_and_no_shell(self):
        with patch("bootstrap.subprocess.run", return_value=Mock(returncode=0)) as run:
            bootstrap.run("systemctl", "--user", "daemon-reload")
        self.assertEqual(run.call_args.args[0], ("systemctl", "--user", "daemon-reload"))
        self.assertEqual(run.call_args.kwargs["timeout"], 30)
        self.assertFalse(run.call_args.kwargs.get("shell", False))


class ManifestTests(unittest.TestCase):
    def test_manifest_declares_only_nonvisual_service(self):
        manifest = json.loads((ROOT / "manifest.json").read_text())
        self.assertEqual(manifest["schemaVersion"], 1)
        self.assertEqual(manifest["id"], "io.github.gsus67.omarchy-cooler-lcd-5131")
        self.assertEqual(manifest["name"], "Omarchy Cooler LCD 5131")
        self.assertEqual(manifest["author"], "gsus")
        self.assertEqual(manifest["license"], "GPL-3.0-or-later")
        self.assertRegex(manifest["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(manifest["kinds"], ["service"])
        self.assertEqual(manifest["entryPoints"], {"service": "Service.qml"})
        self.assertTrue((ROOT / manifest["entryPoints"]["service"]).is_file())


if __name__ == "__main__":
    unittest.main()
