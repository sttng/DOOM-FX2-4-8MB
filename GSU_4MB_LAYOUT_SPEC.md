# Brief: building a Super FX ROM with 4 MB of GSU-reachable ROM (ares + sd2snes)

You are implementing a Super FX (GSU) SNES ROM that is larger than the 2 MB a real GSU2
can address. It must run on **ares** and on **sd2snes**. Everything below was verified on
both targets with a marker test ROM: each address in the tables was read on real ares and
real sd2snes, and every result matched. Follow these rules exactly; anything outside them is
untested or known to differ between the two targets.

This layout does **not** work on MiSTer or on real GSU2 hardware (both wrap at 2 MB). Treat
it as an ares/sd2snes-only format.

## 1. The core idea

The ROM file is **exactly 8 MB** (8,388,608 bytes). Only two 2 MB regions are used:

| File offset | Name | Who can read it |
|---|---|---|
| 0x000000–0x1FFFFF | **Window A** | SNES CPU and GSU |
| 0x200000–0x3FFFFF | unused | nobody: fill with padding ($FF) |
| 0x400000–0x5FFFFF | **Window B** | **GSU only** (portable rule) |
| 0x600000–0x7FFFFF | unused | nobody: fill with padding ($FF) |

That gives 4 MB of GSU-reachable ROM: 2 MB shared with the CPU plus 2 MB for the GSU only.

## 2. Verified behaviour on both targets

| Access | ares | sd2snes | Use it? |
|---|---|---|---|
| CPU 00–3F:8000–FFFF | Window A | Window A | **Yes** |
| CPU 40–5F, 80–BF, C0–DF | Window B | Window A mirror | **No**: targets differ |
| GSU `ROMB` $00–$3F + `GETB` | Window A | Window A | **Yes** |
| GSU `ROMB` $40–$5F + `GETB` | Window B | Window B | **Yes** |
| GSU `ROMB` $60–$7F | reads $00 | file 6–8 MB | **No**: targets differ |
| GSU `ROMB` with bit 7 set | bit 7 dropped | bit 7 dropped | **No**: keep bit 7 = 0 |
| GSU code, PBR $00–$3F | Window A | Window A | **Yes** |
| GSU code, PBR $40–$5F (`LJMP`) | Window B | Window B | **Yes** |
| ROMBR read back at $3036 | 7 bits | 7 bits | Don't rely on it |
| VCR at $303B | $04 | $04 | – |

## 3. Hard rules

1. **The SNES CPU only ever reads ROM in banks $00–$3F, at $8000–$FFFF** (window A). Never read
   ROM through banks $40–$FF from the CPU. This includes DMA sources and FastROM ($80+)
   addressing. On sd2snes those banks are mirrors of window A; on ares they are window B.
2. **The GSU reaches window A only through banks $00–$3F** (LoROM style, 32 KB per bank), and
   **window B only through banks $40–$5F** (HiROM style, 64 KB per bank).
3. **Never set ROMBR or PBR to $60 or above**, and never set bit 7. Both targets keep only 7 bits,
   and $60–$7F behave differently.
4. **Banks $40–$5F are no longer a mirror of $00–$3F.** On retail Super FX carts and in Nintendo's
   manual, $40–$5F is the HiROM image of the same 2 MB. Here it is window B. Never reach window A
   data through a $40+ bank, and never copy retail code that does so without rewriting it.
5. **If the CPU needs anything from window B** (graphics, tables, text), the GSU must copy it into
   Game Pak RAM ($70:xxxx) first. The CPU then reads it from RAM or DMAs it from RAM to VRAM.
6. **The file must be exactly 8 MB.** Both targets derive their address masks from the file size.
   A smaller file changes the mapping.

## 4. Address formulas

### Window A (file offset `f`, 0x000000–0x1FFFFF)

- CPU address: bank = `f >> 15`, offset = `0x8000 | (f & 0x7FFF)`. This is ordinary LoROM.
- GSU data: `ROMB` with R0 = `f >> 15`, then set R14 = `0x8000 | (f & 0x7FFF)`, then `GETB`.
- GSU code: PBR = `f >> 15`, PC = `0x8000 | (f & 0x7FFF)`.
- On the GSU side, offsets $0000–$7FFF of banks $00–$3F mirror $8000–$FFFF of the same bank
  (verified in the target sources, and the normal GSU behaviour).
- Data and code are split into **32 KB pages**. Anything that crosses a 32 KB boundary needs a bank change.

### Window B (file offset `f`, 0x400000–0x5FFFFF)

