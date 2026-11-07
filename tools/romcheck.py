#!/usr/bin/env python3
"""
romcheck.py - finalise and sanity-check the assembled ROM image (in place):
  * make the file exactly 8 MB (GSU_4MB_LAYOUT_SPEC.md): window A at
    $000000, window B at $400000, $200000-$3FFFFF and $600000-$7FFFFF $FF
    (they must be empty: nothing is placed there)
  * write the ROM size ($0D: 8 MB) into the header and check the header
    fields the map needs (LoROM $20, a Super FX cartridge type, no SRAM size,
    the extended header with the GSU RAM size)
  * recompute the SNES checksum/complement over the 8 MB
usage: romcheck.py build/doom.sfc
"""
import sys

SIZE = 0x800000
UNUSED = ((0x200000, 0x400000), (0x600000, 0x800000))

def main():
    fn = sys.argv[1]
    rom = bytearray(open(fn, 'rb').read())
    if len(rom) > SIZE:
        raise SystemExit('%d bytes: more than 8 MB' % len(rom))
    rom += b'\xFF' * (SIZE - len(rom))
    for a, b in UNUSED:
        if any(x not in (0x00, 0xFF) for x in rom[a:b]):
            raise SystemExit('data in the unused file range $%06X-$%06X' % (a, b - 1))
        rom[a:b] = b'\xFF' * (b - a)
    hdr = 0x7FC0
    rom[hdr + 0x17] = 0x0D                          # ROM size: 8 MB
    maptype = rom[hdr + 0x15]; carttype = rom[hdr + 0x16]
    if maptype != 0x20:
        raise SystemExit('header map mode $%02X: the 8 MB map needs $20 (LoROM)' % maptype)
    if carttype not in (0x13, 0x14, 0x15, 0x1A):
        raise SystemExit('header cartridge type $%02X is not a Super FX cart' % carttype)
    if rom[hdr + 0x18] != 0x00 or rom[hdr + 0x1A] != 0x33 or rom[0x7FBD] not in (0x06, 0x07):
        raise SystemExit('header: SRAM size $00, $FFDA = $33 and the GSU RAM size ($FFBD $06/$07) are needed')
    rom[hdr + 0x1C:hdr + 0x20] = b'\xFF\xFF\x00\x00'
    s = sum(rom) & 0xFFFF
    rom[hdr + 0x1C] = (s ^ 0xFFFF) & 0xFF; rom[hdr + 0x1D] = (s ^ 0xFFFF) >> 8
    rom[hdr + 0x1E] = s & 0xFF; rom[hdr + 0x1F] = s >> 8
    open(fn, 'wb').write(rom)
    title = bytes(rom[hdr:hdr + 21]).decode('latin1').rstrip()
    print('%s: "%s", %d KB, map $%02X, type $%02X, GSU RAM %d KB, checksum $%04X' % (
        fn, title, len(rom) // 1024, maptype, carttype, 1 << rom[0x7FBD], s))

if __name__ == '__main__':
    main()
