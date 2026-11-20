import re
import urllib.parse

from doxxx.core.helpers import get_random_user_agent
from doxxx.core.orchestrator import generic_validate
from doxxx.core.result import Result


def validate_tapas(user: str) -> Result:
    """Tapas creator/reader profile lookup.

    A real profile renders ``<handle> | Tapas Creator`` (or ``Reader``) in the
    title; a miss is a dedicated 404 page carrying the generic Tapas title, so
    both verdicts verify an explicit body marker instead of a bare status.
    """
    quoted = urllib.parse.quote(user, safe="")
    url = "https://tapas.io/" + quoted
    show_url = f"https://tapas.io/{user}"

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def process(response) -> Result:
        if response.status_code == 404:
            if "Tapas: Stories You Crave" in response.text:
                return Result.available()
            return Result.error("404 from an unexpected page")

        if response.status_code == 200:
            title = re.search(r"<title>([^<]+)</title>", response.text)
            if not title or " | Tapas " not in title.group(1):
                return Result.error("200 without the Tapas profile title marker")

            display_name = title.group(1).split(" | ")[0].strip()
            extra: dict = {}
            media: dict = {}
            if display_name:
                extra["display_name"] = display_name

            desc = re.search(r'og:description" content="([^"]+)"', response.text)
            if desc and desc.group(1).strip():
                extra["bio"] = desc.group(1).strip()

            image = re.search(r'og:image" content="([^"]+)"', response.text)
            if image and "defaultuser" not in image.group(1):
                media["avatar"] = image.group(1)
            return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected response status {response.status_code}")

    return generic_validate(url, process, headers=headers, show_url=show_url)
