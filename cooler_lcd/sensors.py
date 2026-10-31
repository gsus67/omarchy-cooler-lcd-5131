"""Best-effort sysfs telemetry; the only optional helper is nvidia-smi."""
from pathlib import Path
import math
import shutil
import subprocess
import time

from .protocol import Readings

CPU_FAN_HEADERS = {("B840M-C", "nct6799"): "fan2"}


def read_text(path):
    try:
        return Path(path).read_text().strip()
    except (OSError, ValueError):
        return ""


def number(path, scale=1):
    try:
        value = float(read_text(path)) / scale
        return max(0, value) if math.isfinite(value) else 0
    except (ValueError, OverflowError):
        return 0


def first_number(paths, scale=1):
    for path in paths:
        value = number(path, scale)
        if value:
            return value
    return 0


def cpu_times(path):
    """Linux guest counters are already included in user/nice; don't sum twice."""
    try:
        fields = read_text(path).splitlines()[0].split()
        if fields[0] != "cpu" or len(fields) < 5:
            return None
        values = [int(value) for value in fields[1:9]]
        if any(value < 0 for value in values):
            return None
        return values[3] + (values[4] if len(values) > 4 else 0), sum(values)
    except (ValueError, IndexError):
        return None


class Sensors:
    def __init__(self, sys_root=Path("/sys"), proc_root=Path("/proc"), nvidia_smi="auto"):
        self.sys = Path(sys_root)
        self.proc = Path(proc_root)
        self.previous_cpu = cpu_times(self.proc / "stat")
        self.previous_energy = None
        self.nvidia_smi = shutil.which("nvidia-smi") if nvidia_smi == "auto" else nvidia_smi

    def usage(self):
        current = cpu_times(self.proc / "stat")
        previous, self.previous_cpu = self.previous_cpu, current
        if current is None or previous is None:
            return 0
        idle, total = current[0] - previous[0], current[1] - previous[1]
        if total <= 0 or idle < 0:
            return 0
        return max(0, min(100, 100 * (total - idle) / total))

    def hwmons(self):
        return [(path, read_text(path / "name"))
                for path in sorted((self.sys / "class/hwmon").glob("hwmon*"))]

    @staticmethod
    def temperature(path, label_prefixes=()):
        inputs = sorted(path.glob("temp*_input"))
        if label_prefixes:
            for sensor in inputs:
                label = read_text(sensor.with_name(sensor.name.replace("_input", "_label"))).lower()
                if any(label.startswith(prefix) for prefix in label_prefixes):
                    value = number(sensor, 1000)
                    if value:
                        return value
        # k10temp/zenpower and unlabeled coretemp use temp1 for the package.
        return number(path / "temp1_input", 1000)

    def cpu_power(self, hwmons):
        for path, name in hwmons:
            if name in ("k10temp", "coretemp", "zenpower"):
                watts = first_number([path / "power1_average", path / "power1_input"], 1_000_000)
                if watts:
                    return watts
        # Read an already accessible package RAPL counter. Never change its permissions.
        for path in sorted((self.sys / "class/powercap").glob("intel-rapl:*")):
            if not read_text(path / "name").startswith("package"):
                continue
            try:
                energy = int(read_text(path / "energy_uj"))
            except ValueError:
                continue
            if energy < 0:
                continue
            now = time.monotonic()
            previous, self.previous_energy = self.previous_energy, (path, energy, now)
            if previous and previous[0] == path and now > previous[2]:
                delta = energy - previous[1]
                if delta < 0:
                    delta += number(path / "max_energy_range_uj")
                return max(0, delta / (now - previous[2]) / 1_000_000)
            return 0
        self.previous_energy = None
        return 0

    def cpu_fan(self, hwmons):
        for path, _ in hwmons:
            for label_path in sorted(path.glob("fan*_label")):
                label = read_text(label_path).lower().replace("_", " ")
                if "cpu" in label:
                    rpm = number(label_path.with_name(label_path.name.replace("_label", "_input")))
                    if rpm:
                        return rpm
        # Super I/O drivers expose no fan labels; these headers were measured following CPU load.
        board = read_text(self.sys / "class/dmi/id/board_name")
        for path, name in hwmons:
            fan = CPU_FAN_HEADERS.get((board, name))
            if fan and not any(path.glob("fan*_label")):
                return number(path / f"{fan}_input")
        return 0  # Other unlabeled motherboard fans cannot safely be attributed to CPU.

    def gpu(self, hwmons, result):
        for driver in ("amdgpu", "i915", "xe"):
            for path, name in hwmons:
                if name != driver:
                    continue
                result.gpu_temp = self.temperature(path)
                result.gpu_usage = number(path / "device/gpu_busy_percent")
                result.gpu_mhz = number(path / "freq1_input", 1_000_000)
                result.gpu_rpm = number(path / "fan1_input")
                result.gpu_watts = first_number([path / "power1_average", path / "power1_input"], 1_000_000)
                if driver in ("i915", "xe"):
                    result.gpu_mhz = result.gpu_mhz or first_number([
                        path / "device/gt_cur_freq_mhz", path / "device/gt/gt0/rps_cur_freq_mhz"])
                return
        # Some Intel drivers expose frequency but no hwmon node.
        for card in sorted((self.sys / "class/drm").glob("card[0-9]*")):
            if read_text(card / "device/vendor").lower() != "0x8086":
                continue
            result.gpu_mhz = first_number([card / "gt_cur_freq_mhz",
                                          card / "device/gt_cur_freq_mhz",
                                          card / "gt/gt0/rps_cur_freq_mhz"])
            result.gpu_usage = number(card / "device/gpu_busy_percent")
            return
        if self.nvidia_smi:
            try:
                reply = subprocess.run(
                    [self.nvidia_smi, "--query-gpu=temperature.gpu,utilization.gpu,clocks.gr,power.draw",
                     "--format=csv,noheader,nounits"],
                    capture_output=True, text=True, timeout=0.5, check=True,
                )
                fields = reply.stdout.splitlines()[0].split(",")
                for key, field in zip(("gpu_temp", "gpu_usage", "gpu_mhz", "gpu_watts"), fields):
                    try:
                        value = float(field.strip())
                        setattr(result, key, max(0, value) if math.isfinite(value) else 0)
                    except ValueError:
                        pass  # NVIDIA returns [N/A] for unsupported counters.
            except (OSError, subprocess.SubprocessError, IndexError, UnicodeError):
                pass

    def sample(self):
        result = Readings(cpu_usage=self.usage())
        hwmons = self.hwmons()  # Rediscover: drivers may appear after resume.
        for driver, labels in (("k10temp", ("tctl",)), ("coretemp", ("package",)),
                               ("zenpower", ("tctl",))):
            for path, name in hwmons:
                if name == driver:
                    result.cpu_temp = self.temperature(path, labels)
                    if result.cpu_temp:
                        break
            if result.cpu_temp:
                break
        frequencies = list((self.sys / "devices/system/cpu/cpufreq").glob("policy*/scaling_cur_freq"))
        if not frequencies:
            frequencies = list((self.sys / "devices/system/cpu").glob("cpu[0-9]*/cpufreq/scaling_cur_freq"))
        result.cpu_mhz = max((number(path, 1000) for path in frequencies), default=0)
        result.cpu_rpm = self.cpu_fan(hwmons)
        result.cpu_watts = self.cpu_power(hwmons)
        self.gpu(hwmons, result)
        return result
