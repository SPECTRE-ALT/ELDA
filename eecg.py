import threading
import time
import sys
import webbrowser
from collections import deque
import tkinter as tk
from tkinter import ttk, messagebox
import numpy as np

# Plotting
import matplotlib
matplotlib.use("TkAgg")
from matplotlib.figure import Figure
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

# Serial
try:
    import serial
    from serial.tools import list_ports
except ImportError:
    serial = None
    list_ports = None

# ---------- Config ----------
SERIAL_PORT = 'COM10'  # put your Arduino port here, e.g., 'COM3' or '/dev/ttyUSB0'
BAUD_RATE = 115200
SAMPLE_INTERVAL = 0.01
BUFFER_SECONDS = 10
REMINDER_INTERVAL_SEC = 20 * 60
APP_LINK = "https://6000-firebase-studio-1758901258057.cluster-cz5nqyh5nreq6ua6gaqd7okl7o.cloudworkstations.dev/dashboard"
# --------------------------

class SerialReader(threading.Thread):
    # FIX 1: Was _init_, changed to __init__ (double underscores)
    def __init__(self, port, baudrate, on_sample):
        super().__init__(daemon=True)
        self.port = port
        self.baudrate = baudrate
        self.on_sample = on_sample
        self.running = True
        self._ser = None

    def run(self):
        if serial is None:
            print("pyserial not installed. Cannot use real serial.")
            return
        
        try:
            self._ser = serial.Serial(self.port, self.baudrate, timeout=1)
            print(f"Connected to {self.port} at {self.baudrate} baud")
        except Exception as e:
            print(f"Failed to open {self.port}: {e}")
            return

        while self.running:
            try:
                line = self._ser.readline().decode('utf-8', errors='ignore').strip()
                if not line:
                    continue
                try:
                    sample = int(line)
                    self.on_sample(sample)
                except ValueError:
                    # if line has multiple numbers separated by comma or space
                    parts = line.replace(',', ' ').split()
                    for p in parts:
                        try:
                            sample = int(p)
                            self.on_sample(sample)
                            break
                        except ValueError:
                            continue
            except Exception as e:
                print("Serial read error:", e)
                time.sleep(0.1)

    def stop(self):
        self.running = False
        if self._ser:
            self._ser.close()


