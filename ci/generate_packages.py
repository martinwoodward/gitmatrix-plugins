#!/usr/bin/env python3
"""Write each plugin's package.json and the index.json catalogue.

Adapted from pimoroni/artmatrix-plugins' ci/generate_packages.py, so the index and
manifests keep the Art Matrix format. GitMatrix adds version, tags, size and files to
each index entry, plus the optional settings schema, input, hold and min_firmware.

    python ci/generate_packages.py          # rewrite manifests and index.json
    python ci/generate_packages.py --check  # CI: fail if anything is stale or invalid
"""

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST_NAME = "package.json"
INDEX_NAME = "index.json"
INITIAL_VERSION = "1.0.0"
# the device checks a download against this, so it must match gitmatrix._store.package_hash
HASH_LENGTH = 12
TARGET_PREFIX = "plugins"
NOT_PLUGINS = {"ci", "docs"}
THUMBNAIL = "thumbnail.png"
THUMBNAIL_SIZE = (53, 7)
# recorded by gitmatrix/tools/preview.py from the setup in preview/, for Discover only
PREVIEW = "preview.gif"
PREVIEW_DIR = "preview"
# shown on Discover's cards, so every plugin needs all three
DETAILS = ("description", "author", "category")
CATEGORIES = ("Information", "Visualisations", "Scenes", "Interactive", "3D")
DESCRIPTION_MAX = 60
TAGS_MAX = 10
TAG_MAX = 30
EXCLUDE_NAMES = {MANIFEST_NAME, "config.json", "settings.json", "state.json", ".DS_Store", "Thumbs.db"}
EXCLUDE_SUFFIXES = {".pyc", ".mpy", ".swp"}
EXCLUDE_TAILS = ("_tokens.json",)
EXCLUDE_DIRS = {"__pycache__", ".ruff_cache", ".git"}
SIZE_WARN_BYTES = 48 * 1024
# kept from the author's manifest, in this order, after the generated fields
AUTHOR_FIELDS = ("requires_internet", "tags", "min_firmware", "input", "hold", "settings")
SETTING_TYPES = ("text", "string", "url", "secret", "number", "float", "int", "color", "select", "choice", "bool")
VERSION_RE = re.compile(r"^\d+(\.\d+){0,2}$")
KEY_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def is_plugin(path):
    if not path.is_dir() or path.name.startswith(".") or path.name in NOT_PLUGINS:
        return False
    return (path / "__init__.py").is_file()


def find_plugins():
    return sorted((path for path in ROOT.iterdir() if is_plugin(path)), key=lambda p: p.name)


def is_shippable(path, plugin):
    if path.name in EXCLUDE_NAMES or path.suffix in EXCLUDE_SUFFIXES or path.name.startswith("."):
        return False
    if any(path.name.endswith(tail) for tail in EXCLUDE_TAILS):
        return False
    parts = path.relative_to(plugin).parts
    if parts == (PREVIEW,) or (len(parts) > 1 and parts[0] == PREVIEW_DIR):
        return False
    return not any(part in EXCLUDE_DIRS for part in parts[:-1])


def plugin_files(plugin):
    files = [path for path in plugin.rglob("*") if path.is_file() and is_shippable(path, plugin)]
    return sorted(path.relative_to(plugin).as_posix() for path in files)


def package_hash(plugin, files):
    digest = hashlib.sha1()
    for path in files:
        digest.update(path.encode() + b"\0" + (plugin / path).read_bytes())
    return digest.hexdigest()[:HASH_LENGTH]


def read_manifest(plugin):
    try:
        data = json.loads((plugin / MANIFEST_NAME).read_text())
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def manifest_for(plugin):
    # name, version, details and the GitMatrix fields are the author's, so they're
    # read back out of the manifest this overwrites
    existing = read_manifest(plugin)

    manifest = {}
    name = existing.get("name")
    if isinstance(name, str) and name.strip():
        manifest["name"] = name
    else:
        manifest["name"] = " ".join(word[:1].upper() + word[1:] for word in plugin.name.split("_"))

    version = existing.get("version")
    manifest["version"] = version if isinstance(version, str) and version else INITIAL_VERSION

    files = plugin_files(plugin)
    manifest["hash"] = package_hash(plugin, files)

    for field in DETAILS:
        value = existing.get(field)
        if isinstance(value, str) and value.strip():
            manifest[field] = value

    for field in AUTHOR_FIELDS:
        if field in existing:
            manifest[field] = existing[field]

    manifest["urls"] = [[f"{TARGET_PREFIX}/{plugin.name}/{path}", path] for path in files]
    return manifest


def serialise(data):
    return json.dumps(data, indent=2) + "\n"


def total_bytes(plugin):
    return sum((plugin / path).stat().st_size for path in plugin_files(plugin))


