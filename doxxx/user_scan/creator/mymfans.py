"""MYM.fans username availability validator.

MYM.fans is a creator platform similar to OnlyFans. Creator pages live at
``https://mym.fans/{user}``. A taken username returns a 200 with profile
content; an unavailable username returns a 404 or redirect. This module
uses the impersonating transport.
"""

import re
from doxxx.core.impersonate import impersonate_validate
from doxxx.core.result import Result


def validate_mymfans(user: str) -> Result:
    """Check whether a MYM.fans creator username is taken."""
    url = f"https://mym.fans/{user}"
    show_url = url

    def process(response):
        html = response.text

        # Not-found states.
        if response.status_code == 404:
            if "Page not found" in html or "404" in html:
                return Result.available(url=show_url)
        if response.status_code in (301, 302):
            location = response.headers.get("location", "")
            if location.rstrip("/") == "https://mym.fans" or "/home" in location:
                return Result.available(url=show_url)

        # Taken state: verified by unique profile HTML markers.
        if response.status_code == 200:
            has_profile = any(
                marker in html
                for marker in (
                    "profile",
                    "bio",
                    "photo",
                )
            )
            # Confirm it's not just a generic landing page.
            is_landing = "MYM" in html and ("Sign up" in html or "Log in" in html)
            if has_profile and not is_landing:
                extra: dict[str, str] = {}
                # Extract name from og:title if present.
                title = re.search(
                    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.I,
                )
                if title:
                    extra["display_name"] = title.group(1).strip()
                avatar = re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.I,
                )
                media: dict[str, str] = {}
                if avatar:
                    media["avatar"] = avatar.group(1).strip()
                return Result.taken(extra=extra, media=media)

        return Result.error(
            f"Unexpected MYM.fans response (status {response.status_code})"
        )

    return impersonate_validate(url, process, show_url=show_url, allow_redirects=True)