"""Minimal CPNP print client for the Canon SELPHY QX20 (card paper).

Transport from selphy_go's notes; QX command layout from the official Android app.
Usage: python3 cpnp_print.py <printer_ip> <file.jpg> [--dry-run]
"""
import socket, struct, sys, time

PORT = 8609
DISCOVER, STARTTCP, STATUS, DATA, ID, FLUSH = 0x101, 0x110, 0x120, 0x121, 0x130, 0x151


class Printer:
    def __init__(self, ip):
        self.ip = ip
        self.seq = 0
        self.job = 0
        self.udp = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp.settimeout(5)
        self.tcp = None

    def pkt(self, cmd, payload=b""):
        self.seq += 1
        return b"CPNP" + struct.pack(">HHHHHH", cmd, 0, self.seq, self.job, 0, len(payload)) + payload

    def call(self, cmd, payload=b""):
        p = self.pkt(cmd, payload)
        if self.tcp is None:
            self.udp.sendto(p, (self.ip, PORT))
            data, _ = self.udp.recvfrom(8192)
            return data[:16], data[16:]
        self.tcp.sendall(p)
        head = self._recv(16)
        assert head[:4] == b"CPNP", head
        (n,) = struct.unpack(">I", head[12:16])
        return head, self._recv(n)

    def _recv(self, n):
        buf = b""
        while len(buf) < n:
            chunk = self.tcp.recv(n - len(buf))
            if not chunk:
                raise ConnectionError("printer closed connection")
            buf += chunk
        return buf


def utf16(s, size):
    return s.encode("utf-16-be")[:size].ljust(size, b"\0")


def jpeg_size(data):
    i = 2
    while i < len(data):
        marker, seglen = data[i + 1], struct.unpack(">H", data[i + 2:i + 4])[0]
        if marker in (0xC0, 0xC1, 0xC2):
            h, w = struct.unpack(">HH", data[i + 5:i + 9])
            return w, h
        i += 2 + seglen
    raise ValueError("no SOF marker")


class PrintError(Exception):
    pass


def reachable(ip, timeout=1.0):
    """True if a CPNP printer answers a discover request at ip."""
    p = Printer(ip)
    p.udp.settimeout(timeout)
    try:
        p.call(DISCOVER)
        return True
    except OSError:  # timeout, or no route while on another network
        return False
    finally:
        p.udp.close()


def print_jpeg(ip, data, dry_run=False):
    """Print one JPEG (bytes) on borderless card paper. Raises PrintError on failure.

    dry_run talks to the printer and checks the image bounds, but stops before the print job.
    """
    w, h = jpeg_size(data)
    print(f"image: {len(data)} bytes, {w}x{h}")

    p = Printer(ip)
    try:
        p.call(DISCOVER)
    except socket.timeout:
        raise PrintError(f"no answer from {ip}: is this device on the printer's Wi-Fi?")
    _, body = p.call(ID, b"\0" * 4)
    print("ID:", body[2:].decode(errors="replace"))
    deadline = time.time() + 120
    while True:  # wait out informational states, e.g. 0x10a: remove the previous sheet
        _, body = p.call(STATUS)
        (error,) = struct.unpack("<I", body[68:72])
        if error & 0xFFFF0000:
            raise PrintError(f"printer error {error:#x}, power-cycle it")
        if not error:
            break
        if time.time() > deadline:
            raise PrintError(f"printer still busy ({error:#x})")
        print(f"printer busy ({error:#x}), remove the printed sheet if any")
        time.sleep(1)
    print("status:", body[:8].hex(" "))
    min_w, min_h, max_w, max_h = struct.unpack("<4H", body[132:140])
    if not (min_w <= w <= max_w and min_h <= h <= max_h):
        raise PrintError(f"image {w}x{h} outside printer bounds {min_w}-{max_w} x {min_h}-{max_h}")
    if dry_run:
        print("dry run: printer ready, image accepted, not printing")
        return
    _, body = p.call(FLUSH, b"\0" * 4)
    print("flush:", body.hex(" "))

    b = bytearray(0x188)
    b[0x08:0x48] = utf16("cpnp_print", 0x40)
    b[0x48:0x88] = utf16("user", 0x40)
    b[0x88:0x188] = utf16("photo.jpg", 0x100)
    head, body = p.call(STARTTCP, bytes(b))
    p.job = struct.unpack(">H", head[10:12])[0]
    port = struct.unpack(">H", body[4:6])[0]
    print("start_tcp:", body.hex(" "), "-> port", port, "job", p.job)
    if port == 0:
        raise PrintError("printer not ready (port 0), restart it")
    p.tcp = socket.create_connection((ip, port), timeout=30)

    # Layout from the official app (CPNPMakedata / CPNPConnected), all little-endian.
    START_PRINT, PRINT_DATA, END_PRINT = 0x10000, 0x20000, 0x30000
    last = None
    deadline = time.time() + 300
    while time.time() < deadline:
        _, body = p.call(STATUS)
        error, req = struct.unpack("<II", body[12:20])
        if body == last:
            time.sleep(0.2)
            continue
        last = body
        print(f"req={req:#x} err={error:#x}", body[:0x20].hex(" "))
        if error & 0xFFFF0000:  # ERROR_TYPE_MASK; low-only codes (e.g. 0x10a PAPER_PICK_WAIT) are informational
            raise PrintError(f"printer error {error:#x}, power-cycle it")
        if req & 0xFF:
            raise PrintError("printer asks for overcoat data, not supported")
        if req == 0:
            time.sleep(0.5)
        elif req == START_PRINT:
            f = bytearray(0x40)
            struct.pack_into("<I", f, 0x04, len(f))  # command size
            struct.pack_into("<H", f, 0x0C, 1)  # total images
            struct.pack_into("<H", f, 0x0E, 18)  # QX_BORDERLESS_CARD_SIZE (square: 17)
            f[0x10] = 2  # overcoat: glossy
            p.call(DATA, bytes(f))
        elif req == PRINT_DATA:
            off, length = struct.unpack("<II", body[0x18:0x20])
            print(f"  data request: offset={off} length={length}")
            hdr = bytearray(0x68)
            hdr[0x02] = 1
            struct.pack_into("<I", hdr, 0x04, length + len(hdr))
            hdr[0x0C] = 1
            struct.pack_into("<III", hdr, 0x14, len(data), w, h)
            struct.pack_into("<II", hdr, 0x60, off, length)
            chunk = bytes(hdr) + data[off:off + length].ljust(length, b"\0")
            for i in range(0, len(chunk), 4096):
                p.call(DATA, chunk[i:i + 4096])
        elif req == END_PRINT:
            f = bytearray(0x40)
            struct.pack_into("<I", f, 0x04, len(f))
            f[2] = 3  # end print, mode 0 = all jobs done
            p.call(DATA, bytes(f))
            print("job done")
            return
        else:
            raise PrintError(f"unknown data request {req:#x}: {body.hex(' ')}")
    raise PrintError("timeout")


if __name__ == "__main__":
    try:
        print_jpeg(sys.argv[1], open(sys.argv[2], "rb").read(), dry_run="--dry-run" in sys.argv)
    except PrintError as e:
        sys.exit(str(e))
