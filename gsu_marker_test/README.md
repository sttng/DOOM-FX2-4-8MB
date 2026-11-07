# GSU 8 MB test ROM (v2)

`gsu_8mb_test_v2.sfc` is an 8 MB Super FX (GSU) test ROM. It shows:

- which parts of an 8 MB file the SNES CPU and the GSU can reach;
- whether the 128 KB of Game Pak RAM is really two separate 64 KB banks;
- whether a battery save keeps all 128 KB.

## What is in the file

| File offset | Content | First byte |
|---|---|---|
| 0x000000–0x00FFFF | CPU code, GSU code (00:C000), header, font, screen | – |
| 0x080000 | Marker, window A (0–2 MB) | `A0` |
| 0x080100 | GSU routine: stores `B0` to RAM, then `LJMP` back | – |
| 0x280000 | Marker, gap 1 (2–4 MB) | `A1` |
| 0x480000 | Marker, window B (4–6 MB) | `A2` |
| 0x480100 | GSU routine: stores `B2` to RAM, then `LJMP` back | – |
| 0x680000 | Marker, gap 2 (6–8 MB) | `A3` |
| everything else | `FF` padding | `FF` |

The header declares:

- LoROM ($FFD5 = $20);
- ROM + GSU + RAM + battery ($FFD6 = $15);
- 8 MB of ROM ($FFD7 = $0D);
- an extended header ($FFDA = $33) with 128 KB of expansion RAM ($FFBD = $07).

The ROM creates a 128 KB save file.

## What the screen shows

Each row prints the byte that came back, then a decoded label where one applies.

### ROM tests

| Row | Access | Who |
|---|---|---|
| C1 | read 10:8000 (LoROM) | CPU |
| C2 | read 48:0000 (HiROM) | CPU |
| C3 | read 90:8000 (LoROM, bank ≥ $80) | CPU |
| C4 | read C8:0000 (HiROM, bank ≥ $C0) | CPU |
| G1 | `ROMB $10`, R14 = $8000, `GETB` | GSU |
| G2 | `ROMB $48`, R14 = $0000, `GETB` | GSU |
| G3 | `ROMB $68`, R14 = $0000, `GETB` | GSU |
| G4 | `ROMB $C8`, R14 = $0000, `GETB` (bank bit 7 set) | GSU |
| G5 | `LJMP` to PBR $48 : $0100 (code fetch) | GSU |
| GSU DONE | `5A` = the GSU reached `STOP` | GSU |
| ROMBR 3036 | ROMBR read back by the CPU after G4 | CPU |
| VCR 303B | GSU version code | CPU |

Labels: `WIN A` (A0), `GAP 1` (A1), `WIN B` (A2), `GAP 2` (A3), `CODE A` (B0),
`CODE B` (B2), `NO RUN` (EE: the GSU never wrote this slot), `ZERO` (00), `PAD FF` (FF),
`RAN OK` (5A), `?` (anything else, e.g. open bus).

### RAM tests

| Row | Test | Separate 128 KB gives | 64 KB or smaller (bank 71 mirrors 70) gives |
|---|---|---|---|
| R1 | CPU writes $70 to 70:0100, then $71 to 71:0100, reads **70:0100** | `70` BANK70 | `71` BANK71 |
| R2 | CPU reads **71:0100** | `71` BANK71 | `71` BANK71 |
| R3 | GSU `RAMB 0` stores $C0 at 70:0010, `RAMB 1` stores $C1 at 71:0010; CPU reads **70:0010** | `C0` GSU 70 | `C1` GSU 71 |
| R4 | CPU reads **71:0010** | `C1` GSU 71 | `C1` GSU 71 |
| R5 | CPU reads 00:6100 (8 KB mirror of 70:0100) | `70` BANK70 | `71` BANK71 |
| R6 | RAMBR ($303C) after `RAMB 1` | `01` | `01` |

R1, R3 and R5 decide it: any `71` or `C1` there means bank 71 is not separate memory.

### Battery tests

At power-on, before anything else, the CPU checks for the signature `SAV1` at **70:FFF0** and
at **71:FFF0**. It keeps a boot counter at bb:FFF4 in each bank:

- Signature missing: it writes the signature and sets the counter to 1.
- Signature present: it adds 1 to the counter.

**B1** shows the bank 70 counter and **B2** the bank 71 counter.

How to test:

1. Start the ROM once and note B1 and B2.
2. **Fully close** the game: quit the emulator, unload the ROM, or power off the console. On
   sd2snes, power off, or load another game and come back. A reset alone keeps RAM in place, so
   it proves nothing about saving.
3. Start it again and compare.

| First boot → second boot | Meaning |
|---|---|
| 1, 1 → 2, 2 | 128 KB is separate and the **whole** 128 KB is saved |
| 1, 1 → 2, 1 | 128 KB is separate, but only the lower 64 KB (bank 70) is saved |
| 1, 1 → 1, 1 | nothing is saved |
| 1, 2 → 3, 4 | bank 71 mirrors bank 70 (64 KB or less); the RAM is saved |
| 1, 2 → 1, 2 | bank 71 mirrors bank 70; nothing is saved |

When bank 71 mirrors bank 70, both counters are the same byte, so it goes up by 2 on each boot.

## Results

Observed: ares (234c999), sd2snes (b081ff9), MesenCE master (4b8a196, core 2.2.1, run headless
with `mesence_run.py`) and Mednafen 1.29.0 `snes_faust`. ares, sd2snes and MesenCE matched their
source-based predictions on every row. The MiSTer (SNES 4c2b746) column is a **prediction from
source**, not a run.

