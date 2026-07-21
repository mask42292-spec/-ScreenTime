#!/usr/bin/env python3
"""ScreenTime Desktop Floating Ball - shows users the tracker is running."""

import os
import sys
import time
import threading
import subprocess
import socket
import webbrowser

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# ── Singleton: prevent duplicate instances via Windows Named Mutex ──
# Kernel mutexes are atomic (no TOCTOU race), auto-released on process exit
# (including crashes), and immune to PID recycling.  Far more robust than
# a PID‑file approach.
if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    _kernel32 = ctypes.windll.kernel32
    _CreateMutexW = _kernel32.CreateMutexW
    _CreateMutexW.argtypes = [wintypes.LPCVOID, wintypes.BOOL, wintypes.LPCWSTR]
    _CreateMutexW.restype = wintypes.HANDLE

    ERROR_ALREADY_EXISTS = 183
    MUTEX_NAME = "Local\\ScreenTimeFloatBallSingleton"

    _mutex_handle = _CreateMutexW(None, False, MUTEX_NAME)
    if _kernel32.GetLastError() == ERROR_ALREADY_EXISTS:
        # Another float_ball instance is already running – exit silently.
        if _mutex_handle:
            _kernel32.CloseHandle(_mutex_handle)
        sys.exit(0)
else:
    # Non-Windows fallback: keep the PID-file approach
    import atexit
    PID_FILE = os.path.join(SCRIPT_DIR, ".float_ball.pid")
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE) as f:
                old_pid = int(f.read().strip())
            os.kill(old_pid, 0)
            sys.exit(0)
        except (OSError, ValueError):
            pass
    with open(PID_FILE, "w") as f:
        f.write(str(os.getpid()))
    def _cleanup_pid():
        try:
            os.remove(PID_FILE)
        except Exception:
            pass
    atexit.register(_cleanup_pid)

# Read port
port_file = os.path.join(SCRIPT_DIR, ".port")
PORT = 19999
if os.path.exists(port_file):
    with open(port_file) as f:
        try:
            PORT = int(f.read().strip())
        except:
            pass

PANEL_URL = f"http://localhost:{PORT}"

try:
    import tkinter as tk
except ImportError:
    # If tkinter not available, just exit silently
    sys.exit(0)


