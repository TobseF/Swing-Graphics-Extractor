# `.RES` Format — Swing / Marble Master (Software 2000, 1997, MS-DOS)

Technical documentation of the game's graphics format, reconstructed by reverse engineering.
**This document is updated continuously as new information is discovered.**

Last update: analysis of the files `CD.RES`, `FUNKEN1.RES`, `FUNKEN2.RES`, `FONTS.RES`,
`CORAIN.RES`, `PAUSE.RES`, `BUTTON.RES`, `KRANNORM.RES`, `COLOR.RES`, `BLOCK.RES`,
`BLOCKR.RES`, `BLOCKL.RES`, `GAMMA.RES`, `GAMMA.SWG`, `KEXPLO.RES`, `SMLMENU.RES`,
`SMRM1.RES`, `SMRM2.RES`, `EXTRAS.RES`, `HELPMODE.RES`, `NORMAL.SET`, `MAKE.SET`,
`SHOWSET.EXE`, `SWING.EXE`.

---

## 1. Overall status

| Element | Status |
|---|---|
| Single-image header (16 B) | ✅ Worked out |
| Padding after the header (4 B) | ✅ Confirmed (all known codec variants) |
| Pixel color format | ✅ RGB555 |
| Codec `type=4`/`type=1`/`type=6` (paired RLE) | ✅ Worked out, visually confirmed (CD.RES, PAUSE.RES, KRANNORM.RES, BLOCK.RES, SMLMENU.RES, SMRM1.RES, SMRM2.RES) |
| Codec `type=2`/`type=7`/`type=3` (simple stream) | ✅ Worked out, visually confirmed (BUTTON.RES, FUNKEN2.RES, GAMMA.RES) |
| Escape token | ✅ `0x0003` (most common) or `0x0000` (rarer, e.g. COLOR.RES) — **chosen per frame by trial + validation, NEVER both at once** (see §4.3 and §4.5, important corrections!) |
| Codec selection based on `type` | ⚠️ `type=7` observed in BOTH codecs (COLOR.RES = paired, FUNKEN2/CORAIN/GAMMA = simple) — requires trial + validation, not a simple mapping (see §4.4) |
| Frame-boundary detection in a multi-frame container | ✅ Works reliably on all 11 examined files (0 B leftover) |
| Meaning of the `type` field (beyond codec selection) | ❓ Unknown — confirmed so far: `{1,4,6}` → paired RLE always, `{2}` → simple always, `{7}` → both variants, `{3}` → simple (GAMMA.RES) |
| Meaning of the `extra` field (last 4 B of the header) | ❓ Unknown — it is NOT the escape token (hypothesis disproved, see §4.3) |
| Meaning of the 4-byte padding | ❓ Unknown (always skipped, value usually 0, but not always) |
| `FONTS.RES` | ❌ Does not match the header model OR the archive format — the only unresolved file (see §6.2) |
| `CORAIN.RES` | ✅ **Solved!** The result is a clean flash/explosion animation (see §4.3) |
| `.SWG` format (separate from `.RES`) | ✅ Worked out — raw full-screen bitmap, see §9 |
| Archive format (`EXTRAS.RES`, `HELPMODE.RES`) | ✅ 100% worked out — package files with named sub-files, see §10 |
| `.SET` format (marble skin sets) | ✅ Worked out — 48 B header + `.RES` image block, see §11 |

---

## 2. Header structure (16 bytes)

Little-endian, at the start of every image/frame:

```
offset  size     field         description
0x00    u16      magic         always 0x0014
0x02    u8       type          data codec selector for pixels (see §4)
0x03    u8       const_0f      always 0x0F
0x04    u16      width         image width in pixels
0x06    u16      height        image height in pixels
0x08    u32      dataLen       meaning depends on the codec (see §4)
0x0C    u32      extra         unknown — observed values: 0, 3
```

After the 16-byte header come **4 bytes of padding** (zero in most observations),
and only after that the actual pixel data stream.

Python struct for parsing the header:
```python
magic, typ, const_0f, w, h, datalen, extra = struct.unpack_from('<HBBHHII', data, offset)
```

---

## 3. Pixel color format — RGB555

Each "literal" pixel is a 16-bit word (little-endian):

