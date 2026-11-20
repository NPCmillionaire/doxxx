import html
import re
import urllib.parse

from doxxx.core.impersonate import impersonate_validate
from doxxx.core.result import Result


def validate_cara(user: str) -> Result:
    """Cara artist portfolio lookup.

    The site sits behind a Cloudflare wall that rejects Python's default TLS
    stack, so the request goes through the impersonating session. A real
    portfolio renders ``Cara (@<handle>) | Cara - ...`` in og:title; a miss is
    a 404 with the generic site-wide og:title, giving both states explicit
    markers.
    """
    quoted = urllib.parse.quote(user, safe="")
    url = "https://cara.app/" + quoted
    show_url = f"https://cara.app/{user}"

    def process(response) -> Result:
        if response.status_code == 404:
            if "Artist Social" in response.text and not re.search(r"Cara \(@[^)]+\)", response.text):
                return Result.available()
            return Result.error("404 without the generic-title marker")

        if response.status_code == 200:
            og_title = re.search(r'Cara \(@([^)]+)\)', response.text)
            if not og_title:
                return Result.error("200 without the profile og:title marker")

            extra: dict = {}
            media: dict = {}
            extra["handle"] = og_title.group(1).strip()

            bio = re.search(r'"bio":"([^"]+)"', response.text)
            if bio and bio.group(1).strip():
                extra["bio"] = bio.group(1).strip()

            image = re.search(r'og:image" content="([^"]+)"', response.text)
            if image:
                media["avatar"] = html.unescape(image.group(1))
            return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected response status {response.status_code}")

    return impersonate_validate(
        url,
        process,
        impersonate="chrome",
        show_url=show_url,
        allow_redirects=True,
    )
