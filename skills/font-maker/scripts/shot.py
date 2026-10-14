# -*- coding: utf-8 -*-
"""Screenshot an HTML page with headless Chrome or Edge, so Claude can look.

    python shot.py "<page.html>" "<out.png>" [--width 1200] [--height 2400]
"""
import argparse
import os
import subprocess
import sys
import tempfile
from pathlib import Path

CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Google\Chrome\Application\chrome.exe"),
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
]


def find_browser():
    for c in CANDIDATES:
        if c and Path(c).exists():
            return c
    return None


def main():
    for s in (sys.stdout, sys.stderr):
        try:
            s.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    ap = argparse.ArgumentParser()
    ap.add_argument("page")
    ap.add_argument("out")
    ap.add_argument("--width", type=int, default=1200)
    ap.add_argument("--height", type=int, default=2400)
    a = ap.parse_args()
    browser = find_browser()
    if not browser:
        print("ERROR no Chrome or Edge found")
        sys.exit(1)
    page = Path(a.page).resolve()
    out = Path(a.out).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as prof:
        cmd = [browser, "--headless=new", "--disable-gpu", "--hide-scrollbars", f"--user-data-dir={prof}",
               "--virtual-time-budget=4000", f"--window-size={a.width},{a.height}",
               f"--screenshot={out}", page.as_uri()]
        subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=90)
    if out.exists():
        print(f"SHOT {out}")
    else:
        print("ERROR screenshot failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
