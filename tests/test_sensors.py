from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

from cooler_lcd.protocol import Readings
from cooler_lcd.sensors import Sensors, cpu_times


class SensorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.sys, self.proc = root / "sys", root / "proc"
        self.sensors = Sensors(self.sys, self.proc, nvidia_smi=None)

    @staticmethod
    def write(path, value):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(str(value))

    def hwmon(self, index, name, **values):
        path = self.sys / "class/hwmon" / f"hwmon{index}"
        self.write(path / "name", name)
        for filename, value in values.items():
            self.write(path / filename, value)
        return path

    def test_no_sensors_returns_all_zeroes(self):
        self.assertEqual(self.sensors.sample(), Readings())

    def test_cpu_prefers_k10temp_tctl_over_other_labels_and_drivers(self):
        self.hwmon(0, "coretemp", temp1_input=80000)
        self.hwmon(1, "k10temp", temp1_label="Tdie", temp1_input=40000,
                   temp2_label="Tctl", temp2_input=42000)
        self.hwmon(2, "zenpower", temp1_input=90000)
        self.assertEqual(self.sensors.sample().cpu_temp, 42)

    def test_coretemp_uses_package_label(self):
        self.hwmon(0, "coretemp", temp1_label="Core 0", temp1_input=40000,
                   temp2_label="Package id 0", temp2_input=53000)
        self.assertEqual(self.sensors.sample().cpu_temp, 53)

    def test_zenpower_is_fallback(self):
        self.hwmon(0, "k10temp", temp1_input="unavailable")
        self.hwmon(1, "zenpower", temp1_input=47000)
        self.assertEqual(self.sensors.sample().cpu_temp, 47)

    def test_cpu_usage_uses_deltas_and_excludes_duplicate_guest_time(self):
        self.write(self.proc / "stat", "cpu 100 0 0 100 0 0 0 0 50 0\n")
        self.assertEqual(cpu_times(self.proc / "stat"), (100, 200))
        self.assertEqual(self.sensors.sample().cpu_usage, 0)
        self.write(self.proc / "stat", "cpu 130 0 0 110 0 0 0 0 80 0\n")
        self.assertEqual(self.sensors.sample().cpu_usage, 75)

    def test_cpu_usage_counts_iowait_as_idle(self):
        self.write(self.proc / "stat", "cpu 100 0 0 100 10\n")
        self.sensors.sample()
        self.write(self.proc / "stat", "cpu 110 0 0 110 30\n")
        self.assertEqual(self.sensors.sample().cpu_usage, 25)

    def test_cpu_usage_recovers_after_missing_malformed_or_reset_counters(self):
        for value in ("", "cpu nope", "cpu -1 0 0 1", "cpu0 1 0 0 1"):
            with self.subTest(value=value):
                self.write(self.proc / "stat", value)
                self.assertEqual(self.sensors.sample().cpu_usage, 0)
        for value in ("cpu 100 0 0 100", "cpu 1 0 0 1", "cpu 1 0 0 1"):
            self.write(self.proc / "stat", value)
            self.assertEqual(self.sensors.sample().cpu_usage, 0)

    def test_cpufreq_policy_reports_highest_mhz(self):
        root = self.sys / "devices/system/cpu/cpufreq"
        self.write(root / "policy0/scaling_cur_freq", 3600000)
        self.write(root / "policy1/scaling_cur_freq", 4200000)
        self.assertEqual(self.sensors.sample().cpu_mhz, 4200)

    def test_cpufreq_per_cpu_fallback(self):
        self.write(self.sys / "devices/system/cpu/cpu0/cpufreq/scaling_cur_freq", 3800000)
        self.assertEqual(self.sensors.sample().cpu_mhz, 3800)

    def test_cpu_fan_requires_cpu_label(self):
        path = self.hwmon(0, "nct6798", fan1_input=2000, fan2_label="Chassis", fan2_input=1800)
        self.assertEqual(self.sensors.sample().cpu_rpm, 0)
        self.write(path / "fan3_label", "CPU_FAN")
        self.write(path / "fan3_input", 1234)
        self.assertEqual(self.sensors.sample().cpu_rpm, 1234)

    def test_verified_board_unlabeled_header_is_cpu_fan(self):
        self.write(self.sys / "class/dmi/id/board_name", "B840M-C")
        self.hwmon(0, "nct6799", fan1_input=0, fan2_input=894, fan4_input=669)
        self.assertEqual(self.sensors.sample().cpu_rpm, 894)

    def test_cpu_header_is_not_assumed_on_other_boards(self):
        self.write(self.sys / "class/dmi/id/board_name", "B650M PG Riptide")
        self.hwmon(0, "nct6799", fan2_input=894)
        self.assertEqual(self.sensors.sample().cpu_rpm, 0)

    def test_verified_board_other_chip_is_not_assumed(self):
        self.write(self.sys / "class/dmi/id/board_name", "B840M-C")
        self.hwmon(0, "nct6798", fan2_input=894)
        self.assertEqual(self.sensors.sample().cpu_rpm, 0)

    def test_verified_board_labels_win_over_header(self):
        self.write(self.sys / "class/dmi/id/board_name", "B840M-C")
        self.hwmon(0, "nct6799", fan2_label="Pump Fan", fan2_input=2800)
        self.assertEqual(self.sensors.sample().cpu_rpm, 0)

    def test_verified_board_missing_header_reads_zero(self):
        self.write(self.sys / "class/dmi/id/board_name", "B840M-C")
        self.hwmon(0, "nct6799", fan4_input=669)
        self.assertEqual(self.sensors.sample().cpu_rpm, 0)

    def test_readable_cpu_hwmon_power(self):
        self.hwmon(0, "zenpower", power1_input=65000000)
        self.assertEqual(self.sensors.sample().cpu_watts, 65)

    def test_readable_package_rapl_energy_delta_and_wrap(self):
        path = self.sys / "class/powercap/intel-rapl:0"
        self.write(path / "name", "package-0")
        self.write(path / "energy_uj", 1000000)
        self.write(path / "max_energy_range_uj", 100000000)
        with patch("cooler_lcd.sensors.time.monotonic", side_effect=[1, 2, 3]):
            self.assertEqual(self.sensors.sample().cpu_watts, 0)
            self.write(path / "energy_uj", 66000000)
            self.assertEqual(self.sensors.sample().cpu_watts, 65)
            self.write(path / "energy_uj", 31000000)
            self.assertEqual(self.sensors.sample().cpu_watts, 65)

    def test_unreadable_sensors_are_zero(self):
        self.hwmon(0, "k10temp", temp1_input=42000, power1_input=65000000)
        with patch.object(Path, "read_text", side_effect=PermissionError):
            self.assertEqual(self.sensors.sample(), Readings())

    def test_rapl_zero_is_a_valid_counter_reading(self):
        path = self.sys / "class/powercap/intel-rapl:0"
        self.write(path / "name", "package-0")
        self.write(path / "energy_uj", 0)
        with patch("cooler_lcd.sensors.time.monotonic", side_effect=[1, 2]):
            self.assertEqual(self.sensors.sample().cpu_watts, 0)
            self.write(path / "energy_uj", 65000000)
            self.assertEqual(self.sensors.sample().cpu_watts, 65)

    def test_malformed_and_nonfinite_sensor_values_are_zero(self):
        for value in ("garbage", "NaN", "inf", "-1000"):
            with self.subTest(value=value):
                self.hwmon(0, "k10temp", temp1_input=value, power1_input=value)
                self.assertEqual(self.sensors.sample(), Readings())

    def test_amdgpu_fields_and_units(self):
        path = self.hwmon(0, "amdgpu", temp1_input=51000, freq1_input=2450000000,
                          fan1_input=1500, power1_average=160000000)
        self.write(path / "device/gpu_busy_percent", 82)
        sample = self.sensors.sample()
        self.assertEqual((sample.gpu_temp, sample.gpu_usage, sample.gpu_mhz,
                          sample.gpu_rpm, sample.gpu_watts), (51, 82, 2450, 1500, 160))

    def test_gpu_power_input_fallback(self):
        self.hwmon(0, "amdgpu", power1_input=123000000)
        self.assertEqual(self.sensors.sample().gpu_watts, 123)

    def test_hwmon_is_rediscovered_after_driver_appears(self):
        self.assertEqual(self.sensors.sample().gpu_temp, 0)
        self.hwmon(0, "amdgpu", temp1_input=51000)
        self.assertEqual(self.sensors.sample().gpu_temp, 51)

    def test_intel_hwmon_best_effort(self):
        for driver in ("i915", "xe"):
            with self.subTest(driver=driver):
                path = self.hwmon(0, driver, temp1_input=45000)
                self.write(path / "device/gt_cur_freq_mhz", 900)
                sample = self.sensors.sample()
                self.assertEqual((sample.gpu_temp, sample.gpu_mhz, sample.gpu_usage), (45, 900, 0))

    def test_intel_drm_frequency_without_hwmon(self):
        path = self.sys / "class/drm/card0"
        self.write(path / "device/vendor", "0x8086")
        self.write(path / "gt_cur_freq_mhz", 1100)
        self.assertEqual(self.sensors.sample().gpu_mhz, 1100)

    def test_nvidia_is_skipped_when_helper_is_absent(self):
        with patch("cooler_lcd.sensors.shutil.which", return_value=None), \
                patch("cooler_lcd.sensors.subprocess.run") as run:
            self.assertEqual(Sensors(self.sys, self.proc).sample(), Readings())
        run.assert_not_called()

    def test_nvidia_parses_optional_helper_output(self):
        self.sensors.nvidia_smi = "/fake/nvidia-smi"
        with patch("cooler_lcd.sensors.subprocess.run", return_value=Mock(stdout="51, 82, 2450, 160.5\n")) as run:
            sample = self.sensors.sample()
        self.assertEqual((sample.gpu_temp, sample.gpu_usage, sample.gpu_mhz,
                          sample.gpu_watts, sample.gpu_rpm), (51, 82, 2450, 160.5, 0))
        self.assertEqual(run.call_args.args[0][0], "/fake/nvidia-smi")
        self.assertEqual(run.call_args.kwargs["timeout"], 0.5)

    def test_nvidia_unsupported_values_are_zero(self):
        self.sensors.nvidia_smi = "/fake/nvidia-smi"
        with patch("cooler_lcd.sensors.subprocess.run", return_value=Mock(stdout="[N/A], nan, inf, -1\n")):
            self.assertEqual(self.sensors.sample(), Readings())

    def test_nvidia_helper_errors_do_not_stop_sampling(self):
        self.sensors.nvidia_smi = "/fake/nvidia-smi"
        for error in (OSError(), subprocess.TimeoutExpired("nvidia-smi", 0.5),
                      subprocess.CalledProcessError(1, "nvidia-smi"),
                      UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid output")):
            with self.subTest(error=type(error).__name__), \
                    patch("cooler_lcd.sensors.subprocess.run", side_effect=error):
                self.assertEqual(self.sensors.sample(), Readings())


if __name__ == "__main__":
    unittest.main()
