# JSON feed: fetch any JSON URL, pick a value out of it with a dotted path
# (e.g. "data.0.price") and scroll it with a label. An optional token is sent
# as "Authorization: Bearer <token>".

import gitmatrix
from fetch import AsyncFetch
from scrolling import Scroll

NAME = "json_feed"

api = None
key = None
scroll = None
text = "Loading"
pen = None


def _rgb(value):
    try:
        return int(value[1:3], 16), int(value[3:5], 16), int(value[5:7], 16)
    except (TypeError, ValueError, IndexError):
        return 255, 255, 255


def split_url(url):
    """(host, port, tls, path) for an http(s) URL."""
    tls = url.startswith("https://")
    rest = url.split("://", 1)[1]
    host, _, path = rest.partition("/")
    port = 443 if tls else 80
    if ":" in host:
        host, port = host.rsplit(":", 1)
        port = int(port)
    return host, port, tls, "/" + path


def pick(data, path):
    """Follow a dotted path through dicts and lists; numbers index lists."""
    for part in [p for p in (path or "").split(".") if p]:
        if isinstance(data, list):
            data = data[int(part)]
        else:
            data = data[part]
    return data


def _show(value):
    global text
    label = gitmatrix.settings(NAME).get("label") or ""
    if isinstance(value, float):
        value = f"{value:.2f}".rstrip("0").rstrip(".")
    text = f"{label} {value}".strip() if label else str(value)


def _on_complete(f):
    global text
    try:
        _show(pick(f.to_json(), gitmatrix.settings(NAME).get("path")))
    except (KeyError, IndexError, ValueError, TypeError):
        text = "Path not found"


def _on_error(f):
    global text
    text = "Check token" if f.http_status in (401, 403) else f"HTTP {f.http_status}"
    return True


def _setup():
    global api, key, pen, text
    cfg = gitmatrix.settings(NAME)
    k = (cfg.get("url"), cfg.get("path"), cfg.get("label"), cfg.get("token"), cfg.get("refresh"), cfg.get("colour"))
    if k == key:
        return
    key = k
    url, _, _, token, refresh, colour = k
    pen = color.rgb(*_rgb(colour))
    api = None
    if not url:
        text = "Set a feed URL"
        return
    text = "Loading"
    host, port, tls, path = split_url(url)
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = "Bearer " + token
    api = AsyncFetch(host, port, use_tls=tls, max_bytes=32 * 1024)
    api.on_complete(_on_complete)
    api.on_error(_on_error)
    api.fetch(path, interval=max(30, refresh or 300), headers=headers)


def on_show():
    _setup()


def on_settings():
    _setup()


def update():
    global scroll, text
    if api is not None:
        try:
            api.update()
        except Exception as e:  # noqa: BLE001 - a network blip shouldn't count against the plugin
            text = "Offline"
            print("json_feed:", e)
    if scroll is None:
        scroll = Scroll(text, gap=20)
    elif scroll.text != text:
        scroll.set_text(text)
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    screen.pen = pen or color.rgb(255, 255, 255)
    scroll.update()
    scroll.render()