class CropDialog:
    """Dialog for cropping an image with a circular overlay matching the float ball size."""

    DISPLAY_MAX = 500

    def __init__(self, parent, pil_image, target_size, callback):
        self.pil_image = pil_image
        self.target_size = target_size
        self.callback = callback

        # Scale image to fit display area
        w, h = pil_image.size
        scale = min(self.DISPLAY_MAX / w, self.DISPLAY_MAX / h, 1.0)
        self.display_w = int(w * scale)
        self.display_h = int(h * scale)
        self.scale = scale

        # Display image
        from PIL import ImageTk
        display_img = pil_image.resize((self.display_w, self.display_h), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(display_img)

        # Create window – use a hidden Tk root so we don't rely on
        # the overrideredirect float ball as parent (grab_set fails on those).
        self._tk_root = tk.Tk()
        self._tk_root.withdraw()
        self._tk_root.attributes("-alpha", 0)

        self.win = tk.Toplevel(self._tk_root)
        self.win.title("裁剪悬浮球图片 — 拖动圆圈选择区域")
        self.win.resizable(False, False)
        self.win.attributes("-topmost", True)
        # Pre-calculate geometry so the canvas opens at the right size
        self.win.geometry(f"{self.display_w}x{self.display_h + 42}")

        self.canvas = tk.Canvas(
            self.win, width=self.display_w, height=self.display_h,
            highlightthickness=0, bg="#1c1c1e"
        )
        self.canvas.pack()

        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        self.crop_x = (self.display_w - self.target_size) / 2
        self.crop_y = (self.display_h - self.target_size) / 2

        self.circle_outline = self.canvas.create_oval(
            self.crop_x, self.crop_y,
            self.crop_x + self.target_size, self.crop_y + self.target_size,
            outline="#007AFF", width=2, dash=(4, 2)
        )

        # Hint text
        self.canvas.create_text(
            self.display_w / 2, self.display_h - 16,
            text="拖动圆圈选择区域，点击「确认」完成",
            fill="#888", font=("Microsoft YaHei", 10)
        )

        # Drag state
        self.dragging = False
        self.drag_start_x = 0
        self.drag_start_y = 0
        self.circle_start_x = 0
        self.circle_start_y = 0

        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)

        # Buttons
        btn_frame = tk.Frame(self.win, bg="#1c1c1e")
        btn_frame.pack(pady=10)

        tk.Button(
            btn_frame, text="确认", command=self.on_confirm,
            bg="#007AFF", fg="white", font=("Microsoft YaHei", 11, "bold"),
            relief="flat", padx=24, pady=6, cursor="hand2"
        ).pack(side="left", padx=8)

        tk.Button(
            btn_frame, text="取消", command=self._destroy_dialog,
            bg="#444", fg="white", font=("Microsoft YaHei", 11),
            relief="flat", padx=24, pady=6, cursor="hand2"
        ).pack(side="left", padx=8)

        # Center on screen
        self.win.update_idletasks()
        sw = self.win.winfo_screenwidth()
        sh = self.win.winfo_screenheight()
        dw = self.win.winfo_reqwidth()
        dh = self.win.winfo_reqheight()
        self.win.geometry(f"+{(sw - dw)//2}+{(sh - dh)//2}")

        self.win.deiconify()
        self.win.focus_force()
        self.win.grab_set()

    def on_press(self, event):
        cx = self.crop_x + self.target_size / 2
        cy = self.crop_y + self.target_size / 2
        dx = event.x - cx
        dy = event.y - cy
        if dx * dx + dy * dy <= (self.target_size / 2 + 30) ** 2:
            self.dragging = True
            self.drag_start_x = event.x
            self.drag_start_y = event.y
            self.circle_start_x = self.crop_x
            self.circle_start_y = self.crop_y

    def on_drag(self, event):
        if not self.dragging:
            return
        dx = event.x - self.drag_start_x
        dy = event.y - self.drag_start_y
        self.crop_x = max(0, min(self.display_w - self.target_size, self.circle_start_x + dx))
        self.crop_y = max(0, min(self.display_h - self.target_size, self.circle_start_y + dy))
        self.canvas.coords(
            self.circle_outline,
            self.crop_x, self.crop_y,
            self.crop_x + self.target_size, self.crop_y + self.target_size
        )

    def on_release(self, event):
        self.dragging = False

    def _destroy_dialog(self):
        """Destroy dialog and the hidden helper root."""
        self.win.destroy()
        self._tk_root.destroy()

    def on_confirm(self):
        ox = int(self.crop_x / self.scale)
        oy = int(self.crop_y / self.scale)
        osize = int(self.target_size / self.scale)

        cropped = self.pil_image.crop((ox, oy, ox + osize, oy + osize))
        self._destroy_dialog()
        self.callback(cropped)


