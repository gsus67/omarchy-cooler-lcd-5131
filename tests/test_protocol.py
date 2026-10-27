from dataclasses import fields
from datetime import datetime
import unittest
from unittest.mock import patch

from cooler_lcd.protocol import FAHRENHEIT_FLAG, Readings, build_frame

NOW = datetime(2026, 10, 27, 13, 5)


class ProtocolTests(unittest.TestCase):
    def test_every_byte_of_verified_report(self):
        readings = Readings(42, 37, 4200, 1234, 65, 51, 82, 2450, 1500, 160)
        expected = bytes([
            0, 0x40, 42, 37, 0x10, 0x68, 0x04, 0xD2, 0, 65,
            51, 82, 0x09, 0x92, 0x05, 0xDC, 0, 160,
            0, 0, 0, 0, 0, 0, 0x07, 0xEA, 10, 27, 13, 5, 0xE7,
        ] + [0] * 34)
        actual = build_frame(readings, NOW)
        self.assertEqual(len(actual), 65)
        for offset, (value, wanted) in enumerate(zip(actual, expected)):
            with self.subTest(byte=offset):
                self.assertEqual(value, wanted)

    def test_checksum_wraps_sum_of_bytes_one_through_twenty_nine(self):
        frame = build_frame(Readings(**{field.name: 65535 for field in fields(Readings)}), NOW)
        self.assertGreater(sum(frame[1:30]), 255)
        self.assertEqual(frame[30], sum(frame[1:30]) & 0xFF)

    def test_temperatures_cannot_set_fahrenheit_flag(self):
        self.assertEqual(FAHRENHEIT_FLAG, 0x80)
        frame = build_frame(Readings(cpu_temp=200, gpu_temp=128), NOW)
        for offset in (2, 10):
            self.assertEqual(frame[offset], 127)
            self.assertEqual(frame[offset] & FAHRENHEIT_FLAG, 0)

    def test_field_ranges_are_clamped(self):
        for value, temperature, usage, word in ((-1, 0, 0, 0), (999999, 127, 100, 65535)):
            with self.subTest(value=value):
                frame = build_frame(Readings(**{field.name: value for field in fields(Readings)}), NOW)
                self.assertEqual([frame[2], frame[10]], [temperature] * 2)
                self.assertEqual([frame[3], frame[11]], [usage] * 2)
                for offset in (4, 6, 8, 12, 14, 16):
                    self.assertEqual(int.from_bytes(frame[offset:offset + 2], "big"), word)

    def test_unavailable_and_nonfinite_readings_are_zero(self):
        for value in (None, "bad", float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                frame = build_frame(Readings(**{field.name: value for field in fields(Readings)}), NOW)
                self.assertEqual(frame[2:18], bytes(16))

    def test_readings_are_truncated_to_whole_units(self):
        frame = build_frame(Readings(cpu_temp=42.9, cpu_mhz=4200.9), NOW)
        self.assertEqual(frame[2], 42)
        self.assertEqual(int.from_bytes(frame[4:6], "big"), 4200)

    def test_default_clock_is_local_time(self):
        with patch("cooler_lcd.protocol.datetime") as clock:
            clock.now.return_value = NOW
            frame = build_frame(Readings())
        clock.now.assert_called_once_with()
        self.assertEqual(frame[24:30], bytes([0x07, 0xEA, 10, 27, 13, 5]))


if __name__ == "__main__":
    unittest.main()