```
bit:  15 14 13 12 11 10 09 08 07 06 05 04 03 02 01 00
      x  R  R  R  R  R  G  G  G  G  G  B  B  B  B  B
```

- highest bit (15): unused / not identified
- R: bits 10–14 (5 bits)
- G: bits 5–9 (5 bits)
- B: bits 0–4 (5 bits)

Conversion to 8-bit/channel: `value_8bit = value_5bit * 255 / 31`.

**Important:** RGB565, BGR565, and BGR555 were also tested — only RGB555 gave
realistic, readable images (visually confirmed on `PAUSE.RES`, which clearly shows
a red parachute and a readable "Pause" caption).

---

## 4. Two known pixel-data codecs

The codec choice depends on the `type` field in the header. Confirmed mappings so far:

| `type` | Source file(s) | Codec |
|---|---|---|
| 1 | `KRANNORM.RES` | Paired RLE (described in §4.1) |
| 4 | `CD.RES`, `PAUSE.RES` | Paired RLE (described in §4.1) |
| 2 | `BUTTON.RES` | Simple stream (described in §4.2) |
| 7 | `FUNKEN1.RES` (tentatively), `FUNKEN2.RES` | Simple stream (described in §4.2) |

**Working hypothesis:** `type` values don't map 1:1 to a codec, nor by even/odd —
so far it has been observed that `{1, 4}` use paired RLE, and `{2, 7}` use the
simple stream. This is a **list of known mappings**, not a general rule — it's
unknown how other, still-untested `type` values would behave. The converter
currently treats `type∈{1,4}` as paired RLE, and any other value as the simple
codec (the default fallback).

### 4.1 Codec `type=4` — paired RLE

The data is a sequence of 16-bit words, with a total length of **exactly `dataLen`
words**. Decoding happens **row by row** (an escape+count run never crosses the
`width` boundary, but a single pixel/run can end exactly at the row boundary):

- token `0x0003` = **escape**: the next word is `count` — the number of
  consecutive **transparent** pixels to skip
- any other token = **one literal pixel** in RGB555 format

**Update:** the escape token can also be `0x0000`, not only `0x0003` — see §4.3.

Pseudocode:
```python
idx = 0
for row in range(height):
    col = 0
    while col < width and idx < dataLen:
        token = words[idx]; idx += 1
        if token == 3:
            cnt = words[idx]; idx += 1
            col += cnt   # transparent, skip
        else:
            pixel[col, row] = rgb555_to_rgb888(token)
            col += 1
```

**Validation:** for `CD.RES` and `PAUSE.RES` the number of words consumed matches
`dataLen` exactly, and for `PAUSE.RES` (a container of 64 concatenated frames) the
sum of all records consumes the file **down to the last byte** (815278/815278 B).
Likewise confirmed for `KRANNORM.RES` (`type=1`, a container of **190 frames**, a
crane/hook animation with a blinking light) — file consumed 100% (1420786/1420786 B),
zero leftover bytes.

### 4.2 Codec `type=2` / `type=7` — simple stream, 1 token = 1 pixel

The data is a sequence of 16-bit words, read **continuously** (without row
alignment — a single pixel/run can "cross" the end of a row into the next one)
until `width * height` pixels are filled:

- token `0x0003` = **one transparent pixel** (with no counter following it!)
- any other token = **one literal pixel** in RGB555

**Update:** the escape token can also be `0x0000` — see §4.3.

Pseudocode:
```python
filled = 0
idx = 0
while filled < width*height:
    token = words[idx]; idx += 1
    if token == 3:
        filled += 1   # transparent pixel
    else:
        row, col = divmod(filled, width)
        pixel[col, row] = rgb555_to_rgb888(token)
        filled += 1
```

**Important difference from `type=4`:** here there is NO counter after the escape —
this was the original cause of the corruption seen when trying to decode
`BUTTON.RES` with the `type=4` algorithm (the counter from the next word was
incorrectly "eaten" as a number of pixels to skip, shifting the rest of the stream).

