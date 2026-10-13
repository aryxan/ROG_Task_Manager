# ROG Task Manager

A custom Linux system-monitoring dashboard designed for ASUS ROG laptops, built with Python and PySide6. It provides real-time hardware monitoring, ASUS performance profile control, process monitoring, and Ollama integration in a single desktop application.

## Features

- **Real-time system monitoring** — CPU and RAM utilization with live graphs.
- **GPU monitoring** — NVIDIA GPU utilization, temperature, VRAM usage, and power consumption when supported.
- **Temperature monitoring** — CPU, GPU, SSD, and other available hardware sensors.
- **Fan monitoring** — Separate CPU, GPU, and additional fan readings where exposed by the hardware.
- **ASUS performance profiles** — Switch between Quiet, Balanced, and Performance modes when supported by the laptop and `asusctl`.
- **Ollama integration** — View Ollama service status and locally available models.
- **Process monitoring** — Inspect running processes and their resource consumption.
- **Automatic refresh** — Refreshes monitoring information approximately every second.
- **Lightweight desktop interface** — A native PySide6 GUI designed for everyday use on Linux.

## Screenshots

Add screenshots of the application here.

<img width="1920" height="1200" alt="image" src="https://github.com/user-attachments/assets/e72ba54c-295a-4fda-b3d2-beec5e14b0a2" />

<img width="1920" height="1200" alt="image" src="https://github.com/user-attachments/assets/dfd368af-b8ce-4c88-aa0c-a55300927e5d" />


## Supported Operating Systems

- Kali Linux
- Debian-based Linux distributions with the required dependencies
- Other Linux distributions may work with the appropriate packages and ASUS control utilities

## ASUS Model Compatibility

### Tested configuration

- **Laptop:** ASUS ROG Strix G16 (2026)
- **GPU:** NVIDIA GeForce RTX 5050
- **Operating system:** Kali Linux
- **ASUS control utility:** `asusctl` / `asusd`

### Potentially compatible models

Compatibility may extend to other ASUS ROG and TUF laptops supported by the installed version of `asusctl`, including selected models from these families:

- ASUS ROG Strix G series
- ASUS ROG Zephyrus G series
- ASUS ROG Flow series
- ASUS TUF Gaming A and F series

**Important:** These are potential compatibility targets, not a guarantee that every model supports every feature. GPU telemetry, fan readings, custom fan curves, and performance-profile switching vary by model, firmware, kernel, and `asusctl` support. Other ASUS laptop families may work for general system monitoring even if ASUS-specific controls are unavailable.

