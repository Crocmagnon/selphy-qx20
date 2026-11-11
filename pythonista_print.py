"""Print a photo on the SELPHY QX20 from Pythonista (iOS).

Run it from Pythonista to pick a photo, or from the share sheet (Run Pythonista Script).
If the printer is not reachable, it asks you to switch to the printer's Wi-Fi and prints
as soon as it answers. Keep cpnp_print.py in the same folder.
"""
import io
import time

from PIL import Image, ImageOps

from cpnp_print import PrintError, print_jpeg, reachable

PRINTER_IP = "192.168.0.1"
CARD_SIZE = (644, 826)  # borderless card, portrait


def prepare(img):
    """Orient, rotate landscape photos to portrait, crop-fill to card size, encode JPEG."""
    if hasattr(ImageOps, "exif_transpose"):
        img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    if img.width > img.height:
        img = img.rotate(90, expand=True)
    img = ImageOps.fit(img, CARD_SIZE, Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=95)
    return out.getvalue()


def get_image():
    import appex
    import photos

    if appex.is_running_extension():
        return appex.get_image()
    asset = photos.pick_asset(title="Photo à imprimer")
    return asset.get_image() if asset else None


def wait_for_printer(timeout=120):
    """Ask the user to switch Wi-Fi, then poll until the printer answers."""
    import console

    if reachable(PRINTER_IP):
        return True
    # Cancel raises KeyboardInterrupt and stops the script.
    console.alert(
        "Imprimante introuvable",
        "Connecte l'iPhone au Wi-Fi de l'imprimante : Centre de contrôle, appui long sur "
        "le Wi-Fi, puis choisis QX20-…. L'impression partira toute seule.",
        "Attendre",
    )
    deadline = time.time() + timeout
    while time.time() < deadline:
        if reachable(PRINTER_IP):
            return True
        print("en attente de l'imprimante…")
        time.sleep(1)
    return False


def main():
    import console

    img = get_image()
    if img is None:
        console.hud_alert("Aucune photo", "error")
        return
    data = prepare(img)
    if not wait_for_printer():
        console.alert("Échec", "Imprimante toujours introuvable.", "OK", hide_cancel_button=True)
        return
    console.hud_alert("Impression…")
    try:
        print_jpeg(PRINTER_IP, data)
    except (PrintError, OSError) as e:
        console.alert("Échec", str(e), "OK", hide_cancel_button=True)
        return
    console.hud_alert("Imprimé")


if __name__ == "__main__":
    main()