- GSU data: `ROMB` with R0 = `0x40 + ((f - 0x400000) >> 16)`, then R14 = `f & 0xFFFF`, then `GETB`.
- GSU code: PBR = `0x40 + ((f - 0x400000) >> 16)`, PC = `f & 0xFFFF`. Enter with `LJMP`.
- Pages are **64 KB**, linear.
- CPU: **no access** (rule 1).

### Switching code between windows

Use `LJMP Rn` (opcode $3D prefix + $98–$9D): PBR = Rn, R15 = Sreg (set Sreg with `FROM`).
Example, jump to window B at $48:0100:

```
IWT  R8,  #$0048     ; target bank
IWT  R11, #$0100     ; target address
FROM R11             ; Sreg = R11
ALT1
LJMP R8              ; PBR = $48, R15 = $0100, cache flushed, CBR = $0100
NOP                  ; delay slot (pipeline)
```

The same sequence with bank $00 returns to window A. Verified on both targets: code at
$48:0100 executed from file offset 0x480100.

## 5. Header (file offset 0x7FB0–0x7FFF, LoROM header location)

| Address | File offset | Value | Meaning |
|---|---|---|---|
| $FFB0–$FFB1 | 0x7FB0 | maker code (2 ASCII) | |
| $FFB2–$FFB5 | 0x7FB2 | game code (4 ASCII) | |
| $FFB6–$FFBC | 0x7FB6 | $00 | |
| $FFBD | 0x7FBD | **$06** | Expansion RAM = 64 KB (GSU Game Pak RAM) |
| $FFBE–$FFBF | 0x7FBE | $00 | |
| $FFC0–$FFD4 | 0x7FC0 | title, 21 bytes, space-padded | |
| $FFD5 | 0x7FD5 | **$20** | LoROM, SlowROM |
| $FFD6 | 0x7FD6 | **$14** or **$15** | ROM + GSU + RAM; $15 adds battery. Both verified on ares and sd2snes (full 128 KB saved) |
| $FFD7 | 0x7FD7 | **$0D** | ROM size 8 MB |
| $FFD8 | 0x7FD8 | **$00** | SRAM size: GSU RAM goes in $FFBD instead |
| $FFD9 | 0x7FD9 | region | e.g. $01 |
| $FFDA | 0x7FDA | **$33** | Extended header present (required for $FFBD to be read) |
| $FFDB | 0x7FDB | version | |
| $FFDC–$FFDD | 0x7FDC | checksum complement | |
| $FFDE–$FFDF | 0x7FDE | checksum | |
| $FFE0–$FFFF | 0x7FE0 | vectors | RESET → $8000 etc. |

- Checksum = sum of **all 8 MB** of bytes & $FFFF; complement = checksum XOR $FFFF.
- Before summing, write $FF,$FF,$00,$00 into $FFDC–$FFDF.
- This header makes sd2snes select its GSU core (map $20 + chipset $13–$15/$1A).
- ares sees an unknown ROM and picks its generic `GSU-RAM` board, which produces the ares
  mapping above. Do not try to match a retail game's checksum or database entry.
- 64 KB ($FFBD = $06) and 128 KB ($FFBD = $07) are both verified on ares and sd2snes. With 128 KB,
  banks 70 and 71 are separate for the CPU and the GSU, and the battery save covers all 128 KB.

## 6. Game Pak RAM

- 64 KB at **$70:0000–$70:FFFF**. Use `RAMB` with R0 = 0 (RAMBR = $70).
- With $FFBD = $07, bank **$71** adds another 64 KB (`RAMB` with R0 = 1). Verified on ares and
  sd2snes. With $FFBD = $06, don't use bank $71: it mirrors $70.
- The CPU also sees the first 8 KB at $00–$3F:$6000–$7FFF.
- Back-up RAM (banks $78–$79, BRAMR) and the manual's CPU-only "Super NES CPU ROM" (from 80:8000)
  are **not usable**: sd2snes doesn't implement them, and ares has no board for them.

## 7. Running the GSU (standard protocol, unchanged)

1. The CPU sets PBR ($3034), SCBR ($3038), CFGR ($3037), CLSR ($3039) while the GSU is idle.
2. **The CPU must execute from WRAM while the GSU owns ROM.** Copy a small stub to WRAM
   (e.g. $00:0200) and jump there. The stub does the following:
   - writes SCMR ($303A) with RON (bit 4) and/or RAN (bit 3) set, plus the screen-mode bits you need;
   - writes R15 low byte to $301E, then high byte to $301F, which starts the GSU;
   - polls SFR ($3030) bit 5 (GO) until it reads 0;
   - writes SCMR with RON/RAN cleared;
   - jumps back to ROM.