**Validation:** for `BUTTON.RES` the number of words consumed equals `width*height`
exactly (and matches the `dataLen` field, which for this codec appears to be
**equal to `width*height`** — i.e. redundant, not the actual stream length). For
`FUNKEN2.RES` (`8×8`) the count also matches, although the file contains extra
data after this frame (see §6, uncertainty about the rest of the content).

**Note:** for the `type=2`/`7` codec, the `dataLen` field is NOT a reliable
indicator of the stream's end — the end is determined by filling `width*height`
pixels, not by the `dataLen` value. This distinguishes it from `type=4`, where
`dataLen` is authoritative.

### 4.3 Escape token: `0x0003` or `0x0000` — CHOSEN PER FRAME, NEVER BOTH AT ONCE

**The history of this section matters, because the first fix turned out to be wrong.**

While analyzing `COLOR.RES` (30×30 colored marbles, a 46-frame container), it was
discovered that this file encodes transparency with the token **`0x0000`**, not
`0x0003` like every previously examined file.

**First (incorrect) fix attempt:** make both codecs treat **both** `0x0000` and
`0x0003` as the escape token simultaneously. This fixed `COLOR.RES`, `BUTTON.RES`
(revealing 7 frames instead of 2), and `FUNKEN2.RES` (10 frames instead of 1) — but
**caused a regression**: `KRANNORM.RES` (previously perfect) started "breaking" on
some frames, and `BLOCK.RES`/`BLOCKR.RES` got holes/shifts.

**Cause:** some images (e.g. `KRANNORM.RES`, `BLOCK.RES`) legitimately contain a
**literal pixel with word value `0`** (pure black in RGB555). Diagnostics on
`KRANNORM.RES` showed an exact 1:1 correlation: the frames that "broke" (ranges
0–36 and 88–189) were exactly those containing the token `0` in the data stream as
a genuine pixel; frames without that token (37–87) came out correctly by pure
coincidence. Treating `0` as an escape unconditionally "ate" those legitimate
black pixels together with the (nonexistent) counter after them, throwing off the
rest of the image.

**Correct solution:** for each frame separately, try **one** token at a time,
starting with `0x0003`, and validate the result:
- for the paired-RLE codec: valid = the entire word budget (`dataLen`) was
  consumed AND every row (except possibly the last — trailing transparent rows
  can simply be absent from the data, without explicit encoding) was filled
  exactly to `width`
- for the simple codec: valid = exactly `width*height` pixels were filled
  without running out of data prematurely

If the `0x0003` attempt fails validation, only then is `0x0000` tried for THAT
SAME frame. As a result:
- `KRANNORM.RES` — back to 190/190 frames flawlessly (escape=3 validates
  correctly for every frame, `0x0000` is never even tried)
- `BLOCK.RES` (2 frames), `BLOCKR.RES` (8 frames), `BLOCKL.RES` (8 frames) — all
  without holes/shifts
- `COLOR.RES`, `BUTTON.RES` (7 frames), `FUNKEN2.RES` (10 frames) — still correct,
  because the `0x0003` attempt doesn't validate for their `escape=0` frames, so
  the decoder correctly falls through to `0x0000`
- **`CORAIN.RES` — unexpectedly fixed as well!** The previously "noisy" result
  (diagonal stripes) turned out to be an artifact of the wrong escape token. The
  correct result is a clean, 33-frame animation of a bright flash/explosion
  gradually breaking apart into individual particles — previously marked as an
  open, unresolved issue (§6.3 in earlier versions of this document), now closed

**Rejected intermediate hypothesis:** it was also tested whether `escape = the
value of the header's extra field`. This gave the correct result for `COLOR.RES`
(extra=0, escape=0) purely by coincidence, but **broke `FUNKEN2.RES`** (extra=0,
but the real escape for that frame is 3) — hypothesis disproved and dropped.

### 4.5 Escape-token trial validation must reject implausible counters

On small images (e.g. `KEXPLO.RES`, 14×15 px), it sometimes happens that **both**
attempts (`escape=3` and `escape=0`) formally pass the §4.3 validation (the whole
`dataLen` consumed, rows filled to width) — but only one of them produces a
sensible image. This was discovered on the first frame of the `KEXPLO.RES`
explosion animation: with `escape=3` the image came out as noise (a checkerboard
of diagonal stripes), even though validation formally "passed".