Check the official [asusctl project](https://gitlab.com/asus-linux/asusctl) for supported hardware and installation guidance.

## Requirements

- Python 3
- PySide6
- PySide6 Qt Charts
- `psutil`
- `lm-sensors`
- `asusctl` and `asusd` for ASUS-specific controls
- `nvidia-smi` for NVIDIA GPU telemetry
- Ollama for local AI model monitoring (optional)

Some features are optional. The dashboard may still provide basic CPU, RAM, and process monitoring if NVIDIA utilities, Ollama, or ASUS-specific utilities are unavailable.

## Installation

### 1. Install system dependencies

On Kali Linux or Debian-based distributions:

```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip \
  python3-psutil python3-pyside6.qtwidgets \
  python3-pyside6.qtcharts lm-sensors
```

Install `asusctl` using the instructions for your distribution and laptop model. Availability and installation methods differ between distributions.

For NVIDIA GPU monitoring, install a compatible NVIDIA driver and ensure `nvidia-smi` works:

```bash
nvidia-smi
```

For hardware sensor readings, detect available sensors if needed:

```bash
sudo sensors-detect
sensors
```

Review the prompts before accepting sensor-detection changes.

### 2. Clone the repository

Replace the example URL with your GitHub repository URL:

```bash
https://github.com/aryxan/ROG_Task_Manager
cd ROG_Task_Manager
```

### 3. Create a virtual environment (optional)

If you use the system-provided PySide6 and `psutil` packages, the system Python environment may be the simplest option. Alternatively, create an isolated environment and install compatible dependencies there.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the Python dependencies supported by your project setup. If you use a `requirements.txt` file:

```bash
pip install -r requirements.txt
```

### 4. Run the application

If your system dependencies were installed through APT:

```bash
python3 main.py
```

If using a virtual environment, activate it first and ensure the required GUI and monitoring libraries are installed in that environment.

## Implementation Overview

### 1. GUI layer

The application uses **PySide6**, Qt Widgets, and Qt Charts to present system information through a desktop interface with live graphs, status panels, and a process table.

### 2. System monitoring

`psutil` provides CPU utilization, memory usage, battery information, and process statistics. Available hardware temperatures and fan speeds are collected from Linux sensor interfaces.

### 3. GPU monitoring

For NVIDIA GPUs, the application can use `nvidia-smi` to read supported telemetry, including utilization, temperature, VRAM consumption, and power draw. Availability depends on the installed driver and GPU.

### 4. ASUS hardware controls

The application uses ASUS Linux control utilities for performance profiles and supported fan information. Actual hardware capabilities are determined by the laptop firmware and the installed `asusctl`/`asusd` version.

### 5. Ollama integration

When Ollama is installed and running, the dashboard can display local model information and service status. Model inference and GPU utilization are handled by Ollama and its configured backend.

### 6. Periodic refresh

A timer refreshes monitoring data at approximately one-second intervals, updating the interface and graph history.

## ASUS Control Setup

Verify that the ASUS control utility is installed:

```bash
asusctl --version
```

Check the active profile:

```bash
asusctl profile get
```

Check fan-curve support:

```bash
asusctl fan-curve --help
```

The exact commands and available controls can differ across `asusctl` versions. Avoid changing fan curves until you have confirmed that your model supports them and understand the consequences.

## Ollama Setup (Optional)

Install Ollama using the official instructions at [ollama.com](https://ollama.com/).

Check the service:

```bash
systemctl status ollama
```

List installed models:

```bash
ollama list
```

The dashboard's Ollama-related features require the Ollama service and compatible local access.

## Create a Terminal Command

To launch the application using `taskmanager` from your terminal, create a user-level launcher:

```bash
mkdir -p ~/.local/bin
cat > ~/.local/bin/taskmanager <<'EOF'
#!/bin/sh
exec /usr/bin/python3 "$HOME/rog-task-manager/main.py" "$@"
EOF
chmod +x ~/.local/bin/taskmanager
```

If `~/.local/bin` is not already in your shell's `PATH`, add it to the configuration for your actual shell. For Zsh, add the following to `~/.zshrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Reload Zsh or open a new terminal, then run:

```bash
taskmanager
```

Adjust the script path if you clone the repository into a different directory. If the application uses a virtual environment, update the launcher to point to that environment's Python executable.

## Troubleshooting

**The GUI does not start**
- Confirm that `main.py` exists in the project directory.
- Check that PySide6 and other required dependencies are installed in the Python environment used to launch the app.
- Run `python3 main.py` in a terminal to inspect error messages.

**GPU data is missing**
- Run `nvidia-smi` and verify that the NVIDIA driver is working.
- Note that NVIDIA-specific telemetry is not available on every GPU or driver configuration.

**Temperatures or fan speeds are missing**
- Run `sensors` and check whether Linux exposes the relevant readings.
- Some ASUS models expose limited sensor information.

**ASUS profiles do not change**
- Verify that `asusd` is installed and running and that your model is supported.
- Check `asusctl profile get` for the profiles available on your system.

**Ollama information is unavailable**
- Verify that Ollama is installed and running.
- Run `ollama list` to confirm that local models are available.

## Limitations

- Hardware telemetry depends on kernel, driver, firmware, and sensor support.
- ASUS-specific controls are not guaranteed to work across every ROG or TUF model.
- NVIDIA monitoring requires a compatible NVIDIA driver and utility.
- Ollama monitoring is optional and does not itself guarantee GPU acceleration.
- Performance-profile persistence and fan behavior depend on the application's implementation and ASUS control utilities.

## Contributing

Contributions, bug reports, and compatibility testing on additional ASUS models are welcome. Please include your laptop model, Linux distribution, kernel version, and `asusctl` version when reporting hardware-specific issues.

## License

Choose a license before distributing the project. If you intend to make it open source, add the corresponding license file to the repository.

---

**Built for Linux enthusiasts who want a unified view of their ASUS laptop's hardware and AI workloads.**