def index_entry(plugin, manifest):
    entry = {field: manifest.get(field) for field in DETAILS}
    entry["hash"] = manifest["hash"]
    entry["version"] = manifest["version"]
    entry["requires_internet"] = manifest.get("requires_internet")
    entry["tags"] = manifest.get("tags", [])
    entry["size"] = total_bytes(plugin)
    entry["files"] = len(manifest["urls"])
    entry["settings"] = bool(manifest.get("settings"))
    entry["config"] = (plugin / "config.html").is_file()
    entry["input"] = bool(manifest.get("input"))
    if manifest.get("min_firmware"):
        entry["min_firmware"] = manifest["min_firmware"]
    preview = plugin / PREVIEW
    if preview.is_file():
        # Discover adds it to the GIF's URL, so a new recording isn't served from cache
        entry["preview"] = hashlib.sha1(preview.read_bytes()).hexdigest()[:HASH_LENGTH]
    return entry


def index_for(plugins):
    # details sits beside plugins: Art Matrix firmware reads each plugins value as the title
    manifests = {plugin.name: (plugin, manifest_for(plugin)) for plugin in plugins}
    return {
        "plugins": {name: manifest["name"] for name, (_, manifest) in manifests.items()},
        "details": {name: index_entry(plugin, manifest) for name, (plugin, manifest) in manifests.items()},
    }


def png_size(path):
    data = path.read_bytes()
    if data[:8] != b"\x89PNG\r\n\x1a\n" or data[12:16] != b"IHDR":
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


def validate_settings(name, settings):
    problems = []
    if not isinstance(settings, list):
        return [f"'{name}' settings must be a list"]
    keys = set()
    for i, field in enumerate(settings):
        where = f"'{name}' settings[{i}]"
        if not isinstance(field, dict):
            problems.append(f"{where} is not an object")
            continue
        key = field.get("key")
        if not isinstance(key, str) or not KEY_RE.match(key):
            problems.append(f"{where} key {key!r} is not an identifier")
        elif key in keys:
            problems.append(f"{where} key {key!r} is repeated")
        keys.add(key)
        kind = field.get("type", "text")
        if kind not in SETTING_TYPES:
            problems.append(f"{where} type {kind!r} is not one of {', '.join(SETTING_TYPES)}")
        if kind in ("select", "choice") and not field.get("options", field.get("choices")):
            problems.append(f"{where} is a {kind} with no options")
        lo, hi = field.get("min"), field.get("max")
        if isinstance(lo, (int, float)) and isinstance(hi, (int, float)) and lo > hi:
            problems.append(f"{where} min is above max")
        if kind == "secret" and "default" in field:
            problems.append(f"{where} is a secret with a default; secrets can't ship in the repo")
    return problems


def validate_plugin(plugin, manifest):
    name = plugin.name
    problems = []
    if not KEY_RE.match(name):
        problems.append(f"'{name}' is not a valid Python identifier, so it can't be imported")
    if not isinstance(manifest.get("requires_internet"), bool):
        problems.append(f"'{name}' has no requires_internet, set true or false in {name}/{MANIFEST_NAME}")
    if not VERSION_RE.match(manifest["version"]):
        problems.append(f"'{name}' version {manifest['version']!r} is not like 1.2.3")
    min_fw = manifest.get("min_firmware")
    if min_fw is not None and (not isinstance(min_fw, str) or not VERSION_RE.match(min_fw)):
        problems.append(f"'{name}' min_firmware {min_fw!r} is not like 0.1.0")
    tags = manifest.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(t, str) and 0 < len(t) <= TAG_MAX for t in tags):
        problems.append(f"'{name}' tags must be a list of short strings")
    elif len(tags) > TAGS_MAX:
        problems.append(f"'{name}' has {len(tags)} tags, the limit is {TAGS_MAX}")
    for field in ("input",):
        if field in manifest and not isinstance(manifest[field], bool):
            problems.append(f"'{name}' {field} must be true or false")
    if "hold" in manifest and manifest["hold"] not in (True, False, "audio"):
        problems.append(f"'{name}' hold must be true, false or \"audio\"")
    if "settings" in manifest:
        problems += validate_settings(name, manifest["settings"])
    thumb = plugin / THUMBNAIL
    if not thumb.is_file():
        problems.append(f"'{name}' has no {THUMBNAIL} ({THUMBNAIL_SIZE[0]}x{THUMBNAIL_SIZE[1]})")
    elif png_size(thumb) != THUMBNAIL_SIZE:
        problems.append(f"'{name}' {THUMBNAIL} is {png_size(thumb)}, it should be {THUMBNAIL_SIZE}")
    preview = plugin / PREVIEW
    if preview.is_file() and preview.read_bytes()[:6] not in (b"GIF87a", b"GIF89a"):
        problems.append(f"'{name}' {PREVIEW} is not a GIF")
    return problems


