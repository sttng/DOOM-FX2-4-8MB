#!/usr/bin/env python3
"""Build the GSU 8 MB marker test ROM, v2 (adds 128 KB RAM and battery tests).

Steps: generate font.bin + tilemap.bin, assemble with ca65/ld65,
then pad to 8 MB, place markers and the two LJMP target routines,
and fix the header checksum.
"""
import subprocess, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
os.chdir(HERE)

# ---------------------------------------------------------------- font
# 5x7 glyphs, '#' = pixel. Each glyph: 7 rows of 5 chars.
G = {
' ': ["     "]*7,
'0': [" ### ","#   #","#  ##","# # #","##  #","#   #"," ### "],
'1': ["  #  "," ##  ","  #  ","  #  ","  #  ","  #  "," ### "],
'2': [" ### ","#   #","    #","   # ","  #  "," #   ","#####"],
'3': ["#####","   # ","  #  ","   # ","    #","#   #"," ### "],
'4': ["   # ","  ## "," # # ","#  # ","#####","   # ","   # "],
'5': ["#####","#    ","#### ","    #","    #","#   #"," ### "],
'6': ["  ## "," #   ","#    ","#### ","#   #","#   #"," ### "],
'7': ["#####","    #","   # ","  #  "," #   "," #   "," #   "],
'8': [" ### ","#   #","#   #"," ### ","#   #","#   #"," ### "],
'9': [" ### ","#   #","#   #"," ####","    #","   # "," ##  "],
'A': [" ### ","#   #","#   #","#####","#   #","#   #","#   #"],
'B': ["#### ","#   #","#   #","#### ","#   #","#   #","#### "],
'C': [" ### ","#   #","#    ","#    ","#    ","#   #"," ### "],
'D': ["#### ","#   #","#   #","#   #","#   #","#   #","#### "],
'E': ["#####","#    ","#    ","#### ","#    ","#    ","#####"],
'F': ["#####","#    ","#    ","#### ","#    ","#    ","#    "],
'G': [" ### ","#   #","#    ","# ###","#   #","#   #"," ####"],
'H': ["#   #","#   #","#   #","#####","#   #","#   #","#   #"],
'I': [" ### ","  #  ","  #  ","  #  ","  #  ","  #  "," ### "],
'J': ["  ###","   # ","   # ","   # ","   # ","#  # "," ##  "],
'K': ["#   #","#  # ","# #  ","##   ","# #  ","#  # ","#   #"],
'L': ["#    ","#    ","#    ","#    ","#    ","#    ","#####"],
'M': ["#   #","## ##","# # #","# # #","#   #","#   #","#   #"],
'N': ["#   #","#   #","##  #","# # #","#  ##","#   #","#   #"],
'O': [" ### ","#   #","#   #","#   #","#   #","#   #"," ### "],
'P': ["#### ","#   #","#   #","#### ","#    ","#    ","#    "],
'Q': [" ### ","#   #","#   #","#   #","# # #","#  # "," ## #"],
'R': ["#### ","#   #","#   #","#### ","# #  ","#  # ","#   #"],
'S': [" ####","#    ","#    "," ### ","    #","    #","#### "],
'T': ["#####","  #  ","  #  ","  #  ","  #  ","  #  ","  #  "],
'U': ["#   #","#   #","#   #","#   #","#   #","#   #"," ### "],
'V': ["#   #","#   #","#   #","#   #","#   #"," # # ","  #  "],
'W': ["#   #","#   #","#   #","# # #","# # #","# # #"," # # "],
'X': ["#   #","#   #"," # # ","  #  "," # # ","#   #","#   #"],
'Y': ["#   #","#   #"," # # ","  #  ","  #  ","  #  ","  #  "],
'Z': ["#####","    #","   # ","  #  "," #   ","#    ","#####"],
':': ["     ","  #  ","  #  ","     ","  #  ","  #  ","     "],
'-': ["     ","     ","     ","#####","     ","     ","     "],
'/': ["    #","    #","   # ","  #  "," #   ","#    ","#    "],
'?': [" ### ","#   #","    #","   # ","  #  ","     ","  #  "],
'.': ["     ","     ","     ","     ","     "," ##  "," ##  "],
'=': ["     ","     ","#####","     ","#####","     ","     "],
'(': ["   # ","  #  "," #   "," #   "," #   ","  #  ","   # "],
')': [" #   ","  #  ","   # ","   # ","   # ","  #  "," #   "],
'+': ["     ","  #  ","  #  ","#####","  #  ","  #  ","     "],
}
font = bytearray()
for code in range(32, 128):
    rows = G.get(chr(code), ["     "] * 7) + ["     "]
    for r in rows:
        bits = 0
        for i, ch in enumerate(r):
            if ch == '#':
                bits |= 0x80 >> (i + 1)      # 1 px left margin
        font += bytes([bits, 0x00])          # plane0, plane1 -> colour 1
