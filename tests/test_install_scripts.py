from pathlib import Path
import os
import subprocess
import tempfile
import unittest

from cooler_lcd.sensors import CPU_FAN_HEADERS

REPO = Path(__file__).resolve().parent.parent
MODULES_CONF = "etc/modules-load.d/omarchy-cooler-lcd-5131.conf"
UDEV_RULE = "etc/udev/rules.d/70-omarchy-cooler-lcd-5131.rules"
INSTALL_STUB = ('#!/usr/bin/env bash\n[[ "$1" == -D ]] && mkdir -p "$(dirname "${@: -1}")"\n'
                'cp "${@: -2:1}" "${@: -1}"\n')
SUDO_STUB = '#!/usr/bin/env bash\nexec "$@"\n'


class InstallScriptTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "commands.log"
        (self.root / UDEV_RULE).parent.mkdir(parents=True)
        for command in ("udevadm", "modprobe", "systemctl", "omarchy"):
            self.stub(command)
        self.stub("install", INSTALL_STUB)
        self.stub("sudo", SUDO_STUB)

    def stub(self, command, body=None):
        path = self.bin / command
        path.write_text(body or f'#!/usr/bin/env bash\necho "{command} $*" >> "{self.log}"\n')
        path.chmod(0o700)

    def run_script(self, name, privilege_check):
        """Run the real script with its absolute paths redirected into the sandbox."""
        text = (REPO / name).read_text()
        self.assertIn(privilege_check, text)
        text = text.replace(privilege_check, "false")
        text = text.replace("/etc/", f"{self.root}/etc/").replace("/sys/", f"{self.root}/sys/")
        script = self.root / name
        script.write_text(text)
        environment = {**os.environ, "HOME": str(self.root / "home"),
                       "PATH": f"{self.bin}:{os.environ['PATH']}"}
        environment.pop("XDG_CONFIG_HOME", None)
        return subprocess.run(["bash", str(script)], env=environment, capture_output=True, text=True)

    def run_setup(self, board=None):
        if board is not None:
            path = self.root / "sys/class/dmi/id/board_name"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(board + "\n")
        return self.run_script("setup.sh", "(( EUID != 0 ))")

    def commands(self):
        return self.log.read_text() if self.log.exists() else ""

    def test_setup_loads_driver_on_verified_board(self):
        result = self.run_setup("B840M-C")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual((self.root / MODULES_CONF).read_text(), "nct6775\n")
        self.assertIn("modprobe nct6775", self.commands())
        self.assertTrue((self.root / UDEV_RULE).exists())

    def test_setup_leaves_other_boards_without_driver(self):
        for board in ("B760 GAMING PLUS WIFI (MS-7D98)", "B840M-C2", "b840m-c", ""):
            with self.subTest(board=board):
                (self.root / UDEV_RULE).unlink(missing_ok=True)
                result = self.run_setup(board)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertFalse((self.root / MODULES_CONF).exists())
                self.assertNotIn("modprobe", self.commands())
                self.assertTrue((self.root / UDEV_RULE).exists())

    def test_setup_without_dmi_keeps_working(self):
        result = self.run_setup()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse((self.root / MODULES_CONF).exists())
        self.assertTrue((self.root / UDEV_RULE).exists())

    def test_setup_survives_driver_load_failure(self):
        self.stub("modprobe", "#!/usr/bin/env bash\nexit 1\n")
        result = self.run_setup("B840M-C")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue((self.root / MODULES_CONF).exists())
        self.assertTrue((self.root / UDEV_RULE).exists())
        self.assertIn("nct6775", result.stdout + result.stderr)

    def test_setup_lists_every_measured_board(self):
        text = (REPO / "setup.sh").read_text()
        for board, _ in CPU_FAN_HEADERS:
            self.assertIn(f"'{board}') driver=", text)

    def test_uninstall_removes_driver_config(self):
        conf = self.root / MODULES_CONF
        conf.parent.mkdir(parents=True)
        conf.write_text("nct6775\n")
        result = self.run_script("uninstall.sh", "(( EUID == 0 ))")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(conf.exists())

    def test_uninstall_without_system_files_never_calls_sudo(self):
        self.stub("sudo", f'#!/usr/bin/env bash\necho "sudo $*" >> "{self.log}"\n')
        result = self.run_script("uninstall.sh", "(( EUID == 0 ))")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("sudo", self.commands())


if __name__ == "__main__":
    unittest.main()
