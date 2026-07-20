#!/usr/bin/env python3
"""ScreenTime Flask Web Panel - iOS Style"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

import json
import socket
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, send_file
from db_manager import (
    init_db, get_today_summary, get_app_usage_by_date,
    get_app_usage_by_date_hour, get_hourly_breakdown,
    get_daily_summaries, get_top_apps_by_date_range,
    get_notifications_by_date, get_all_settings, set_setting, get_setting,
    get_category_breakdown, get_today_pomodoro_count,
    get_daily_score, get_data_days_count, classify_process,
    get_score_history, DB_PATH, DB_DIR
)

app = Flask(__name__)
init_db()

# ── Port detection ──
def find_free_port(start=19999):
    for port in range(start, start + 100):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex(("127.0.0.1", port)) != 0:
                return port
    return start

PORT = find_free_port(19999)
with open(os.path.join(SCRIPT_DIR, ".port"), "w") as f:
    f.write(str(PORT))

# ── Helpers ──
WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]

def today_str():
    return datetime.now().strftime("%Y-%m-%d")

def get_date_label(d):
    if isinstance(d, str):
        d = datetime.strptime(d, "%Y-%m-%d")
    return f"{d.year}年{d.month:02d}月{d.day:02d}日 {WEEKDAYS[d.weekday()]}"

def format_time(secs):
    if secs < 60:
        return f"{secs}秒"
    h = secs // 3600
    m = (secs % 3600) // 60
    if h > 0:
        return f"{h}小时{m}分钟"
    return f"{m}分钟"

def format_time_short(secs):
    h = secs // 3600
    m = (secs % 3600) // 60
    if h > 0:
        return f"{h}h {m}m"
    return f"{m}m"

# ── API Routes ──
@app.route("/")
def index():
    return HTML_PAGE

@app.route("/api/data")
def api_data():
    rng = request.args.get("range", "today")
    hour_str = request.args.get("hour", "")
    day_str = request.args.get("day", "")
    fast = request.args.get("fast", "0")

    today = datetime.now()
    date_str = today.strftime("%Y-%m-%d")

    if rng == "today":
        start = end = date_str
        timeline_label = f"{date_str} 逐小时"
        if hour_str:
            apps = get_app_usage_by_date_hour(date_str, int(hour_str))
            hourly = get_hourly_breakdown(date_str)
            timeline_data = [{"key": h, "label": f"{h}:00", "value": hourly.get(h, 0)} for h in range(24)]
        else:
            apps = get_app_usage_by_date(date_str)
            hourly = get_hourly_breakdown(date_str)
            timeline_data = [{"key": h, "label": f"{h}:00", "value": hourly.get(h, 0)} for h in range(24)]
        date_label = get_date_label(today)
    elif rng == "week":
        start = (today - timedelta(days=today.weekday())).strftime("%Y-%m-%d")
        end = date_str
        timeline_label = f"{start} ~ {end} 每日"
        if day_str:
            apps = get_app_usage_by_date(day_str)
        else:
            apps = get_top_apps_by_date_range(start, end, 50)
        summaries = get_daily_summaries(start, end)
        timeline_data = []
        for i in range(7):
            d = (today - timedelta(days=today.weekday()) + timedelta(days=i))
            ds = d.strftime("%Y-%m-%d")
            match = [s for s in summaries if s["date"] == ds]
            val = match[0]["total_active_seconds"] if match else 0
            timeline_data.append({"key": ds, "label": f"{d.month}/{d.day} {WEEKDAYS[d.weekday()]}", "value": val})
        date_label = f"{get_date_label(datetime.strptime(start, '%Y-%m-%d'))} ~ {get_date_label(today)}"
    else:  # month
        start = today.strftime("%Y-%m-01")
        end = date_str
        timeline_label = f"{start} ~ {end} 每日"
        if day_str:
            apps = get_app_usage_by_date(day_str)
        else:
            apps = get_top_apps_by_date_range(start, end, 50)
        summaries = get_daily_summaries(start, end)
        month_start = datetime.strptime(start, "%Y-%m-%d")
        days_in_month = (today - month_start).days + 1
        timeline_data = []
        for i in range(days_in_month):
            d = month_start + timedelta(days=i)
            ds = d.strftime("%Y-%m-%d")
            match = [s for s in summaries if s["date"] == ds]
            val = match[0]["total_active_seconds"] if match else 0
            timeline_data.append({"key": ds, "label": f"{d.day}日", "value": val})
        date_label = f"{get_date_label(month_start)} ~ {get_date_label(today)}"

    # Summary
    summary_row = get_today_summary(date_str)
    total_secs = summary_row["total_active_seconds"] if summary_row else 0
    notif_count = summary_row["total_notifications"] if summary_row else 0
    app_count = len(apps) if apps else 0
    pomo = get_today_pomodoro_count()

    # Score
    settings = get_all_settings()
    score_enabled = settings.get("show_score", "true") == "true"
    score_data = {"enabled": score_enabled}
    if score_enabled:
        sc = get_daily_score(date_str)
        if sc:
            score_data["score"] = sc["score"]
            score_data["work_ratio"] = sc["work_ratio"]
            score_data["focus_count"] = sc["focus_count"]
            score_data["total_hours"] = sc["total_hours"]

    # Categories
    cat_enabled = settings.get("show_categories", "true") == "true"
    cat_data = {"enabled": cat_enabled}
    if cat_enabled:
        cat_data["data"] = get_category_breakdown(date_str)

    # Apps list
    app_list = []
    for a in apps:
        proc = a["process_name"]
        app_list.append({
            "process_name": proc,
            "foreground_seconds": a["foreground_seconds"],
            "background_seconds": a["background_seconds"],
            "launch_count": a["launch_count"],
            "notification_count": a["notification_count"],
            "category": classify_process(proc),
        })

    # Advice
    days_count = get_data_days_count()
    advice = []
    if days_count >= 3:
        work_cat = cat_data.get("data", {}).get("工作", 0) if cat_enabled else 0
        ent_cat = cat_data.get("data", {}).get("娱乐", 0) if cat_enabled else 0
        if total_secs > 0:
            work_pct = work_cat / total_secs
            if work_pct < 0.2:
                advice.append({"text": "今天工作占比偏低，试试专注模式提升效率。", "type": "warning"})
            elif work_pct > 0.6:
                advice.append({"text": "今天工作状态很好！记得适当休息眼睛。", "type": "good"})
        if ent_cat > 3600 * 3:
            advice.append({"text": "娱乐时间超过3小时，注意平衡工作与休息。", "type": "warning"})
        if total_secs > 3600 * 10:
            advice.append({"text": "屏幕使用时间较长，建议每隔1小时起身活动。", "type": "warning"})

    return jsonify({
        "date_label": date_label,
        "timeline": {"label": timeline_label, "data": timeline_data},
        "summary": {
            "total_time": format_time(total_secs),
            "app_count": app_count,
            "notif_count": notif_count,
            "pomodoro_count": f"{pomo}" if pomo > 0 else "--",
        },
        "score": score_data,
        "categories": cat_data,
        "apps": app_list,
        "advice": advice,
    })

@app.route("/api/settings")
def api_settings():
    return jsonify(get_all_settings())

@app.route("/api/settings/toggle", methods=["POST"])
def api_settings_toggle():
    data = request.get_json(force=True)
    key = data.get("key")
    value = data.get("value")
    if key:
        set_setting(key, str(value))
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": "missing key"}), 400

@app.route("/api/info")
def api_info():
    db_size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
    return jsonify({
        "version": "1.0",
        "port": PORT,
        "db_size_mb": round(db_size / 1048576, 1),
        "db_path": DB_PATH,
    })

@app.route("/api/icon/<process_name>")
def api_icon(process_name):
    import base64, tempfile
    try:
        import win32ui, win32gui, win32con, win32api
        from PIL import Image
        # Try to get exe path from process name
        exe_path = None
        import psutil
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                if proc.info["name"].lower() == process_name.lower():
                    exe_path = proc.info["exe"]
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        if exe_path and os.path.exists(exe_path):
            ico_x = win32api.GetSystemMetrics(win32con.SM_CXICON)
            ico_y = win32api.GetSystemMetrics(win32con.SM_CYICON)
            large, small = win32gui.ExtractIconEx(exe_path, 0)
            if large:
                hicon = large[0]
                hdc = win32ui.CreateDCFromHandle(win32gui.GetDC(0))
                hbmp = win32ui.CreateBitmap()
                hbmp.CreateCompatibleBitmap(hdc, ico_x, ico_y)
                hdc_mem = hdc.CreateCompatibleDC()
                hdc_mem.SelectObject(hbmp)
                hdc_mem.DrawIcon((0, 0), hicon)
                bmp_info = hbmp.GetInfo()
                bmp_bits = hbmp.GetBitmapBits(True)
                img = Image.frombuffer("RGBA", (bmp_info["bmWidth"], bmp_info["bmHeight"]), bmp_bits, "raw", "BGRA", 0, 1)
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tf:
                    img.save(tf.name, "PNG")
                    with open(tf.name, "rb") as ff:
                        b64 = base64.b64encode(ff.read()).decode()
                    os.unlink(tf.name)
                hdc_mem.DeleteDC()
                win32gui.DeleteObject(hbmp.GetHandle())
                return b64
    except Exception:
        pass
    return "", 404

# ── HTML Page ──
HTML_PAGE = r'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>屏幕使用时间</title>
<style>
:root {
    --bg: #f2f2f7; --card-bg: #ffffff; --text: #1c1c1e; --text-sec: #8e8e93;
    --blue: #007AFF; --green: #34c759; --orange: #ff9500; --red: #ff3b30;
    --radius: 16px;
}
.dark {
    --bg: #1c1c1e; --card-bg: #2c2c2e; --text: #f5f5f7; --text-sec: #98989d;
}
* { margin: 0; padding: 0; box-sizing: border-box; }
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; background: var(--bg); color: var(--text); min-height: 100vh; }
.container { max-width: 800px; margin: 0 auto; padding: 20px 16px 40px; }
.card { background: var(--card-bg); border-radius: var(--radius); padding: 20px; margin-bottom: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.08); }

/* Header */
.header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }
.header h1 { font-size: 28px; font-weight: 700; }
.header-actions { display: flex; gap: 10px; }
.icon-btn { width: 40px; height: 40px; border-radius: 50%; border: none; background: var(--card-bg); cursor: pointer; font-size: 18px; display: flex; align-items: center; justify-content: center; color: var(--text); box-shadow: 0 1px 3px rgba(0,0,0,0.1); transition: transform 0.2s; }
.icon-btn:hover { transform: scale(1.05); }

/* Range Selector */
.range-selector { display: flex; gap: 8px; margin-bottom: 16px; }
.range-btn { flex: 1; padding: 10px; border-radius: 10px; border: 1.5px solid #e0e0e0; background: var(--card-bg); color: var(--text); cursor: pointer; font-size: 14px; font-weight: 500; transition: all 0.2s; }
.range-btn.active { background: var(--blue); color: #fff; border-color: var(--blue); }

/* View Selector */
.view-selector { display: flex; gap: 8px; margin-bottom: 12px; }
.view-btn { flex: 1; padding: 8px; border-radius: 8px; border: 1.5px solid #e0e0e0; background: var(--card-bg); color: var(--text); cursor: pointer; font-size: 13px; font-weight: 500; transition: all 0.2s; }
.view-btn.active { background: var(--text); color: var(--card-bg); border-color: var(--text); }

/* Refresh bar */
.refresh-bar { display: flex; justify-content: space-between; align-items: center; font-size: 12px; color: var(--text-sec); margin-bottom: 12px; padding: 0 4px; }
.refresh-dot { display: inline-block; width: 8px; height: 8px; background: var(--green); border-radius: 50%; margin-right: 6px; animation: pulse 2s infinite; }
@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.4} }

/* Timeline Chart */
.timeline-chart { display: flex; align-items: flex-end; gap: 2px; height: 144px; padding: 28px 0 4px 0; overflow-x: auto; }
.timeline-bar { flex: 1; min-width: 8px; background: var(--blue); border-radius: 4px 4px 0 0; cursor: pointer; transition: opacity 0.2s; opacity: 0.7; position: relative; }
.timeline-bar:hover { opacity: 1; }
.timeline-bar.active-bar { opacity: 1; background: #0056cc; }
.timeline-tooltip { display: none; position: absolute; bottom: 100%; left: 50%; transform: translateX(-50%); background: #333; color: #fff; padding: 4px 8px; border-radius: 6px; font-size: 11px; white-space: nowrap; z-index: 10; }
.timeline-bar:hover .timeline-tooltip { display: block; }

/* Summary Cards */
.summary-cards { display: grid; grid-template-columns: repeat(4, 1fr); gap: 10px; }
.summary-item { text-align: center; padding: 12px 4px; }
.summary-item .val { font-size: 22px; font-weight: 700; }
.summary-item .lbl { font-size: 11px; color: var(--text-sec); margin-top: 2px; }

/* Score */
.score-card { display: flex; align-items: center; gap: 20px; }
.score-ring { position: relative; width: 80px; height: 80px; flex-shrink: 0; }
.score-ring svg { width: 80px; height: 80px; transform: rotate(-90deg); }
.score-ring .score-text { position: absolute; top: 50%; left: 50%; transform: translate(-50%,-50%); font-size: 28px; font-weight: 700; }
.score-details { display: flex; flex-direction: column; gap: 4px; font-size: 13px; color: var(--text-sec); }

/* Pie Chart */
.pie-container { display: flex; align-items: center; gap: 20px; }
.pie-svg { width: 100px; height: 100px; flex-shrink: 0; }
.pie-legend { display: flex; flex-direction: column; gap: 6px; }
.legend-item { display: flex; align-items: center; gap: 6px; font-size: 13px; }
.legend-dot { width: 10px; height: 10px; border-radius: 3px; }

/* App List */
.app-header { display: grid; grid-template-columns: 1fr 120px; gap: 10px; padding: 0 12px 8px; font-size: 11px; color: var(--text-sec); font-weight: 600; }
.app-row { display: grid; grid-template-columns: 1fr 120px; gap: 10px; align-items: center; padding: 10px 12px; border-radius: 10px; transition: background 0.2s; }
.app-row:hover { background: rgba(0,122,255,0.06); }
.app-idx { text-align: center; color: var(--text-sec); font-size: 13px; }
.app-info { display: flex; align-items: center; gap: 10px; }
.app-icon { width: 36px; height: 36px; border-radius: 9px; display: flex; align-items: center; justify-content: center; font-size: 15px; font-weight: 600; color: #fff; background: var(--blue); flex-shrink: 0; }
.app-icon img { width: 36px; height: 36px; border-radius: 9px; }
.app-name { font-weight: 500; font-size: 14px; }
.app-meta { display: flex; gap: 4px; margin-top: 2px; flex-wrap: wrap; }
.cat-tag { font-size: 10px; padding: 2px 6px; border-radius: 8px; background: rgba(0,122,255,0.1); color: var(--blue); }
.notif-badge { font-size: 10px; padding: 2px 6px; border-radius: 8px; background: rgba(255,59,48,0.1); color: var(--red); }
.app-stats { text-align: right; font-size: 13px; }
.app-stats .fg { font-weight: 600; }
.app-stats .bg { color: var(--text-sec); font-size: 11px; margin-top: 1px; }

/* Advice */
.advice-item { padding: 8px 12px; border-radius: 10px; margin-bottom: 6px; font-size: 13px; display: flex; align-items: center; gap: 8px; }
.advice-warning { background: rgba(255,149,0,0.1); color: var(--orange); }
.advice-good { background: rgba(52,199,89,0.1); color: var(--green); }

/* Settings Panel */
.settings-overlay { display: none; position: fixed; top: 0; left: 0; right: 0; bottom: 0; background: rgba(0,0,0,0.4); z-index: 100; justify-content: center; align-items: center; }
.settings-overlay.show { display: flex; }
.settings-panel { background: var(--card-bg); border-radius: var(--radius); padding: 24px; width: 340px; max-height: 80vh; overflow-y: auto; }
.settings-panel h3 { font-size: 18px; margin-bottom: 16px; }
.setting-row { display: flex; justify-content: space-between; align-items: center; padding: 12px 0; border-bottom: 1px solid rgba(128,128,128,0.15); }
.setting-row:last-child { border-bottom: none; }
.toggle { width: 50px; height: 30px; border-radius: 15px; border: none; cursor: pointer; position: relative; transition: background 0.3s; background: #e0e0e0; }
.toggle.on { background: var(--green); }
.toggle::after { content: ''; position: absolute; width: 26px; height: 26px; border-radius: 50%; background: #fff; top: 2px; left: 2px; transition: transform 0.3s; box-shadow: 0 1px 3px rgba(0,0,0,0.2); }
.toggle.on::after { transform: translateX(20px); }
.setting-label { font-size: 14px; }
.settings-close { width: 100%; padding: 10px; border-radius: 10px; border: none; background: var(--blue); color: #fff; font-size: 15px; cursor: pointer; margin-top: 16px; }

/* Loading / Error */
.loading { text-align: center; padding: 40px; color: var(--text-sec); }
.error-msg { text-align: center; padding: 40px; color: var(--red); }
.spinner { display: inline-block; width: 24px; height: 24px; border: 3px solid #e0e0e0; border-top-color: var(--blue); border-radius: 50%; animation: spin 0.8s linear infinite; }
@keyframes spin { to { transform: rotate(360deg); } }

/* Responsive */
@media (max-width: 600px) {
    .summary-cards { grid-template-columns: repeat(2, 1fr); }
    .score-card { flex-direction: column; text-align: center; }
    .app-header, .app-row { grid-template-columns: 1fr 90px; }
}
</style>
</head>
<body>
<div class="container">
    <div class="header">
        <h1>屏幕使用时间</h1>
        <div class="header-actions">
            <button class="icon-btn" id="darkToggle" title="暗色模式" onclick="toggleDark()">🌙</button>
            <button class="icon-btn" id="settingsBtn" title="设置" onclick="toggleSettings()">⚙</button>
        </div>
    </div>

    <div class="range-selector" id="rangeSelector">
        <button class="range-btn active" data-range="today">今日</button>
        <button class="range-btn" data-range="week">本周</button>
        <button class="range-btn" data-range="month">本月</button>
    </div>

    <div class="refresh-bar" id="refreshBar">
        <span><span class="refresh-dot"></span>实时采集</span>
        <span id="countdown">60s</span>
    </div>

    <div class="card" id="timelineCard">
        <div style="font-size:13px;color:var(--text-sec);margin-bottom:8px" id="timelineLabel">今日 逐小时</div>
        <div class="timeline-chart" id="timelineChart"></div>
    </div>

    <div class="card" id="summaryCard">
        <div class="summary-cards">
            <div class="summary-item"><div class="val" id="sumTime">--</div><div class="lbl">活跃时长</div></div>
            <div class="summary-item"><div class="val" id="sumApps">--</div><div class="lbl">使用应用</div></div>
            <div class="summary-item"><div class="val" id="sumNotifs">--</div><div class="lbl">通知数</div></div>
            <div class="summary-item"><div class="val" id="sumPomo">--</div><div class="lbl">专注次数</div></div>
        </div>
    </div>

    <div class="card" id="scoreCard" style="display:none">
        <div class="score-card">
            <div class="score-ring">
                <svg viewBox="0 0 80 80">
                    <circle cx="40" cy="40" r="34" fill="none" stroke="#e0e0e0" stroke-width="6"/>
                    <circle cx="40" cy="40" r="34" fill="none" stroke="var(--green)" stroke-width="6" stroke-linecap="round" id="scoreCircle"/>
                </svg>
                <div class="score-text" id="scoreNum" style="color:var(--green)">--</div>
            </div>
            <div class="score-details" id="scoreDetails"></div>
        </div>
    </div>

    <div class="card" id="catCard" style="display:none">
        <div class="pie-container">
            <svg class="pie-svg" viewBox="0 0 100 100" id="pieSvg"></svg>
            <div class="pie-legend" id="pieLegend"></div>
        </div>
    </div>

    <div class="view-selector" id="viewSelector">
        <button class="view-btn active" data-view="foreground">前台</button>
        <button class="view-btn" data-view="background">后台</button>
    </div>

    <div class="card" id="appCard">
        <div class="app-header"><span style="text-align:right" id="appHeaderTitle">前台时长</span></div>
        <div id="appList" style="max-height: calc(20 * 60px); overflow-y: auto; padding-right: 4px;"></div>
    </div>

    <div class="card" id="adviceCard" style="display:none">
        <div style="font-weight:600;margin-bottom:10px">使用建议</div>
        <div id="adviceList"></div>
    </div>
</div>

<!-- Settings -->
<div class="settings-overlay" id="settingsOverlay">
    <div class="settings-panel">
        <h3>设置</h3>
        <div id="settingsList"></div>
        <button class="settings-close" onclick="toggleSettings()">关闭</button>
    </div>
</div>

<script>
let currentRange = 'today';
let currentView = 'foreground';
let lastApps = [];
let activeHour = null;
let activeDay = null;
let refreshTimer = null;
let fastRefreshInterval = 5000;
let fullRefreshInterval = 60000;
let fastCountdown = 5;
let fullCountdown = 60;
let retries = 0;
let maxRetries = 3;

// ── Settings ──
let appSettings = {};
function loadSettings() {
    fetch('/api/settings').then(r => r.json()).then(d => {
        appSettings = d;
        applySettings();
        renderSettings();
    });
}
function applySettings() {
    document.body.classList.toggle('dark', appSettings.dark_mode === 'true');
    document.getElementById('darkToggle').innerText = appSettings.dark_mode === 'true' ? '☀' : '🌙';
}
function toggleDark() {
    appSettings.dark_mode = appSettings.dark_mode === 'true' ? 'false' : 'true';
    saveSetting('dark_mode', appSettings.dark_mode);
    applySettings();
}
function saveSetting(key, val) {
    fetch('/api/settings/toggle', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({key, value: val})
    });
}
function renderSettings() {
    const items = [
        {key: 'show_categories', label: '分类标签'},
        {key: 'show_score', label: '评分卡片'},
        {key: 'weekly_report_enabled', label: '周报'},
        {key: 'auto_start', label: '自启动'},
    ];
    document.getElementById('settingsList').innerHTML = items.map(it => {
        const on = appSettings[it.key] === 'true';
        return `<div class="setting-row">
            <span class="setting-label">${it.label}</span>
            <button class="toggle ${on ? 'on' : ''}" onclick="toggleSetting('${it.key}', ${!on})"></button>
        </div>`;
    }).join('');
}
function toggleSetting(key, val) {
    saveSetting(key, val);
    appSettings[key] = val ? 'true' : 'false';
    renderSettings();
    applySettings();
    loadData();
}
function toggleSettings() {
    document.getElementById('settingsOverlay').classList.toggle('show');
}

// ── Data Loading ──
async function loadData(fast = false) {
    const el = document.getElementById('appList');
    if (!fast) el.innerHTML = '<div class="loading"><div class="spinner"></div></div>';

    let url = `/api/data?range=${currentRange}&fast=${fast ? 1 : 0}`;
    if (activeHour !== null) url += `&hour=${activeHour}`;
    if (activeDay !== null) url += `&day=${activeDay}`;

    try {
        const r = await fetch(url);
        if (!r.ok) throw new Error('HTTP ' + r.status);
        const data = await r.json();
        retries = 0;
        renderAll(data, fast);
    } catch (e) {
        if (!fast && retries < maxRetries) {
            retries++;
            setTimeout(() => loadData(false), 2000);
            return;
        }
        if (!fast) {
            el.innerHTML = '<div class="error-msg">数据加载失败，请检查采集器是否运行</div>';
        }
    }
}

function renderAll(data, fast) {
    document.getElementById('timelineLabel').innerText = data.date_label + ' · ' + data.timeline.label;
    renderTimeline(data.timeline.data);
    document.getElementById('sumTime').innerText = data.summary.total_time;
    document.getElementById('sumApps').innerText = data.summary.app_count;
    document.getElementById('sumNotifs').innerText = data.summary.notif_count;
    document.getElementById('sumPomo').innerText = data.summary.pomodoro_count;
    lastApps = data.apps;
    renderApps(data.apps);

    if (!fast) {
        // Score
        if (data.score.enabled && data.score.score !== undefined) {
            document.getElementById('scoreCard').style.display = '';
            const sc = data.score;
            const pct = sc.score || 0;
            const circ = 2 * Math.PI * 34;
            document.getElementById('scoreCircle').setAttribute('stroke-dasharray', `${(pct/100)*circ} ${circ}`);
            document.getElementById('scoreNum').innerText = sc.score || 0;
            document.getElementById('scoreNum').style.color = pct >= 70 ? 'var(--green)' : pct >= 40 ? 'var(--orange)' : 'var(--red)';
            document.getElementById('scoreDetails').innerHTML = `
                <span>生产力分数</span>
                <span>工作占比: ${(sc.work_ratio*100).toFixed(0)}%</span>
                <span>专注次数: ${sc.focus_count}</span>
            `;
        } else {
            document.getElementById('scoreCard').style.display = 'none';
        }

        // Categories
        if (data.categories.enabled) {
            document.getElementById('catCard').style.display = '';
            renderPie(data.categories.data);
        } else {
            document.getElementById('catCard').style.display = 'none';
        }

        // Advice
        if (data.advice.length > 0) {
            document.getElementById('adviceCard').style.display = '';
            document.getElementById('adviceList').innerHTML = data.advice.map(a =>
                `<div class="advice-item advice-${a.type}">${a.type === 'warning' ? '⚠' : '✓'} ${a.text}</div>`
            ).join('');
        } else {
            document.getElementById('adviceCard').style.display = 'none';
        }
    }
}

// ── Timeline ──
function renderTimeline(data) {
    const maxVal = Math.max(...data.map(d => d.value), 1);
    const chart = document.getElementById('timelineChart');
    chart.innerHTML = data.map(d => {
        const h = Math.max((d.value / maxVal) * 100, 2);
        const activeCls = (activeHour !== null && d.key === activeHour) || (activeDay !== null && d.key === activeDay) ? ' active-bar' : '';
        const label = d.label || '';
        return `<div class="timeline-bar${activeCls}" style="height:${h}%" data-key="${d.key}" onclick="selectBar('${d.key}')">
            <div class="timeline-tooltip">${label}: ${formatTimeShort(d.value)}</div>
        </div>`;
    }).join('');
}

function selectBar(key) {
    if (currentRange === 'today') {
        activeHour = (activeHour === parseInt(key)) ? null : parseInt(key);
        activeDay = null;
    } else {
        activeDay = (activeDay === key) ? null : key;
        activeHour = null;
    }
    loadData();
}

// ── Apps ──
const CAT_COLORS = { '工作': '#007AFF', '娱乐': '#ff9500', '社交': '#34c759', '学习': '#5856d6', '其他': '#8e8e93' };
function renderApps(apps) {
    const el = document.getElementById('appList');
    document.getElementById('appHeaderTitle').innerText = currentView === 'foreground' ? '前台时长' : '后台时长';
    if (apps.length === 0) {
        el.innerHTML = '<div style="text-align:center;padding:20px;color:var(--text-sec)">暂无数据</div>';
        return;
    }
    el.innerHTML = apps.map((a, i) => {
        const cat = a.category || '其他';
        const catColor = CAT_COLORS[cat] || '#8e8e93';
        const initial = a.process_name.replace('.exe','').charAt(0).toUpperCase();
        const mainSecs = currentView === 'foreground' ? a.foreground_seconds : a.background_seconds;
        const otherSecs = currentView === 'foreground' ? a.background_seconds : a.foreground_seconds;
        const otherLabel = currentView === 'foreground' ? '后台' : '前台';
        return `<div class="app-row">
            <div class="app-info">
                <div class="app-icon" style="background:${catColor};" id="icon-${i}">${initial}</div>
                <div>
                    <div class="app-name">${a.process_name}</div>
                    <div class="app-meta">
                        <span class="cat-tag">${cat}</span>
                        ${a.notification_count > 0 ? `<span class="notif-badge">${a.notification_count} 通知</span>` : ''}
                    </div>
                </div>
            </div>
            <div class="app-stats">
                <div class="fg">${formatTimeShort(mainSecs)}</div>
                ${otherSecs > 0 ? `<div class="bg">${otherLabel} ${formatTimeShort(otherSecs)}</div>` : ''}
            </div>
        </div>`;
    }).join('');
    // Async load real icons
    apps.forEach((a, i) => {
        fetch(`/api/icon/${encodeURIComponent(a.process_name)}`).then(r => {
            if (r.ok) return r.text();
            throw new Error('no icon');
        }).then(b64 => {
            const iconEl = document.getElementById(`icon-${i}`);
            if (iconEl && b64) {
                iconEl.innerHTML = `<img src="data:image/png;base64,${b64}" style="width:36px;height:36px;border-radius:9px;">`;
            }
        }).catch(() => {});
    });
}

// ── Pie Chart ──
const PIE_COLORS = ['#007AFF', '#ff9500', '#34c759', '#5856d6', '#ff3b30', '#ffcc00', '#8e8e93'];
function renderPie(data) {
    const entries = Object.entries(data).filter(([k,v]) => v > 0);
    if (entries.length === 0) { document.getElementById('catCard').style.display = 'none'; return; }
    const total = entries.reduce((s, [k,v]) => s + v, 0);
    const svg = document.getElementById('pieSvg');
    const legend = document.getElementById('pieLegend');
    let paths = '';
    let cum = 0;
    const cx = 50, cy = 50, r = 40;
    entries.forEach(([k, v], i) => {
        const pct = v / total;
        const a1 = cum * 2 * Math.PI - Math.PI / 2;
        const a2 = (cum + pct) * 2 * Math.PI - Math.PI / 2;
        const x1 = cx + r * Math.cos(a1), y1 = cy + r * Math.sin(a1);
        const x2 = cx + r * Math.cos(a2), y2 = cy + r * Math.sin(a2);
        const large = pct > 0.5 ? 1 : 0;
        paths += `<path d="M${cx},${cy} L${x1},${y1} A${r},${r} 0 ${large} 1 ${x2},${y2} Z" fill="${PIE_COLORS[i % PIE_COLORS.length]}" opacity="0.85"/>`;
        cum += pct;
    });
    svg.innerHTML = paths;
    legend.innerHTML = entries.map(([k, v], i) => {
        const h = Math.floor(v / 3600);
        const m = Math.floor((v % 3600) / 60);
        return `<div class="legend-item"><span class="legend-dot" style="background:${PIE_COLORS[i % PIE_COLORS.length]}"></span>${k} ${h}h${m}m</div>`;
    }).join('');
}

// ── Utilities ──
function formatTimeShort(secs) {
    const h = Math.floor(secs / 3600);
    const m = Math.floor((secs % 3600) / 60);
    if (h > 0) return `${h}h ${m}m`;
    return `${m}m`;
}

// ── Range Selector ──
document.getElementById('rangeSelector').addEventListener('click', e => {
    if (!e.target.classList.contains('range-btn')) return;
    document.querySelectorAll('.range-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentRange = e.target.dataset.range;
    activeHour = null;
    activeDay = null;
    loadData();
});

// ── View Selector ──
document.getElementById('viewSelector').addEventListener('click', e => {
    if (!e.target.classList.contains('view-btn')) return;
    document.querySelectorAll('.view-btn').forEach(b => b.classList.remove('active'));
    e.target.classList.add('active');
    currentView = e.target.dataset.view;
    renderApps(lastApps);
});

// ── Auto Refresh ──
function startAutoRefresh() {
    let fastTick = 5;
    let fullTick = 60;
    const countdown = document.getElementById('countdown');
    refreshTimer = setInterval(() => {
        fastTick--;
        fullTick--;
        countdown.innerText = `${fastTick}s / ${fullTick}s`;
        if (fastTick <= 0) {
            loadData(true);
            fastTick = 5;
        }
        if (fullTick <= 0) {
            loadData(false);
            fullTick = 60;
        }
    }, 1000);
}

// ── Init ──
document.addEventListener('DOMContentLoaded', () => {
    loadSettings();
    setTimeout(() => {
        loadData();
        startAutoRefresh();
    }, 500);
});
</script>
</body>
</html>'''

if __name__ == "__main__":
    print(f"ScreenTime Panel running at http://localhost:{PORT}")
    app.run(host="127.0.0.1", port=PORT, debug=False)