open("font.bin", "wb").write(font)

# ---------------------------------------------------------------- tilemap
lines = {
    0:  "GSU 8MB TEST V2  128KB RAM+BAT",
    1:  "A0=0-2M A1=2-4M A2=4-6M A3=6-8M",
    2:  " C1 CPU 10:8000",
    3:  " C2 CPU 48:0000",
    4:  " C3 CPU 90:8000",
    5:  " C4 CPU C8:0000",
    7:  " G1 ROMB 10",
    8:  " G2 ROMB 48",
    9:  " G3 ROMB 68",
    10: " G4 ROMB C8",
    11: " G5 PBR 48",
    12: " GSU DONE",
    13: " ROMBR 3036",
    14: " VCR   303B",
    16: "RAM 128KB",
    17: " R1 CPU 70:0100",
    18: " R2 CPU 71:0100",
    19: " R3 GSU 70:0010",
    20: " R4 GSU 71:0010",
    21: " R5 CPU 00:6100",
    22: " R6 RAMBR 303C",
    24: "BATTERY BOOT COUNT",
    25: " B1 70:FFF4",
    26: " B2 71:FFF4",
    27: "RESET: BOTH +1 IF SAVED",
}
tm = bytearray(32 * 28 * 2)
for row, text in lines.items():
    assert len(text) <= 32, text
    for col, ch in enumerate(text):
        idx = ord(ch) - 32
        tm[(row * 32 + col) * 2] = idx
open("tilemap.bin", "wb").write(tm)

# ---------------------------------------------------------------- assemble
subprocess.run(["ca65", "--cpu", "65816", "-o", "marker.o", "marker.s"], check=True)
subprocess.run(["ld65", "-C", "marker.cfg", "-o", "marker.bin", "-m", "marker.map", "marker.o"], check=True)
base = open("marker.bin", "rb").read()
assert len(base) == 0x10000, hex(len(base))

# ---------------------------------------------------------------- 8 MB image
SIZE = 0x800000
rom = bytearray([0xFF]) * SIZE
rom[0:len(base)] = base

def marker(off, ident):
    tag = bytes([ident]) + b"MARKER @" + f"{off:06X}".encode() + b" "
    rom[off:off + len(tag)] = tag

marker(0x080000, 0xA0)   # window A
marker(0x280000, 0xA1)   # gap 1
marker(0x480000, 0xA2)   # window B
marker(0x680000, 0xA3)   # gap 2

def routine(ident):
    # IWT R0,#ident ; SM ($000E),R0 ; IWT R8,#$0000 ; IWT R11,#$C100 ;
    # FROM R11 ; ALT1 ; LJMP R8 ; NOP
    return bytes([0xF0, ident, 0x00,
                  0x3E, 0xF0, 0x0E, 0x00,
                  0xF8, 0x00, 0x00,
                  0xFB, 0x00, 0xC1,
                  0xBB, 0x3D, 0x98, 0x01, 0x01, 0x01])

rom[0x080100:0x080100 + 19] = routine(0xB0)   # reached if PBR $48 mirrors window A
rom[0x480100:0x480100 + 19] = routine(0xB2)   # reached if PBR $48 maps to window B

# checksum (header at file 0x7FB0; complement $7FDC, checksum $7FDE)
rom[0x7FDC:0x7FE0] = bytes([0xFF, 0xFF, 0x00, 0x00])
csum = sum(rom) & 0xFFFF
rom[0x7FDC] = (csum ^ 0xFFFF) & 0xFF
rom[0x7FDD] = (csum ^ 0xFFFF) >> 8
rom[0x7FDE] = csum & 0xFF
rom[0x7FDF] = csum >> 8

out = "gsu_8mb_test_v2.sfc"
open(out, "wb").write(rom)
print(f"wrote {out}: {len(rom)} bytes, checksum {csum:04X}")
