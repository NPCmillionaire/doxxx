"""Ghost username availability validator.

Ghost is a popular publishing/newsletter platform. Creator publications
live at ``https://{user}.ghost.io`` or ``https://{user}.substack.com``.
A taken username returns a 200 with publication content; an unavailable
username returns a 404 or redirect. This module uses the impersonating
transport because Ghost may inspect TLS fingerprints.

NOTE: Ghost publications use a subdomain format, so we probe the
``{user}.ghost.io`` subdomain directly.
"""

import re
from doxxx.core.impersonate import impersonate_validate
from doxxx.core.result import Result


def validate_ghost(user: str) -> Result:
    """Check whether a Ghost.io publication username is taken."""
    url = f"https://{user}.ghost.io"
    show_url = url

    def process(response):
        html = response.text

        # Not-found states: Ghost returns 404 for non-existent subdomains.
        if response.status_code == 404:
            if "Page not found" in html or "404" in html:
                return Result.available(url=show_url)
        if response.status_code in (301, 302):
            location = response.headers.get("location", "")
            if location.rstrip("/") == "https://ghost.io" or "/home" in location:
                return Result.available(url=show_url)

        # Taken state: verified by unique publication HTML markers.
        if response.status_code == 200:
            has_publication = any(
                marker in html
                for marker in (
                    "publication",
                    "post",
                    "article",
                )
            )
            # Confirm it's not just a generic landing page.
            is_landing = "Ghost" in html and ("Sign up" in html or "Log in" in html)
            if has_publication and not is_landing:
                extra: dict[str, str] = {}
                # Extract publication name from og:title if present.
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

        return Result.error(f"Unexpected Ghost response (status {response.status_code})")

    return impersonate_validate(url, process, show_url=show_url, allow_redirects=True)