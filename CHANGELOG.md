# CHANGELOG

## v1.0.2 (2026-07-20)

### 新增
- 前台/后台视图切换器：饼图下方新增切换标签，可切换查看前台/后台使用时长，主数字和表头动态变化
- 桌面悬浮球（float_ball.py）：蓝色圆形 56px，显示"ST"标识，始终置顶、可拖拽，双击打开面板
- 悬浮球右键菜单：打开面板 / 隐藏悬浮球 / 关闭脚本（终止所有 ScreenTime 进程后自毁）
- 悬浮球呼吸灯动画：颜色脉动，每 10 秒检测服务器健康状态
- 悬浮球单例锁：PID 文件防止重复启动
- 悬浮球自定义图片：将 float_ball.png 放入 ScreenTime 目录即可替换默认圆形图标，自动圆形裁剪

### 修复
- 修复系统睡眠/唤醒后采集器单 tick 内 elapsed 暴增导致使用时长数据膨胀的 Bug：增加 MAX_TICK_ELAPSED=5 秒上限，超出部分计入空闲时间
- 修复多采集器实例同时运行导致同一 (date, hour, process_name) 行数据成倍累加的 Bug：增加 PID 文件单例锁（ensure_single_instance），启动时检测已有实例并拒绝重复启动

### 优化
- 应用列表限制 20 行显示，超出行可滚动查看
- 应用图标异步加载：优先获取真实 exe 图标（base64），失败时降级为首字母占位

### 变更
- 视图切换器从时间段选择器下方移至饼图下方、应用列表上方
- 启动脚本（panel_start.bat / start_all.bat）追加悬浮球后台启动

## v1.0.1 (2026-07-20)

### 修复
- 修复 start_all.bat 和 panel_start.bat 无法在 Program Files 安装环境下找到 Python 运行时的问题
- 原先仅扫描 `%AppData%\Tencent\Marvis\MarvisAgent\`，现增加 `%ProgramFiles%\Tencent\Marvis\MarvisAgent\` 回退扫描
- 修复快捷方式启动报错"找不到文件 runtime\python311\python.exe"
- 修复双击快捷方式弹出命令提示符窗口的问题：批处理中 `start` 命令增加 `/B` 参数，Python 进程不再创建新窗口
- 修复面板 VBS 脚本因服务未启动导致的 80070002 错误

## v1.0 (2026-07-20)

### 初始版本
- 后台采集器：每秒检测前台窗口，真实记录应用使用时长
- Windows 空闲检测：GetLastInputInfo，5分钟阈值
- SQLite 数据库：7张表，完整索引
- Flask Web 面板（端口 19999，自动冲突检测）
- iOS 风格面板 UI：时间轴柱状图、汇总卡片、评分环形图、分类饼图、应用列表
- 今日/本周/本月视图切换
- 应用自动分类（工作/娱乐/社交/学习/其他）
- 暗色模式（localStorage 持久化）
- 设置面板：分类标签、评分、周报、自启动开关
- 使用建议（3天数据后启用）
- 自动刷新：5秒快速 + 60秒完整
- 桌面快捷方式创建（C:\Users\24918\Desktop\G\）
- 静默启动（VBScript，不弹黑窗）
- Watchdog 崩溃恢复（最多10次）
- 采集器日志：collector.log
- Windows 通知数据库读取
