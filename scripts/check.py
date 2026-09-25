#!/usr/bin/env python3
"""Project health check. Run from the repo root:  python3 scripts/check.py

1. Builds the site with Hugo and fails on any WARN or ERROR.
2. Checks every event file against the Pages CMS schema (.pages.yml) and
   validates the date format Hugo needs (seconds included).
3. Parses every generated .ics calendar file.
4. Confirms every language got its home, events and event pages.
5. Checks that every internal link (href, src, CSS url()) resolves to a file
   in the build, with the site served from a subpath like /tangoescape/.

Needs: hugo (extended, >= 0.166), python packages pyyaml and icalendar
  pip install pyyaml icalendar
"""
import glob
import os
import re
import shutil
import subprocess
import sys
import tempfile
from html.parser import HTMLParser
from urllib.parse import unquote, urljoin, urlsplit

import yaml

try:
    import icalendar
except ImportError:
    icalendar = None

LANGS = {"de": "", "en": "en/"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
# Subpath build, like the preview, to catch root-absolute links.
BASE = "http://localhost/tangoescape/"
problems = []


def fail(msg):
    problems.append(msg)


# 1. Build -------------------------------------------------------------------
out = tempfile.mkdtemp(prefix="tango-build-")
res = subprocess.run(
    ["hugo", "--gc", "--minify", "--baseURL", BASE, "--destination", out],
    capture_output=True, text=True,
)
log = res.stdout + res.stderr
for line in log.splitlines():
    if line.startswith(("WARN", "ERROR")):
        fail(f"hugo: {line}")
if res.returncode != 0:
    fail("hugo build failed")
    print(log)

# 2. Content vs CMS schema -----------------------------------------------------
cms = yaml.safe_load(open(".pages.yml"))
events_schema = next(c for c in cms["content"] if c["name"] == "events")
schema_keys = {f["name"] for f in events_schema["fields"]} - {"body"}
# Pages CMS drops empty fields on save, so only required ones must be present
required_keys = {f["name"] for f in events_schema["fields"] if f.get("required")}
tr_fields = {f["name"] for f in cms["components"]["translation"]["fields"]}

for path in sorted(glob.glob("content/events/*.md")):
    parts = open(path, encoding="utf-8").read().split("---", 2)
    if len(parts) < 3:
        fail(f"{path}: no front matter")
        continue
    fm = yaml.safe_load(parts[1], ) or {}
    extra, missing = set(fm) - schema_keys, required_keys - set(fm)
    if extra:
        fail(f"{path}: fields not in .pages.yml: {sorted(extra)}")
    if missing:
        fail(f"{path}: required fields missing: {sorted(missing)}")
    for key in ("date", "end"):
        val = fm.get(key)
        if val and not DATE_RE.match(str(val).replace(" ", "T")):
            fail(f"{path}: {key} '{val}' must look like 2026-10-01T18:00:00")
    for lang, tr in (fm.get("translations") or {}).items():
        if lang not in LANGS:
            fail(f"{path}: translation for unknown language '{lang}'")
        if tr and set(tr) - tr_fields:
            fail(f"{path}: translations.{lang} has unknown fields {sorted(set(tr) - tr_fields)}")

# 3. Calendar files ------------------------------------------------------------
ics_files = glob.glob(f"{out}/**/*.ics", recursive=True)
if not ics_files:
    fail("no .ics files generated")
if icalendar:
    for f in ics_files:
        raw = open(f, "rb").read()
        if b"\r\n" not in raw:
            fail(f"{f}: calendar lines must end with CRLF")
        try:
            icalendar.Calendar.from_ical(raw)
        except Exception as e:  # noqa: BLE001
            fail(f"{f}: invalid calendar: {e}")
else:
    print("note: pip install icalendar to validate .ics files")

# 4. Pages per language ----------------------------------------------------------
slugs = [p.split("/")[-1][:-3] for p in glob.glob("content/events/*.md")]
for lang, prefix in LANGS.items():
    for rel in ["index.html", "events/index.html", "events/index.ics"] + [
        f"events/{s}/index.html" for s in slugs
    ]:
        if not glob.glob(f"{out}/{prefix}{rel}"):
            fail(f"missing page for {lang}: /{prefix}{rel}")

# 5. Internal links ----------------------------------------------------------------
class LinkParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links = []

    def handle_starttag(self, tag, attrs):
        self.links += [v for k, v in attrs if k in ("href", "src") and v]


def page_url(path):
    rel = os.path.relpath(path, out).replace(os.sep, "/")
    return BASE + (rel[: -len("index.html")] if rel.endswith("index.html") else rel)


def check_link(src, link):
    """Checks one link; returns True if it points at the site itself."""
    if link.startswith("#") or link.split(":", 1)[0] in ("mailto", "tel", "data"):
        return False
    link = re.sub(r"^webcal://", "http://", link)
    url = urlsplit(urljoin(page_url(src), link))
    if url.scheme not in ("http", "https") or url.netloc != urlsplit(BASE).netloc:
        return False  # external
    base_path = urlsplit(BASE).path
    if not url.path.startswith(base_path):
        fail(f"{page_url(src)}: link '{link}' points outside {base_path}")
        return True
    target = os.path.join(out, unquote(url.path[len(base_path):]))
    if url.path.endswith("/") or os.path.isdir(target):
        target = os.path.join(target, "index.html")
    if not os.path.isfile(target):
        fail(f"{page_url(src)}: broken link '{link}'")
    return True


n_links = 0
for f in glob.glob(f"{out}/**/*.html", recursive=True):
    parser = LinkParser()
    parser.feed(open(f, encoding="utf-8").read())
    n_links += sum(check_link(f, link) for link in parser.links)
for f in glob.glob(f"{out}/**/*.css", recursive=True):
    css = open(f, encoding="utf-8").read()
    n_links += sum(check_link(f, link) for link in re.findall(r"url\(\s*['\"]?([^'\")]+)", css))

shutil.rmtree(out, ignore_errors=True)

if problems:
    print("✗ check failed:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print(f"✓ all good: build clean, {len(slugs)} events, {len(ics_files)} calendar files, {len(LANGS)} languages, {n_links} internal links")
