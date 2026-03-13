"""
installer/build_exe.py
Run this on a Windows machine to produce StockFlow_Installer.exe

Requirements:
    pip install pyinstaller

Usage:
    python installer/build_exe.py
"""
import os
import sys
import shutil
import subprocess

HERE     = os.path.dirname(os.path.abspath(__file__))
ROOT     = os.path.dirname(HERE)
DIST_DIR = os.path.join(ROOT, "dist")
WORK_DIR = os.path.join(ROOT, "build_work")

# ── launcher.py — the Python entry point PyInstaller wraps ───────────────────
LAUNCHER_CODE = r'''
import os
import sys
import subprocess
import tempfile

def main():
    # Extract install.bat from the bundle to a temp location and run it
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.abspath(__file__))

    bat = os.path.join(base, 'install.bat')
    seed = os.path.join(base, 'seed.py')

    # Copy seed.py next to bat so bat can find it
    tmp = tempfile.mkdtemp()
    import shutil
    shutil.copy(bat, os.path.join(tmp, 'install.bat'))
    shutil.copy(seed, os.path.join(tmp, 'seed.py'))

    subprocess.call(['cmd', '/c', os.path.join(tmp, 'install.bat')], shell=False)

if __name__ == '__main__':
    main()
'''

launcher_path = os.path.join(HERE, "launcher.py")
with open(launcher_path, "w") as f:
    f.write(LAUNCHER_CODE)

print("[build] Building StockFlow_Installer.exe ...")

cmd = [
    sys.executable, "-m", "PyInstaller",
    "--onefile",
    "--noconsole",
    "--name", "StockFlow_Installer",
    "--distpath", DIST_DIR,
    "--workpath", WORK_DIR,
    "--specpath", WORK_DIR,
    "--add-data", f"{os.path.join(HERE, 'install.bat')};.",
    "--add-data", f"{os.path.join(HERE, 'seed.py')};.",
    "--add-data", f"{os.path.join(HERE, 'uninstall.bat')};.",
    launcher_path
]

result = subprocess.run(cmd, cwd=ROOT)

# Cleanup
os.remove(launcher_path)
if os.path.exists(WORK_DIR):
    shutil.rmtree(WORK_DIR, ignore_errors=True)

if result.returncode == 0:
    exe = os.path.join(DIST_DIR, "StockFlow_Installer.exe")
    print(f"\n[build] SUCCESS: {exe}")
    print("        Share this .exe with clients to install StockFlow.")
else:
    print("\n[build] FAILED. Check errors above.")
    sys.exit(1)