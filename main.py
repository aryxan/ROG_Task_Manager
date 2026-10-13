import sys
import re
import json
import time
import subprocess
import urllib.request
from pathlib import Path
from collections import deque

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QPainter
from PySide6.QtCharts import QChart, QChartView, QLineSeries, QValueAxis
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QLabel, QPushButton,
    QComboBox, QFrame, QVBoxLayout, QHBoxLayout, QGridLayout,
    QStackedWidget, QTableWidget, QTableWidgetItem, QHeaderView,
    QMessageBox
)

APP_DIR = Path.home() / ".config/rog-task-manager"
PROFILE_FILE = APP_DIR / "profiles.json"
PROFILES = ["Quiet", "Balanced", "Performance"]
HISTORY_SIZE = 60

STYLE = """
QMainWindow, QWidget {
    background: #0b0f19; color: #e6eaf2;
    font-family: Sans Serif; font-size: 13px;
}
QLabel#Title { font-size: 23px; font-weight: bold; color: #ff4568; }
QLabel#Section { font-size: 16px; font-weight: bold; }
QLabel#Metric { font-size: 25px; font-weight: bold; color: white; }
QLabel#SubTitle { color: #91a0ba; font-size: 12px; }
QFrame#Card {
    background: #151c2b; border: 1px solid #29354a;
    border-radius: 10px;
}
QPushButton {
    background: #202b40; border: 1px solid #34435c;
    border-radius: 7px; padding: 9px; color: #e6eaf2;
}
QPushButton:hover { background: #2b3a54; }
QPushButton#NavButton { border: none; padding: 12px; text-align: left; }
QPushButton#NavButton:checked {
    background: #29374f; color: #ff7890; font-weight: bold;
}
QPushButton#Primary { background: #d93659; font-weight: bold; }
QComboBox {
    background: #202b40; border: 1px solid #34435c;
    border-radius: 7px; padding: 8px; min-width: 120px;
}
QTableWidget {
    background: #121927; alternate-background-color: #182235;
    gridline-color: #29354a; border: 1px solid #29354a;
}
QHeaderView::section {
    background: #202b40; padding: 8px; border: none;
}
"""

def run(args, timeout=2):
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           timeout=timeout, check=False)
        return p.stdout.strip(), p.returncode, p.stderr.strip()
    except (OSError, subprocess.TimeoutExpired) as exc:
        return "", 1, str(exc)

def power_source():
    battery = psutil.sensors_battery()
    if battery is None:
        return "AC"
    return "AC" if battery.power_plugged else "Battery"

def profile_info():
    output, code, _ = run(["asusctl", "profile", "get"])
    info = {"active": "Unknown", "AC": None, "Battery": None}
    if code == 0:
        m = re.search(r"Active profile:\s*(.+)", output)
        if m:
            info["active"] = m.group(1).strip()
        for source in ("AC", "Battery"):
            m = re.search(
                rf"{source} profile\s*:?\s*(Quiet|Balanced|Performance)",
                output, re.I
            )
            if m:
                info[source] = m.group(1).title()
    return info

def load_preferences():
    APP_DIR.mkdir(parents=True, exist_ok=True)
    info = profile_info()
    prefs = {
        "AC": info["AC"] if info["AC"] in PROFILES else "Performance",
        "Battery": info["Battery"] if info["Battery"] in PROFILES else "Balanced"
    }
    try:
        saved = json.loads(PROFILE_FILE.read_text())
        for source in prefs:
            if saved.get(source) in PROFILES:
                prefs[source] = saved[source]
    except (OSError, ValueError, TypeError):
        pass
    return prefs

def save_preferences(prefs):
    APP_DIR.mkdir(parents=True, exist_ok=True)
    PROFILE_FILE.write_text(json.dumps(prefs, indent=2))

def sensors():
    output, _, _ = run(["sensors"])
    data = {}
    pattern = (
        r"^\s*(Tctl|Tccd1|Tccd2|edge|cpu_fan|gpu_fan|mid_fan):"
        r"\s*([+-]?\d+(?:\.\d+)?)\s*(°C|RPM)?"
    )
    for line in output.splitlines():
        m = re.match(pattern, line)
        if m:
            data[m.group(1)] = (float(m.group(2)), m.group(3) or "")
    return data

