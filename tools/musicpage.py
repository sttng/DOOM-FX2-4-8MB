#!/usr/bin/env python3
"""
musicpage.py - the music/sound data laid out for ROM window A (LoROM, 32 KB pages).

The CPU reads the music chunks (APU uploads, RLC unpacking, turbo sound
streaming) with 24-bit pointers that must not run over the end of a 32 KB
LoROM page.  This splits MUSIC_C into pieces of at most 32 KB, each a section
of its own (MUSIC_C0, MUSIC_C1, ...) that tools/layout.py keeps inside one
page, wherever there is room; a chunk is never split.  With the chunk table and
the turbo table (unpacked) for them:

  data/RLDATA/MUSIC/MUSIC_C.P<n>  piece n
  data/RLDATA/MUSIC/MUSIC_T.P     5 bytes per chunk: address, size word
  data/RLDATA/MUSIC/MUSIC_O.P     the turbo table, 6 bytes per effect (rlsound.inc rlsett*)

The addresses are $47:0000 + piece * $8000 + offset in the piece; musicdat.asm /
musicdrv.asm turn them into the LoROM address of the piece (romlo).  build.sh
runs this before every build.

usage: musicpage.py [--data data]
"""
import os, sys, glob, struct, argparse
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import snescomp as sc

ORG = 0x470000
PAGE = 0x8000
MAXPIECES = 32                      # (MUSIC_C0..MUSIC_C31 in tools/sections.json)

def stored_len(s):
    return (s & 0x7FFF) + 2 if s & 0x8000 else s     # (packed: unpacked-size word + RLC stream)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--data', default='data')
    a = ap.parse_args()
    d = os.path.join(a.data, 'RLDATA', 'MUSIC')
    T = open(os.path.join(d, 'MUSIC_T'), 'rb').read(); C = open(os.path.join(d, 'MUSIC_C'), 'rb').read()
    chunks = [(T[i] | T[i + 1] << 8 | T[i + 2] << 16, T[i + 3] | T[i + 4] << 8) for i in range(0, len(T), 5)]
    pieces = [bytearray()]; moved = {}     # old address -> new address
    for addr, s in sorted(set(chunks)):
        if addr in moved: continue
        n = stored_len(s)
        if n > PAGE: raise SystemExit('music chunk at $%06X: %d bytes, more than a 32 KB page' % (addr, n))
        if len(pieces[-1]) + n > PAGE: pieces.append(bytearray())
        moved[addr] = ORG + (len(pieces) - 1) * PAGE + len(pieces[-1])
        pieces[-1] += C[addr - ORG:addr - ORG + n]
    if len(pieces) > MAXPIECES: raise SystemExit('music: %d pieces of 32 KB, the sections hold %d' % (len(pieces), MAXPIECES))
    t = bytearray()
    for addr, s in chunks:
        na = moved[addr]
        t += bytes((na & 0xFF, (na >> 8) & 0xFF, na >> 16, s & 0xFF, s >> 8))
    turbo = bytearray(sc.decompress(open(os.path.join(d, 'MUSIC_O.C'), 'rb').read())[0])
    starts = sorted(moved)
    for i in range(0, len(turbo) - 5, 6):
        bw, addr, n = turbo[i], turbo[i + 1] | turbo[i + 2] << 8 | turbo[i + 3] << 16, turbo[i + 4] | turbo[i + 5] << 8
        if not addr & 0xFF0000: continue                   # (unused entry: bank 0)
        base = max([x for x in starts if x <= addr], default=None)
        if base is None: raise SystemExit('turbo sound %d: $%06X is not in a music chunk' % (i // 6, addr))
        na = moved[base] + addr - base
        if (na - ORG) // PAGE != (na - ORG + n - 1) // PAGE:
            raise SystemExit('turbo sound %d crosses a 32 KB page' % (i // 6))
        turbo[i + 1:i + 4] = bytes((na & 0xFF, (na >> 8) & 0xFF, na >> 16))
    for f in glob.glob(os.path.join(d, 'MUSIC_C.P*')): os.remove(f)
    for i, p in enumerate(pieces): open(os.path.join(d, 'MUSIC_C.P%d' % i), 'wb').write(p)
    open(os.path.join(d, 'MUSIC_T.P'), 'wb').write(t)
    open(os.path.join(d, 'MUSIC_O.P'), 'wb').write(turbo)
    print('musicpage: %d chunks, MUSIC_C %d bytes in %d pieces, %d turbo entries' % (len(moved), len(C), len(pieces), len(turbo) // 6))

if __name__ == '__main__':
    main()
