#!/usr/bin/env python3
"""ScreenTime SQLite Database Manager"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import sqlite3
import threading

DB_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(DB_DIR, "screentime.db")

_local = threading.local()

def get_connection():
    if not hasattr(_local, "conn") or _local.conn is None:
        _local.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        _local.conn.execute("PRAGMA journal_mode=WAL")
        _local.conn.execute("PRAGMA synchronous=NORMAL")
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

DEFAULT_CATEGORIES = {
    "工作": "winword,excel,powerpnt,code,vscode,sublime_text,notepad++,idea,pycharm,eclipse,devenv,outlook,onenote,notepad,terminal,cmd,powershell,xshell,putty,wps,typora,obsidian,logseq",
    "娱乐": "steam,bilibili,potplayer,vlc,spotify,qqmusic,kugou,douyin,tiktok,youku,iqiyi,mangotv,netease,cloudmusic,game,xbox,epicgames,league of legends,genshin,minecraft",
    "社交": "wechat,weixin,qq,dingtalk,telegram,discord,slack,teams,feishu,lark,skype,zoom,tim",
    "学习": "chrome,msedge,firefox,brave,pdf,reader,acrobat,calibre,zotero,endnote,anki,duolingo",
}

def init_db():
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS daily_summary (
            date TEXT PRIMARY KEY,
            total_active_seconds INTEGER DEFAULT 0,
            total_idle_seconds INTEGER DEFAULT 0,
            total_notifications INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS app_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            hour INTEGER,
            process_name TEXT,
            window_title TEXT DEFAULT '',
            foreground_seconds INTEGER DEFAULT 0,
            background_seconds INTEGER DEFAULT 0,
            launch_count INTEGER DEFAULT 0,
            notification_count INTEGER DEFAULT 0,
            last_updated TEXT DEFAULT (datetime('now','localtime')),
            UNIQUE(date, hour, process_name)
        );
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT,
            hour INTEGER,
            app_name TEXT,
            count INTEGER DEFAULT 0,
            UNIQUE(date, hour, app_name)
        );
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT,
            updated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS app_categories (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            keyword TEXT UNIQUE,
            category TEXT
        );
        CREATE TABLE IF NOT EXISTS weekly_reports (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            week_start TEXT UNIQUE,
            file_path TEXT,
            generated_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE TABLE IF NOT EXISTS daily_scores (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE,
            score INTEGER DEFAULT 0,
            work_ratio REAL DEFAULT 0.0,
            focus_count INTEGER DEFAULT 0,
            total_hours REAL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now','localtime'))
        );
        CREATE INDEX IF NOT EXISTS idx_app_usage_date ON app_usage(date);
        CREATE INDEX IF NOT EXISTS idx_app_usage_process ON app_usage(process_name);
        CREATE INDEX IF NOT EXISTS idx_notifications_date ON notifications(date);
    """)
    for cat, keywords in DEFAULT_CATEGORIES.items():
        for kw in keywords.split(","):
            kw = kw.strip().lower()
            if kw:
                conn.execute("INSERT OR IGNORE INTO app_categories (keyword, category) VALUES (?, ?)", (kw, cat))
    defaults = {
        "show_categories": "true", "show_score": "true",
        "pomodoro_enabled": "false", "weekly_report_enabled": "false",
        "auto_start": "false", "dark_mode": "false",
    }
    for k, v in defaults.items():
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))
    conn.commit()
    return conn

def classify_process(process_name):
    name = process_name.lower().replace(".exe", "").strip()
    conn = get_connection()
    row = conn.execute("SELECT category FROM app_categories WHERE keyword=?", (name,)).fetchone()
    return row["category"] if row else "其他"

def upsert_daily_summary(date, active_secs, idle_secs, notif_count):
    conn = get_connection()
    conn.execute("""
        INSERT INTO daily_summary (date, total_active_seconds, total_idle_seconds, total_notifications)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            total_active_seconds = total_active_seconds + ?,
            total_idle_seconds = total_idle_seconds + ?,
            total_notifications = total_notifications + ?,
            created_at = datetime('now','localtime')
    """, (date, active_secs, idle_secs, notif_count, active_secs, idle_secs, notif_count))
    conn.commit()

def upsert_app_usage(date, hour, process_name, window_title, fg_secs, bg_secs, launches, notifs):
    conn = get_connection()
    conn.execute("""
        INSERT INTO app_usage (date, hour, process_name, window_title, foreground_seconds, background_seconds, launch_count, notification_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(date, hour, process_name) DO UPDATE SET
            foreground_seconds = foreground_seconds + ?,
            background_seconds = background_seconds + ?,
            launch_count = launch_count + ?,
            notification_count = notification_count + ?,
            window_title = ?,
            last_updated = datetime('now','localtime')
    """, (date, hour, process_name, window_title, fg_secs, bg_secs, launches, notifs,
          fg_secs, bg_secs, launches, notifs, window_title))
    conn.commit()

def upsert_notification(date, hour, app_name, count):
    conn = get_connection()
    conn.execute("""
        INSERT INTO notifications (date, hour, app_name, count) VALUES (?, ?, ?, ?)
        ON CONFLICT(date, hour, app_name) DO UPDATE SET count = count + ?
    """, (date, hour, app_name, count, count))
    conn.commit()

