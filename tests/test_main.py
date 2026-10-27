import unittest
from unittest.mock import Mock, call, patch

from cooler_lcd.__main__ import main
from cooler_lcd.protocol import Readings, build_frame


class MainTests(unittest.TestCase):
    def test_refuses_to_run_as_root(self):
        with patch("cooler_lcd.__main__.os.geteuid", return_value=0):
            with self.assertRaisesRegex(SystemExit, "never as root"):
                main()

    def test_sends_celsius_reports_on_fixed_one_second_ticks_and_keeps_retrying(self):
        readings = Readings(cpu_temp=42)
        sensors = Mock()
        sensors.sample.return_value = readings
        report = build_frame(readings)
        with patch("cooler_lcd.__main__.os.geteuid", return_value=1000), \
                patch("cooler_lcd.__main__.Sensors", return_value=sensors), \
                patch("cooler_lcd.__main__.build_frame", return_value=report) as build, \
                patch("cooler_lcd.__main__.send", side_effect=["not_found", "no_permission", "disconnected", "found"]) as send, \
                patch("cooler_lcd.__main__.time.monotonic", side_effect=[0, 0.2, 1, 1.2, 2, 2.2, 3, 3.2]), \
                patch("cooler_lcd.__main__.time.sleep", side_effect=[None, None, None, KeyboardInterrupt]) as sleep, \
                patch("cooler_lcd.__main__.logging.info"):
            with self.assertRaises(KeyboardInterrupt):
                main()
        self.assertEqual(build.call_args_list, [call(readings)] * 4)
        self.assertEqual(send.call_args_list, [call(report)] * 4)
        self.assertEqual(sensors.sample.call_count, 4)
        for invocation in sleep.call_args_list:
            self.assertAlmostEqual(invocation.args[0], 0.8)


if __name__ == "__main__":
    unittest.main()
