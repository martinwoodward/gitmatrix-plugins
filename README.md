# GitMatrix plugins

Plugins for **GitMatrix**, the firmware for the Pimoroni 53×7 GitHub Contribution Widget.
Your GitMatrix lists everything here on its **Discover** page (`http://gitmatrix.local/discover.html`),
and installs plugins straight onto the device.

The format is the same as [pimoroni/artmatrix-plugins](https://github.com/pimoroni/artmatrix-plugins),
so Art Matrix plugins port with small changes (mostly: the screen is 53×7). See the
[plugin API](https://github.com/martinwoodward/ghcontrib/blob/main/docs/gitmatrix/plugin-api.md)
and the author guide and examples below for GitMatrix-specific details. The API link
will work once the firmware repository is public and the documentation reaches `main`;
GitHub redirects it if the repository is renamed.

| Plugin | What it does |
| --- | --- |
| [`github_contributions`](github_contributions) | Anyone's contribution graph from GitHub's public `.contribs` feed (no token needed) |
| [`json_feed`](json_feed) | Scrolls a value from any JSON URL (URL, secret and colour settings) |
| [`matrix_rain`](matrix_rain) | Falling green code (an Art Matrix-style `config.html`) |

## Writing a plugin

Each plugin is a folder at the top of this repo, named as a Python identifier:

```
my_plugin/
    __init__.py      # the code: update() draws one frame into `screen` (53x7)
    package.json     # manifest (below)
    thumbnail.png    # 53x7 still, shown on Discover until there's a preview.gif
    config.html      # optional Art Matrix-style settings page
    preview/         # optional setup for the animated preview (below)
    preview.gif      # written by CI, don't edit
```

A minimal `__init__.py`:

```python
import gitmatrix

def update():
    screen.pen = color.rgb(0, 0, 0)
    screen.clear()
    screen.pen = color.rgb(57, 211, 83)
    screen.rectangle(0, 0, 10, 7)
```

Optional hooks: `on_show()`, `on_hide()`, `on_settings()`, `on_input(event)` (with
`"input": true`) and `process_config(form)` (with `config.html`).

### `package.json`

You write `name`, `version`, `description`, `author`, `category` and `requires_internet`;
the generator adds `hash` and `urls`.

```json
{
  "name": "My Plugin",
  "version": "1.0.0",
  "description": "One line, at most 60 characters",
  "author": "your-github-handle",
  "category": "Information",
  "requires_internet": true,
  "tags": ["weather", "api"],
  "min_firmware": "0.1.0",
  "settings": [
    {"key": "url", "type": "url", "label": "Feed URL"},
    {"key": "token", "type": "secret", "label": "API token"},
    {"key": "refresh", "type": "int", "label": "Refresh (s)", "min": 30, "max": 3600, "default": 300}
  ]
}
```

- `category`: `Information`, `Visualisations`, `Scenes`, `Interactive` or `3D`.
- `tags` (up to 10), `min_firmware`, `input`, `hold` and `settings` are optional.
- **Settings** are rendered as a form on the device's plugin page. Types: `text`, `url`,
  `secret`, `number`, `int`, `color`, `select` (with `options`), `bool`; each takes
  `label`, `default`, `help`, `placeholder`, and `min`/`max`/`step` for numbers.
  Read them with `gitmatrix.settings("my_plugin")`.
- **Secrets** are stored on the device in `/secrets/`, never sent back to the browser,
  and must never be committed here: a `secret` field can't have a `default`.
- Bump `version` whenever you change a plugin, so devices offer the update.

### Publishing

```sh
python ci/generate_packages.py          # writes package.json hashes/urls and index.json
python ci/generate_packages.py --check  # what CI runs
```

Commit the result and open a pull request. CI validates every manifest, settings
schema and thumbnail; on `main` it records each plugin's `preview.gif` and regenerates
`index.json` if anything is stale.

### Previews

Discover shows an animated `preview.gif` of each plugin: CI runs it for a few seconds
with the firmware's
[`tools/preview.py`](https://github.com/martinwoodward/gitmatrix/blob/main/gitmatrix/tools/preview.py)
and draws the display as LED dots. Neither `preview.gif` nor `preview/` is installed on
the device. A pull request's previews are attached to its CI run as the `previews`
artifact, so you can check them before merging.

The recording has no network and no settings, so a plugin that needs either should add
`preview/preview.json` with canned ones (secrets included: use fake values, it's public):

```json
{
  "skip": 1,
  "settings": {"username": "octocat"},
  "fetch": {"github.com/octocat.contribs": "contribs.json"}
}
```

`fetch` maps `"host/path"` (no query string) to a file in `preview/` that
`fetch.AsyncFetch` returns; anything else gets HTTP 404. `seconds` (1–15, default 6),
`skip` (seconds to run first) and `seed` (for `random`) are optional. See
[`json_feed/preview/`](json_feed/preview) and
[`github_contributions/preview/`](github_contributions/preview), and the
[plugin API](https://github.com/martinwoodward/gitmatrix/blob/main/docs/gitmatrix/plugin-api.md#store-previews)
for what renders faithfully. To record one locally (needs Pillow and a checkout of
[martinwoodward/gitmatrix](https://github.com/martinwoodward/gitmatrix)):

```sh
python3 ../gitmatrix/gitmatrix/tools/preview.py my_plugin   # writes my_plugin/preview.gif
```

### Good citizenship on the device

- Keep `update()` fast (under ~20 ms) and never block: use `fetch.AsyncFetch` and call
  its `update()` from yours.
- Don't write files yourself. Flash writes while the Bluetooth speaker is streaming can
  hang the board, so use `gitmatrix.state()` and `gitmatrix.settings()`, which wait.
- Catch network errors in `update()`: five exceptions in a row stop the plugin.

## Using another repo

A GitMatrix reads `PLUGIN_REPO` and `PLUGIN_BRANCH` from `/gitmatrix_config.py` on the
device (default `martinwoodward/gitmatrix-plugins`, `main`). Point them at a fork to test
your own plugins.

## License

MIT, see [LICENSE](LICENSE).
