#!/usr/bin/env python3
"""Create desktop shortcuts for ScreenTime"""

import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import subprocess

script_dir = os.path.dirname(os.path.abspath(__file__))
desktop = os.path.join(os.path.expanduser("~"), "Desktop", "G")
os.makedirs(desktop, exist_ok=True)

def create_shortcut(name, vbs_file):
    target = os.path.join(script_dir, vbs_file)
    ico = os.path.join(script_dir, "screentime.ico")
    lnk_path = os.path.join(desktop, f"{name}.lnk")
    ps = f'''
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("{lnk_path}")
$Shortcut.TargetPath = "C:\\Windows\\System32\\wscript.exe"
$Shortcut.Arguments = '"{target}"'
$Shortcut.IconLocation = "{ico},0"
$Shortcut.Save()
'''
    r = subprocess.run(["powershell", "-Command", ps], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"[OK] {lnk_path}")
    else:
        print(f"[FAIL] {name}: {r.stderr}")

if __name__ == "__main__":
    create_shortcut("屏幕使用时间", "start_silent.vbs")
    create_shortcut("屏幕使用时间面板", "panel_silent.vbs")
    print("Shortcuts created.")
