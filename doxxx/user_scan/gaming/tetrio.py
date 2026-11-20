import json
import urllib.parse

from doxxx.core.helpers import get_random_user_agent
from doxxx.core.orchestrator import generic_validate
from doxxx.core.result import Result


def validate_tetrio(user: str) -> Result:
    """TETR.IO player lookup via the public TETR.IO API.

    The API answers with an explicit JSON verdict for both states:
    ``{"success": true, "data": {...}}`` for a real player and
    ``{"success": false, "error": {"msg": "No such user! | ..."}}`` with a 404
    for a nonexistent one, so neither verdict relies on a bare status code.
    """
    quoted = urllib.parse.quote(user, safe="")
    url = "https://ch.tetr.io/api/users/" + quoted
    show_url = f"https://tetr.io/u/{user}"

    headers = {
        "User-Agent": get_random_user_agent(),
        "Accept": "application/json",
    }

    def process(response) -> Result:
        if response.status_code == 404:
            try:
                body = response.json()
            except json.JSONDecodeError:
                return Result.error("404 with non-JSON body")
            error = body.get("error") or {}
            if body.get("success") is False and "No such user" in str(error.get("msg", "")):
                return Result.available()
            return Result.error("404 without the no-such-user marker")

        if response.status_code == 200:
            try:
                body = response.json()
            except json.JSONDecodeError:
                return Result.error("200 with non-JSON body")
            data = body.get("data") or {}
            if body.get("success") is not True or not data.get("username"):
                return Result.error("200 without verified player data")

            extra: dict = {}
            media: dict = {}
            extra["player"] = data["username"]
            if data.get("role"):
                extra["role"] = data["role"]
            if data.get("country"):
                extra["country"] = data["country"]
            if data.get("xp"):
                extra["xp"] = int(data["xp"])
            if data.get("friend_count") is not None:
                extra["friends"] = data["friend_count"]
            if data.get("gamesplayed") is not None:
                extra["games_played"] = data["gamesplayed"]
            if data.get("bio"):
                extra["bio"] = data["bio"]
            if data.get("_id"):
                media["avatar"] = f"https://tetr.io/user-content/avatars/{data['_id']}.jpg"
            return Result.taken(extra=extra, media=media)

        return Result.error(f"Unexpected response status {response.status_code}")

    return generic_validate(url, process, headers=headers, show_url=show_url)
