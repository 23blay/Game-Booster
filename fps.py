import tkinter as tk
from tkinter import ttk
import psutil
import threading
import time

try:
    import win32gui
    import win32process
except:
    win32gui = None

CHECK_INTERVAL = 3
RUNNING = False

GAME_LIST = [
    "forhonor.exe",
    "r6.exe",
    "valorant.exe",
    "cs2.exe"
]

BACKGROUND_TARGETS = [
    "chrome.exe",
    "msedge.exe",
    "discord.exe",
    "epicgameslauncher.exe",
    "steamwebhelper.exe"
]


class Optimizer:
    def __init__(self, status_label):
        self.status_label = status_label
        self.current_game_pid = None

    def get_foreground_pid(self):
        if not win32gui:
            return None
        hwnd = win32gui.GetForegroundWindow()
        if hwnd == 0:
            return None
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        return pid

    def boost_game(self, pid):
        try:
            p = psutil.Process(pid)
            p.nice(psutil.HIGH_PRIORITY_CLASS)
            p.cpu_affinity(list(range(psutil.cpu_count())))
        except:
            pass

    def lower_background(self):
        for proc in psutil.process_iter(['pid', 'name']):
            try:
                name = proc.info['name'].lower()
                if name in BACKGROUND_TARGETS:
                    p = psutil.Process(proc.info['pid'])
                    p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
            except:
                continue

    def monitor(self):
        global RUNNING
        while RUNNING:
            pid = self.get_foreground_pid()

            if pid:
                try:
                    process = psutil.Process(pid)
                    name = process.name().lower()

                    if name in GAME_LIST:
                        self.status_label.config(text=f"Boosting: {name}", fg="#1a1a1a")
                        self.boost_game(pid)
                        self.lower_background()
                    else:
                        self.status_label.config(text="Idle (no game detected)", fg="#777777")

                except:
                    pass

            time.sleep(CHECK_INTERVAL)


def start():
    global RUNNING
    RUNNING = True
    status_label.config(text="Monitoring...", fg="#777777")
    threading.Thread(target=optimizer.monitor, daemon=True).start()


def stop():
    global RUNNING
    RUNNING = False
    status_label.config(text="Stopped", fg="#999999")


# ===== UI =====
root = tk.Tk()
root.title("Smart Gaming Optimizer")
root.geometry("420x220")
root.configure(bg="white")
root.resizable(False, False)

style = ttk.Style()
style.theme_use("clam")

title = tk.Label(root,
                 text="Smart Gaming Optimizer",
                 font=("Segoe UI", 16, "bold"),
                 bg="white",
                 fg="#111111")
title.pack(pady=(25, 10))

status_label = tk.Label(root,
                        text="Ready",
                        font=("Segoe UI", 11),
                        bg="white",
                        fg="#777777")
status_label.pack(pady=5)

button_frame = tk.Frame(root, bg="white")
button_frame.pack(pady=25)

start_btn = tk.Button(button_frame,
                      text="Start",
                      font=("Segoe UI", 10),
                      width=12,
                      bg="#f2f2f2",
                      activebackground="#e6e6e6",
                      bd=0,
                      command=start)

start_btn.grid(row=0, column=0, padx=10)

stop_btn = tk.Button(button_frame,
                     text="Stop",
                     font=("Segoe UI", 10),
                     width=12,
                     bg="#f2f2f2",
                     activebackground="#e6e6e6",
                     bd=0,
                     command=stop)

stop_btn.grid(row=0, column=1, padx=10)

optimizer = Optimizer(status_label)

root.mainloop()
