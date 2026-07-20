#!/usr/bin/env python3
"""ScreenTime Background Collector - Real system usage data collection"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import time
import logging
import threading
from datetime import datetime
from collections import defaultdict

from db_manager import (
    init_db, upsert_daily_summary, upsert_app_usage, upsert_notification,
    DB_DIR
)

# ── Logger ──
LOG_PATH = os.path.join(DB_DIR, "collector.log")
logging.basicConfig(
    filename=LOG_PATH,
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("collector")

# ── Windows APIs ──
try:
    import win32gui
    import win32process
    import win32api
    import win32con
except ImportError:
    logger.error("pywin32 not installed. Run: pip install pywin32")
    sys.exit(1)

try:
    import psutil
except ImportError:
    logger.error("psutil not installed. Run: pip install psutil")
    sys.exit(1)

# ── Idle detection ──
try:
    from ctypes import Structure, windll, c_uint, sizeof, byref

    class LASTINPUTINFO(Structure):
        _fields_ = [("cbSize", c_uint), ("dwTime", c_uint)]

    def get_idle_seconds():
        lii = LASTINPUTINFO()
        lii.cbSize = sizeof(LASTINPUTINFO)
        windll.user32.GetLastInputInfo(byref(lii))
        return (windll.kernel32.GetTickCount() - lii.dwTime) / 1000.0
except Exception:
    def get_idle_seconds():
        return 0

IDLE_THRESHOLD = 300  # 5 minutes

# ── Notification reading ──
def read_notifications():
    """Try to read Windows notification DB"""
    notif_path = os.path.join(
        os.environ.get("LOCALAPPDATA", ""),
        r"Microsoft\Windows\Notifications\wpndatabase.db"
    )
    counts = defaultdict(int)
    if not os.path.exists(notif_path):
        return counts
    try:
        import sqlite3
        conn = sqlite3.connect(notif_path, timeout=2, uri=True if "?" in notif_path else False)
        cursor = conn.execute("SELECT AppId FROM Notification WHERE ArrivalTime > ?",
                              (datetime.now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat(),))
        for row in cursor:
            app = (row[0] or "未知").split("!")[0] if row[0] else "未知"
            counts[app] += 1
        conn.close()
    except Exception:
        pass
    return counts

# ── Process helpers ──
def get_foreground_process():
    """Get the process name of the foreground window"""
    try:
        hwnd = win32gui.GetForegroundWindow()
        _, pid = win32process.GetWindowThreadProcessId(hwnd)
        window_title = win32gui.GetWindowText(hwnd)
        try:
            proc = psutil.Process(pid)
            proc_name = proc.name().lower()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return None, ""
        return proc_name, window_title
    except Exception:
        return None, ""

def get_running_processes():
    """Get list of running process names"""
    procs = set()
    for proc in psutil.process_iter(["name"]):
        try:
            procs.add(proc.info["name"].lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return procs

# ── Main Collector ──
class ScreenTimeCollector:
    def __init__(self):
        init_db()
        self.buffer = defaultdict(lambda: {"fg": 0, "bg": 0, "launches": 0, "notifs": 0, "title": ""})
        self.daily_buffer = {"active": 0, "idle": 0, "notif": 0}
        self.notif_buffer = defaultdict(int)
        self.last_process = None
        self.last_check = time.time()
        self.last_flush = time.time()
        self.last_notif_check = 0
        self.running = True
        self.restart_count = 0
        self.max_restarts = 10

    def flush(self):
        """Write buffer to SQLite"""
        now = datetime.now()
        date = now.strftime("%Y-%m-%d")
        hour = now.hour

        for proc_name, data in self.buffer.items():
            if data["fg"] > 0 or data["bg"] > 0:
                upsert_app_usage(
                    date, hour, proc_name, data["title"],
                    data["fg"], data["bg"], data["launches"], data["notifs"]
                )

        for app_name, cnt in self.notif_buffer.items():
            if cnt > 0:
                upsert_notification(date, hour, app_name, cnt)

        if self.daily_buffer["active"] > 0 or self.daily_buffer["idle"] > 0:
            upsert_daily_summary(
                date, self.daily_buffer["active"],
                self.daily_buffer["idle"], self.daily_buffer["notif"]
            )

        self.buffer.clear()
        self.notif_buffer.clear()
        self.daily_buffer = {"active": 0, "idle": 0, "notif": 0}
        self.last_flush = time.time()
        logger.info(f"Flushed data at {now.strftime('%H:%M:%S')}")

    def tick(self):
        """Single collection tick"""
        now_time = time.time()
        elapsed = now_time - self.last_check
        self.last_check = now_time

        # Cap elapsed to prevent sleep/wake from injecting hours into a single tick.
        # After system sleep, time.time() advances but GetTickCount() does not,
        # causing the idle check to pass and huge elapsed values to inflate active/foreground time.
        MAX_TICK_ELAPSED = 5  # seconds – tick loop sleeps 1s, so 5s is generous overhead
        overflow = 0
        if elapsed > MAX_TICK_ELAPSED:
            overflow = int(elapsed - MAX_TICK_ELAPSED)
            elapsed = MAX_TICK_ELAPSED

        # Overflow from sleep/wake: treat as idle
        if overflow > 0:
            self.daily_buffer["idle"] += overflow

        # Idle check
        idle_secs = get_idle_seconds()
        is_idle = idle_secs > IDLE_THRESHOLD

        if is_idle:
            self.daily_buffer["idle"] += int(elapsed)
            # Still track background processes
            running = get_running_processes()
            for proc in running:
                self.buffer[proc]["bg"] += int(elapsed)
            return

        self.daily_buffer["active"] += int(elapsed)

        # Foreground
        fg_proc, window_title = get_foreground_process()
        if fg_proc:
            self.buffer[fg_proc]["fg"] += int(elapsed)
            if window_title:
                self.buffer[fg_proc]["title"] = window_title
            if fg_proc != self.last_process:
                self.buffer[fg_proc]["launches"] += 1
                self.last_process = fg_proc

        # Background processes
        running = get_running_processes()
        for proc in running:
            if proc != fg_proc:
                self.buffer[proc]["bg"] += int(elapsed)

        # Notifications (every 60s)
        if now_time - self.last_notif_check > 60:
            notifs = read_notifications()
            for app, cnt in notifs.items():
                self.notif_buffer[app] += cnt
                self.daily_buffer["notif"] += cnt
            self.last_notif_check = now_time

    def run(self):
        """Main loop"""
        logger.info("ScreenTime Collector started")
        print(f"[Collector] Started. Log: {LOG_PATH}")
        try:
            while self.running:
                self.tick()
                time.sleep(1)

                if time.time() - self.last_flush >= 60:
                    self.flush()
        except KeyboardInterrupt:
            logger.info("Collector interrupted by user")
        except Exception as e:
            logger.error(f"Collector crashed: {e}")
            raise
        finally:
            self.flush()
            logger.info("ScreenTime Collector stopped")

    def run_with_watchdog(self):
        """Run with crash recovery"""
        while self.restart_count < self.max_restarts:
            try:
                self.run()
                break
            except KeyboardInterrupt:
                break
            except Exception as e:
                self.restart_count += 1
                logger.error(f"Watchdog restart {self.restart_count}/{self.max_restarts}: {e}")
                if self.restart_count >= self.max_restarts:
                    logger.error("Max restarts reached. Exiting.")
                    break
                time.sleep(5)


def ensure_single_instance(lock_file):
    """Prevent multiple collector instances via PID-based lock file."""
    import json
    my_pid = os.getpid()
    if os.path.exists(lock_file):
        try:
            with open(lock_file, "r") as f:
                old = json.load(f)
            old_pid = old.get("pid", 0)
            try:
                import psutil
                if psutil.pid_exists(old_pid):
                    proc = psutil.Process(old_pid)
                    cmd = " ".join(proc.cmdline() or [])
                    if "collector.py" in cmd:
                        logger.warning("Another collector (PID %d) is still running. Exiting.", old_pid)
                        print(f"[Collector] Another instance (PID {old_pid}) is already running. Exiting.")
                        return False
            except Exception:
                pass
        except Exception:
            pass
    with open(lock_file, "w") as f:
        json.dump({"pid": my_pid, "started": datetime.now().isoformat()}, f)
    return True


if __name__ == "__main__":
    lock_file = os.path.join(DB_DIR, ".collector.lock")
    if not ensure_single_instance(lock_file):
        sys.exit(0)
    try:
        collector = ScreenTimeCollector()
        collector.run_with_watchdog()
    finally:
        try:
            os.remove(lock_file)
        except Exception:
            pass
