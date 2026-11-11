"""Print photos on the SELPHY QX20 from Pythonista (iOS).

Run it from Pythonista to pick photos, or from the share sheet (Run Pythonista Script).
It shows a numbered preview and asks for confirmation. If the printer is not reachable, it
asks you to switch to the printer's Wi-Fi and prints as soon as it answers.
Keep cpnp_print.py in the same folder.
"""
import importlib
import io
import time

from PIL import Image, ImageDraw, ImageOps

import cpnp_print

importlib.reload(cpnp_print)  # Pythonista keeps modules loaded between runs
from cpnp_print import PrintError, print_jpeg, reachable  # noqa: E402

PRINTER_IP = "192.168.0.1"
CARD_SIZE = (644, 826)  # borderless card, portrait


def prepare(img):
    """Orient, rotate landscape photos to portrait, crop-fill to card size, encode JPEG.

    Returns (jpeg_bytes, rotated).
    """
    if hasattr(ImageOps, "exif_transpose"):
        img = ImageOps.exif_transpose(img)
    img = img.convert("RGB")
    rotated = img.width > img.height
    if rotated:
        img = img.rotate(90, expand=True)
    img = ImageOps.fit(img, CARD_SIZE, Image.LANCZOS)
    out = io.BytesIO()
    img.save(out, "JPEG", quality=95)
    return out.getvalue(), rotated


