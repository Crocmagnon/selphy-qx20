"""Pythonista: download the latest scripts from GitHub into this script's folder.

Files are fetched at the latest commit's SHA rather than at "main": raw.githubusercontent.com
caches branch URLs for a few minutes, but each commit URL is unique.
"""
import os

import requests

REPO = "Crocmagnon/selphy-qx20"
FILES = ("cpnp_print.py", "pythonista_print.py", "pythonista_dry_run.py", "update.py")
HERE = os.path.dirname(os.path.abspath(__file__))

r = requests.get(
    f"https://api.github.com/repos/{REPO}/commits/main",
    headers={"Accept": "application/vnd.github.sha"},
    timeout=15,
)
r.raise_for_status()
sha = r.text.strip()
print("latest commit", sha[:7])

texts = {}
for name in FILES:  # download everything first, so a failure leaves the folder untouched
    r = requests.get(f"https://raw.githubusercontent.com/{REPO}/{sha}/{name}", timeout=15)
    r.raise_for_status()
    texts[name] = r.text
for name, text in texts.items():
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(text)
    print("updated", name)