class FloatBall:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("ScreenTime")
        self.root.overrideredirect(True)
        self.root.attributes("-topmost", True)
        self.root.attributes("-transparentcolor", "#010101")

        self.size = 56
        self.x = self.root.winfo_screenwidth() - self.size - 20
        self.y = self.root.winfo_screenheight() // 2 - self.size // 2

        self.root.geometry(f"{self.size}x{self.size}+{self.x}+{self.y}")

        self.canvas = tk.Canvas(
            self.root, width=self.size, height=self.size,
            bg="#010101", highlightthickness=0
        )
        self.canvas.pack()

        self.ball_radius = 24
        self.cx = self.size // 2
        self.cy = self.size // 2

        self.ball_id = self.canvas.create_oval(
            self.cx - self.ball_radius, self.cy - self.ball_radius,
            self.cx + self.ball_radius, self.cy + self.ball_radius,
            fill="#007AFF", outline=""
        )

        # Try to load custom image
        custom_img = os.path.join(SCRIPT_DIR, "float_ball.png")
        self.custom_image_id = None
        if os.path.exists(custom_img):
            try:
                from PIL import Image, ImageDraw, ImageTk
                img = Image.open(custom_img).convert("RGBA")
                size = self.ball_radius * 2
                img = img.resize((size, size), Image.LANCZOS)
                # Apply circle mask
                mask = Image.new("L", (size, size), 0)
                ImageDraw.Draw(mask).ellipse((0, 0, size, size), fill=255)
                img.putalpha(mask)
                self._tk_image = ImageTk.PhotoImage(img)
                self.custom_image_id = self.canvas.create_image(
                    self.cx, self.cy, image=self._tk_image
                )
            except Exception:
                pass

        # Fallback text
        if self.custom_image_id is None:
            self.text_id = self.canvas.create_text(
                self.cx, self.cy, text="ST", font=("Segoe UI", 14, "bold"),
                fill="#ffffff"
            )
        else:
            self.text_id = None

        # Shadow ring for depth
        self.shadow_id = self.canvas.create_oval(
            self.cx - self.ball_radius - 1, self.cy - self.ball_radius - 1,
            self.cx + self.ball_radius + 1, self.cy + self.ball_radius + 1,
            fill="", outline="#ffffff", width=1
        )
        self.canvas.itemconfig(self.shadow_id, state="hidden")

        # Drag state
        self.dragging = False
        self.drag_offset_x = 0
        self.drag_offset_y = 0

        # Bind events
        self.canvas.bind("<Button-1>", self.on_press)
        self.canvas.bind("<B1-Motion>", self.on_drag)
        self.canvas.bind("<ButtonRelease-1>", self.on_release)
        self.canvas.bind("<Double-Button-1>", self.on_double_click)
        self.canvas.bind("<Button-3>", self.on_right_click)
        self.root.bind("<Escape>", lambda e: self.hide_ball())

        # Context menu
        self.menu = tk.Menu(self.root, tearoff=0)
        self.menu.add_command(label="打开面板", command=self.open_panel)
        self.menu.add_command(label="自定义图片", command=self.customize_image)
        self.menu.add_separator()
        self.menu.add_command(label="隐藏悬浮球", command=self.hide_ball)
        self.menu.add_command(label="关闭脚本", command=self.shutdown_all)

        # Pulse animation
        self.pulse_phase = 0
        self.running = True
        self.pulse_animation()

        # Monitor server health
        self.health_thread = threading.Thread(target=self.monitor_health, daemon=True)
        self.health_thread.start()

    def on_press(self, event):
        self.dragging = True
        self.drag_offset_x = event.x
        self.drag_offset_y = event.y
        self.canvas.itemconfig(self.shadow_id, state="normal")

    def on_drag(self, event):
        if self.dragging:
            new_x = self.root.winfo_x() + event.x - self.drag_offset_x
            new_y = self.root.winfo_y() + event.y - self.drag_offset_y
            self.root.geometry(f"+{new_x}+{new_y}")

    def on_release(self, event):
        self.dragging = False
        self.canvas.itemconfig(self.shadow_id, state="hidden")

    def on_double_click(self, event):
        self.open_panel()

    def on_right_click(self, event):
        try:
            self.menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.menu.grab_release()

    def open_panel(self):
        webbrowser.open(PANEL_URL)

    def customize_image(self):
        """Open file dialog to pick an image, then crop dialog."""
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            title="选择悬浮球图片",
            filetypes=[("图片文件", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"), ("所有文件", "*.*")]
        )
        if not path:
            return
        try:
            from PIL import Image
            img = Image.open(path).convert("RGBA")
        except Exception as e:
            from tkinter import messagebox
            messagebox.showerror("错误", f"无法打开图片:\n{e}")
            return

        target_size = self.ball_radius * 2  # 48px for 56px ball (ball_radius=24)

        # If image is small enough, just resize and save directly
        if img.width <= target_size * 3 and img.height <= target_size * 3:
            self._save_and_reload_icon(img, target_size)
            return

        # Open crop dialog
        CropDialog(self.root, img, target_size, callback=lambda cropped: self._save_and_reload_icon(cropped, target_size))

    def _save_and_reload_icon(self, img, target_size):
        """Resize image to target_size, apply circle mask, save and reload."""
        from PIL import Image, ImageDraw, ImageTk

        # Resize
        img = img.resize((target_size, target_size), Image.LANCZOS)

        # Circle mask
        mask = Image.new("L", (target_size, target_size), 0)
        ImageDraw.Draw(mask).ellipse((0, 0, target_size, target_size), fill=255)
        img.putalpha(mask)

        custom_img = os.path.join(SCRIPT_DIR, "float_ball.png")
        img.save(custom_img)

        # Reload in float ball
        self._tk_image = ImageTk.PhotoImage(img)
        if self.custom_image_id:
            self.canvas.delete(self.custom_image_id)
        if self.text_id:
            self.canvas.delete(self.text_id)
            self.text_id = None
        self.custom_image_id = self.canvas.create_image(
            self.cx, self.cy, image=self._tk_image
        )

    def hide_ball(self):
        self.running = False
        self.root.destroy()

    def shutdown_all(self):
        """Kill all ScreenTime processes (server, collector) and close float ball."""
        import signal
        killed = []
        try:
            import psutil
            current_pid = os.getpid()
            for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                try:
                    cmdline = " ".join(proc.info["cmdline"] or [])
                    if proc.info["pid"] == current_pid:
                        continue
                    if "ScreenTime" in cmdline and any(x in cmdline for x in ("server.py", "collector.py")):
                        proc.terminate()
                        killed.append(proc.info["pid"])
                except:
                    pass
            if killed:
                time.sleep(0.5)
                # Force kill any that didn't terminate
                for proc in psutil.process_iter(["pid", "name", "cmdline"]):
                    try:
                        cmdline = " ".join(proc.info["cmdline"] or [])
                        if proc.info["pid"] in killed:
                            if proc.is_running():
                                proc.kill()
                    except:
                        pass
        except ImportError:
            # Fallback: use taskkill
            subprocess.run(
                ['taskkill', '/F', '/FI', 'IMAGENAME eq python.exe', '/FI', 'WINDOWTITLE eq ScreenTime'],
                capture_output=True
            )
        self.hide_ball()

    def pulse_animation(self):
        if not self.running:
            return
        self.pulse_phase = (self.pulse_phase + 1) % 120
        import math
        if self.custom_image_id is None:
            # Only pulse the circle if no custom image
            scale = 1.0 + 0.03 * math.sin(self.pulse_phase * math.pi / 30)
            r = int(self.ball_radius * scale)
            self.canvas.coords(
                self.ball_id,
                self.cx - r, self.cy - r,
                self.cx + r, self.cy + r
            )
        # Color shift for "alive" feel
        g = int(122 + 20 * math.sin(self.pulse_phase * math.pi / 40))
        b = int(255 - 20 * math.sin(self.pulse_phase * math.pi / 40))
        color = f"#{0:02x}{max(0,min(255,g)):02x}{max(0,min(255,b)):02x}"
        self.canvas.itemconfig(self.ball_id, fill=color)

        self.root.after(40, self.pulse_animation)

    def monitor_health(self):
        """Check if server is still alive; exit if not."""
        time.sleep(5)  # Initial grace period
        fail_count = 0
        while self.running:
            try:
                s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                s.settimeout(2)
                s.connect(("127.0.0.1", PORT))
                s.close()
                fail_count = 0
            except:
                fail_count += 1
                if fail_count >= 5:
                    # Server has been down for ~50s, exit
                    self.running = False
                    self.root.after(0, self.root.destroy)
                    return
            time.sleep(10)

    def run(self):
        self.root.mainloop()


if __name__ == "__main__":
    # Wait a moment for server to start
    time.sleep(1.5)
    if "--hidden" not in sys.argv:
        FloatBall().run()
