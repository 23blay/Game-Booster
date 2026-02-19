import subprocess
import threading
import time
import tkinter as tk
from tkinter import ttk

import psutil

try:
    import win32api
    import win32con
    import win32gui
    import win32process
except Exception:
    win32api = None
    win32con = None
    win32gui = None
    win32process = None

CHECK_INTERVAL = 1.0
RUNNING = False

# Processes that usually consume resources while gaming.
BACKGROUND_TARGETS = {
    "chrome.exe",
    "msedge.exe",
    "firefox.exe",
    "discord.exe",
    "epicgameslauncher.exe",
    "steamwebhelper.exe",
    "onedrive.exe",
    "searchhost.exe",
    "widgets.exe",
}


class Optimizer:
    def __init__(self, status_label, detail_label):
        self.status_label = status_label
        self.detail_label = detail_label
        self.last_boosted_pid = None
        self.original_priorities = {}

    @staticmethod
    def is_windows_supported():
        return all((win32gui, win32process, win32api, win32con))

    def get_foreground_window(self):
        if not self.is_windows_supported():
            return None
        hwnd = win32gui.GetForegroundWindow()
        return hwnd if hwnd else None

    def get_foreground_pid(self):
        hwnd = self.get_foreground_window()
        if not hwnd:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid

    def is_fullscreen_window(self, hwnd):
        """Treat any borderless/fullscreen foreground app as a game target."""
        if not hwnd or not self.is_windows_supported():
            return False

        if not win32gui.IsWindowVisible(hwnd):
            return False

        # Ignore desktop and shell windows.
        class_name = win32gui.GetClassName(hwnd)
        if class_name in {"Progman", "WorkerW", "Shell_TrayWnd"}:
            return False

        left, top, right, bottom = win32gui.GetWindowRect(hwnd)
        width = right - left
        height = bottom - top

        monitor = win32api.MonitorFromWindow(hwnd, win32con.MONITOR_DEFAULTTONEAREST)
        monitor_info = win32api.GetMonitorInfo(monitor)
        mon_left, mon_top, mon_right, mon_bottom = monitor_info["Monitor"]
        mon_width = mon_right - mon_left
        mon_height = mon_bottom - mon_top

        # Allow tiny border mismatches for borderless fullscreen windows.
        width_match = abs(width - mon_width) <= 8
        height_match = abs(height - mon_height) <= 8

        if not (width_match and height_match):
            return False

        # Exclude minimized windows.
        return not win32gui.IsIconic(hwnd)

    def set_process_high_priority(self, pid):
        try:
            proc = psutil.Process(pid)
            if pid not in self.original_priorities:
                self.original_priorities[pid] = proc.nice()

            proc.nice(psutil.HIGH_PRIORITY_CLASS)
            proc.cpu_affinity(list(range(psutil.cpu_count(logical=True))))
            return proc
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            return None

    def tune_background_apps(self, active_pid):
        throttled = 0
        for proc in psutil.process_iter(["pid", "name"]):
            try:
                pid = proc.info["pid"]
                name = (proc.info["name"] or "").lower()
                if pid == active_pid:
                    continue

                if name in BACKGROUND_TARGETS:
                    psutil.Process(pid).nice(psutil.IDLE_PRIORITY_CLASS)
                    throttled += 1
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                continue

        return throttled

    def apply_system_tweaks(self):
        """Enable high performance power profile when possible."""
        try:
            # High performance GUID (built-in on Windows)
            subprocess.run(
                ["powercfg", "/SETACTIVE", "SCHEME_MIN"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        except Exception:
            pass

    def update_status(self, text, detail, color):
        self.status_label.config(text=text, fg=color)
        self.detail_label.config(text=detail)

    def monitor(self):
        global RUNNING
        self.apply_system_tweaks()

        while RUNNING:
            pid = self.get_foreground_pid()
            hwnd = self.get_foreground_window()

            if pid and hwnd and self.is_fullscreen_window(hwnd):
                proc = self.set_process_high_priority(pid)
                if proc:
                    throttled = self.tune_background_apps(pid)
                    self.last_boosted_pid = pid
                    self.update_status(
                        text=f"BOOSTING: {proc.name()}",
                        detail=f"Fullscreen detected • PID {pid} • throttled {throttled} background app(s)",
                        color="#0f4c1a",
                    )
                else:
                    self.update_status(
                        text="Detected fullscreen app (limited permissions)",
                        detail="Run as administrator for deeper process priority tuning.",
                        color="#8a6d00",
                    )
            else:
                self.update_status(
                    text="Idle - waiting for fullscreen application",
                    detail="Start any game/app in fullscreen or borderless fullscreen mode.",
                    color="#666666",
                )

            time.sleep(CHECK_INTERVAL)


def start():
    global RUNNING
    if RUNNING:
        return
    RUNNING = True
    status_label.config(text="Monitoring...", fg="#555555")
    detail_label.config(text="Initializing booster engine...")
    threading.Thread(target=optimizer.monitor, daemon=True).start()


def stop():
    global RUNNING
    RUNNING = False
    status_label.config(text="Stopped", fg="#999999")
    detail_label.config(text="All active monitoring has been disabled.")


# ===== UI =====
root = tk.Tk()
root.title("Extreme Fullscreen Game Booster")
root.geometry("560x280")
root.configure(bg="white")
root.resizable(False, False)

style = ttk.Style()
style.theme_use("clam")

title = tk.Label(
    root,
    text="Extreme Fullscreen Game Booster",
    font=("Segoe UI", 17, "bold"),
    bg="white",
    fg="#101010",
)
title.pack(pady=(20, 8))

subtitle = tk.Label(
    root,
    text="Auto-detects any fullscreen app and applies aggressive performance tuning",
    font=("Segoe UI", 9),
    bg="white",
    fg="#666666",
)
subtitle.pack(pady=(0, 12))

status_label = tk.Label(
    root,
    text="Ready",
    font=("Segoe UI", 12, "bold"),
    bg="white",
    fg="#4a4a4a",
)
status_label.pack(pady=4)

detail_label = tk.Label(
    root,
    text="Press Start to enable real-time fullscreen detection and boosting.",
    font=("Segoe UI", 10),
    bg="white",
    fg="#666666",
)
detail_label.pack(pady=4)

button_frame = tk.Frame(root, bg="white")
button_frame.pack(pady=24)

start_btn = tk.Button(
    button_frame,
    text="Start Booster",
    font=("Segoe UI", 10, "bold"),
    width=18,
    bg="#eaf7ea",
    activebackground="#dcf0dc",
    bd=0,
    command=start,
)
start_btn.grid(row=0, column=0, padx=10)

stop_btn = tk.Button(
    button_frame,
    text="Stop",
    font=("Segoe UI", 10),
    width=12,
    bg="#f1f1f1",
    activebackground="#e6e6e6",
    bd=0,
    command=stop,
)
stop_btn.grid(row=0, column=1, padx=10)

optimizer = Optimizer(status_label, detail_label)

root.mainloop()
