"""Print a photo on the SELPHY QX20 from Pythonista (iOS).

Run it from Pythonista to pick a photo, or from the share sheet (Run Pythonista Script).
The iPhone must be on the printer's Wi-Fi. Keep cpnp_print.py in the same folder.
"""
import io

from PIL import Image, ImageOps

from cpnp_print import PrintError, print_jpeg

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


def main():
    import console

    img = get_image()
    if img is None:
        console.hud_alert("Aucune photo", "error")
        return
    console.show_activity("Impression…")
    try:
        print_jpeg(PRINTER_IP, prepare(img))
    except (PrintError, OSError) as e:
        console.hide_activity()
        console.alert("Échec", str(e), "OK", hide_cancel_button=True)
        return
    console.hide_activity()
    console.hud_alert("Imprimé")


if __name__ == "__main__":
    main()