| Row | ares (observed) | sd2snes (observed) | MiSTer (source) | MesenCE master (observed) | Mednafen `snes_faust` (observed) |
|---|---|---|---|---|---|
| C1 | A0 | A0 | A0 | A0 | A0 |
| C2 | **A2** | A0 | A0 | A0 | A0 |
| C3 | **A2** | A0 | A0 | **A1** | **A1** |
| C4 | **A2** | A0 | A0 | **A2** | **A1** |
| G1 | A0 | A0 | A0 | A0 | A0 |
| G2 | **A2** | **A2** | A0 | A0 | A0 |
| G3 | 00 | **A3** | A0 | 00 | A0 |
| G4 | **A2** | **A2** | A0 | A0 | A0 |
| G5 | **B2** | **B2** | B0 | B0 | B0 |
| GSU DONE | 5A | 5A | 5A | 5A | 5A |
| ROMBR | 48 | 48 | 48 | 48 | **C8** |
| VCR | 04 | 04 | 04 | 04 | 04 |
| R1 | 70 | 70 | **71** | 70 | **71** |
| R2 | 71 | 71 | 71 | 71 | 71 |
| R3 | C0 | C0 | **C1** | C0 | **C1** |
| R4 | C1 | C1 | C1 | C1 | C1 |
| R5 | 70 | 70 | **71** | 70 | **71** |
| R6 | 01 | 01 | 01 | 01 | 01 |
| B1, B2 after a reload | 2, 2 | 2, 2 | 3, 4 if saved | 2, 2 (128 KB `.srm`) | 3, 4 (32 KB save file) |

Notes on the predicted and observed columns:

- **MiSTer:** the core drops RAM address bit 16 (`BSRAM_ADDR = RAM_A(15:0)`), so it has 64 KB of
  RAM and bank 71 mirrors 70.
- **Mednafen `snes_faust`:** it allocates 32 KB of RAM whatever $FFBD says.
- **MesenCE:** the CPU sees file 2–4 MB at 80–BF and 4–8 MB at C0–FF (Book II's CPU-only ROM), and
  the GSU sees only 0–2 MB. Builds from before 6 Oct 2026 show C3 = C4 = A0 instead.

## How to read the ROM rows

- **GSU reaches window B** when G2 shows A2 and G5 shows B2 (ares, sd2snes).
- **The CPU reaches window B** when C2, C3 or C4 show A2 (ares only).
- **G3 = A3** means the GSU can read beyond 6 MB with `ROMB $60+` (sd2snes only). On sd2snes this
  also confirms the firmware loads all 8 MB.
- **ROMBR = 48 after `ROMB $C8`** means only 7 bits of the bank are kept; C8 means all 8 bits are
  kept. Book II defines ROMBR as 8 bits.
- **Everything A0 and B0** means the emulator wraps at 2 MB, like a real GSU2 with its 21 ROM
  address lines.

## Portable layout (ares + sd2snes)

On both, the GSU reaches window A with `ROMB` $00–$3F and window B with `ROMB` $40–$5F, and can run
code from window B. Both have 128 KB of separate RAM, saved in full. Only ares lets the CPU see
window B.

A ROM that works on both:

- CPU code, the header and anything the CPU DMAs go in window A.
- GSU-only data and code go in window B.
- Never use `ROMB` $60 or higher.

MiSTer, MesenCE and a real GSU2 can't run it, because their GSU stops at 2 MB. The full rules are in
`GSU_4MB_LAYOUT_SPEC.md`.

## Real hardware

A GSU2 has 21 ROM address lines (2 MB), so the markers above 2 MB can't exist on a retail-style board.
On a Doom or Yoshi board with the first 2 MB of the image in an EPROM:

- C1 and G1 should read A0; C2 and G2 should read A0 (HiROM mirror); G5 should read B0.
- C3 and C4 should read open bus. nocash measured banks 80–FF as open bus on a Doom cart.
- G3, G4 and the ROMBR read-back answer test plan item T7, which no source documents.
- The RAM rows show what SRAM is fitted:
  - Doom: 64 KB with no battery. Expect mirroring and no save.
  - Yoshi's Island: 32 KB with a battery. Expect mirroring and 3, 4 after a power cycle.
  - A board fitted with 128 KB would test GSU2 pin 106 (SRAM.A16).

## Running headless in MesenCE

Build the core with `make core LTO=false` in a MesenCE checkout (needs clang and libsdl2-dev). Then:

```
python3 mesence_run.py <MesenCE>/InteropDLL/obj.linux-x64/MesenCore.so gsu_8mb_test_v2.sfc <home> 3
```

It prints the 20 result bytes from WRAM $0100–$0113 and stores the save in `<home>/Saves`. Run it
twice with the same `<home>` folder to test the battery save.

## Building

Needs `ca65`/`ld65` (cc65) and Python 3:

```
python3 build.py
```

This generates `font.bin` and `tilemap.bin` and assembles `marker.s` with `marker.cfg`. It then pads
the image to 8 MB, places the markers and the two routines, and fixes the header checksum.

## Files

| File | What |
|---|---|
| `gsu_8mb_test_v2.sfc` | the test ROM |
| `marker.s`, `marker.cfg`, `build.py` | source and build |
| `GSU_4MB_LAYOUT_SPEC.md` | brief for building a ROM with the ares + sd2snes layout |
| `ares.png`, `sd2snes.jpg`, `mednafen_snes_faust.png` | observed screens |
| `mesence_run.py` | runs the ROM headless in a MesenCE core build and prints the 20 result bytes |
