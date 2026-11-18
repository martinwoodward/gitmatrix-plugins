# Matrix rain: green code trickling down the 53x7 grid. Settings come from the
# Art Matrix-style config.html via plugin_config(), so it ports both ways.

import random

from plugin_config import plugin_config

cfg = plugin_config("matrix_rain", {
    "colour": (0, 255, 70),
    "speed": 1.0,
    "density": 12,
    "white_heads": True,
})
colour = cfg["colour"]
speed = cfg["speed"]
density = cfg["density"]
white_heads = cfg["white_heads"]

TRAIL = 6
drops = []
pens = []
head_pen = None


class Drop:
    def __init__(self, x=None):
        self.reset(x)
        self.y = random.uniform(-screen.height * 2, screen.height)

    def reset(self, x=None):
        self.x = random.randrange(screen.width) if x is None else x
        self.y = -random.uniform(0, screen.height * 2)
        self.v = random.uniform(0.04, 0.12) * speed


def _setup():
    global head_pen
    r, g, b = colour
    pens[:] = [color.rgb(int(r * f), int(g * f), int(b * f)) for f in (1.0, 0.6, 0.35, 0.2, 0.1, 0.05)]
    head_pen = color.rgb(200, 255, 220) if white_heads else pens[0]
    drops[:] = [Drop() for _ in range(max(1, min(60, density)))]


def update():
    if not drops:
        _setup()
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    for d in drops:
        d.y += d.v
        if d.y - TRAIL > screen.height:
            d.reset()
        head = int(d.y)
        for i in range(TRAIL):
            y = head - i
            if 0 <= y < screen.height:
                screen.pen = head_pen if i == 0 else pens[i]
                screen.rectangle(d.x, y, 1, 1)