def validate_index(index, plugins):
    if not isinstance(index, dict):
        return ["index is not a JSON object"]
    catalogue = index.get("plugins")
    if not isinstance(catalogue, dict):
        return ["'plugins' is missing or is not an object"]

    problems = []
    if not catalogue:
        problems.append("'plugins' is empty, which would empty every device's catalogue")

    names = list(catalogue)
    for name in names:
        display = catalogue[name]
        if not isinstance(display, str) or not display.strip():
            problems.append(f"display name {display!r} for {name!r} is not a non-empty string")
    if names != sorted(names):
        problems.append("'plugins' is not sorted")

    details = index.get("details")
    if not isinstance(details, dict):
        problems.append("'details' is missing or is not an object")
        details = {}

    for name in names:
        entry = details.get(name)
        if not isinstance(entry, dict):
            problems.append(f"'{name}' has no entry in 'details'")
            continue
        for field in DETAILS:
            value = entry.get(field)
            if not isinstance(value, str) or not value.strip():
                problems.append(f"'{name}' has no {field}, set one in {name}/{MANIFEST_NAME}")
        description = entry.get("description")
        if isinstance(description, str) and len(description) > DESCRIPTION_MAX:
            problems.append(f"'{name}' description is {len(description)} characters, the limit is {DESCRIPTION_MAX}")
        category = entry.get("category")
        if isinstance(category, str) and category.strip() and category not in CATEGORIES:
            problems.append(f"'{name}' category {category!r} is not one of {', '.join(CATEGORIES)}")

    installable = {plugin.name for plugin in plugins if (plugin / MANIFEST_NAME).is_file()}
    for name in names:
        if name not in installable:
            problems.append(f"'{name}' is in the index but has no {MANIFEST_NAME}")
    return problems


def untracked_plugins(plugins):
    try:
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=True).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    tracked = {Path(path).parts[0] for path in listing.decode().split("\0") if path}
    return [plugin.name for plugin in plugins if plugin.name not in tracked]


def main():
    parser = argparse.ArgumentParser(description="Generate each plugin's package.json and index.json.")
    parser.add_argument("--check", action="store_true", help="report stale or invalid files and exit non-zero")
    parser.add_argument("--quiet", action="store_true", help="only report problems")
    args = parser.parse_args()

    plugins = find_plugins()
    if not plugins:
        print(f"No plugins found in {ROOT}", file=sys.stderr)
        return 1

    stale, written, problems = [], [], []

    for plugin in plugins:
        manifest = manifest_for(plugin)
        problems += validate_plugin(plugin, manifest)
        wanted = serialise(manifest)
        path = plugin / MANIFEST_NAME
        try:
            current = path.read_text()
        except OSError:
            current = None
        if current != wanted:
            if args.check:
                stale.append(plugin.name)
            else:
                path.write_text(wanted)
                written.append(plugin.name)
        if not args.quiet:
            size = total_bytes(plugin)
            note = "  <-- large, staged to flash on install" if size > SIZE_WARN_BYTES else ""
            print(f"{plugin.name:<24} {len(manifest['urls']):>3} files  {size / 1024:>7.1f} kB{note}")

    untracked = untracked_plugins(plugins)
    shippable = [plugin for plugin in plugins if plugin.name not in untracked]
    if untracked and not args.quiet:
        print(f"\nLeft out of {INDEX_NAME}, not committed:", file=sys.stderr)
        for name in untracked:
            print(f"  {name}", file=sys.stderr)

    index_path = ROOT / INDEX_NAME
    wanted_index = serialise(index_for(shippable))
    try:
        current_index = index_path.read_text()
    except OSError:
        current_index = None
    index_stale = current_index != wanted_index
    if index_stale and not args.check:
        index_path.write_text(wanted_index)

    problems += validate_index(json.loads(wanted_index), shippable)
    if problems:
        print(f"\n{INDEX_NAME} would not be safe to publish:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 1

    if args.check:
        if index_stale:
            stale.append(INDEX_NAME)
        if stale:
            print("\nThese are missing or out of date:", file=sys.stderr)
            for name in stale:
                print(f"  {name if name == INDEX_NAME else f'{name}/{MANIFEST_NAME}'}", file=sys.stderr)
            print("\nRun `python ci/generate_packages.py` and commit the result.", file=sys.stderr)
            return 1
        print(f"\n{len(plugins)} manifests and {INDEX_NAME} up to date.")
        return 0

    if index_stale:
        written.append(INDEX_NAME)
    if written:
        print(f"\nWrote {len(written)} file(s): {', '.join(written)}")
    else:
        print(f"\n{len(plugins)} manifests and {INDEX_NAME} already up to date.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
