#!/usr/bin/env python3
"""SWING / Marble Master .RES / .SWG / .SET -> PNG converter (CLI).

Usage:
    python res_to_png.py <path-to-file> [-o OUTPUT_DIR]

Port of the decoder in CONVERTER.html - see README.md for the full format
writeup. No third-party dependencies; PNGs are written by hand via zlib.
"""

import argparse
import re
import struct
import sys
import zlib
from pathlib import Path

SET_SIGNATURE = "Gib mir 'ne Kugel\n"
MAX_FRAMES = 4000
PRINTABLE_ASCII_RE = re.compile(r'^[\x20-\x7e]+$')


def rgb555_to_rgb888(v):
    r = (v >> 10) & 0x1F
    g = (v >> 5) & 0x1F
    b = v & 0x1F
    return (
        (r * 255 + 15) // 31,
        (g * 255 + 15) // 31,
        (b * 255 + 15) // 31,
    )


# Two known codecs. The header's "type" byte is the primary signal, but
# type=7 has been observed using EITHER codec, so it gets a validated trial
# of the paired codec before falling back:
#   type 1, 4, or 6 -> paired RLE (dataLen from the header is trusted directly).
#   type 2      -> simple stream.
#   type 7      -> try paired RLE first (validated), else simple stream.
#   any other type (e.g. 3) -> simple stream (fallback).
# ESCAPE TOKEN: most files use 0x0003, but some (e.g. COLOR.RES) use 0x0000
# instead. Some images (e.g. KRANNORM.RES, BLOCK.RES) contain literal
# RGB555-black pixels (word value 0) as real image data, so the two escape
# values must never both be treated as escape at once - each frame is
# decoded with a single candidate escape value at a time, trying 0x0003
# first and validating the result; only if that fails do we retry with
# 0x0000.
def decode_paired_rle(data, byte_offset, w, h, data_len, escape_token, strict_validate):
    data_start = byte_offset + 16 + 4
    if data_start + data_len * 2 > len(data):
        return None
    words = struct.unpack_from('<%dH' % data_len, data, data_start) if data_len else ()

    total_px = w * h
    pixels = bytearray(total_px * 4)
    idx = 0
    rows_completed = 0
    implausible = False  # a single skip run can never exceed the whole image
    for row in range(h):
        col = 0
        while col < w and idx < data_len:
            token = words[idx]
            idx += 1
            if token == escape_token:
                if idx >= data_len:
                    break
                cnt = words[idx]
                idx += 1
                if cnt > total_px:
                    implausible = True
                col += cnt
            else:
                r, g, b = rgb555_to_rgb888(token)
                if col < w:
                    p = (row * w + col) * 4
                    pixels[p] = r
                    pixels[p + 1] = g
                    pixels[p + 2] = b
                    pixels[p + 3] = 255
                col += 1
        if col >= w:
            rows_completed += 1

    # Valid if the whole word budget was used, every row filled exactly to
    # width (except possibly the very last row - trailing transparency can
    # be implicit, simply omitted rather than encoded), AND no skip run
    # claimed to cover more pixels than the entire image (a sure sign the
    # wrong escape token was tried).
    valid = idx == data_len and rows_completed >= h - 1 and not implausible
    if strict_validate and not valid:
        return None
    return {'pixels': bytes(pixels), 'next_offset': data_start + data_len * 2, 'valid': valid}


def decode_simple_stream(data, byte_offset, w, h, escape_token):
    total_px = w * h
    pixels = bytearray(total_px * 4)
    pos = byte_offset + 16 + 4
    n = len(data)
    filled = 0
    while filled < total_px and pos < n - 1:
        token = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        if token == escape_token:
            filled += 1
        else:
            row, col = divmod(filled, w)
            if row < h:
                r, g, b = rgb555_to_rgb888(token)
                p = (row * w + col) * 4
                pixels[p] = r
                pixels[p + 1] = g
                pixels[p + 2] = b
                pixels[p + 3] = 255
            filled += 1
    if filled < total_px:
        return None  # wrong escape token or ran out of data
    return {'pixels': bytes(pixels), 'next_offset': pos}


# Tries escape=0x0003 first (validated), falls back to escape=0x0000.
def try_paired_with_escape_fallback(data, byte_offset, w, h, data_len, strict_validate):
    for esc in (3, 0):
        res = decode_paired_rle(data, byte_offset, w, h, data_len, esc, True)
        if res:
            return res
    if not strict_validate:
        # Last resort: trust dataLen unconditionally with escape=3, even if
        # row-completeness didn't validate (should rarely be needed).
        return decode_paired_rle(data, byte_offset, w, h, data_len, 3, False)
    return None


def try_simple_with_escape_fallback(data, byte_offset, w, h):
    for esc in (3, 0):
        res = decode_simple_stream(data, byte_offset, w, h, esc)
        if res:
            return res
    return None


