; GSU 8 MB marker test ROM, v2: adds 128 KB RAM and battery-save tests
; Reads marker bytes placed at 0x080000 (A0), 0x280000 (A1),
; 0x480000 (A2), 0x680000 (A3) from the CPU and from the GSU
; and prints what each access returned.

.p816
.smart -

WRAMBUF = $7E2000           ; tilemap work buffer (32x28 words)
STUB    = $000200           ; WRAM stub that runs while the GSU owns ROM
RES     = $0100             ; result bytes in direct page / WRAM

; result slots (bytes at RES+n)
R_C1 = 0
R_C2 = 1
R_C3 = 2
R_C4 = 3
R_G1 = 4
R_G2 = 5
R_G3 = 6
R_G4 = 7
R_G5 = 8
R_DONE = 9
R_ROMBR = 10
R_VCR = 11
R_R1 = 12
R_R2 = 13
R_R3 = 14
R_R4 = 15
R_R5 = 16
R_R6 = 17
R_B1 = 18
R_B2 = 19
NRES = 20

tmp = $00F0
cnt = $00F4
idx = $00F6
GSU_START = $C000
GSU_RET   = $C100

; ---------------- GSU opcode macros ----------------
.macro G_IBT rn, imm
  .byte $A0 + rn, imm
.endmacro
.macro G_IWT rn, imm
  .byte $F0 + rn, <(imm), >(imm)
.endmacro
.macro G_ROMB          ; ALT3 ROMB : ROMBR = Sreg (R0)
  .byte $3F, $DF
.endmacro
.macro G_RAMB          ; ALT2 RAMB : RAMBR = Sreg (R0)
  .byte $3E, $DF
.endmacro
.macro G_GETB          ; R0 = ROM buffer byte
  .byte $EF
.endmacro
.macro G_SM addr, rn   ; ALT2 SM (addr), Rn
  .byte $3E, $F0 + rn, <(addr), >(addr)
.endmacro
.macro G_FROM rn
  .byte $B0 + rn
.endmacro
.macro G_ALT1
  .byte $3D
.endmacro
.macro G_LJMP rn       ; (after ALT1) PBR = Rn, R15 = Sreg
  .byte $90 + rn
.endmacro
.macro G_NOP
  .byte $01
.endmacro
.macro G_STOP
  .byte $00
.endmacro

; Battery test: signature 'SAV1' at bb:FFF0, boot counter at bb:FFF4.
; Fresh RAM -> write signature, counter = 1. Signature found -> counter + 1.
.macro BOOTCOUNT bank, slot
  .local bc_cmp, bc_fresh, bc_done, bc_cp
  ldx #$0000
bc_cmp:
  lda f:bank*$10000+$FFF0,x
  cmp sigtxt,x
  bne bc_fresh
  inx
  cpx #$0004
  bne bc_cmp
  lda f:bank*$10000+$FFF4
  clc
  adc #$01
  sta f:bank*$10000+$FFF4
  bra bc_done
bc_fresh:
  ldx #$0000
bc_cp:
  lda sigtxt,x
  sta f:bank*$10000+$FFF0,x
  inx
  cpx #$0004
  bne bc_cp
  lda #$01
  sta f:bank*$10000+$FFF4
bc_done:
  lda f:bank*$10000+$FFF4
  sta RES+slot
.endmacro

; ---------------- CPU code ----------------
.segment "CODE"