**Cause:** with the wrong escape token, the algorithm sometimes "lands" on a word
count matching the row width by pure coincidence — especially on small images,
where the space of possibilities is limited. Checking the actual skip counters
(`count` following the escape token) revealed an implausible value of **5251**
(for an image of only 210 pixels!) under `escape=3`, while `escape=0` gave only
sensible counters (1–14).

**Additional validation rule:** the skip counter (`count`) cannot exceed the
**total pixel count of the image** (`width*height`) — a single run of
transparency physically cannot be longer than the entire image. If such an
implausible counter appears, the attempt is rejected and the decoder moves on to
the next candidate (`escape=0`, then possibly the simple codec). This fixed frame
0 of `KEXPLO.RES` (a 29-frame explosion animation: bright cloud → smoke → glowing
remnants) with no regression on the other 10 known files.

### 4.4 The `type` field does not uniquely determine the codec

`type=7` has been observed in **both** codecs:
- `FUNKEN2.RES`, `CORAIN.RES` → simple codec
- `COLOR.RES` → paired RLE codec

Additionally, a **new value `type=3`** was discovered (`GAMMA.RES`, 225×60, 10
frames — menu buttons with German captions like "Optionen") — handled correctly
by the default fallback (simple codec), the same as `type=2`.

This means `type` alone is not enough to choose the codec for the value `7` —
trial with validation is needed. The solution implemented (in the converter):

1. `type ∈ {1, 4, 6}` → always the paired RLE codec, the header's `dataLen` is
   trusted directly (verified as reliable — works for all known files, including
   multi-frame containers).
2. `type = 2` → always the simple codec.
3. `type = 7` → first **try** the paired RLE codec with validation (see §4.3 for
   the exact validation criteria). If validation fails, the simple codec is used.
4. Any other/unknown `type` value (including the confirmed `3`) → the simple
   codec by default.

In EACH of the cases above, the escape token is additionally chosen per frame by
the trial+validation method described in §4.3 (first `0x0003`, then `0x0000`).

**Important side observation:** in `PAUSE.RES` (paired RLE codec, `type=4`) the
last row of some frames is sometimes incomplete — the data simply ends before the
row reaches full width. This suggests that **trailing transparent pixels/rows
don't need to be explicitly encoded** — the absence of further data means default
transparency to the end of the frame. For this reason, the validation in point 3
allows incompleteness only for the **last** row, not for any other.

---

## 5. Multi-frame containers

A single `.RES` file can contain multiple images concatenated sequentially, each
with its own full header (16 B) + padding (4 B) + data. After decoding one frame,
the next one starts exactly where the previous one's data ended.

Confirmed examples:
- `PAUSE.RES` → **64 frames** (character spinning on a parachute animation), file
  consumed 100% (0 leftover bytes)
- `KRANNORM.RES` → **190 frames** (crane/hook animation with a blinking warning
  light), file consumed 100% (0 leftover bytes), `type=1`
- `COLOR.RES` → **46 frames** (colored marbles/gems, each a different hue), file
  consumed 100% (0 leftover bytes), `type=7`, escape=`0x0000`
- `BUTTON.RES` → **7 frames** (a full set of UI button states: on/off, forward/back
  navigation arrows), file consumed 100%, `type=2`
- `FUNKEN2.RES` → **10 frames** (dissipating spark animation), file consumed 100%,
  `type=7`, simple codec
- `CORAIN.RES` → **33 frames** (flash/explosion animation breaking apart into
  particles), file consumed 100%, `type=7`, simple codec
- `BLOCK.RES` → **2 frames**, `type=4`
- `BLOCKR.RES` / `BLOCKL.RES` → **8 frames each** (orange triangular directional
  indicator pointing right/left, different pulsing phases), `type=4`
- `GAMMA.RES` → **10 frames** (menu buttons with German captions, e.g.
  "Optionen"), file consumed 100%, `type=3` (new value, simple codec)
- `KEXPLO.RES` → **29 frames** (explosion animation: bright cloud → smoke →
  glowing remnants), file consumed 100%, `type=7`