def contact_sheet(jpegs, per_row=4):
    """Numbered thumbnails of the prepared images, in print order."""
    tw, th, pad = CARD_SIZE[0] // 4, CARD_SIZE[1] // 4, 8
    rows = (len(jpegs) + per_row - 1) // per_row
    cols = min(len(jpegs), per_row)
    sheet = Image.new("RGB", (cols * (tw + pad) + pad, rows * (th + pad) + pad), "white")
    draw = ImageDraw.Draw(sheet)
    for i, data in enumerate(jpegs):
        x, y = pad + (i % per_row) * (tw + pad), pad + (i // per_row) * (th + pad)
        sheet.paste(Image.open(io.BytesIO(data)).resize((tw, th)), (x, y))
        draw.rectangle((x, y, x + 22, y + 16), fill="black")
        draw.text((x + 4, y + 2), str(i + 1), fill="white")
    return sheet


def downscaled(data, max_px=1600):
    """Decode an image file (JPEG, HEIC…) to a small, upright PIL image.

    Uses iOS ImageIO thumbnails, which never hold the full-size bitmap: a 48 MP photo
    decoded by PIL takes ~145 MB, enough to get the share extension killed.
    """
    import ctypes
    from ctypes import c_double, c_size_t, c_void_p

    from objc_util import ObjCClass, ObjCInstance, c, ns

    imageio = ctypes.cdll.LoadLibrary("/System/Library/Frameworks/ImageIO.framework/ImageIO")
    create_source = imageio.CGImageSourceCreateWithData
    create_source.restype, create_source.argtypes = c_void_p, [c_void_p, c_void_p]
    create_thumb = imageio.CGImageSourceCreateThumbnailAtIndex
    create_thumb.restype, create_thumb.argtypes = c_void_p, [c_void_p, c_size_t, c_void_p]
    c.CFRelease.restype, c.CFRelease.argtypes = None, [c_void_p]
    to_jpeg = c.UIImageJPEGRepresentation
    to_jpeg.restype, to_jpeg.argtypes = c_void_p, [c_void_p, c_double]

    options = ns({
        "kCGImageSourceCreateThumbnailFromImageAlways": True,
        "kCGImageSourceCreateThumbnailWithTransform": True,  # apply EXIF orientation
        "kCGImageSourceThumbnailMaxPixelSize": max_px,
    })
    source = create_source(ns(data).ptr, None)
    if not source:
        raise ValueError("unreadable image")
    try:
        cg_image = create_thumb(source, 0, options.ptr)
    finally:
        c.CFRelease(source)
    if not cg_image:
        raise ValueError("could not decode image")
    try:
        ui_image = ObjCClass("UIImage").imageWithCGImage_(c_void_p(cg_image))
    finally:
        c.CFRelease(cg_image)
    jpeg = ObjCInstance(to_jpeg(ui_image.ptr, 0.95))
    return Image.open(io.BytesIO(ctypes.string_at(jpeg.bytes(), jpeg.length())))


def fingerprint(img):
    """16x16 grayscale pixels, enough to recognise the same picture in another format."""
    return list(img.convert("L").resize((16, 16)).getdata())


def same_picture(a, b, tolerance=3):
    """Mean absolute pixel difference below tolerance (out of 255)."""
    return sum(abs(x - y) for x, y in zip(a, b)) / len(a) < tolerance


def load_images():
    """Yield the shared or picked photos one by one, downscaled, to keep memory low."""
    import appex
    import photos

    if appex.is_running_extension():
        # Photos may hand over each photo twice (e.g. HEIC and JPEG): skip near-identical ones.
        seen = []
        for data in appex.get_images_data() or []:
            img = downscaled(data)
            fp = fingerprint(img)
            if any(same_picture(fp, other) for other in seen):
                print("doublon ignoré")
                continue
            seen.append(fp)
            yield img
        return
    for asset in photos.pick_asset(title="Photos à imprimer", multi=True) or []:
        yield downscaled(asset.get_image_data().getvalue())


def wait_for_printer(timeout=120):
    """Poll until the printer answers."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if reachable(PRINTER_IP):
            return True
        print("en attente de l'imprimante…")
        time.sleep(1)
    return False


def confirm(sheet, n, rotated, connected, dry_run):
    """Show the preview with a recap and a confirm button. True if confirmed.

    A ui view rather than console.alert, whose dimmed overlay hid the preview.
    """
    import ui

    what = f"{n} photo{'s' if n > 1 else ''}"
    lines = [f"{what} au format carte sans bordure, dans l'ordre de l'aperçu (1 à {n})."]
    if rotated:
        lines.append(f"{rotated} en paysage, tournée{'s' if rotated > 1 else ''} pour remplir la carte.")
    if dry_run:
        lines.append("Test : rien ne sera imprimé.")
    if not connected:
        lines.append(
            "Imprimante introuvable : connecte l'iPhone à son Wi-Fi (Centre de contrôle, "
            "appui long sur le Wi-Fi, QX20-…). Ça partira tout seul."
        )
    verb = "Tester" if dry_run else "Imprimer"
    confirmed = []

    def on_confirm(sender):
        confirmed.append(True)
        view.close()

    png = io.BytesIO()
    sheet.save(png, "PNG")
    view = ui.View(frame=(0, 0, 540, 680), background_color="white", name=f"{verb} {what} ?")
    view.add_subview(ui.ImageView(
        frame=(10, 10, 520, 440), flex="WH", content_mode=ui.CONTENT_SCALE_ASPECT_FIT,
        image=ui.Image.from_data(png.getvalue()),
    ))
    view.add_subview(ui.Label(
        frame=(16, 460, 508, 150), flex="WT", number_lines=0, text="\n".join(lines),
        text_color="black",
    ))
    view.add_subview(ui.Button(
        frame=(16, 620, 508, 48), flex="WT", corner_radius=10, action=on_confirm,
        title=verb if connected else f"Attendre et {verb.lower()}",
        background_color="#007aff", tint_color="white",
    ))
    view.present("sheet")  # closing it with the title bar's X cancels
    view.wait_modal()
    return bool(confirmed)


def main(dry_run=False):
    import console

    jpegs, rotated = [], 0
    for img in load_images():
        data, r = prepare(img)
        jpegs.append(data)
        rotated += r
        del img
    if not jpegs:
        console.hud_alert("Aucune photo", "error")
        return

    connected = reachable(PRINTER_IP)
    if not confirm(contact_sheet(jpegs), len(jpegs), rotated, connected, dry_run):
        console.hud_alert("Annulé")
        return
    if not connected and not wait_for_printer():
        console.alert("Échec", "Imprimante toujours introuvable.", "OK", hide_cancel_button=True)
        return

    for i, data in enumerate(jpegs, 1):
        console.hud_alert(f"{'Test' if dry_run else 'Impression'} {i}/{len(jpegs)}…")
        try:
            print_jpeg(PRINTER_IP, data, dry_run=dry_run)
        except (PrintError, OSError) as e:
            done = f"{i - 1}/{len(jpegs)} photo(s) {'testée(s)' if dry_run else 'imprimée(s)'}."
            console.alert(f"Échec sur la photo {i}", f"{e}\n\n{done}", "OK", hide_cancel_button=True)
            return
    console.hud_alert(f"Test OK, rien imprimé ({len(jpegs)})" if dry_run else f"{len(jpegs)} imprimée(s)")


if __name__ == "__main__":
    main()