.a8
.i16
reset:
  sei
  clc
  xce
  rep #$38
  .a16
  .i16
  ldx #$1FFF
  txs
  lda #$0000
  tcd
  sep #$20
  .a8
  lda #$00
  pha
  plb
  stz $4200            ; NMI/IRQ/autojoy off
  lda #$80
  sta $2100            ; forced blank

  ; --- PPU setup: mode 0, BG1 map at word $0000, chr at word $1000
  stz $2105
  stz $2107
  lda #$01
  sta $210B
  stz $210D
  stz $210D
  lda #$FF
  sta $210E            ; vscroll -1 so row 0 is visible
  stz $210E
  lda #$01
  sta $212C
  stz $212D
  stz $2130
  stz $2131
  stz $2133
  ; palette: 0 = dark blue, 1 = white
  stz $2121
  lda #$00
  sta $2122
  lda #$28
  sta $2122
  lda #$FF
  sta $2122
  lda #$7F
  sta $2122

  ; --- font -> VRAM word $1000 (DMA ch0, mode 1)
  lda #$80
  sta $2115
  ldx #$1000
  stx $2116
  lda #$01
  sta $4300
  lda #$18
  sta $4301
  ldx #.loword(font)
  stx $4302
  lda #^font
  sta $4304
  ldx #FONT_SIZE
  stx $4305
  lda #$01
  sta $420B

  ; --- battery boot counters (bank 70 first, then 71)
  BOOTCOUNT $70, R_B1
  BOOTCOUNT $71, R_B2

  ; --- copy tilemap template to WRAM buffer
  ldx #$0000
@tm:
  lda f:tilemap,x
  sta f:WRAMBUF,x
  inx
  cpx #(32*28*2)
  bne @tm

  ; --- CPU reads (GSU idle, CPU owns ROM)
  lda f:$108000
  sta RES+R_C1
  lda f:$480000
  sta RES+R_C2
  lda f:$908000
  sta RES+R_C3
  lda f:$C80000
  sta RES+R_C4

  ; --- prefill GSU RAM result area with $EE
  ldx #$0000
  lda #$EE
@clr:
  sta f:$700000,x
  inx
  cpx #$0010
  bne @clr

  ; --- GSU setup (all while GSU idle)
  lda #$80
  sta $3037            ; CFGR: IRQ masked, normal multiplier
  stz $3039            ; CLSR: 10.7 MHz
  stz $3038            ; SCBR
  stz $3034            ; PBR = 0

  ; --- copy WRAM stub and run it
  ldx #$0000
@cp:
  lda f:stub_src,x
  sta f:STUB,x
  inx
  cpx #(stub_end - stub_src)
  bne @cp
  jml STUB

gsu_done:
  ; --- collect GSU results (CPU owns RAM again)
  lda f:$700000
  sta RES+R_G1
  lda f:$700002
  sta RES+R_G2
  lda f:$700004
  sta RES+R_G3
  lda f:$700006
  sta RES+R_G4
  lda f:$70000E
  sta RES+R_G5
  lda f:$700008
  sta RES+R_DONE
  lda $3036
  sta RES+R_ROMBR
  lda $303B
  sta RES+R_VCR

  ; --- 128 KB RAM tests (CPU owns RAM again)
  lda #$70
  sta f:$700100
  lda #$71
  sta f:$710100
  lda f:$700100
  sta RES+R_R1         ; $70 = separate banks, $71 = bank 71 aliases 70
  lda f:$710100
  sta RES+R_R2
  lda f:$700010
  sta RES+R_R3         ; GSU wrote $C0 with RAMB 0
  lda f:$710010
  sta RES+R_R4         ; GSU wrote $C1 with RAMB 1
  lda f:$006100
  sta RES+R_R5         ; 8 KB mirror of 70:0100
  lda $303C
  sta RES+R_R6         ; RAMBR after RAMB 1

  ; --- patch values into the tilemap
  ldy #$0000
@row:
  sty idx
  tya
  asl a
  tay
  rep #$20
  .a16
  lda valpos,y         ; tilemap byte offset of the hex digits
  tax
  sep #$20
  .a8
  ldy idx
  lda RES,y
  jsr put_hex
  ldy idx
  lda haslabel,y       ; 0 = no decoded label for this row
  beq @next
  tya
  asl a
  tay
  rep #$20
  .a16
  lda valpos,y
  clc
  adc #(4*2)           ; label starts 4 tiles after the hex digits
  tax
  sep #$20
  .a8
  ldy idx
  lda RES,y
  jsr put_label