- `SMLMENU.RES` → **7 frames** (main menu "SINGLE PLAYER / MULTI PLAYER / INFO /
  HIGHSCORE / OPTIONS / SWING OUT" + highlight variants for each entry), file
  consumed 100%, `type=6` (new value, paired RLE codec)
- `SMRM1.RES` → **12 frames** (game mode menu: "Sudden Death", "New", "Load",
  difficulty levels Easy/Normal/Hard/Expert/Custom + highlights), file consumed
  100%, `type=6`
- `SMRM2.RES` → **6 frames** (menu "Competition / Arcade / Splitscreen / New /
  Network / Join" + highlights), file consumed 100%, `type=6`

---

## 6. Open problems and uncertainties

### 6.1 False frame-boundary detection — ✅ resolved
It was previously thought that `BUTTON.RES` had only 2 real frames, and that the
rest of the file was noise from randomly matching the header pattern. After the
escape-token fix (§4.3) it turned out these were **real, valid frames**, simply
decoded incorrectly. All 11 examined `.RES` files are now consumed 100% (0
leftover bytes) with the current decoder.

### 6.2 `FONTS.RES` does not match the header model — the ONLY unresolved issue
Parsing with the standard 16 B header gave nonsensical values (`w=3, h=57349`) —
the file has a **different top-level structure**.

**State of investigation (hypotheses tried and rejected):**
- It is not the archive format described in §10 — the first 4 bytes as an "entry
  count" (=3) don't lead to sensible 12-byte ASCII names at the expected location.
- The whole file (64047 B) was searched for embedded standard image headers
  (`magic=0x0014`, `const_0f=0x0F`) — **zero hits**. So the glyphs are not stored
  as standard `.RES` images.
- Bytes 16–136 (121 B) are all zero, the first non-zero byte only appears at
  offset 137 — suggesting some kind of table (character widths? glyph offsets?),
  but no simple record size (1, 2, or 4 bytes per entry) gives a sensible split
  matching the standard ASCII range (printable characters start at code 32).
- Rendering the raw bytes as a bitmap was tried (RGB555 and 8-bit grayscale) at
  various widths (8–256 px) — no variant revealed readable letter shapes.
- The "3 color copies of the same font" hypothesis was tested (splitting the data
  into 3 equal parts) — disproved; the middle part contains a repeating filler
  pattern (`0x0300` over and over), not pixel data.

**To investigate in the future:** analyzing `SWING.EXE` for text-rendering code
might reveal the exact layout of this format (e.g. by finding a
`DrawText`/`DrawChar` function and tracing how it indexes data from `FONTS.RES`).

### 6.3 `CORAIN.RES` — ✅ resolved
It previously decoded "without error", but the rendered image looked like noisy
diagonal stripes. The cause was the wrong escape token (see §4.3) — after the fix
(trying `0x0003`→`0x0000` per frame with validation, instead of accepting both at
once) the file decodes cleanly as a **33-frame animation** of a flash/explosion
breaking apart into individual particles, consuming the file 100%.

### 6.4 Meaning of the `extra` field and the exact meaning of the 4 B padding
Unknown. The hypothesis that `extra` = escape token was tested and **disproved**
(it worked by coincidence for `COLOR.RES`, but broke `FUNKEN2.RES` — see §4.3).
Observed `extra` values: `0` (FUNKEN2, CORAIN) and `3` (CD, PAUSE, BUTTON,
KRANNORM). Padding is always skipped — it hasn't been systematically checked
whether it is always zero across all 66 files.

### 6.5 The file `SWING.EXE` has not been analyzed yet
It may contain additional clues (e.g. resource offset tables, explicit format
constants, a possible palette) — still to be investigated.

---

## 7. Conversion tool

A standalone HTML/JS application (`RES_to_PNG_Converter.html`) was built,
implementing both confirmed codecs (§4.1, §4.2), automatically selected based on
the `type` field. It runs entirely locally in the browser (no files are uploaded
to a server), supports multi-frame containers, single PNG export, and bulk ZIP
export of all frames.

---

## 8. Findings log (chronological)

1. **CD.RES** (32×32, `type=4`) — the first file cracked. The header structure and
   paired RLE codec were established, along with (incorrectly at first) the
   RGB565 color format → corrected to **RGB555** after testing on `PAUSE.RES`.
2. **PAUSE.RES** (64 frames, `type=4`) — confirmed that files can be containers of
   multiple concatenated images; 100% match between file size and the sum of frames.
3. **BUTTON.RES** (`type=2`) — discovered the **second codec** (simple stream with
   no counter after the escape); the previous algorithm (from `type=4`) caused
   visible image corruption by incorrectly "eating" subsequent pixels as counters.
4. **FUNKEN2.RES** (`type=7`) — confirmed that the same simple codec also fits
   `type=7` (a small 8×8 "spark" sprite, read correctly).
5. **CORAIN.RES** (`type=7`) — the codec formally "works" (consumes exactly the
   right number of words), but the visual result raises doubts — an open issue.
6. **FONTS.RES** — doesn't match the header model at all — an open issue.
7. **KRANNORM.RES** (`type=1`, 190 frames) — discovered a **third `type` value
   mapping to an already-known codec** (paired RLE, same as `type=4`), not a new,
   separate codec. The earlier version of the converter (treating "anything other
   than `type=4`" as the simple codec) incorrectly applied the simple codec to
   this file, producing a distorted image — fixed by adding `type=1` to the
   paired-RLE group. The crane/hook animation with a blinking light decoded
   flawlessly, file consumed 100%.
8. **COLOR.RES** (`type=7`, 46 frames, colored marbles/gems) — discovered that the
   escape token isn't always `0x0003` — this file uses `0x0000`. Several
   hypotheses were checked (including that escape = the header's `extra` field —
   turned out to be false, disproved on `FUNKEN2.RES`). The fix from that session
   (accepting **both** tokens at once) turned out to be incorrect — see point 9.
9. **Regression and escape-token fix** — it was reported that `KRANNORM.RES`
   (previously perfect) started "breaking" on parts of frames (ranges 0–36 and
   88–189 out of 190), and `BLOCK.RES`/`BLOCKR.RES` got holes/shifts, even though
   `BLOCKL.RES` remained correct in both versions. Diagnostics showed an exact
   correlation: the broken `KRANNORM.RES` frames were exactly those containing a
   legitimate literal pixel with value `0` (pure black), incorrectly eaten as an
   escape. **Fix:** the escape token is chosen per frame by trial+validation
   (first `0x0003`, on failure `0x0000`), never both at once — see §4.3. This
   fixed the regression (KRANNORM 190/190, BLOCK/BLOCKR/BLOCKL clean) WITHOUT
   losing earlier progress (COLOR/BUTTON/FUNKEN2 still correct), and as an
   unexpected bonus **also solved the long-standing noise problem in
   `CORAIN.RES`** (§6.3) — it turned out to be the same escape-token bug. All 11
   known `.RES` files are now consumed 100% (0 B leftover).
10. **GAMMA.RES + GAMMA.SWG** — the first `.RES`+`.SWG` file pair encountered.
    `GAMMA.RES` revealed a **new `type=3` value** (225×60, 10 frames — menu
    buttons with German captions like "Optionen"), handled correctly by the
    default fallback (simple codec). `GAMMA.SWG` turned out to be a **completely
    different format** — a raw, uncompressed full-screen 640×480 RGB555 bitmap
    with no header at all (614400 B = exactly 640×480×2), showing the game's
    gamma correction settings screen (4 previews of the "SWING" logo at different
    brightness levels). Details in §9.
11. **KEXPLO.RES** (`type=7`, 29 frames, explosion animation) — the first frame
    (a small 14×15 image) decoded as noise, even though the §4.3 validation
    formally passed for both `escape=3` and `escape=0`. It was discovered that
    with the wrong escape token, the skip counter can reach an implausible value
    (found `5251` for an image of 210 pixels) — added a rule rejecting the
    attempt when a single counter exceeds `width*height` (see §4.5). This fixed
    frame 0 with no regression on the other files.
12. **SMLMENU.RES / SMRM1.RES / SMRM2.RES** (game menus) — discovered a **fourth
    `type=6` value**, mapping to the paired RLE codec (like `type=1` and `4`),
    not the simple codec (the default fallback for unknown `type` values, which
    was being wrongly chosen, giving a partially correct, partially noisy image —
    exactly the symptom described by the user: "shifted bars/noise"). After
    adding `type=6` to the paired-RLE group, all three files decode 100% as
    complete, multi-item game menus (main menu, mode selection, difficulty
    level) along with highlight variants for each entry.
13. **EXTRAS.RES + HELPMODE.RES** — discovered that these are **NOT images**, but
    **archives/packages** containing several named sub-files (readable ASCII
    names visible inside, e.g. `HEDGE.3LB`, `STONE.3LB`, `GSTAR.6SP`, `M00.DAT`).
    Reconstructed the container format (see §10) — every sub-file with the
    extension `.3LB`/`.6SP` turned out to be an ordinary, already-known `.RES`
    file (starting with `magic=0x14, type=1`), decoding flawlessly with the same
    decoder. `EXTRAS.RES`: 38/38 sub-files are images (1502 frames total — a
    library of **power-ups** for the game: spiky, stone, tower, heart, skull,
    star, lightning/twist, flash). `HELPMODE.RES`: 29/58 sub-files are `.6SP`
    images (1217 frames) — **the same power-ups, but at a higher resolution (2x
    larger)**, the other 29 are `.DAT` files (`M00.DAT`–`M44.DAT`) — probably
    help/dialog text, not images, not recognized by this decoder (a different
    purpose, not a bug). **Note:** the ordinary, playable marbles (not power-ups)
    are NOT in these files — found only in the `.SET` format, see point 14.
14. **NORMAL.SET + MAKE.SET + SHOWSET.EXE** (folder `KUGELN`) — finally located
    the **ordinary, playable marbles**. `NORMAL.SET` ("standard") starts with the
    text signature `"Gib mir 'ne Kugel\n"` (German for "give me a marble") +
    the set name, followed by a plain `.RES` image block — **46 marbles, 30×30
    px**, decoded with no changes to the decoder (`.SET` format described in
    §11). `MAKE.SET` turned out to be a red herring — it's an ordinary Watcom
    C/C++ makefile for building `SHOWSET.EXE`, not graphics data. After the image
    block in `NORMAL.SET`, 3033 B of unrecognized structure remains, starting
    with the identical byte sequence as `FONTS.RES` — a clue suggesting a
    possible connection, set aside for later per the user's established priority.

---

## 9. `.SWG` format — raw full-screen bitmaps

Some graphics resources appear as a separate `.SWG` file alongside a `.RES` file
of the same name (e.g. `GAMMA.RES` + `GAMMA.SWG`). This is a **completely
different, much simpler format** than `.RES`:

- **No header** — the file starts directly with pixel data
- **No compression** — every 16-bit word (little-endian) is one RGB555 pixel
  (the same color format as `.RES`, see §3), read row by row, with no
  escape/transparency tokens at all
- **Fixed size 640×480** — the only file examined so far (`GAMMA.SWG`) has
  exactly `640*480*2 = 614400` bytes, which matches this resolution perfectly
  with no remainder
- Visual result: a full-screen game menu/settings screen (in the case of
  `GAMMA.SWG` — the gamma calibration screen with four previews of the "SWING"
  logo at different brightness correction levels and German UI text)

**Working hypothesis:** `.SWG` files are static full-screen backgrounds (menus,
loading screens, settings), while `.RES` files are UI elements/sprites overlaid
on those backgrounds (in the case of `GAMMA` — the menu buttons from
`GAMMA.RES`). It hasn't yet been checked whether ALL `.SWG` files are 640×480, or
whether this can vary — more samples are needed.

---

## 10. Archive format — package files with named sub-files

Some files with the `.RES` extension (e.g. `EXTRAS.RES`, `HELPMODE.RES`) are not a
single image at all — they are **archives** bundling several named sub-files,
recognizable by the fact that the standard image header (§2) doesn't match
(`magic ≠ 0x0014`), but the first bytes can be read as an entry count, followed by
readable 8.3-style ASCII names (e.g. `HEDGE.3LB`, `GSTAR.6SP`).

**Structure (100% validated — every byte matches):**

```
offset  size           field          description
0x00    u32            count          number of entries in the archive

Then `count` records of 20 bytes each:
0x00    char[12]       name           8.3 name, zero-padded (e.g. "HEDGE.3LB\0\0\0")
0x0C    u32            size           size of this entry's data in bytes
0x10    u32            offset         offset of the entry's data, from the start of the file

Right after the header table: the data of all entries, concatenated sequentially
in the same order as the table (the offset of the first entry = end of the
table; the offset of each next entry = the previous one's offset + its size).
```

Python struct:
```python
count = struct.unpack_from('<I', data, 0)[0]
pos = 4
for i in range(count):
    name = data[pos:pos+12].split(b'\x00')[0].decode('ascii')
    size, offset = struct.unpack_from('<II', data, pos+12)
    pos += 20
```

**Sub-file content:** entries with the `.3LB` and `.6SP` extensions are ordinary
files in the already-known `.RES` format (starting with `magic=0x0014,
type=1` — paired RLE codec) — decoded with no changes to the existing decoder.
`.DAT` entries are NOT images (they don't match the `.RES` header) — probably
text/script data (in `HELPMODE.RES` the names `M00.DAT` through `M44.DAT`
suggest numbered help messages/texts).

**Confirmed examples:**
- `EXTRAS.RES` — 38 entries, all `.3LB`, all images, file consumed 100%
  (2467976/2467976 B). Content: a library of **power-ups** for the game (the
  ordinary playable marbles are in the separate `.SET` format, see §11).
- `HELPMODE.RES` — 58 entries (29× `.6SP` images + 29× `.DAT` text data), file
  consumed 100% (7435338/7435338 B).

**Open question:** whether the `.3LB`/`.6SP` extensions carry any additional
meaning (e.g. an animation frame count encoded in the name), or whether they're
just arbitrary labels given by the game's developers — not checked.

---

## 11. `.SET` format — marble skin sets

`.SET` files (folder `KUGELN` — German for "marbles") are the game's
configurable **marble appearance sets**. Structure, confirmed on `NORMAL.SET`:

```
offset  size     field           description
0x00    19 B     signature       ASCII text "Gib mir 'ne Kugel\n" + byte 0x00
0x14    12 B     name            set name, zero-padded ASCII (e.g. "standard")
0x20    4 B      unknown1        observed: 0
0x24    4 B      unknown2        observed: a non-zero value (possibly a checksum)
0x28    4 B      unknown3        observed: 0
0x2C    4 B      imageBlockSize  size in bytes of the image block that follows
```

Right after the 48-byte header, a **plain, already-known `.RES` image block**
begins (a multi-frame container, `type=1`/paired RLE), decoded with NO changes to
the existing decoder. The `imageBlockSize` field is, in practice, redundant: the
existing decoding loop stops on its own exactly where the last valid image header
ends.

**Confirmed example — `NORMAL.SET`** (internal name: "standard"): **46 marbles,
30×30 px**, exactly the same colors/patterns as in `COLOR.RES` (solid colors:
blue, red, green, turquoise, purple, brown, black, magenta, orange; multicolor/
marbled variants; silver; marbles with a special texture) — this is apparently
the **standard, default marble set** for the game.

**Unrecognized remainder of the file:** after the image block (75624 out of
78705 B), 3033 B of unknown structure remains. Note: these bytes begin with
**exactly the same sequence** as the first bytes of `FONTS.RES`
(`01/03 00 00 00 | 03 00 05 e0 01 00 00 00` + a long run of zeros) — strong
evidence that this is a smaller instance of the same, still-unresolved structure
(possibly marble color names/labels, encoded in the same unknown format as the
fonts). Set aside for later per priority — `FONTS.RES` and this structure are not
currently critical.

**The file `MAKE.SET` is a red herring — it is not game data.** It's an ordinary
**Watcom C/C++ makefile** (build script) for `SHOWSET.EXE`, which happens to have
a `.SET` extension. It contains plain text: a list of source files
(`showset.obj`, `graphasm.obj`, `graphik.obj`, `newalloc.obj`), libraries
(`mss.lib`, `vidlib.lib`), and compiler commands (`wcc386`, `tasm`). An
interesting side effect: **it reveals the source file names of the
`SHOWSET.EXE` tool** (a marble-set viewer) — useful if this executable is ever
analyzed.

---

*This document will be updated after every further finding about the format.*
