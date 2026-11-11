# selphy-qx20

> **Barebones proof of concept.** A standard-library Python client plus a Pythonista wrapper,
> tested on one printer (firmware 1.00) with one photo on card paper. No error recovery, no
> square paper. Not affiliated with Canon.

Prints a JPEG on a **Canon SELPHY QX20** over Wi-Fi, without the official SELPHY Photo
Layout app.

## Usage

1. Turn the printer on. It broadcasts its own Wi-Fi network (`QX20-xxx`); its password is
   on the label inside the ink cassette door. Connect the computer to it. The printer is
   `192.168.0.1`.
2. Prepare a JPEG that fits the printer's bounds (see below). For borderless card paper,
   644×826 portrait works:

   ```sh
   uv run --no-project --with pillow python -c '
   import sys
   from PIL import Image, ImageOps
   im = ImageOps.exif_transpose(Image.open(sys.argv[1])).convert("RGB")
   ImageOps.fit(im, (644, 826), Image.LANCZOS).save(sys.argv[2], "JPEG", quality=95)
   ' photo.jpg card.jpg
   ```

3. Print:

   ```sh
   python3 cpnp_print.py 192.168.0.1 card.jpg
   ```

The script prints every status change and stops on any real printer error. If the printer's
LED turns red, power-cycle it. Add `--dry-run` to talk to the printer and check the image
without printing.

### From an iPhone, with Pythonista

`pythonista_print.py` turns photos into card-sized JPEGs (landscape photos are rotated to
fill the portrait card) and prints them.

1. Get the scripts with `update.py`, which downloads them next to itself (and updates
   itself). Create a folder in Pythonista's local storage, then paste this in the console,
   with the iPhone on a network that has internet access:

   ```python
   import requests; open("update.py", "w").write(requests.get("https://raw.githubusercontent.com/Crocmagnon/selphy-qx20/main/update.py").text)
   ```

   This saves `update.py` in the console's current folder; move it into your folder if
   needed, then run it. Run it again to update.

   Keep the scripts in Pythonista's local storage: the share extension only offers local
   scripts (an external folder opened from Working Copy does not show up).
2. Either run `pythonista_print.py` in Pythonista and pick one or more photos, or share
   them from Photos. The script shows a numbered preview of the crops and asks for
   confirmation, then prints the photos one after the other. To share from Photos:
   - once: in a Photos share sheet, *Edit Actions…* and enable *Run Pythonista Script*;
     in Pythonista's settings, *Share Extension Shortcuts*, add `pythonista_print.py`;
   - then: share a photo → *Run Pythonista Script* → tap the shortcut.

   `pythonista_dry_run.py` does the same without printing: it previews the prepared image,
   waits for the printer and checks the printer accepts it. Add it as a second shortcut.
3. If the iPhone is not on the printer's Wi-Fi, the script says so and waits: switch networks
   from Control Center (long-press the Wi-Fi button) so Pythonista stays in the foreground,
   and printing starts as soon as the printer answers.

On first run iOS asks for local network access: allow it.

**Gotcha:** the printer's network is `192.168.0.0/24`, a common home subnet. If the computer
also reaches a `192.168.0.0/24` network through another interface (Ethernet, Tailscale subnet
router…), pin the route: `ip route add 192.168.0.1/32 dev <wifi-iface>`, plus
`ip rule add to 192.168.0.1/32 lookup main priority 100` if Tailscale is involved.

## Protocol notes

The QX20 speaks **CPNP**, the protocol of older SELPHY CP models, documented by
[selphy_go](https://github.com/tbleher/selphy_go). The QX-specific parts below were read from
the official Android app's printing code.

### Framing

Every packet starts with a 16-byte big-endian header:

| Offset | Size | Field |
|---|---|---|
| 0 | 4 | `CPNP` |
| 4 | 2 | command (bit 15 set in responses) |
| 8 | 2 | sequence number, echoed in the response |
| 10 | 2 | job id (from `START_TCP` response), 0 over UDP |
| 12 | 4 | payload length |

Commands: `0x101` discover, `0x110` start TCP, `0x120` status, `0x121` data, `0x130` IEEE 1284
id (`MDL:SELPHY QX20;CMD:Raster3;…`), `0x151` flush.

### Flow

1. UDP port 8609: discover, get id, status, flush, then `START_TCP`. Its response holds the TCP
   port at payload offset 4 (big-endian, 49152 in practice).
2. TCP to that port: poll status (`0x120`) and answer the printer's requests with data
   packets (`0x121`, at most 4096 bytes of payload each).

**Payloads are little-endian from here on.**

### UDP status (payload)

| Offset | Size | Field |
|---|---|---|
| 68 | 4 | error |
| 132 / 134 | 2 / 2 | min JPEG width / height (644 / 768) |
| 136 / 138 | 2 / 2 | max JPEG width / height (848 / 826) |

### TCP status (payload)

| Offset | Size | Field |
|---|---|---|
| 8 | 2 | device status |
| 12 | 4 | error |
| 16 | 4 | data request: `0x10000` start print, `0x20000` print data, `0x30000` end print; a non-zero low byte asks for overcoat data |
| 24 | 4 | requested offset |
| 28 | 4 | requested length |

### Requests

**Start print** (64 bytes): offset 2 code `0`, offset 4 size `64`, offset 12 (u16) image
count `1`, offset 14 (u16) print size (`17` borderless square, `18` borderless card), offset 16
(u8) overcoat (`2` glossy).

**Print data** (104-byte header + JPEG slice): offset 2 code `1`, offset 4 `104 + length`,
offset 12 image count `1`, offset 20 JPEG file size, 24 width, 28 height, 96 slice offset,
100 slice length. The printer asks for the file in slices: first a tiny one, then the whole
file.

**End print** (64 bytes): offset 2 code `3`, offset 4 size `64`.

### Errors seen

Codes whose upper 16 bits are zero are informational.

| Code | Meaning |
|---|---|
| `0x10a` | paper pick wait: the print is done, remove the sheet |
| `0xffff04` | invalid command (for instance the CP900 start-print layout) |
| `0xffff05` | JPEG decode error (for instance an image outside the size bounds) |

## Wi-Fi

The QX20 only offers its own access point. The app can change that network's passphrase,
but has no command to join another network.

Pythonista cannot switch the iPhone to that network by itself: calling
`NEHotspotConfigurationManager.applyConfiguration` through `objc_util` is silently refused
(no system prompt, no network change), presumably because Pythonista lacks the Hotspot
Configuration entitlement.

## License

Public domain (Unlicense), see [LICENSE](LICENSE).