def decode_frame(data, byte_offset):
    if byte_offset + 16 > len(data):
        return None
    magic = struct.unpack_from('<H', data, byte_offset)[0]
    type_ = data[byte_offset + 2]
    const0f = data[byte_offset + 3]
    w = struct.unpack_from('<H', data, byte_offset + 4)[0]
    h = struct.unpack_from('<H', data, byte_offset + 6)[0]
    data_len = struct.unpack_from('<I', data, byte_offset + 8)[0]
    extra = struct.unpack_from('<I', data, byte_offset + 12)[0]

    if magic != 0x14 or const0f != 0x0F:
        return None
    if w == 0 or h == 0 or w > 4096 or h > 4096:
        return None

    result = None
    if type_ in (1, 4, 6):
        result = try_paired_with_escape_fallback(data, byte_offset, w, h, data_len, False)
    elif type_ == 7:
        result = try_paired_with_escape_fallback(data, byte_offset, w, h, data_len, True)
        if not result:
            result = try_simple_with_escape_fallback(data, byte_offset, w, h)
    else:
        # type 2, type 3, and any other/unknown type.
        result = try_simple_with_escape_fallback(data, byte_offset, w, h)

    if not result:
        return None
    return {
        'pixels': result['pixels'],
        'w': w,
        'h': h,
        'type': type_,
        'data_len': data_len,
        'extra': extra,
        'next_offset': result['next_offset'],
    }


# Decodes a .SWG file: a raw, headerless, uncompressed full-screen bitmap.
# Every sample seen so far is exactly 640x480 RGB555 (614400 bytes). No
# escape tokens, no RLE: every word is a literal pixel, read left-to-right,
# top-to-bottom.
def decode_swg(data):
    w, h = 640, 480
    if len(data) != w * h * 2:
        return None
    pixels = bytearray(w * h * 4)
    pos = 0
    for i in range(w * h):
        token = struct.unpack_from('<H', data, pos)[0]
        pos += 2
        r, g, b = rgb555_to_rgb888(token)
        p = i * 4
        pixels[p] = r
        pixels[p + 1] = g
        pixels[p + 2] = b
        pixels[p + 3] = 255
    return {'pixels': bytes(pixels), 'w': w, 'h': h}


# Detects the marble-skin "set" format used by files like NORMAL.SET: a
# fixed 48-byte header, then an ordinary multi-frame .RES image block (the
# marbles themselves), optionally followed by trailing bytes of a still
# unidentified structure (ignored here - it isn't image data).
# Header layout (48 bytes):
#   0x00  19 B   ASCII signature "Gib mir 'ne Kugel\n" + trailing NUL
#   0x14  12 B   set name, NUL-padded ASCII (e.g. "standard")
#   0x20   4 B   unknown (seen as 0)
#   0x24   4 B   unknown (seen as a non-zero value - possibly a checksum)
#   0x28   4 B   unknown (seen as 0)
#   0x2C   4 B   size in bytes of the image block that follows
def parse_set_header(data):
    if len(data) < 48:
        return None
    sig_len = len(SET_SIGNATURE)
    try:
        sig = data[:sig_len].decode('ascii')
    except UnicodeDecodeError:
        return None
    if sig != SET_SIGNATURE:
        return None
    name_bytes = data[20:32]
    nul = name_bytes.find(0)
    name = (name_bytes[:nul] if nul >= 0 else name_bytes).decode('ascii', errors='replace')
    return {'name': name, 'data_start': 48}


# Detects and parses the "package" container format used by files like
# EXTRAS.RES and HELPMODE.RES: these are NOT single sprites but archives
# bundling multiple named sub-resources (commonly with extensions like
# .3LB or .6SP, which are themselves ordinary multi-frame .RES images).
# Layout: u32 entry count, then that many 20-byte records (12-byte
# null-padded ASCII name + u32 size + u32 offset - offset is absolute from
# the start of the file), followed immediately by the concatenated raw
# bytes of every entry, back to back, in table order.
def parse_archive(data):
    if len(data) < 4:
        return None
    count = struct.unpack_from('<I', data, 0)[0]
    if count == 0 or count > 5000:
        return None
    header_end = 4 + count * 20
    if header_end > len(data):
        return None

    entries = []
    pos = 4
    for _ in range(count):
        name_bytes = data[pos:pos + 12]
        nul = name_bytes.find(0)
        raw_name = name_bytes[:nul] if nul >= 0 else name_bytes
        try:
            name = raw_name.decode('ascii')
        except UnicodeDecodeError:
            return None
        size = struct.unpack_from('<I', data, pos + 12)[0]
        offset = struct.unpack_from('<I', data, pos + 16)[0]
        if not PRINTABLE_ASCII_RE.match(name):
            return None  # not printable ASCII - not this format
        entries.append({'name': name, 'size': size, 'offset': offset})
        pos += 20

    # Validate: offsets must be strictly sequential starting right after the
    # header table, and the last entry must end exactly at file size.
    expected = header_end
    for e in entries:
        if e['offset'] != expected:
            return None
        expected += e['size']
    if expected != len(data):
        return None
    return entries