def gpu_data():
    output, code, _ = run([
        "nvidia-smi",
        "--query-gpu=utilization.gpu,temperature.gpu,power.draw,memory.used,memory.total",
        "--format=csv,noheader,nounits"
    ])
    if code:
        return None
    try:
        p = [x.strip() for x in output.splitlines()[0].split(",")]
        return {
            "usage": float(p[0]), "temp": float(p[1]),
            "power": float(p[2]), "used": float(p[3]), "total": float(p[4])
        }
    except (ValueError, IndexError):
        return None

def ollama_data():
    result = {"status": "Offline", "installed": [], "running": []}
    try:
        for endpoint, key in (("/api/tags", "installed"), ("/api/ps", "running")):
            req = urllib.request.Request("http://127.0.0.1:11434" + endpoint)
            with urllib.request.urlopen(req, timeout=0.7) as response:
                result[key] = json.loads(response.read()).get("models", [])
        result["status"] = "Online"
    except (OSError, ValueError):
        pass
    return result

def gb(n):
    return n / (1024 ** 3)

def make_card(title, value="--", detail=""):
    frame = QFrame()
    frame.setObjectName("Card")
    layout = QVBoxLayout(frame)
    layout.setContentsMargins(14, 12, 14, 12)
    t = QLabel(title)
    t.setObjectName("SubTitle")
    v = QLabel(value)
    v.setObjectName("Metric")
    v.setWordWrap(True)
    d = QLabel(detail)
    d.setObjectName("SubTitle")
    d.setWordWrap(True)
    layout.addWidget(t)
    layout.addWidget(v)
    layout.addWidget(d)
    return frame, v, d

def make_chart(title, names, low=0, high=100):
    chart = QChart()
    chart.setTitle(title)
    chart.setBackgroundBrush(QColor("#151c2b"))
    chart.setTitleBrush(QColor("#e6eaf2"))
    chart.legend().setLabelColor(QColor("#c6d0e1"))
    chart.setAnimationOptions(QChart.AnimationOption.NoAnimation)

    x = QValueAxis()
    x.setRange(0, HISTORY_SIZE - 1)
    x.setTitleText("Recent seconds")
    x.setLabelsColor(QColor("#91a0ba"))
    x.setGridLineColor(QColor("#29354a"))

    y = QValueAxis()
    y.setRange(low, high)
    y.setLabelsColor(QColor("#91a0ba"))
    y.setGridLineColor(QColor("#29354a"))

    chart.addAxis(x, Qt.AlignmentFlag.AlignBottom)
    chart.addAxis(y, Qt.AlignmentFlag.AlignLeft)

    series = {}
    for name in names:
        s = QLineSeries()
        s.setName(name)
        chart.addSeries(s)
        s.attachAxis(x)
        s.attachAxis(y)
        series[name] = s

    view = QChartView(chart)
    view.setRenderHint(QPainter.RenderHint.Antialiasing)
    view.setMinimumHeight(245)
    return view, series

