from colorama import Fore
import sys


from doxxx.core.version import get_remote_version, load_local_version
from doxxx.utils.update import update_self
from doxxx.core.helpers import load_config, save_config_value
# Color configs
R = Fore.RED
G = Fore.GREEN
C = Fore.CYAN
Y = Fore.YELLOW
X = Fore.RESET

VERSION_URL = "https://raw.githubusercontent.com/NPCmillionaire/doxxx/main/doxxx/version.json"


def check_for_updates():
    if not load_config().get("auto_update_status", False):
        return

    try:
        latest_ver = get_remote_version(VERSION_URL)
        current_ver, _ = load_local_version()

        if latest_ver is None:
            print(f"[{Y}!{X}] {R}Could not reach GitHub, skipping update check.{X}")
            return
            
        if current_ver != latest_ver:
            print(
                f"\n[!] New version available: "
                f"{R}{current_ver}{X} -> {C}{latest_ver}{X}\n"
            )

            choice = input(
                f"{Y}Do you want to update?{X} (y/n/d: {R}don't ask again{X}): "
            ).strip().lower()

            if choice == "y":
                update_self()
                print(f"[{G}+{X}] {G}Update successful. Please restart the tool.{X}")
                sys.exit(0)

            elif choice == "d":
                save_config_value("auto_update_status", False)
                print(f"[{Y}*{X}] {R}Auto-update checks disabled.{X}")

    except Exception as e:
        print(f"[{Y}!{X}] {R}Update check failed{X}: {e}")