# Minimal hand-rolled PNG writer (no third-party dependencies): a single
# IDAT chunk holding one "no filter" scanline per row, zlib-compressed.
def write_png(path, width, height, rgba_pixels):
    def chunk(tag, payload):
        return (
            struct.pack('>I', len(payload))
            + tag
            + payload
            + struct.pack('>I', zlib.crc32(tag + payload) & 0xFFFFFFFF)
        )

    stride = width * 4
    raw = bytearray()
    for y in range(height):
        raw.append(0)  # filter type 0 (None)
        raw.extend(rgba_pixels[y * stride:(y + 1) * stride])

    ihdr = struct.pack('>IIBBBBB', width, height, 8, 6, 0, 0, 0)
    idat = zlib.compress(bytes(raw), 9)

    with open(path, 'wb') as f:
        f.write(b'\x89PNG\r\n\x1a\n')
        f.write(chunk(b'IHDR', ihdr))
        f.write(chunk(b'IDAT', idat))
        f.write(chunk(b'IEND', b''))


def convert(path_str, out_dir_str=None):
    src = Path(path_str)
    data = src.read_bytes()
    base_name = src.stem
    out_dir = Path(out_dir_str) if out_dir_str else src.parent / f"{base_name}_frames"

    saved = []

    def save(name, w, h, pixels):
        out_dir.mkdir(parents=True, exist_ok=True)
        out_path = out_dir / name
        write_png(out_path, w, h, pixels)
        saved.append(out_path)
        return out_path

    if src.suffix.lower() == '.swg':
        res = decode_swg(data)
        if not res:
            print(
                f"Error: the .SWG file has an unexpected size ({len(data)} B). "
                "Known .SWG files are raw 640x480 RGB555 bitmaps (614400 B) with "
                "no header - this file may have a different resolution.",
                file=sys.stderr,
            )
            return 1
        save(f"{base_name}_frame000.png", res['w'], res['h'], res['pixels'])
        print("Decoded a raw 640x480 screen (.SWG, no header or compression).")
        print(f"Saved 1 PNG file to {out_dir}")
        return 0

    set_header = parse_set_header(data)
    offset = set_header['data_start'] if set_header else 0
    frames = []
    while offset < len(data) - 16 and len(frames) < MAX_FRAMES:
        res = decode_frame(data, offset)
        if not res:
            break
        frames.append(res)
        offset = res['next_offset']
    count = len(frames)

    if count > 0 and set_header:
        for i, fr in enumerate(frames):
            save(f"{base_name}_frame{i:03d}.png", fr['w'], fr['h'], fr['pixels'])
        leftover = len(data) - offset
        msg = f'Marble set "{set_header["name"]}": {count} marbles decoded.'
        if leftover > 16:
            msg += (
                f" ({leftover} B at the end of the file is a different, "
                "still-unrecognized structure - skipped.)"
            )
        print(msg)
        print(f"Saved {len(saved)} PNG file(s) to {out_dir}")
        return 0

    if count == 0:
        entries = parse_archive(data)
        if entries:
            image_entry_count = 0
            other_entry_count = 0
            for entry in entries:
                entry_offset = entry['offset']
                entry_end = entry['offset'] + entry['size']
                entry_base = Path(entry['name']).stem
                entry_frame_count = 0
                while entry_offset < entry_end - 16:
                    res = decode_frame(data, entry_offset)
                    if not res:
                        break
                    save(f"{entry_base}_frame{entry_frame_count:03d}.png", res['w'], res['h'], res['pixels'])
                    entry_offset = res['next_offset']
                    entry_frame_count += 1
                if entry_frame_count > 0:
                    image_entry_count += 1
                else:
                    other_entry_count += 1

            msg = (
                f"Archive: {len(entries)} files inside, {image_entry_count} are "
                f"images ({len(saved)} frames total)"
            )
            msg += (
                f", {other_entry_count} are data of another type (not images, skipped)."
                if other_entry_count > 0
                else "."
            )
            print(msg)
            print(f"Saved {len(saved)} PNG file(s) to {out_dir}")
            return 0

        print(
            "Error: could not recognize the header (magic 0x14 / const 0x0F) or "
            "the archive format. This file may be of a type not supported yet.",
            file=sys.stderr,
        )
        return 1

    for i, fr in enumerate(frames):
        save(f"{base_name}_frame{i:03d}.png", fr['w'], fr['h'], fr['pixels'])
    leftover = len(data) - offset
    msg = f"Decoded {count} frames. "
    if leftover > 16:
        msg += f"Note: {leftover} unrecognized bytes remain at the end of the file."
    else:
        msg += f"Entire file consumed ({leftover} bytes of padding/end remaining)."
    print(msg)
    print(f"Saved {len(saved)} PNG file(s) to {out_dir}")
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="Convert a SWING/Marble Master .RES/.SWG/.SET file to PNG frames."
    )
    parser.add_argument('path', help="Path to the .RES, .SWG, or .SET file to convert")
    parser.add_argument(
        '-o', '--output',
        help="Output directory for the PNG frames (default: <input>_frames next to the input file)",
    )
    args = parser.parse_args()
    sys.exit(convert(args.path, args.output))


if __name__ == '__main__':
    main()
