"""OnlyFans username availability validator.

OnlyFans exposes public creator pages at ``https://onlyfans.com/{user}``. A
taken username returns a 200 with profile markers; an unavailable username
returns a redirect / 404 with no profile content. This module uses the
impersonating transport because OnlyFans inspects TLS fingerprints and bot
behaviour.

NOTE: OnlyFans may rate-limit frequent probes from a single IP. Use the
``--delay`` and ``-C`` (concurrency) flags to stay respectful.
"""

import re

from doxxx.core.impersonate import impersonate_validate
from doxxx.core.result import Result


def validate_onlyfans(user: str) -> Result:
    """Check whether an OnlyFans creator username is taken."""
    url = f"https://onlyfans.com/{user}"
    show_url = url

    def process(response):
        html = response.text

        # Not-found states: redirect to home page or explicit 404 page.
        if response.status_code == 404:
            if "Page not found" in html or "404" in html:
                return Result.available(url=show_url)
        if response.status_code in (301, 302):
            location = response.headers.get("location", "")
            if location.rstrip("/") == "https://onlyfans.com" or "/home" in location:
                return Result.available(url=show_url)

        # Taken state: verified by unique profile HTML markers.
        if response.status_code == 200:
            has_profile = any(
                marker in html
                for marker in (
                    "profile",
                    "creator",
                    "subscription",
                )
            )
            # Confirm it's not just a generic login/landing page.
            is_landing = "OnlyFans is 18+" in html or "Join OnlyFans" in html
            if has_profile and not is_landing:
                extra: dict[str, str] = {}
                # Extract creator name from og:title if present.
                title = re.search(
                    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.I,
                )
                if title:
                    extra["name"] = title.group(1).strip()
                avatar = re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.I,
                )
                media: dict[str, str] = {}
                if avatar:
                    media["avatar"] = avatar.group(1).strip()
                return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected OnlyFans response (status {response.status_code})")

    return impersonate_validate(url, process, show_url=show_url, allow_redirects=True)
