# GitHub contributions: a user's last year of contributions, one column per week,
# fetched live from the GitHub GraphQL API. Needs a token (any classic or
# fine-grained token works; it needs no scopes for public contributions).

import json

import gitmatrix
from fetch import AsyncFetch
from scrolling import Scroll

NAME = "github_contributions"
HOST = "api.github.com"
QUERY = ("query($login:String!){user(login:$login){contributionsCollection{contributionCalendar"
         "{totalContributions weeks{contributionDays{contributionCount weekday}}}}}}")
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
    data = f.to_json()
    user = (data.get("data") or {}).get("user")
    if not user:
        errors = data.get("errors") or [{}]
        message = errors[0].get("message", "No such user")[:40]
        return
    cal = user["contributionsCollection"]["contributionCalendar"]
    total = cal["totalContributions"]
    out = []
    for week in cal["weeks"]:
        days = [0] * 7
        for day in week["contributionDays"]:
            days[day["weekday"]] = day["contributionCount"]
        out.append(days)
    weeks = out[-screen.width:]
    message = None


def _on_error(f):
    global message
    message = "Check token" if f.http_status in (401, 403) else f"HTTP {f.http_status}"
    return True


def _setup():
    global api, key, pens, message
    cfg = gitmatrix.settings(NAME)
    k = (cfg.get("username"), cfg.get("token"), cfg.get("refresh"), cfg.get("colour"))
    if k == key:
        return
    key = k
    username, token, refresh, colour = k
    r, g, b = _rgb(colour)
    pens = [color.rgb(int(r * f), int(g * f), int(b * f)) for f in LEVELS]
    api = None
    if not username or not token:
        message = "Set a username and token"
        return
    message = None
    body = json.dumps({"query": QUERY, "variables": {"login": username}}).encode()
    api = AsyncFetch(HOST, 443, use_tls=True)
    api.on_complete(_on_complete)
    api.on_error(_on_error)
    api.fetch("/graphql", interval=max(60, refresh or 900), method="POST", data=body,
              headers={"Authorization": "bearer " + token, "Content-Type": "application/json"})


def on_show():
    _setup()


def on_settings():
    _setup()


def _level(count, top):
    if count <= 0 or top <= 0:
        return 0
    return min(4, 1 + (count - 1) * 4 // top)


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
    top = max(max(w) for w in weeks)
    x0 = screen.width - len(weeks)
    for i, days in enumerate(weeks):
        for y, count in enumerate(days):
            screen.pen = pens[_level(count, top)]
            screen.rectangle(x0 + i, y, 1, 1)
