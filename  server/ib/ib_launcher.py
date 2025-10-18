import os
import socket
import subprocess
import sys
import time

import pyautogui

from .execute import execute

USERNAME = "xxx"
PASSWORD = "xxx"


def is_tws_running():
    """Check if TWS is already running."""
    try:
        # Use pgrep to look for "tws" process
        subprocess.check_output(["pgrep", "-f", "tws"])
        return True
    except subprocess.CalledProcessError:
        return False


def is_port_open(port, host="127.0.0.1", timeout=0.3):
    """Heuristic: IB TWS often listens on 7496/7497 when API enabled."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except Exception:
        return False


def is_tws_ready():
    if is_tws_running():
        for p in (7497, 7496):
            if is_port_open(p):
                return True
    return False


def kill_tws():
    """Brutally stop TWS (Linux)."""
    subprocess.run(["pkill", "-f", "tws"], check=False)


def launch_tws():
    """Launch TWS from $HOME/Jts/tws."""
    home = os.path.expanduser("~")
    tws_path = os.path.join(home, "Jts", "tws")
    if not os.path.exists(tws_path):
        print(f"TWS not found at {tws_path}")
        sys.exit(1)
    print(f"Launching TWS from {tws_path}...")
    subprocess.Popen([tws_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def login_tws():
    screen_width, screen_height = pyautogui.size()
    # Enter username
    pyautogui.moveTo(screen_width / 2 + 100, screen_height / 2 - 10)
    pyautogui.click()
    pyautogui.write(USERNAME, interval=0.1)
    # Enter password
    pyautogui.moveTo(screen_width / 2 + 100, screen_height / 2 + 30)
    pyautogui.click()
    pyautogui.write(PASSWORD, interval=0.1)
    # Click "Login" button
    pyautogui.moveTo(screen_width / 2 + 100, screen_height / 2 + 100)
    pyautogui.click()


def main():
    is_ready = False
    if is_tws_ready():
        print("TWS is running and ready.")
        is_ready = True
    else:
        print("TWS is not running or not ready. Launching...")
        for _ in range(3):
            if is_tws_running():
                print("TWS is running but not ready. Killing it...")
                kill_tws()
                time.sleep(5)
            launch_tws()
            time.sleep(30)
            login_tws()
            time.sleep(30)
            if is_tws_ready():
                is_ready = True
                break
    if is_ready:
        execute()


if __name__ == "__main__":
    main()
