import errno
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from cooler_lcd.device import HID_ID, discover, send


class DeviceTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.sys, self.dev = root / "sys", root / "dev"
        self.dev.mkdir()

    def device(self, name, identity=HID_ID):
        uevent = self.sys / "class/hidraw" / name / "device/uevent"
        uevent.parent.mkdir(parents=True, exist_ok=True)
        uevent.write_text("DRIVER=hid-generic\nHID_ID=" + identity + "\nHID_NAME=\n")
        node = self.dev / name
        node.touch()
        return node

    def test_discovery_matches_exact_hid_id_not_descriptors(self):
        self.device("hidraw1", "0003:00005131:00002008")
        self.device("hidraw2", HID_ID + "0")
        self.device("hidraw3", "0005:00005131:00002007")
        wanted = self.device("hidraw9")
        self.assertEqual(discover(self.sys, self.dev), [wanted])

    def test_missing_or_unreadable_uevent_is_skipped(self):
        self.device("hidraw9")
        with patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertEqual(discover(self.sys, self.dev), [])
        (self.sys / "class/hidraw/hidraw9/device/uevent").unlink()
        self.assertEqual(discover(self.sys, self.dev), [])

    def test_absent_device_is_normal(self):
        self.assertEqual(send(bytes(65), self.sys, self.dev), "not_found")

    def test_writes_one_whole_report(self):
        node = self.device("hidraw9")
        report = bytes(range(65))
        self.assertEqual(send(report, self.sys, self.dev), "found")
        self.assertEqual(node.read_bytes(), report)

    def test_permission_probe_never_writes(self):
        node = self.device("hidraw9")
        node.write_bytes(b"unchanged")
        self.assertEqual(send(None, self.sys, self.dev), "found")
        self.assertEqual(node.read_bytes(), b"unchanged")

    def test_denied_permission_has_distinct_status(self):
        self.device("hidraw9")
        with patch("cooler_lcd.device.os.open", side_effect=PermissionError):
            self.assertEqual(send(bytes(65), self.sys, self.dev), "no_permission")

    def test_short_write_is_not_split_into_another_hid_report(self):
        self.device("hidraw9")
        with patch("cooler_lcd.device.os.open", return_value=123), \
                patch("cooler_lcd.device.os.write", return_value=12) as write, \
                patch("cooler_lcd.device.os.close") as close:
            self.assertEqual(send(bytes(65), self.sys, self.dev), "disconnected")
        write.assert_called_once()
        close.assert_called_once_with(123)

    def test_write_failure_closes_descriptor(self):
        self.device("hidraw9")
        with patch("cooler_lcd.device.os.open", return_value=123), \
                patch("cooler_lcd.device.os.write", side_effect=OSError(errno.ENODEV, "unplugged")), \
                patch("cooler_lcd.device.os.close") as close:
            self.assertEqual(send(bytes(65), self.sys, self.dev), "disconnected")
        close.assert_called_once_with(123)

    def test_reconnect_rediscovers_changed_hidraw_number(self):
        old = self.device("hidraw1")
        self.assertEqual(send(bytes(65), self.sys, self.dev), "found")
        old.unlink()
        (self.sys / "class/hidraw/hidraw1/device/uevent").unlink()
        self.assertEqual(send(bytes(65), self.sys, self.dev), "not_found")
        new = self.device("hidraw8")
        self.assertEqual(send(bytes([42]) * 65, self.sys, self.dev), "found")
        self.assertEqual(new.read_bytes(), bytes([42]) * 65)

    def test_reopening_recovers_after_suspend_write_failure(self):
        self.device("hidraw9")
        with patch("cooler_lcd.device.os.write", side_effect=OSError(errno.EIO, "suspended")):
            self.assertEqual(send(bytes(65), self.sys, self.dev), "disconnected")
        self.assertEqual(send(bytes(65), self.sys, self.dev), "found")


if __name__ == "__main__":
    unittest.main()
