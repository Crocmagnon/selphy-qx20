"""Same as pythonista_print.py, but stops before printing: shows the prepared image,
waits for the printer and checks it accepts the image. No paper or ink used."""
from pythonista_print import main

main(dry_run=True)