class ECGApp:
    # FIX 2: Was _init_, changed to __init__ (double underscores)
    def __init__(self, root):
        self.root = root
        root.title("ECG / Pulse Monitor")
        self.running = True

        self.maxlen = int(BUFFER_SECONDS / SAMPLE_INTERVAL)
        self.timestamps = deque(maxlen=self.maxlen)
        self.values = deque(maxlen=self.maxlen)
        self.peak_timestamps = deque()

        # Serial port UI
        top = ttk.Frame(root, padding=8)
        top.pack(side=tk.TOP, fill=tk.X)
        ttk.Label(top, text="Serial Port:").pack(side=tk.LEFT)
        self.port_var = tk.StringVar(value=SERIAL_PORT)
        ttk.Entry(top, textvariable=self.port_var, width=15).pack(side=tk.LEFT, padx=4)
        ttk.Label(top, text="Baud:").pack(side=tk.LEFT, padx=(10,0))
        self.baud_var = tk.StringVar(value=str(BAUD_RATE))
        ttk.Entry(top, textvariable=self.baud_var, width=10).pack(side=tk.LEFT, padx=4)
        self.connect_btn = ttk.Button(top, text="Connect", command=self.toggle_connect)
        self.connect_btn.pack(side=tk.LEFT, padx=6)

        # BPM and status
        stats = ttk.Frame(root, padding=8)
        stats.pack(fill=tk.X)
        self.bpm_var = tk.StringVar(value="--")
        ttk.Label(stats, text="BPM:").pack(side=tk.LEFT)
        ttk.Label(stats, textvariable=self.bpm_var, font=("Helvetica", 16, "bold")).pack(side=tk.LEFT, padx=6)
        self.status_var = tk.StringVar(value="Idle")
        ttk.Label(stats, text="Status:").pack(side=tk.LEFT, padx=(20,0))
        ttk.Label(stats, textvariable=self.status_var).pack(side=tk.LEFT, padx=6)

        # Plot
        fig = Figure(figsize=(8,3))
        self.ax = fig.add_subplot(111)
        self.ax.set_ylim(0, 1023)
        self.ax.set_xlim(0, BUFFER_SECONDS)
        self.ax.set_xlabel("Time (s)")
        self.ax.set_ylabel("ADC")
        self.line, = self.ax.plot([], [])

        canvas = FigureCanvasTkAgg(fig, master=root)
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        self.canvas = canvas

        # Link UI
        link_frame = ttk.Frame(root, padding=8)
        link_frame.pack(fill=tk.X)
        ttk.Label(link_frame, text="Relax App Link:").pack(side=tk.LEFT)
        self.link_var = tk.StringVar(value=APP_LINK)
        ttk.Entry(link_frame, textvariable=self.link_var, width=70).pack(side=tk.LEFT, padx=4)
        ttk.Button(link_frame, text="Open Link", command=self.open_link_now).pack(side=tk.LEFT, padx=4)

        # Controls
        ttk.Button(root, text="Stop", command=self.stop_app).pack(side=tk.RIGHT, padx=8, pady=4)

        self.reader = None
        self.update_plot()
        self.schedule_next_reminder(REMINDER_INTERVAL_SEC)

    def toggle_connect(self):
        if self.reader and self.reader.is_alive():
            self.reader.stop()
            self.reader = None
            self.connect_btn.config(text="Connect")
            self.status_var.set("Disconnected")
        else:
            port = self.port_var.get().strip()
            baud = int(self.baud_var.get())
            self.reader = SerialReader(port, baud, self.on_sample)
            self.reader.start()
            self.connect_btn.config(text="Disconnect")
            self.status_var.set(f"Running ({port})")

    def on_sample(self, sample):
        ts = time.time()
        self.timestamps.append(ts)
        self.values.append(sample)
        self.detect_peak(ts, sample)

    def detect_peak(self, ts, val):
        if len(self.values) < 5:
            return
        arr = np.array(self.values)
        threshold = arr.mean() + 1.2 * arr.std()
        if val > threshold and (not self.peak_timestamps or ts - self.peak_timestamps[-1] > 0.3):
            self.peak_timestamps.append(ts)
            cutoff = ts - 60
            while self.peak_timestamps and self.peak_timestamps[0] < cutoff:
                self.peak_timestamps.popleft()
            
            # Check for divide by zero if only one peak
            if len(self.peak_timestamps) > 1:
                bpm = len(self.peak_timestamps) * 60 / max(1, self.peak_timestamps[-1]-self.peak_timestamps[0])
                self.bpm_var.set(f"{int(bpm)}")
                if bpm > 110:
                    self.show_quick_suggestion(reason=f"High heart rate: {int(bpm)} BPM")
            else:
                self.bpm_var.set("--") # Not enough data yet


    def update_plot(self):
        if self.timestamps:
            t0 = self.timestamps[0]
            xs = np.array(self.timestamps) - t0
            ys = np.array(self.values)
            self.ax.set_xlim(max(0, xs[-1]-BUFFER_SECONDS), max(BUFFER_SECONDS, xs[-1]))
            self.line.set_data(xs, ys)
        else:
            self.line.set_data([], [])
        self.canvas.draw_idle()
        if self.running:
            self.root.after(int(SAMPLE_INTERVAL*1000), self.update_plot)

    def schedule_next_reminder(self, delay_sec):
        self.root.after(int(delay_sec*1000), self.show_reminder_popup)

    def show_reminder_popup(self):
        if not self.running: return # Don't show if app is closing
        resp = messagebox.askyesno("Relaxation suggestion", "Time for a short relaxation break. Open the app?")
        if resp:
            self.open_link_now()
        # Schedule the *next* one only after this one is handled
        if self.running:
            self.schedule_next_reminder(REMINDER_INTERVAL_SEC)

    def show_quick_suggestion(self, reason=""):
        popup = tk.Toplevel(self.root)
        popup.title("Suggestion")
        ttk.Label(popup, text=f"{reason}\nTry this app to relax.", wraplength=300).pack(padx=10, pady=10)
        ttk.Button(popup, text="Open App", command=lambda: [self.open_link_now(), popup.destroy()]).pack(side=tk.LEFT, padx=5)
        ttk.Button(popup, text="Dismiss", command=popup.destroy).pack(side=tk.LEFT, padx=5)
        popup.after(15000, popup.destroy)

    def open_link_now(self):
        link = self.link_var.get().strip()
        if link:
            webbrowser.open(link)

    def stop_app(self):
        self.running = False
        if self.reader:
            self.reader.stop()
        self.root.quit()


# FIX 3: Was _name_ == "_main_", changed to __name__ == "__main__"
if __name__ == "__main__":
    if serial is None:
        print("="*50)
        print("ERROR: 'pyserial' library not found.")
        print("Please install it by running: pip install pyserial")
        print("="*50)
        sys.exit(1)
        
    root = tk.Tk()
    app = ECGApp(root)
    root.protocol("WM_DELETE_WINDOW", app.stop_app)
    root.mainloop()