@next:
  ldy idx
  iny
  cpy #NRES
  bne @row

  ; --- tilemap -> VRAM word $0000
  lda #$80
  sta $2115
  ldx #$0000
  stx $2116
  lda #$01
  sta $4300
  lda #$18
  sta $4301
  ldx #.loword(WRAMBUF)
  stx $4302
  lda #^WRAMBUF
  sta $4304
  ldx #(32*28*2)
  stx $4305
  lda #$01
  sta $420B

  lda #$0F
  sta $2100            ; screen on
forever:
  bra forever

; A = byte, X = tilemap byte offset. Writes two hex tiles.
put_hex:
  pha
  lsr a
  lsr a
  lsr a
  lsr a
  jsr nib
  pla
  and #$0F
  jsr nib
  rts
nib:
  phx
  rep #$20
  .a16
  and #$000F
  tax
  sep #$20
  .a8
  lda f:hexchars,x
  plx
  sec
  sbc #$20             ; font starts at ASCII 32
  sta f:WRAMBUF,x
  lda #$00
  sta f:WRAMBUF+1,x
  inx
  inx
  rts

; A = byte, X = tilemap byte offset. Writes a 6-char label.
put_label:
  phx
  ldx #$0000
@find:
  cmp f:dec_keys,x
  beq @hit
  inx
  cpx #(dec_keys_end - dec_keys - 1)
  bne @find
@hit:                  ; x = index (last entry = default "?")
  rep #$20
  .a16
  txa
  asl a
  sta tmp
  asl a
  clc
  adc tmp              ; x*6
  tay
  sep #$20
  .a8
  plx
  lda #6
  sta cnt
@ch:
  lda dec_text,y
  sec
  sbc #$20
  sta f:WRAMBUF,x
  lda #$00
  sta f:WRAMBUF+1,x
  inx
  inx
  iny
  dec cnt
  bne @ch
  rts


hexchars: .byte "0123456789ABCDEF"

dec_keys:
  .byte $A0, $A1, $A2, $A3, $B0, $B2, $EE, $00, $FF, $5A, $70, $71, $C0, $C1, $FF
dec_keys_end:
dec_text:
  .byte "WIN A "
  .byte "GAP 1 "
  .byte "WIN B "
  .byte "GAP 2 "
  .byte "CODE A"
  .byte "CODE B"
  .byte "NO RUN"
  .byte "ZERO  "
  .byte "PAD FF"
  .byte "RAN OK"
  .byte "BANK70"
  .byte "BANK71"
  .byte "GSU 70"
  .byte "GSU 71"
  .byte "?     "

; tilemap byte offsets of each result's hex digits: row*64 + col*2, col 17
valpos:
  .word  2*64 + 17*2      ; C1
  .word  3*64 + 17*2      ; C2
  .word  4*64 + 17*2      ; C3
  .word  5*64 + 17*2      ; C4
  .word  7*64 + 17*2      ; G1
  .word  8*64 + 17*2      ; G2
  .word  9*64 + 17*2      ; G3
  .word 10*64 + 17*2      ; G4
  .word 11*64 + 17*2      ; G5
  .word 12*64 + 17*2      ; DONE
  .word 13*64 + 17*2      ; ROMBR
  .word 14*64 + 17*2      ; VCR
  .word 17*64 + 17*2      ; R1
  .word 18*64 + 17*2      ; R2
  .word 19*64 + 17*2      ; R3
  .word 20*64 + 17*2      ; R4
  .word 21*64 + 17*2      ; R5
  .word 22*64 + 17*2      ; R6
  .word 25*64 + 17*2      ; B1
  .word 26*64 + 17*2      ; B2

haslabel:
  .byte 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1, 1, 1, 1, 1, 0, 0, 0

sigtxt: .byte "SAV1"

; WRAM stub: runs from $00:0200 while the GSU owns ROM and RAM.
stub_src:
  lda #$18
  sta f:$00303A        ; SCMR: RON=1, RAN=1
  lda #<GSU_START
  sta f:$00301E
  lda #>GSU_START
  sta f:$00301F        ; writing R15 high byte starts the GSU
