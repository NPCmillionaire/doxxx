import html
import json
import re
import urllib.parse

from doxxx.core.helpers import get_random_user_agent
from doxxx.core.orchestrator import generic_validate
from doxxx.core.result import Result


def validate_wattpad(user: str) -> Result:
    """Wattpad author profile lookup.

    The profile page redirects to the canonical case and embeds the user object
    in the ``window.prefetched`` cache (``{"user.<Handle>": {"data": [...]}}``).
    The 404 state is a dedicated Wattpad error page, not a bare status.
    """
    quoted = urllib.parse.quote(user, safe="")
    url = "https://www.wattpad.com/user/" + quoted
    show_url = f"https://www.wattpad.com/user/{user}"

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
    }

    def process(response) -> Result:
        if response.status_code == 404:
            if "Wattpad" in response.text:
                return Result.available()
            return Result.error("404 from an unexpected page")

        if response.status_code == 200:
            # The prefetched cache JSON-serializes cleanly; fall back to a
            # narrow regex on the user object when extraction gets noisy.
            profile = None
            prefetched = re.search(r"window\.prefetched = (\{.*?\});\s*\n", response.text, re.DOTALL)
            if prefetched:
                try:
                    cache = json.loads(prefetched.group(1))
                    user_keys = [k for k in cache if k.lower() == f"user.{user}".lower()]
                    if user_keys:
                        profile = cache[user_keys[0]]["data"][0]
                except (json.JSONDecodeError, KeyError, IndexError, TypeError):
                    profile = None
            if profile is None or not profile.get("username"):
                fallback = re.search(r'"username":"([^"]+)","avatar":"([^"]+)"', response.text)
                if fallback and fallback.group(1).lower() == user.lower():
                    profile = {"username": fallback.group(1), "avatar": fallback.group(2)}
            if profile is None:
                return Result.error("Profile prefetch block not found")

            extra: dict = {}
            media: dict = {}
            extra["username"] = profile.get("username")
            if profile.get("name"):
                extra["fullname"] = profile["name"]
            description = profile.get("description")
            if description:
                clean = html.unescape(str(description)).strip()
                if clean:
                    extra["bio"] = clean
            if profile.get("avatar"):
                media["avatar"] = profile["avatar"]
            if profile.get("backgroundUrl"):
                media["banner"] = profile["backgroundUrl"]
            return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected response status {response.status_code}")

    return generic_validate(
        url, process, headers=headers, show_url=show_url, follow_redirects=True
    )