class ROGTaskManager(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("ROG Task Manager")
        self.resize(1250, 820)
        self.setMinimumSize(950, 650)

        self.prefs = load_preferences()
        self.source = power_source()
        self.history = {
            n: deque(maxlen=HISTORY_SIZE)
            for n in ["CPU", "GPU", "RAM", "CPU Temp", "GPU Temp"]
        }
        self.last_ollama = 0
        self.ollama = {"status": "Checking...", "installed": [], "running": []}

        base = QWidget()
        self.setCentralWidget(base)
        outer = QHBoxLayout(base)
        outer.setContentsMargins(12, 12, 12, 12)

        sidebar = QFrame()
        sidebar.setObjectName("Card")
        sidebar.setFixedWidth(180)
        side = QVBoxLayout(sidebar)
        brand = QLabel("ROG\nMONITOR")
        brand.setObjectName("Title")
        side.addWidget(brand)
        side.addSpacing(15)

        self.pages = QStackedWidget()
        self.nav = []
        names = ["Overview", "Performance", "Fans & Thermals", "Processes", "Ollama"]
        for name in names:
            b = QPushButton(name)
            b.setObjectName("NavButton")
            b.setCheckable(True)
            b.clicked.connect(lambda checked=False, n=name: self.navigate(n))
            side.addWidget(b)
            self.nav.append((name, b))
        side.addStretch()
        self.sidebar_status = QLabel("Starting...")
        self.sidebar_status.setObjectName("SubTitle")
        side.addWidget(self.sidebar_status)
        outer.addWidget(sidebar)
        outer.addWidget(self.pages, 1)

        self.build_overview()
        self.build_performance()
        self.build_fans()
        self.build_processes()
        self.build_ollama()
        self.navigate("Overview")

        psutil.cpu_percent(interval=None)
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.refresh)
        self.timer.start(1000)
        self.refresh()

    def navigate(self, name):
        index = {
            "Overview": 0, "Performance": 1, "Fans & Thermals": 2,
            "Processes": 3, "Ollama": 4
        }[name]
        self.pages.setCurrentIndex(index)
        for n, b in self.nav:
            b.setChecked(n == name)

    def build_overview(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        header = QHBoxLayout()
        title = QLabel("System Overview")
        title.setObjectName("Title")
        header.addWidget(title)
        header.addStretch()
        header.addWidget(QLabel("Live · 1-second refresh"))
        layout.addLayout(header)

        profile = QFrame()
        profile.setObjectName("Card")
        row = QHBoxLayout(profile)
        row.addWidget(QLabel("POWER SOURCE"))
        self.source_label = QLabel("Detecting...")
        self.source_label.setObjectName("Section")
        row.addWidget(self.source_label)
        row.addWidget(QLabel("PROFILE"))
        self.profile_combo = QComboBox()
        self.profile_combo.addItems(PROFILES)
        row.addWidget(self.profile_combo)
        self.apply_button = QPushButton("Apply to current source")
        self.apply_button.setObjectName("Primary")
        self.apply_button.clicked.connect(self.change_profile)
        row.addWidget(self.apply_button)
        row.addStretch()
        self.active_label = QLabel("Active: checking...")
        row.addWidget(self.active_label)
        layout.addWidget(profile)

        grid = QGridLayout()
        self.metrics = {}
        specs = [
            ("CPU", "CPU Usage"), ("RAM", "Memory"),
            ("GPU", "RTX 5050 Usage"), ("CPU Temp", "CPU Temperature"),
            ("GPU Temp", "GPU Temperature"), ("GPU Power", "GPU Power"),
            ("VRAM", "GPU Memory"), ("Battery", "Battery")
        ]
        for i, (key, title) in enumerate(specs):
            frame, value, detail = make_card(title)
            self.metrics[key] = (value, detail)
            grid.addWidget(frame, i // 2, i % 2)
        layout.addLayout(grid)
        self.status = QLabel("Reading sensors...")
        self.status.setObjectName("SubTitle")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        layout.addStretch()
        self.pages.addWidget(page)

    def build_performance(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Performance History")
        title.setObjectName("Title")
        layout.addWidget(title)
        self.usage_view, self.usage_series = make_chart(
            "CPU / GPU / RAM utilisation (%)", ["CPU", "GPU", "RAM"]
        )
        self.temp_view, self.temp_series = make_chart(
            "Temperatures (°C)", ["CPU Temp", "GPU Temp"], 0, 110
        )
        layout.addWidget(self.usage_view)
        layout.addWidget(self.temp_view)
        self.pages.addWidget(page)

    def build_fans(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Fans & Thermals")
        title.setObjectName("Title")
        layout.addWidget(title)
        note = QLabel("Live RPM readings. Fan curves are not modified by this app.")
        note.setObjectName("SubTitle")
        layout.addWidget(note)

        grid = QGridLayout()
        self.fans = {}
        for i, (key, name) in enumerate([
            ("cpu_fan", "CPU FAN"), ("gpu_fan", "GPU FAN"), ("mid_fan", "MID FAN")
        ]):
            frame, value, detail = make_card(name, "-- RPM", "Fan speed")
            self.fans[key] = (value, detail)
            grid.addWidget(frame, 0, i)
        layout.addLayout(grid)

        grid2 = QGridLayout()
        self.thermals = {}
        for i, (key, name) in enumerate([
            ("Tctl", "CPU Tctl"), ("Tccd1", "CPU CCD1"),
            ("Tccd2", "CPU CCD2"), ("edge", "AMD Graphics")
        ]):
            frame, value, detail = make_card(name, "-- °C", "Temperature")
            self.thermals[key] = (value, detail)
            grid2.addWidget(frame, 0, i)
        layout.addLayout(grid2)
        self.fan_policy = QLabel("Checking fan policy...")
        self.fan_policy.setObjectName("SubTitle")
        layout.addWidget(self.fan_policy)
        layout.addStretch()
        self.pages.addWidget(page)

    def build_processes(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Processes")
        title.setObjectName("Title")
        layout.addWidget(title)
        self.process_table = QTableWidget(0, 5)
        self.process_table.setHorizontalHeaderLabels(
            ["PID", "Process", "CPU %", "RAM %", "Memory"]
        )
        self.process_table.setAlternatingRowColors(True)
        self.process_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.process_table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        header = self.process_table.horizontalHeader()
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        for col in [0, 2, 3, 4]:
            header.setSectionResizeMode(col, QHeaderView.ResizeMode.ResizeToContents)
        layout.addWidget(self.process_table)
        self.pages.addWidget(page)

    def build_ollama(self):
        page = QWidget()
        layout = QVBoxLayout(page)
        title = QLabel("Local AI · Ollama")
        title.setObjectName("Title")
        layout.addWidget(title)
        self.ollama_status = QLabel("Checking Ollama...")
        self.ollama_status.setObjectName("Section")
        layout.addWidget(self.ollama_status)
        self.installed_label = QLabel("Installed models...")
        self.installed_label.setObjectName("SubTitle")
        self.installed_label.setWordWrap(True)
        layout.addWidget(self.installed_label)
        self.running_label = QLabel("Loaded models...")
        self.running_label.setObjectName("SubTitle")
        self.running_label.setWordWrap(True)
        layout.addWidget(self.running_label)
        b = QPushButton("Refresh Ollama")
        b.clicked.connect(self.refresh_ollama)
        layout.addWidget(b)
        layout.addStretch()
        self.pages.addWidget(page)

    def change_profile(self):
        source = power_source()
        selected = self.profile_combo.currentText()
        answer = QMessageBox.question(
            self, "Confirm profile",
            f"Set {selected} for {source} only?\n\n"
            "The application will save this preference for that power source "
            "and restore it when you switch between AC and battery.",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            QMessageBox.StandardButton.No
        )
        if answer != QMessageBox.StandardButton.Yes:
            return

        self.apply_button.setEnabled(False)
        QApplication.processEvents()
        output, code, error = run(
            ["asusctl", "profile", "set", selected], timeout=8
        )
        actual = profile_info()["active"]
        self.apply_button.setEnabled(True)

        if code == 0 and actual.lower() == selected.lower():
            self.prefs[source] = selected
            try:
                save_preferences(self.prefs)
            except OSError as exc:
                QMessageBox.warning(self, "Save warning", str(exc))
            QMessageBox.information(
                self, "Profile changed",
                f"Active profile: {actual}\nSaved for: {source}"
            )
        else:
            QMessageBox.warning(
                self, "Change not confirmed",
                f"Requested: {selected}\nActive: {actual}\n"
                f"{error or output or 'asusctl did not confirm the change.'}"
            )

    def restore_source_profile(self, source):
        wanted = self.prefs.get(source)
        if wanted not in PROFILES:
            return
        actual = profile_info()["active"]
        if actual.lower() == wanted.lower():
            return
        run(["asusctl", "profile", "set", wanted], timeout=5)

    def refresh_ollama(self):
        result = {"status": "Offline", "installed": [], "running": []}
        try:
            for endpoint, key in [
                ("/api/tags", "installed"), ("/api/ps", "running")
            ]:
                req = urllib.request.Request(
                    "http://127.0.0.1:11434" + endpoint
                )
                with urllib.request.urlopen(req, timeout=0.7) as response:
                    result[key] = json.loads(response.read()).get("models", [])
            result["status"] = "Online"
        except (OSError, ValueError):
            pass

        self.ollama = result
        self.ollama_status.setText("Ollama API: " + result["status"])

        installed = result["installed"]
        self.installed_label.setText(
            "Installed models:\n" + "\n".join(
                f"{m.get('name', 'Unknown')} · {gb(m.get('size', 0)):.1f} GB"
                for m in installed
            ) if installed else "No installed models found or API offline"
        )
        running = result["running"]
        self.running_label.setText(
            "Loaded models:\n" + "\n".join(
                f"{m.get('name', 'Unknown')} · GPU allocation "
                f"{gb(m.get('size_vram', 0)):.1f} GB"
                for m in running
            ) if running else "No models currently loaded"
        )

    def update_charts(self):
        for name, series in self.usage_series.items():
            series.clear()
            for i, value in enumerate(self.history[name]):
                series.append(i, value)
        for name, series in self.temp_series.items():
            series.clear()
            for i, value in enumerate(self.history[name]):
                series.append(i, value)

    def refresh_processes(self):
        rows = []
        for proc in psutil.process_iter(
            ["pid", "name", "memory_percent", "memory_info"]
        ):
            try:
                info = proc.info
                cpu = proc.cpu_percent(None)
                mem_percent = info.get("memory_percent") or 0
                mem_info = info.get("memory_info")
                memory = mem_info.rss if mem_info else 0
                rows.append((cpu, info.get("pid", 0), info.get("name") or "?",
                             mem_percent, memory))
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        rows.sort(reverse=True, key=lambda x: x[0])
        self.process_table.setRowCount(min(25, len(rows)))
        for r, row in enumerate(rows[:25]):
            cpu, pid, name, mem_percent, memory = row
            values = [str(pid), name, f"{cpu:.1f}", f"{mem_percent:.1f}",
                      f"{memory / (1024 ** 2):.0f} MB"]
            for c, value in enumerate(values):
                self.process_table.setItem(r, c, QTableWidgetItem(value))

    def refresh(self):
        source = power_source()
        if source != self.source:
            self.source = source
            self.restore_source_profile(source)

        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        s = sensors()
        gpu = gpu_data()
        cpu_temp = s.get("Tctl", (None, ""))[0]
        gpu_temp = gpu["temp"] if gpu else None
        gpu_usage = gpu["usage"] if gpu else 0.0

        self.history["CPU"].append(cpu)
        self.history["GPU"].append(gpu_usage)
        self.history["RAM"].append(mem.percent)
        if cpu_temp is not None:
            self.history["CPU Temp"].append(cpu_temp)
        if gpu_temp is not None:
            self.history["GPU Temp"].append(gpu_temp)

        self.metrics["CPU"][0].setText(f"{cpu:.1f}%")
        self.metrics["RAM"][0].setText(f"{mem.percent:.1f}%")
        self.metrics["RAM"][1].setText(f"{gb(mem.used):.1f} / {gb(mem.total):.1f} GB")

        if gpu:
            self.metrics["GPU"][0].setText(f"{gpu['usage']:.0f}%")
            self.metrics["GPU Temp"][0].setText(f"{gpu['temp']:.0f}°C")
            self.metrics["GPU Power"][0].setText(f"{gpu['power']:.1f} W")
            self.metrics["VRAM"][0].setText(
                f"{gpu['used'] / 1024:.1f} / {gpu['total'] / 1024:.1f} GB"
            )
        else:
            for key in ["GPU", "GPU Temp", "GPU Power", "VRAM"]:
                self.metrics[key][0].setText("Unavailable")

        self.metrics["CPU Temp"][0].setText(
            f"{cpu_temp:.1f}°C" if cpu_temp is not None else "Unavailable"
        )

        battery = psutil.sensors_battery()
        if battery:
            self.metrics["Battery"][0].setText(f"{battery.percent:.0f}%")
            self.metrics["Battery"][1].setText(
                "Plugged into AC" if battery.power_plugged else "On battery"
            )
        else:
            self.metrics["Battery"][0].setText("Unknown")

        info = profile_info()
        active = info["active"]
        self.source_label.setText(source)
        self.active_label.setText(f"Active: {active}")
        if active in PROFILES and not self.profile_combo.hasFocus():
            self.profile_combo.setCurrentText(active)

        self.status.setText(
            f"Source: {source} · Profile: {active} · CPU {cpu:.0f}% · "
            f"RAM {mem.percent:.0f}% · GPU {gpu_usage:.0f}%"
        )
        self.sidebar_status.setText(
            f"{source} power\nProfile: {active}\nRefresh: 1 second"
        )

        for key, (value, detail) in self.fans.items():
            if key in s:
                value.setText(f"{s[key][0]:,.0f} RPM")
                detail.setText("Live sensor")
            else:
                value.setText("Unavailable")
                detail.setText("No RPM sensor")
        for key, (value, detail) in self.thermals.items():
            if key in s:
                value.setText(f"{s[key][0]:.1f}°C")
                detail.setText("Live sensor")
            else:
                value.setText("Unavailable")
                detail.setText("Sensor not exposed")

        self.fan_policy.setText(
            f"Active profile: {active}\n"
            f"Saved AC preference: {self.prefs.get('AC')}\n"
            f"Saved battery preference: {self.prefs.get('Battery')}\n"
            "Fan curves remain unchanged."
        )

        self.update_charts()
        self.refresh_processes()

        if time.monotonic() - self.last_ollama >= 5:
            self.last_ollama = time.monotonic()
            self.refresh_ollama()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setApplicationName("ROG Task Manager")
    psutil.cpu_percent(interval=None)
    window = ROGTaskManager()
    window.show()
    sys.exit(app.exec())