@w:
  lda f:$003030
  and #$20             ; GO flag
  bne @w
  lda #$00
  sta f:$00303A        ; give ROM/RAM back to the CPU
  jml gsu_done
stub_end:

nmi_irq:
  rti

; ---------------- GSU program (bank 00, $C000) ----------------
.segment "GSUMAIN"
  G_IBT 0, $00
  G_RAMB                ; RAMBR = $70
  ; G1: ROMB $10, R14=$8000 -> file 0x080000 everywhere
  G_IBT 0, $10
  G_ROMB
  G_IWT 14, $8000
  G_GETB
  G_SM $0000, 0
  ; G2: ROMB $48, R14=$0000
  G_IBT 0, $48
  G_ROMB
  G_IWT 14, $0000
  G_GETB
  G_SM $0002, 0
  ; G3: ROMB $68, R14=$0000
  G_IBT 0, $68
  G_ROMB
  G_IWT 14, $0000
  G_GETB
  G_SM $0004, 0
  ; G5: code fetch from PBR $48 (routine at $48:0100 stores its id at $000E)
  G_IWT 8, $0048
  G_IWT 11, $0100
  G_FROM 11
  G_ALT1
  G_LJMP 8
  G_NOP
  ; rest of this segment is $01 (NOP) fill

.segment "GSURET"
  ; G4: ROMB $C8, R14=$0000 (bit 7 of the bank)
  G_IWT 0, $00C8
  G_ROMB
  G_IWT 14, $0000
  G_GETB
  G_SM $0006, 0
  ; done flag
  G_IBT 0, $5A
  G_SM $0008, 0
  ; 128 KB RAM: $C0 -> 70:0010 (RAMB 0), $C1 -> 71:0010 (RAMB 1)
  G_IBT 0, $00
  G_RAMB
  G_IWT 0, $00C0
  G_SM $0010, 0
  G_IBT 0, $01
  G_RAMB
  G_IWT 0, $00C1
  G_SM $0010, 0
  G_NOP
  G_NOP
  G_STOP
  G_NOP

; ---------------- header ----------------
.segment "HEADER"
  ; $FFB0 extended header
  .byte "01"            ; maker code
  .byte "GMK2"          ; game code
  .res 6, $00
  .byte $00             ; $FFBC expansion flash
  .byte $07             ; $FFBD expansion RAM: 128 KB (GSU RAM)
  .byte $00             ; $FFBE special version
  .byte $00             ; $FFBF chipset subtype
  ; $FFC0 title, 21 bytes
  .byte "GSU 8MB TEST V2      "
  .byte $20             ; $FFD5 map mode: LoROM, SlowROM
  .byte $15             ; $FFD6 ROM + GSU + RAM + battery
  .byte $0D             ; $FFD7 ROM size: 8 MB
  .byte $00             ; $FFD8 SRAM size (GSU RAM is in $FFBD)
  .byte $01             ; $FFD9 region: North America
  .byte $33             ; $FFDA extended header present
  .byte $00             ; $FFDB version
  .word $0000           ; $FFDC checksum complement (patched)
  .word $0000           ; $FFDE checksum (patched)
  ; $FFE0 native vectors
  .word 0, 0
  .word .loword(nmi_irq)   ; COP
  .word .loword(nmi_irq)   ; BRK
  .word .loword(nmi_irq)   ; ABORT
  .word .loword(nmi_irq)   ; NMI
  .word 0
  .word .loword(nmi_irq)   ; IRQ
  ; $FFF0 emulation vectors
  .word 0, 0
  .word .loword(nmi_irq)   ; COP
  .word 0
  .word .loword(nmi_irq)   ; ABORT
  .word .loword(nmi_irq)   ; NMI
  .word .loword(reset)     ; RESET
  .word .loword(nmi_irq)   ; IRQ/BRK

; ---------------- bank 01: font + tilemap ----------------
.segment "DATA1"
font:
  .incbin "font.bin"
FONT_SIZE = * - font
tilemap:
  .incbin "tilemap.bin"