3. While the GSU owns ROM, the CPU sees fixed vectors: NMI → $00:0108, IRQ → $00:010C,
   COP → $00:0104, BRK/others → $00:0100. If interrupts stay enabled during GSU runs, place `JML`
   handlers in WRAM at those addresses. The verified test ran with interrupts disabled (`SEI`,
   $4200 = 0) and CFGR = $80 (GSU IRQ masked).
4. End every GSU program with `STOP` followed by `NOP`. Put a couple of `NOP`s between a RAM store
   and `STOP`.

## 8. GSU opcodes used in the verified test (no Super FX assembler needed)

| Instruction | Bytes |
|---|---|
| `IBT Rn,#imm8` (sign-extended) | `A0+n, imm` |
| `IWT Rn,#imm16` | `F0+n, lo, hi` |
| `ROMB` (ROMBR = Sreg) | `3F DF` |
| `RAMB` (RAMBR = Sreg) | `3E DF` |
| `GETB` (Dreg = ROM buffer byte) | `EF` |
| `SM (addr),Rn` | `3E, F0+n, lo, hi` |
| `FROM Rn` | `B0+n` |
| `ALT1` | `3D` |
| `LJMP Rn` (after ALT1, n = 8–13) | `90+n` |
| `NOP` / `STOP` | `01` / `00` |

Set ROMBR (`ROMB`) **before** writing R14: a write to R14 starts the ROM buffer fetch, and `ROMB`
alone does not. A 65816 assembler (e.g. ca65 from cc65) handles the CPU side; emit GSU opcodes as
bytes from macros if no Super FX assembler is available.

## 9. Building the image

1. Assemble the CPU code and window A content into the first 2 MB, laid out as LoROM.
2. Create an 8 MB buffer filled with $FF and copy window A to offset 0.
3. Place window B content at offset 0x400000.
4. Leave 0x200000–0x3FFFFF and 0x600000–0x7FFFFF as $FF.
5. Fix the header checksum over the full 8 MB.

## 10. Verifying on the targets

The test ROM `gsu_8mb_test_v2.sfc` (with source) puts an ID byte at the start of each 2 MB block
and prints what the CPU and GSU read. It also tests 128 KB Game Pak RAM and battery saves. These
were the observed results:

| Row | Access | ares | sd2snes |
|---|---|---|---|
| C1 | CPU 10:8000 | A0 (window A) | A0 |
| C2 | CPU 48:0000 | A2 (window B) | A0 (mirror) |
| C3 | CPU 90:8000 | A2 | A0 |
| C4 | CPU C8:0000 | A2 | A0 |
| G1 | GSU `ROMB $10` | A0 | A0 |
| G2 | GSU `ROMB $48` | A2 | A2 |
| G3 | GSU `ROMB $68` | 00 | A3 (6–8 MB) |
| G4 | GSU `ROMB $C8` | A2 | A2 |
| G5 | GSU code at PBR $48 | B2 (window B) | B2 |
| ROMBR | read back after `ROMB $C8` | 48 | 48 |

| R1 | CPU 70:0100 after writing $70 / $71 to banks 70 / 71 | 70 | 70 |
| R2 | CPU 71:0100 | 71 | 71 |
| R3 | GSU `RAMB 0` store, CPU reads 70:0010 | C0 | C0 |
| R4 | GSU `RAMB 1` store, CPU reads 71:0010 | C1 | C1 |
| R5 | CPU 00:6100 (8 KB mirror of 70:0100) | 70 | 70 |
| B1, B2 | boot counters in banks 70 / 71 after a reload | 2, 2 | 2, 2 |

Rows C1, G1, G2 and G5 are the ROM guarantees this layout relies on. The other ROM rows show why the
rules in section 3 exist. R1–R5 and B1/B2 confirm 128 KB of separate RAM, saved in full.

## 11. Things not verified (avoid or test first)

- CPU DMA directly from ROM while the GSU runs (the normal GSU rule applies: the CPU has no ROM
  access while RON = 1).
- GSU instruction cache behaviour across a PBR change other than `LJMP` (the cache is flushed on
  `LJMP` and on PBR writes from the CPU).
- Any file size other than exactly 8 MB.
- Other emulators. bsnes-derived cores and MiSTer wrap at 2 MB, and snes_faust maps CPU banks
  $80+ to the 2–4 MB region. None of them can run this layout.
