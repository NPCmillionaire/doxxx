"""Stan Store username availability validator.

Stan Store is a creator commerce platform (digital products, courses,
bookings). Creator storefronts live at ``https://stan.store/{user}`` or
``https://{user}.stan.store``. A taken username returns a 200 with
storefront content; an unavailable username returns a 404 or redirect.
This module uses the impersonating transport.
"""

import re
from doxxx.core.impersonate import impersonate_validate
from doxxx.core.result import Result


def validate_stanstore(user: str) -> Result:
    """Check whether a Stan Store creator username is taken."""
    url = f"https://stan.store/{user}"
    show_url = url

    def process(response):
        html = response.text

        # Not-found states.
        if response.status_code == 404:
            if "Page not found" in html or "404" in html:
                return Result.available(url=show_url)
        if response.status_code in (301, 302):
            location = response.headers.get("location", "")
            if location.rstrip("/") == "https://stan.store" or "/home" in location:
                return Result.available(url=show_url)

        # Taken state: verified by unique storefront HTML markers.
        if response.status_code == 200:
            has_storefront = any(
                marker in html
                for marker in (
                    "storefront",
                    "product",
                    "course",
                    "booking",
                )
            )
            # Confirm it's not just a generic landing page.
            is_landing = "Stan Store" in html and (
                "Sign up" in html or "Log in" in html
            )
            if has_storefront and not is_landing:
                extra: dict[str, str] = {}
                # Extract name from og:title if present.
                title = re.search(
                    r'<meta[^>]+property=["\']og:title["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.IGNORECASE,
                )
                if title:
                    extra["display_name"] = title.group(1).strip()
                avatar = re.search(
                    r'<meta[^>]+property=["\']og:image["\'][^>]+content=["\']([^"\']+)',
                    html,
                    re.IGNORECASE,
                )
                media: dict[str, str] = {}
                if avatar:
                    media["avatar"] = avatar.group(1).strip()
                return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected Stan Store response (status {response.status_code})")

    return impersonate_validate(url, process, show_url=show_url, allow_redirects=True)