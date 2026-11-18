# GitHub contributions: a user's last year of contributions, one column per week,
# from GitHub's public https://github.com/<username>.contribs endpoint. No token is
# needed; GitHub refreshes that data once a day.

import gitmatrix
from fetch import AsyncFetch
from scrolling import Scroll

NAME = "github_contributions"
HOST = "github.com"
DAY_S = 24 * 60 * 60
# ticks_diff() only spans ~6.2 days, so AsyncFetch can't time a longer interval
MAX_DAYS = 6
# brightness for GitHub's five levels (none, then quartiles of the busiest day)
LEVELS = (0.04, 0.2, 0.45, 0.7, 1.0)

api = None
key = None
weeks = []
total = None
pens = []
message = None
scroll = None


def _rgb(text):
    try:
        return int(text[1:3], 16), int(text[3:5], 16), int(text[5:7], 16)
    except (TypeError, ValueError, IndexError):
        return 57, 211, 83


def _on_complete(f):
    global weeks, total, message
    try:
        data = f.to_json()
        out = []
        for week in data["weeks"]:
            days = [0] * 7
            for day in week["contribution_days"]:
                days[day["weekday"] % 7] = max(0, min(4, int(day["level"])))
            out.append(days)
    except (ValueError, KeyError, TypeError):
        message = "Bad data"
        return
    total = data.get("total_contributions")
    weeks = out[-screen.width:]
    message = None


def _on_error(f):
    global message
    message = "No such user" if f.http_status == 404 else f"HTTP {f.http_status}"
    return True


def _setup():
    global api, key, pens, message
    cfg = gitmatrix.settings(NAME)
    k = ((cfg.get("username") or "").strip().lstrip("@"), cfg.get("refresh_days"), cfg.get("colour"))
    if k == key:
        return
    key = k
    username, days, colour = k
    r, g, b = _rgb(colour)
    pens = [color.rgb(int(r * f), int(g * f), int(b * f)) for f in LEVELS]
    api = None
    if not username:
        message = "Set a username"
        return
    message = None
    days = max(1, min(MAX_DAYS, days or 1))
    api = AsyncFetch(HOST, 443, use_tls=True)
    api.on_complete(_on_complete)
    api.on_error(_on_error)
    api.fetch("/" + username + ".contribs", interval=days * DAY_S, headers={"Accept": "application/json"})


def on_show():
    _setup()


def on_settings():
    _setup()


def _say(text):
    global scroll
    if scroll is None:
        scroll = Scroll(text)
    elif scroll.text != text:
        scroll.set_text(text)
    screen.pen = pens[-1] if pens else color.rgb(57, 211, 83)
    scroll.update()
    scroll.render()


def update():
    global message
    if api is not None:
        try:
            api.update()
        except Exception as e:  # noqa: BLE001 - a network blip shouldn't count against the plugin
            message = "Offline" if not weeks else None
            print("github_contributions:", e)

    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    if not weeks:
        _say(message or "Loading")
        return
    x0 = screen.width - len(weeks)
    for i, days in enumerate(weeks):
        for y, level in enumerate(days):
            screen.pen = pens[level]
            screen.rectangle(x0 + i, y, 1, 1)
