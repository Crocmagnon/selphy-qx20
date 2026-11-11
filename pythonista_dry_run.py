"""Same as pythonista_print.py, but stops before printing: shows the preview, waits for the
printer and checks it accepts the images. No paper or ink used."""
import importlib

import pythonista_print

importlib.reload(pythonista_print)  # Pythonista keeps modules loaded between runs
pythonista_print.main(dry_run=True)
