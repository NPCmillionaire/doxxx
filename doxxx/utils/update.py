import subprocess
import sys
from colorama import Fore

# doxxx is not on PyPI (the "doxxx" name there is not ours); update from the fork.
GIT_URL = "git+https://github.com/NPCmillionaire/doxxx.git"

def get_version(package_name):
    try:
        from importlib.metadata import version  # Python 3.8+
        return version(package_name)
    except Exception:
        return "Unknown"

def update_self():
    print("Updating doxxx from GitHub using pip...\n")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade", GIT_URL
        ])
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Failed to update doxxx: {e}{Fore.RESET}")
        return


    doxx_ver = get_version("doxxx")

    print("\nInstalled Version:")
    print(f"   • doxxx: {doxx_ver}")

if __name__ == "__main__":
    doxx_ver = get_version("doxxx")
    print(doxx_ver)

