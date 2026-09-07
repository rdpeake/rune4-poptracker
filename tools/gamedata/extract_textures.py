"""Pull named textures out of the game bundle as PNGs.

Same container as the item icons (see tools/README.md, Artwork), the one
darkxex's Rune-Factory-4-Special-Texture-Extractor converts to DDS. The payload is
BC7 at 1 byte/pixel for most things, but the `mini_map_*` map art is stored
uncompressed at 4 bytes/pixel; both forms are handled. The art comes out a
quarter turn over, so every image is rotated back counter-clockwise.

    python3 tools/gamedata/extract_textures.py '<regex>' <outdir> [bundle]
"""
import os
import re
import struct
import subprocess
import sys
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
# paths also pins SOURCE_DATE_EPOCH, so ImageMagick leaves the tIME chunk out
from paths import BUNDLE                             # noqa: E402
from extract_map_graph import MBundle          # noqa: E402

BC7 = os.environ.get('BC7DEC', '/home/russell/.claude/jobs/1bc7d016/tmp/bc7dec')


def chunks(d):
    tbl = struct.unpack_from('<i', d, 0x38)[0]
    n = struct.unpack_from('<i', d, tbl + 4)[0]
    save = tbl + 4 + 4 + 8 + n * 16 + 8
    sp = struct.unpack_from('<i', d, save + 4)[0]
    out = []
    for x in range(n):
        p = save + sp * x
        sp = struct.unpack_from('<i', d, p + 4)[0]
        w = struct.unpack_from('<i', d, p + 8 + 0x1C)[0]
        h = struct.unpack_from('<i', d, p + 8 + 0x1C + 4)[0]
        sz = struct.unpack_from('<i', d, p + 8 + 0x1C + 8 + 0x24)[0]
        out.append((w, h, sz))
    return out, struct.unpack_from('<i', d, 0x30)[0] + 0x10


def png(path, w, h, rgba):
    raw = b''.join(b'\x00' + bytes(rgba[y * w * 4:(y + 1) * w * 4]) for y in range(h))

    def ch(t, dd):
        return (struct.pack('>I', len(dd)) + t + dd
                + struct.pack('>I', zlib.crc32(t + dd) & 0xffffffff))
    open(path, 'wb').write(
        b'\x89PNG\r\n\x1a\n'
        + ch(b'IHDR', struct.pack('>IIBBBBB', w, h, 8, 6, 0, 0, 0))
        + ch(b'IDAT', zlib.compress(raw)) + ch(b'IEND', b''))


def main():
    pat = re.compile(sys.argv[1])
    out = sys.argv[2].rstrip('/') + '/'
    bundle = (sys.argv[3] if len(sys.argv) > 3 else
              BUNDLE)
    os.makedirs(out, exist_ok=True)
    b = MBundle(bundle)
    names = b.names()
    made = skipped = 0
    for i, n in enumerate(names):
        if not n.endswith('.texture') or not pat.search(n):
            continue
        d = b.read(i)
        try:
            texs, start = chunks(d)
        except Exception:
            skipped += 1
            continue
        w, h, sz = texs[0]
        if w and sz == w * h * 4:         # uncompressed RGBA -- the mini_map form
            rgba = d[start:start + sz]
        elif w and sz == w * h:           # 1 byte/pixel BC7 -- everything else
            r = subprocess.run([BC7, str(w), str(h)], input=d[start:start + sz],
                               capture_output=True)
            rgba = r.stdout
            if len(rgba) != w * h * 4:
                skipped += 1
                continue
        else:
            skipped += 1
            continue
        dst = out + n[:-8] + '.png'
        png(dst, w, h, rgba)
        subprocess.run(['/usr/bin/mogrify-im6.q16', '-rotate', '-90', dst],
                       stderr=subprocess.DEVNULL)
        made += 1
    print('extracted %d, skipped %d' % (made, skipped))


if __name__ == '__main__':
    main()
