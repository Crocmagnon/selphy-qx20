"""Pythonista: download the latest scripts from GitHub into this script's folder."""
import os

import requests

BASE = "https://raw.githubusercontent.com/Crocmagnon/selphy-qx20/main/"
FILES = ("cpnp_print.py", "pythonista_print.py", "update.py")
HERE = os.path.dirname(os.path.abspath(__file__))

texts = {}
for name in FILES:  # download everything first, so a failure leaves the folder untouched
    r = requests.get(BASE + name, timeout=15)
    r.raise_for_status()
    texts[name] = r.text
for name, text in texts.items():
    with open(os.path.join(HERE, name), "w", encoding="utf-8") as f:
        f.write(text)
    print("updated", name)
