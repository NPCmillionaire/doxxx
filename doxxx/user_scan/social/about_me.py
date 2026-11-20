import re
import urllib.parse

from doxxx.core.helpers import get_random_user_agent
from doxxx.core.orchestrator import generic_validate
from doxxx.core.result import Result


def validate_about_me(user: str) -> Result:
    """About.me profile lookup.

    Real profiles resolve to 200 with a title like ``<Full Name> - <Location> | about.me``
    and an ``og:title`` of ``<Full Name> on about.me``; missing handles land on the bare
    ``about.me`` homepage (title exactly "about.me"). Both verdicts verify explicit body
    markers instead of relying on a bare status code.
    """
    quoted = urllib.parse.quote(user, safe="")
    url = f"https://about.me/{quoted}"
    show_url = f"https://about.me/{user}"

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def process(response) -> Result:
        if response.status_code == 404:
            # A real profile resolves to 200; a missing handle lands on the bare
            # about.me homepage whose title is just "about.me".
            title = re.search(r"<title>([^<]+)</title>", response.text)
            if title and title.group(1).strip() == "about.me":
                return Result.available()
            return Result.error("404 without the bare about.me title marker")

        if response.status_code == 200:
            title = re.search(r"<title>([^<]+)</title>", response.text)
            if not title or "| about.me" not in title.group(1):
                return Result.error("200 without the About.me profile title marker")

            # Some handles (e.g. ``aboutme``) resolve to the site landing page rather than
            # a user profile; gate on the og:title marker too.
            og_title = re.search(r'property="og:title" content="([^"]+)"', response.text)
            if not og_title or "on about.me" not in og_title.group(1):
                return Result.error("200 without the og:title profile marker")

            extra: dict = {}
            media: dict = {}

            raw = title.group(1).rsplit("|", 1)[0].strip()
            if " - " in raw:
                display_name, location = raw.split(" - ", 1)
            else:
                display_name, location = raw, ""
            if display_name.strip():
                extra["full_name"] = display_name.strip()
            if location.strip():
                extra["location"] = location.strip()

            bio = re.search(r'<meta name="description" content="([^"]+)"', response.text)
            if bio and bio.group(1).strip():
                extra["bio"] = bio.group(1).strip()

            image = re.search(r'property="og:image" content="([^"]+)"', response.text)
            if image:
                media["avatar"] = image.group(1)
            return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected response status {response.status_code}")

    return generic_validate(
        url, process, headers=headers, show_url=show_url, follow_redirects=True
    )
