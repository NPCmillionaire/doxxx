import subprocess
import sys
from colorama import Fore

# doxx is not on PyPI (the "doxx" name there is not ours); update from the fork.
GIT_URL = "git+https://github.com/NPCmillionaire/doxx.git"

def get_version(package_name):
    try:
        from importlib.metadata import version  # Python 3.8+
        return version(package_name)
    except Exception:
        return "Unknown"

def update_self():
    print("Updating doxx from GitHub using pip...\n")
    try:
        subprocess.check_call([
            sys.executable, "-m", "pip", "install", "--upgrade", GIT_URL
        ])
    except subprocess.CalledProcessError as e:
        print(f"{Fore.RED}Failed to update doxx: {e}{Fore.RESET}")
        return


    doxx_ver = get_version("doxx")

    print("\nInstalled Version:")
    print(f"   • doxx: {doxx_ver}")

if __name__ == "__main__":
    doxx_ver = get_version("doxx")
    print(doxx_ver)

