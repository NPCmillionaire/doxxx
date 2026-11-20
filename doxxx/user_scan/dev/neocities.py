import re
import urllib.parse

from doxxx.core.helpers import get_random_user_agent
from doxxx.core.orchestrator import generic_validate
from doxxx.core.result import Result


def validate_neocities(user: str) -> Result:
    """Neocities site-owner profile lookup.

    Real profiles are titled ``Neocities - The web site of <user>`` and embed
    the sharded screenshot path plus the ``<user>.neocities.org`` subdomain;
    misses return a dedicated ``Neocities - Not Found`` page with a 404.
    """
    quoted = urllib.parse.quote(user, safe="")
    url = "https://neocities.org/site/" + quoted
    show_url = f"https://neocities.org/site/{user}"

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def process(response) -> Result:
        if response.status_code == 404:
            if "Neocities - Not Found" in response.text:
                return Result.available()
            return Result.error("404 without the Neocities not-found marker")

        if response.status_code == 200:
            if "The web site of " not in response.text:
                return Result.error("200 without the profile title marker")

            extra: dict = {}
            media: dict = {}

            tagline = re.search(r"The web site of ([^<]+)", response.text)
            if tagline and tagline.group(1).strip():
                extra["tagline"] = tagline.group(1).strip()

            subdomain = re.search(r"([A-Za-z0-9_-]+\.neocities\.org)", response.text)
            if subdomain:
                extra["site"] = subdomain.group(1).lower()

            screenshot = re.search(r"(screenshots/[a-z0-9/_.-]+\.webp)", response.text)
            if screenshot:
                media["screenshot"] = "https://neocities.org/" + screenshot.group(1)
            return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected response status {response.status_code}")

    return generic_validate(url, process, headers=headers, show_url=show_url)
