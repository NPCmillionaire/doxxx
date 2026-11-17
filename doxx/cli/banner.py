from colorama import Fore, Style, init
from ..core.version import load_local_version


version, version_type = load_local_version()
init(autoreset=True)
C_RED = Fore.RED + Style.BRIGHT
C_CYAN = Fore.CYAN + Style.BRIGHT
C_GREEN = Fore.GREEN + Style.BRIGHT
C_WHITE = Fore.WHITE + Style.BRIGHT
C_MAGENTA = Fore.MAGENTA + Style.BRIGHT
BANNER_ASCII = fr"""{C_CYAN}      _
   __| | _____  ____  __
  / _` |/ _ \ \/ /\ \/ /
 | (_| | (_) >  <  >  <
  \__,_|\___/_/\_\/_/\_\  Version: {version}
{Style.RESET_ALL}""".strip()


REPO_URL = "https://github.com/NPCmillionaire/doxx"


def print_banner():
    print(BANNER_ASCII)
    print(f"  {C_CYAN}Repo:{Style.RESET_ALL} {REPO_URL}\n")


if __name__ == "__main__":
    print_banner()
