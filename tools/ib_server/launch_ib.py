import os
import socket
import subprocess
import sys
import time

import pyautogui


TWS_USERNAME = os.getenv("TWS_USERNAME")
TWS_PASSWORD = os.getenv("TWS_PASSWORD")


def is_ib_running():
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


def is_ib_ready():
    if is_ib_running():
        for p in (7497, 7496):
            if is_port_open(p):
                return True
    return False


def kill_ib():
    """Brutally stop TWS (Linux)."""
    subprocess.run(["pkill", "-f", "tws"], check=False)


def launch_ib():
    """Launch TWS from $HOME/Jts/tws."""
    home = os.path.expanduser("~")
    tws_path = os.path.join(home, "Jts", "tws")
    if not os.path.exists(tws_path):
        print(f"TWS not found at {tws_path}")
        sys.exit(1)
    print(f"Launching TWS from {tws_path}...")
    subprocess.Popen([tws_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def login_ib():
    screen_width, screen_height = pyautogui.size()
    # Enter username
    pyautogui.moveTo(screen_width / 2 + 100, screen_height / 2 - 10)
    pyautogui.click()
    pyautogui.write(TWS_USERNAME, interval=0.1)
    # Enter password
    pyautogui.moveTo(screen_width / 2 + 100, screen_height / 2 + 30)
    pyautogui.click()
    pyautogui.write(TWS_PASSWORD, interval=0.1)
    # Click "Login" button
    pyautogui.moveTo(screen_width / 2 + 100, screen_height / 2 + 100)
    pyautogui.click()


def main():
    if not is_ib_ready():
        print("TWS is not running or not ready. Launching...")
        for _ in range(3):
            if is_ib_running():
                print("TWS is running but not ready. Killing it...")
                kill_ib()
                time.sleep(5)
            launch_ib()
            time.sleep(30)
            login_ib()
            time.sleep(30)
            if is_ib_ready():
                break
    print("TWS is running and ready.")


if __name__ == "__main__":
    main()
