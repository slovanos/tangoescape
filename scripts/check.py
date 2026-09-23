#!/usr/bin/env python3
"""Project health check. Run from the repo root:  python3 scripts/check.py

1. Builds the site with Hugo and fails on any WARN or ERROR.
2. Checks every event file against the Pages CMS schema (.pages.yml) and
   validates the date format Hugo needs (seconds included).
3. Parses every generated .ics calendar file.
4. Confirms every language got its home, events and event pages.

Needs: hugo (extended, >= 0.166), python packages pyyaml and icalendar
  pip install pyyaml icalendar
"""
import glob
import re
import shutil
import subprocess
import sys
import tempfile

import yaml

try:
    import icalendar
except ImportError:
    icalendar = None

LANGS = {"de": "", "en": "en/", "es": "es/"}
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}$")
problems = []


def fail(msg):
    problems.append(msg)


# 1. Build -------------------------------------------------------------------
out = tempfile.mkdtemp(prefix="tango-build-")
res = subprocess.run(
    ["hugo", "--gc", "--minify", "--destination", out],
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
tr_fields = {f["name"] for f in cms["components"]["translation"]["fields"]}

for path in sorted(glob.glob("content/events/*.md")):
    parts = open(path, encoding="utf-8").read().split("---", 2)
    if len(parts) < 3:
        fail(f"{path}: no front matter")
        continue
    fm = yaml.safe_load(parts[1], ) or {}
    extra, missing = set(fm) - schema_keys, schema_keys - set(fm)
    if extra:
        fail(f"{path}: fields not in .pages.yml: {sorted(extra)}")
    if missing:
        fail(f"{path}: fields missing (CMS expects them): {sorted(missing)}")
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

shutil.rmtree(out, ignore_errors=True)

if problems:
    print("✗ check failed:")
    for p in problems:
        print("  -", p)
    sys.exit(1)
print(f"✓ all good: build clean, {len(slugs)} events, {len(ics_files)} calendar files, {len(LANGS)} languages")
