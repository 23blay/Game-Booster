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

CHECK_INTERVAL = 0.7
RUNNING = False

# Apps frequently active while gaming.
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
    "obs64.exe",
    "teams.exe",
}

# Never throttle Windows critical components.
PROTECTED_PROCESSES = {
    "system",
    "registry",
    "dwm.exe",
    "csrss.exe",
    "wininit.exe",
    "winlogon.exe",
    "lsass.exe",
    "services.exe",
    "smss.exe",
    "explorer.exe",
}


class Optimizer:
    def __init__(self, status_label, detail_label, turbo_var):
        self.status_label = status_label
        self.detail_label = detail_label
        self.turbo_var = turbo_var
        self.last_boosted_pid = None
        self.original_priorities = {}
        self.power_plan_applied = False

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
        if not hwnd or not self.is_windows_supported():
            return False
        if not win32gui.IsWindowVisible(hwnd) or win32gui.IsIconic(hwnd):
            return False

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

        return abs(width - mon_width) <= 8 and abs(height - mon_height) <= 8

    def set_process_high_priority(self, pid, turbo=False):
        try:
            proc = psutil.Process(pid)
            if pid not in self.original_priorities:
                self.original_priorities[pid] = proc.nice()

            target_priority = getattr(psutil, "HIGH_PRIORITY_CLASS", 0)
            if turbo:
                target_priority = getattr(psutil, "REALTIME_PRIORITY_CLASS", target_priority)

            proc.nice(target_priority)
            proc.cpu_affinity(list(range(psutil.cpu_count(logical=True))))

            if turbo:
                try:
                    proc.ionice(getattr(psutil, "IOPRIO_HIGH", 3))
                except Exception:
                    pass

            return proc
        except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
            return None

    def tune_background_apps(self, active_pid, turbo=False):
        throttled = 0
        candidates = []
        for proc in psutil.process_iter(["pid", "name", "cpu_percent"]):
            try:
                pid = proc.info["pid"]
                name = (proc.info["name"] or "").lower()
                if pid == active_pid or name in PROTECTED_PROCESSES:
                    continue
                if name in BACKGROUND_TARGETS:
                    candidates.append((proc, name, proc.info.get("cpu_percent", 0.0)))
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                continue

        # In turbo mode lower all target background apps.
        if turbo:
            selected = candidates
        else:
            # Otherwise only lower the most CPU-active to stay safer.
            selected = sorted(candidates, key=lambda item: item[2], reverse=True)[:5]

        for proc, _, _ in selected:
            try:
                proc.nice(getattr(psutil, "IDLE_PRIORITY_CLASS", proc.nice()))
                throttled += 1
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                continue

        return throttled

    def apply_system_tweaks(self):
        if self.power_plan_applied:
            return
        try:
            subprocess.run(
                ["powercfg", "/SETACTIVE", "SCHEME_MIN"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
            self.power_plan_applied = True
        except Exception:
            pass

    def restore_priorities(self):
        for pid, original_priority in list(self.original_priorities.items()):
            try:
                psutil.Process(pid).nice(original_priority)
            except (psutil.AccessDenied, psutil.NoSuchProcess, OSError):
                pass
        self.original_priorities.clear()

    def update_status(self, text, detail, color):
        self.status_label.config(text=text, fg=color)
        self.detail_label.config(text=detail)

    def monitor(self):
        global RUNNING
        self.apply_system_tweaks()

        while RUNNING:
            pid = self.get_foreground_pid()
            hwnd = self.get_foreground_window()
            turbo = self.turbo_var.get()

            if pid and hwnd and self.is_fullscreen_window(hwnd):
                proc = self.set_process_high_priority(pid, turbo=turbo)
                if proc:
                    throttled = self.tune_background_apps(pid, turbo=turbo)
                    self.last_boosted_pid = pid
                    mode = "TURBO" if turbo else "BALANCED"
                    self.update_status(
                        text=f"BOOSTING {mode}: {proc.name()}",
                        detail=f"Fullscreen lock • PID {pid} • tuned {throttled} background app(s)",
                        color="#0f4c1a",
                    )
                else:
                    self.update_status(
                        text="Fullscreen app detected (needs admin)",
                        detail="Run as Administrator to unlock maximum process priority control.",
                        color="#8a6d00",
                    )
            else:
                self.update_status(
                    text="Idle - waiting for fullscreen application",
                    detail="Launch your game fullscreen/borderless, then keep this running.",
                    color="#666666",
                )

            time.sleep(CHECK_INTERVAL)

        self.restore_priorities()


def start():
    global RUNNING
    if RUNNING:
        return
    RUNNING = True
    status_label.config(text="Monitoring...", fg="#555555")
    detail_label.config(text="Booster engine warming up...")
    threading.Thread(target=optimizer.monitor, daemon=True).start()


def stop():
    global RUNNING
    RUNNING = False
    status_label.config(text="Stopped", fg="#999999")
    detail_label.config(text="Monitoring disabled. Priorities restored where possible.")


# ===== UI =====
root = tk.Tk()
root.title("FPS Booster Pro")
root.geometry("600x320")
root.configure(bg="white")
root.resizable(False, False)

style = ttk.Style()
style.theme_use("clam")

title = tk.Label(
    root,
    text="FPS Booster Pro",
    font=("Segoe UI", 18, "bold"),
    bg="white",
    fg="#101010",
)
title.pack(pady=(20, 8))

subtitle = tk.Label(
    root,
    text="High-performance boosts for any fullscreen app to reduce choppy gameplay",
    font=("Segoe UI", 9),
    bg="white",
    fg="#666666",
)
subtitle.pack(pady=(0, 10))

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
    text="Press Start to enable live fullscreen detection and performance tuning.",
    font=("Segoe UI", 10),
    bg="white",
    fg="#666666",
)
detail_label.pack(pady=4)

turbo_var = tk.BooleanVar(value=True)
turbo_check = tk.Checkbutton(
    root,
    text="Turbo mode (maximum boost, may affect multitasking)",
    variable=turbo_var,
    bg="white",
    fg="#333333",
    activebackground="white",
    font=("Segoe UI", 9),
)
turbo_check.pack(pady=(8, 0))

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

optimizer = Optimizer(status_label, detail_label, turbo_var)

root.mainloop()