def get_today_summary(date):
    return get_connection().execute("SELECT * FROM daily_summary WHERE date=?", (date,)).fetchone()

def get_app_usage_by_date(date):
    return get_connection().execute("""
        SELECT process_name, window_title,
               SUM(foreground_seconds) as foreground_seconds,
               SUM(background_seconds) as background_seconds,
               SUM(launch_count) as launch_count,
               SUM(notification_count) as notification_count
        FROM app_usage WHERE date=? GROUP BY process_name ORDER BY foreground_seconds DESC
    """, (date,)).fetchall()

def get_app_usage_by_date_hour(date, hour):
    return get_connection().execute("""
        SELECT process_name, window_title,
               SUM(foreground_seconds) as foreground_seconds,
               SUM(background_seconds) as background_seconds,
               SUM(launch_count) as launch_count,
               SUM(notification_count) as notification_count
        FROM app_usage WHERE date=? AND hour=? GROUP BY process_name ORDER BY foreground_seconds DESC
    """, (date, hour)).fetchall()

def get_hourly_breakdown(date):
    rows = get_connection().execute("""
        SELECT hour, SUM(foreground_seconds) as total FROM app_usage WHERE date=? GROUP BY hour ORDER BY hour
    """, (date,)).fetchall()
    result = {h: 0 for h in range(24)}
    for r in rows:
        result[r["hour"]] = r["total"]
    return result

def get_daily_summaries(start_date, end_date):
    return get_connection().execute("""
        SELECT * FROM daily_summary WHERE date BETWEEN ? AND ? ORDER BY date
    """, (start_date, end_date)).fetchall()

def get_top_apps_by_date_range(start_date, end_date, limit=30):
    return get_connection().execute("""
        SELECT process_name,
               SUM(foreground_seconds) as foreground_seconds,
               SUM(background_seconds) as background_seconds,
               SUM(launch_count) as launch_count,
               SUM(notification_count) as notification_count
        FROM app_usage WHERE date BETWEEN ? AND ?
        GROUP BY process_name ORDER BY foreground_seconds DESC LIMIT ?
    """, (start_date, end_date, limit)).fetchall()

def get_notifications_by_date(date):
    return get_connection().execute("""
        SELECT app_name, SUM(count) as total_count FROM notifications WHERE date=? GROUP BY app_name ORDER BY total_count DESC
    """, (date,)).fetchall()

def get_setting(key):
    row = get_connection().execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    return row["value"] if row else None

def set_setting(key, value):
    conn = get_connection()
    conn.execute("""
        INSERT INTO settings (key, value, updated_at) VALUES (?, ?, datetime('now','localtime'))
        ON CONFLICT(key) DO UPDATE SET value=?, updated_at=datetime('now','localtime')
    """, (key, value, value))
    conn.commit()

def get_all_settings():
    rows = get_connection().execute("SELECT key, value FROM settings").fetchall()
    return {r["key"]: r["value"] for r in rows}

def get_category_breakdown(date):
    rows = get_connection().execute("""
        SELECT process_name, SUM(foreground_seconds) as total FROM app_usage WHERE date=? GROUP BY process_name
    """, (date,)).fetchall()
    breakdown = {}
    for r in rows:
        cat = classify_process(r["process_name"])
        breakdown[cat] = breakdown.get(cat, 0) + r["total"]
    return breakdown

def get_today_pomodoro_count():
    row = get_connection().execute("SELECT COUNT(*) as cnt FROM settings WHERE key LIKE 'pomodoro_%'").fetchone()
    return row["cnt"] if row else 0

def get_daily_score(date):
    return get_connection().execute("SELECT * FROM daily_scores WHERE date=?", (date,)).fetchone()

def upsert_daily_score(date, score, work_ratio, focus_count, total_hours):
    conn = get_connection()
    conn.execute("""
        INSERT INTO daily_scores (date, score, work_ratio, focus_count, total_hours)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT(date) DO UPDATE SET
            score=?, work_ratio=?, focus_count=?, total_hours=?,
            created_at=datetime('now','localtime')
    """, (date, score, work_ratio, focus_count, total_hours, score, work_ratio, focus_count, total_hours))
    conn.commit()

def save_weekly_report(week_start, file_path):
    conn = get_connection()
    conn.execute("""
        INSERT INTO weekly_reports (week_start, file_path) VALUES (?, ?)
        ON CONFLICT(week_start) DO UPDATE SET file_path=?, generated_at=datetime('now','localtime')
    """, (week_start, file_path, file_path))
    conn.commit()

def get_last_report_week():
    row = get_connection().execute("SELECT week_start FROM weekly_reports ORDER BY generated_at DESC LIMIT 1").fetchone()
    return row["week_start"] if row else None

def get_score_history():
    return get_connection().execute("SELECT * FROM daily_scores ORDER BY date DESC LIMIT 30").fetchall()

def get_data_days_count():
    row = get_connection().execute("SELECT COUNT(DISTINCT date) as cnt FROM daily_summary").fetchone()
    return row["cnt"] if row else 0

def get_app_avg_usage(process_name):
    row = get_connection().execute("SELECT AVG(foreground_seconds) as avg_fg FROM app_usage WHERE process_name=?", (process_name,)).fetchone()
    return row["avg_fg"] if row and row["avg_fg"] else 0

if __name__ == "__main__":
    init_db()
    print(f"Database initialized: {DB_PATH}")
