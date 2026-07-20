# ScreenTime - 屏幕使用时间

版本 v1.0.2

本地电脑屏幕使用时间采集与可视化工具。静默采集真实使用数据，通过美观的 Web 面板展示每日/每周/每月的屏幕使用情况。

## 核心功能

| 功能 | 说明 |
|---|---|
| 实时采集 | 每秒检测前台窗口、空闲状态，真实记录每个应用的使用时长 |
| 空闲检测 | 超过5分钟无键盘鼠标操作自动判定为离开，不统计时长 |
| 前台/后台视图 | 一键切换查看前台或后台使用时长，主数字和表头动态变化 |
| 真实图标 | 应用列表优先加载真实 exe 图标，列表限 20 行可滚动 |
| 桌面悬浮球 | 56px 圆形悬浮按钮，始终置顶可拖拽，双击打开面板 |
| 悬浮球菜单 | 右键：打开面板 / 隐藏悬浮球 / 一键关闭所有脚本 |
| 自定义图片 | 将 float_ball.png 放入目录即可替换悬浮球默认图标 |
| 进程分类 | 自动将应用分类为工作/娱乐/社交/学习/其他 |
| 通知统计 | 读取 Windows 通知数据库，统计每日通知数 |
| 多维视图 | 今日/本周/本月时间轴 + 逐小时/逐日详情 |
| 分类饼图 | 可视化各分类的使用时间占比 |
| 评分系统 | 基于工作时长、工作占比、专注次数生成每日评分 |
| 使用建议 | 数据满3天后自动生成使用习惯建议 |
| 暗色模式 | 支持深色/浅色主题切换 |
| 自动刷新 | 每5秒快速刷新，每60秒完整刷新 |
| 日志记录 | 采集器写入 collector.log，记录启动/停止/错误 |
| 崩溃恢复 | Watchdog 机制，崩溃后 5 秒自动重启（最多10次） |
| 桌面快捷方式 | 一键启动采集+面板，或单独启动面板 |

## 技术栈

- **Python 3.11** + **Flask**：Web 面板后端
- **SQLite**：轻量级本地数据库
- **win32gui / win32process / psutil**：Windows 窗口和进程监控
- **HTML/CSS/JS**：iOS 风格单页 Web 面板（全部内嵌在 server.py 中）
- **VBScript**：静默启动，不弹黑窗

## 项目结构

```
ScreenTime/
├── collector.py         # 后台采集程序
├── server.py            # Flask Web 面板（内嵌 HTML/CSS/JS）
├── db_manager.py        # SQLite 数据库管理
├── float_ball.py        # 桌面悬浮球（可拖拽、右键菜单、自定义图片）
├── start_all.bat        # 启动采集+面板+悬浮球
├── panel_start.bat      # 仅启动面板+悬浮球
├── start_silent.vbs     # 静默启动（不弹黑窗）
├── panel_silent.vbs     # 静默启动面板+打开浏览器
├── panel_start.vbs      # panel_silent.vbs 的辅助脚本
├── create_shortcuts.py  # 创建桌面快捷方式
├── screentime.ico       # 程序图标
├── float_ball.png       # 可选：自定义悬浮球图片
├── README.md
└── CHANGELOG.md
```

## 使用方式

### 1. 安装依赖

```bash
pip install flask psutil pywin32 pillow
```

### 2. 创建桌面快捷方式

```bash
python create_shortcuts.py
```

### 3. 启动

- **双击桌面快捷方式**「屏幕使用时间」→ 静默启动采集 + 后台面板
- **双击桌面快捷方式**「屏幕使用时间面板」→ 仅打开 Web 面板（浏览器）
- 或直接运行 `start_all.bat` 启动全部

### 4. 访问面板

浏览器打开 `http://localhost:19999`（端口冲突时自动分配，见 `.port` 文件）。

### 5. 自定义悬浮球图片

将任意 PNG 图片重命名为 `float_ball.png` 放入 ScreenTime 目录，重启悬浮球即可。图片会自动缩放并裁剪为圆形。删除该文件则恢复默认"ST"样式。

## 数据库

SQLite 数据库位于 `ScreenTime/screentime.db`，包含以下表：

- `daily_summary`：每日汇总
- `app_usage`：应用使用记录（按日期+小时+进程名）
- `notifications`：通知记录
- `settings`：用户设置
- `app_categories`：应用分类
- `weekly_reports`：周报记录
- `daily_scores`：每日评分
