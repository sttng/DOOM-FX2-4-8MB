# DOOM-FX 8 MB: technical notes

Details behind the [README](../README.md): how the data is converted, the
DOOM II and shareware sets, the renderer's speed-ups, the memory map, save
games, the music format and the tools.

## Converting from a WAD

Each part of a data set can be built from a WAD and switched back to the
cartridge's. The conversions follow how the SNES version was made from the
PC data: which DOOM texture became which SNES wall and floor colour, how
each wall and sprite was resized, and how each sound effect was resampled.
These rules come with the source (`tools/rules/`); `make data` adds DOOM's
palette and texture signatures from your `DOOM.WAD` (`tools/rules.py
install`, giving `data/*.json`). `make data LEARN=1` learns them from your
cartridge again instead, and `rules.py check` compares the result with
`tools/rules/`.

```sh
make wadlevels WAD=DOOM.WAD [MAPS="E1M6 E3M5"]                 # make fx3levels
make wadgfx    WAD=DOOM.WAD [PWAD=x.wad]                        # make fx3gfx
make wadart    WAD=DOOM.WAD                                     # make fx3art
make wadsfx    WAD=DOOM.WAD [FULL=1]                            # make fx3sfx
```

* **Levels** (`wad2rl.py`, `wadlevels.py`): a port of Sculptured's RIPDOOM
  level converter. The BSP comes from the WAD; FACES, LINES, SECTORS, OBJECTS,
  BLOCKMAP and the door/stair/floor/lift lists are built as RIPDOOM did. Line
  types the engine has no code for are cleared. WAD texture names map to the
  cartridge's walls and floor colours. The visibility table (REJECT) is
  computed with 2D portal flow (`rlpvs.py`): it must never hide a visible
  sector, and it is much tighter than the WAD's. Converted maps match the FX3
  levels to 98–100 % in every field (`wad2rl.py compare`) except the upper
  and lower textures of two-sided lines (42 % and 49 %).
* **Node rebuilds** (`wadnodes.py`, ZokumBSP at commit `22af6de`): every
  converted map gets new nodes (`-np=b`: node picks that split fewer segs and
  make fewer subsectors; `-nb`: no back side for lines whose back sector is
  closed and never moves). Nothing visible changes, and the maps get smaller.
  A map whose BSP, areas, vertexes and segs still exceed one 64 KB bank
  is rebuilt without invisible segs and with look-alike sectors merged, and
  when the ROM is full the map that gains most is rebuilt. If a map still
  does not fit, it keeps the cartridge version (DOOM II, TNT, Plutonia: it is
  left out).
* **Walls and sprites** (`wad2gfx.py`): the PC art in the SNES palette, with
  the cartridge's size savings learned per wall and sprite. Wall columns are
  shared with the most similar column of the same wall until the strips fit
  the 20 wall/sprite banks. The converted art is closer to the PC than the
  cartridge's in less space. The engine has 232 sprites (the FX3 cartridge
  206: no multiplayer frames), not the 229 of the source's `ImageList` (three
  barrel-explosion frames were missing).
* **Title, menus, fonts** (`wad2art.py`): `TITLEPIC`, the menus in DOOM's
  menu lettering (scaled to the cartridge's line height), the menu skull and
  the HUD font. `--intermission` adds the WIMAP pictures, `--textfont` the
  credits/end-text font, `--episodes N` limits the episode menu, `--title PNG`
  takes a 256×224 picture instead of `TITLEPIC`, `--cart ITEM,...` keeps the
  cartridge's skill/episode menu, skull or fonts. Every build keeps the
  cartridge's skill menu (`make wadart`, `doom2set`, `swset` and `doomfx` pass
  `--cart skill`).
* **Pause, Save Game and Load Game menus** in the cartridge's lettering
  (the cartridge had no saving: `menus.py build` assembles them from its
  menu font; "Rumble:" from the FX3 main menu), retouched by hand in
  `tools/menus/*.png`. `menus.py retouch`
  puts them into the data set; `make data`, `wadart`, `fx3art`, `doom2set`,
  `swset` and `doomfx` run it (`PNGMENUS=` leaves them out).
* **Weapons** (`wad2cut.py --weapons`; the CUT format is described there,
  `wad2cut.py show` renders a weapon): the PC frames at the 216/320 view
  scale, clipped at the view bottom, each 8×8 tile with its best palette; a
  frame too big for its tile budget is shrunk.
* **Sound effects** (`wad2soundfx.py`): the WAD sounds resampled, cut and
  levelled as the cartridge did, stored as BRR (`brr.py`). A look-ahead
  limiter keeps them below full scale (the matched gain would clip most WAD
  sounds). `--drop-missing` silences sounds the WAD lacks. 7 samples are
  resident in sound RAM, 27 (and the three chainsaw sounds below) are
  streamed into the APU blast buffer. The
  demon death sample was never played (demons die with the imp's sound):
  its slot holds DOOM II's super shotgun (`DSDSHTGN`, whole, 4 kHz). The
  chainsaw has the WAD's start-up (`DSSAWUP`), cutting (`DSSAWFUL`) and hit
  (`DSSAWHIT`) sounds as streamed effects (4 kHz, at most 1.47 s: the
  cutting sound fades out, the others play whole; at the WAD's own level,
  not boosted), the start-up and hit ones in the two other demon death
  effect numbers. A streamed sound already in a slot is replayed from
  there (the slot keeps the sample's start address).
* **Music** (`tools/music/`, `make wadmusic`): `wad2music.py` converts the
  WAD's MUS scores into song modules for the SPC700 driver (*Song format*),
  played with the cartridge's instruments and arranged by the rules of the
  cartridge's own conversions (instrument per GM program, voice priorities,
  an echo of the lead part, repeats as pattern calls). A song must fit sound
  RAM; one that does not is simplified step by step (stand-in instruments,
  no echo, no guitar layer, no velocity detail, coarser or no pitch bends, fewer
  chord voices), and otherwise keeps the cartridge's song. Every ROM uses
  its WAD's music (`make wadmusic WAD=...` on each data set;
  DOOM-FX from the Ultimate DOOM `DOOM.WAD`, whose Episode 4 uses Episode 1-3
  songs as on the PC). Kept from the cartridge because they do not fit sound
  RAM: DOOM II `D_DDTBLU`, `D_DDTBL2`, `D_DDTBL3`; TNT `D_THEDA2`. The music
  is split into pieces of at most 32 KB that may go anywhere in window A
  (`musicpage.py`), so these songs (240-480 KB) need no room in one piece.
  `rlsong.py` reads the songs (`list`, `dump`, `midi`, `compare`),
  `spcrender.py` renders them to WAV through the real driver (in an SPC
  emulator, `spcrender/build.sh <libgme source>`).

The game targets of the README (`make doomfx`, `doom2`, `tnt`, `plutonia`,
`shareware`) copy `gamedata-fx3` to `gamedata-<game>`, link it as `data/`
and run these steps on it: `doomfx` runs `wad2gfx.py`, `wad2art.py --cart
skill` and `wadlevels.py` (as `make wadgfx`, `wadart`, `wadlevels`); DOOM
II, TNT and Plutonia `make doom2set` with the settings below; shareware
`make swset`; then each the music (`make wadmusic`), the reworked skies
(`make skypng`) and the build, copied to `roms/`. The steps also work alone
on the linked data set.

## DOOM II, TNT and Plutonia

`make doom2set` settings (the Makefile's `TNT_SET` and `PLUTONIA_SET`):
DOOM II the defaults; TNT `NAMES=tnt BANK3F=0x6000 MASKED=65536
MASKEDBANKS=3C` and `MASKEDMAPS` its 20 maps; Plutonia `NAMES=plutonia
BANK3F= MASKED=65536 MASKEDBANKS=29` and `MASKEDMAPS` its 29 maps. The
reworked skies: `TNT_SKIES`, `PLUTONIA_SKIES`.

* **Super shotgun** (weapon type 16): 2 shells, wider aim window, its own
  frames from the WAD; between shotgun and chainsaw in the weapon cycle.
* **Walls:** a wall set chosen for the maps (`--map-walls`, `wallset.py`):
  252 slots picked by visual likeness to the WAD textures, stored as 2×4
  blocks indexed into per-group 256-block codebooks (wall format 3,
  `wallvq.py`); `WALLS=rle` gives the older run-length format 2. Skies are
  placed at the PC's horizon. Flats are one colour each.
* **Switches:** every switch the maps use has its own slot, with its pressed
  state (`SW1*`/`SW2*`, the alternate texture of `TEXTURE2.TBL`) also when
  the maps never show that state, and its texels count 8 times in the
  codebooks (`SWITCH_WEIGHT`), so lamps and levers keep their colours.
* **Middle textures of two-sided lines** (grates, bars, fences, windows,
  and those without holes, which the PC draws once, untiled) are drawn
  masked with the objects, so monsters behind them show through: up to 32
  textures, 255 high and 256 wide, chosen by area seen per byte within
  `MASKED` bytes of strips. DOOM II's banks are full, so its 48 KB come out
  of the walls. TNT and Plutonia get one more GamePak bank for them first
  (`MASKEDBANKS`, of `$3C $39 $29 $23 $27 $2B`: the one their maps leave
  emptiest; a second one cost each a map), the rest comes out of the walls;
  `MASKEDMAPS` counts only the maps that fit. DOOM II has 15 masked
  textures, TNT 16, Plutonia 12; left out (used on few sides): DOOM II
  SKSPINE2 BFALL1 BIGBRIK2 SP_FACE2 PIPE4 TEKBRON1, TNT FIREBLU1 BSTONE2
  GSTFONT3 BROWN96 ROCK2 MARBFAC2 ROCK4 BRNSMAL2 GSTFONT2 METAL METAL5 PIPE2
  SP_ROCK1 BRONZE2 METAL2, Plutonia FIRELAV2 SKSPINE2 A-BROCK2 FIRELAVA
  METAL BRWINDOW A-CAMO4 A-DBRI2 A-BRICK1 DBRAIN1 PIPE2 STONE6 A-BRBRK2
  BIGBRIK1. Animated ones show their first frame.
* **Score screen:** the WAD's `INTERPIC` behind every level (`wad2art.py
  --interpic`), no map and no level markers; no DOOM episode text between
  maps (MAP09, 18, 27), only at the end of the game. The finished level's
  name above FINISHED, from the WAD's `CWILVnn` pictures (`--level-names`;
  the shareware set has them too, from `WILVem`).
* **Music** from the WAD (`make wadmusic`, see above).

## Shareware set

Data-set flags in `levels.inc`: `!RLEPISODES` (episodes offered, score
screens kept), `!RLNOPLASMABFG` (no plasma/BFG frames), `!RLORDERSCREEN`
(every episode in the menu; the missing ones, and the end of the game after
the end text, show the order screen, `wad2art.py --order HELP2`).

| | original cartridge | shareware | full build |
|---|---|---|---|
| ROM | 2 MB | 8 MB file (1.5 MB used) | 8 MB file |
| levels | 22 | 9 | 36 (DOOM II: 32) |
| GSU RAM | 64 KB, no battery | 128 KB, battery | 128 KB, battery |

**Shareware DOOM:** Episode 1, *Knee-Deep in the Dead* (E1M1–E1M9), from
the shareware `DOOM1.WAD` (v1.9).

```sh
make shareware WAD=DOOM1.WAD     # a copy of gamedata-fx3 as gamedata-shareware, make swset, music
```

* `tools/mk2mb.py shareware` keeps the nine Episode 1 slots, makes E1M8 end the
  game and sets `!RLEPISODES = 1` and `!RLNOPLASMABFG`. With
  `--wad` it rebuilds the three walls whose texture the shareware WAD lacks
  (PIPE4, ROCKRED3, STARG2) from the texture the maps use there (PIPE2,
  REDWALL1, STARG3).
* **Everything from the WAD** except the engine, the music, the status bar,
  the palette, the list of wall slots and the title, menus and fonts below:
  maps, walls, sprites, intermission picture, order screen, sound effects and
  weapon frames. Sounds the WAD lacks are silent, art it lacks is a 1×1
  placeholder (38 of 67 walls and 163 of 232 sprites are used).
* **Title screen:** `tools/title/TITLE.png`, the WAD's `TITLEPIC` at
  256×224 with a retouched bottom line ("PROVIDED BY id FREE OF CHARGE •
  PRICE $9.00"), converted by `wad2art.py --title`.
* **Menus:** the retouched Pause, Save Game and Load Game menus
  (`tools/menus/*.png`, `menus.py retouch`); the cartridge's skill and
  four-episode menus, menu skull, message and text fonts (`wad2art.py
  --cart`). `!RLORDERSCREEN`: a new game on Episodes 2–4 shows the WAD's
  order screen (`HELP2`) until a button is pressed, then the title.
* **Windows and grates** (the BRNBIG/BRNSMAL windows, BROWNGRN) are drawn
  masked, as on the PC; the cartridge had none.

Tested in MesenCE: boot → title → E1M1, the episode menu, E1M8's end text →
order screen → title, every map, save/load on all nine maps. The shareware
licence allows passing on `DOOM1.WAD` unchanged only: a ROM built from it is
for your own use.

## Speed

Frame times at the real Super FX clock (MesenCE, Hurt Me Plenty, the
`test/det_suite.sh` input with `dettest.py --gsuclock 100`, 600 rendered
frames):

| level | VBlanks per frame | fps |
|---|---|---|
| E1M1 | 3.37 | 17.8 |
| E3M5 | 3.44 | 17.5 |
| E4M2 | 5.37 | 11.2 |
| E4M8 | 5.52 | 10.9 |

What makes the renderer faster than the original's:

* **Wall band buffer:** walls are drawn 8 pixels wide into a buffer and
  plotted row by row, so the pixel cache never reads back the screen.
* **BSP visibility bits:** the walk skips subtrees the player's sector cannot
  see.
* **BSP walk in chunks:** the segment passes run after each 1 KB chunk and
  the walk stops once the view is covered.
* **Screen thirds through WRAM:** each finished third is copied to WRAM at
  once, so the GSU no longer waits for the VBlank. The upload to VRAM goes
  strip by strip, starting a GSU that halted in between, so the GSU runs
  during it.
* **3-VBlank frames:** the weapon phase's VBlank is empty when the weapon
  picture did not change (96–99 % of frames); the next frame's first third
  is uploaded in it, so a frame takes 3 VBlanks instead of 4 when the GSU
  keeps up. Same game; input lands up to a frame later in game frames, the
  same in real time. A changed weapon picture waits for the next third's
  upload and goes in the rest of its blank when it fits.
* **Wall texel loops** (cartridge wall format): a magnified wall plot keeps a
  texel's pixels in a LOOP (9 cycles a pixel instead of 15), a minified one
  steps a whole run in a LOOP (25 instead of 36).
* **Wall colour maps in GSU RAM:** the wall pixel loops read the lit colour
  from a RAM copy instead of switching the ROM bank to the colour maps and
  back for every pixel (the emulators charge nothing for a GSU RAM read;
  real hardware does, so the gain there is smaller).
* Smaller gains: the BSP walk fits the 512-byte GSU cache, fast paths for
  single-colour floor strips and skies, and a LOOP for magnified wall plots
  (wall format 3).

The frame rate is capped at 20 fps (3 screen thirds take 3 VBlanks; a changed
weapon picture needs a VBlank of its own when it does not fit after a third).

## Cartridge and memory map

The ROM file is **8 MB** (map `$20`, type `$15`: Super FX + RAM + battery,
ROM size `$0D`, 128 KB GSU RAM in the extended header), laid out as
`GSU_4MB_LAYOUT_SPEC.md` describes, verified on ares and the sd2snes:

| file offset | CPU | GSU | contents |
|---|---|---|---|
| `$000000-$1FFFFF` | `$00-$3F:8000` | `$00-$3F` (LoROM) | **window A**: CPU code, GSU code, walls and sprite strips, colour maps, sector data and faces, level RAM tables, music, menus, pictures, weapon graphics, status bar, save and cheat code |
| `$200000-$3FFFFF` | – | – | unused (`$FF`) |
| `$400000-$5FFFFF` | – | `$40-$5F` | **window B**: the level parts the GSU reads from ROM (BSP, areas, vertexes, segs; REJECT when it stays in ROM), the level RAM images, sprite tables, sine/cosine and pixel-scale tables, wall table, font |
| `$600000-$7FFFFF` | – | – | unused (`$FF`) |

The CPU reads ROM only at `$00-$3F:8000-FFFF` (window A, 32 KB pages): its
code, data and DMA sources are assembled for LoROM, and nothing it reads
crosses a page (the music chunks: `musicpage.py`). Window B is the GSU's
alone; the GSU copies a level's RAM image from there to `$71:0000` at level
start, and the sector data and faces, which the CPU reads too, are in
window A (the GSU reads the faces there, in the sector data's bank, so they
do not count against the 64 KB bank of the other level parts).
`tools/regions.json` lists the window B sections; every other section goes
to window A. The GSU reads window A sections at their LoROM
addresses, so a table both read has one address.

| GSU RAM | contents |
|---|---|
| `$70:0000-$FFFF` | variables, screen buffer, sectors, objects, vertexes, lines, visibility bits, the renderer's work lists |
| `$71:0000-$ACBF` | level RAM image, copied from ROM at level start |
| `$71:ACC0-$AEFF` | wall band buffer |
| `$71:AF00-$CFFF` | the walls' colour maps (33 × 256 bytes), copied from ROM at level start |
| `$71:D000-$FFFF` | save games (12 KB, battery backed) |

**Hardware.** ares (its generic `GSU-RAM` board) and the stock sd2snes /
FXPak Pro Super FX core map the 8 MB file this way. Real Super FX 2
hardware and MiSTer wrap at 2 MB and are not known to run it.
`tools/mesence-doomfx.patch` adds the map to MesenCE (and keeps a 4 MB map
with the GSU in the first 2 MB); `tools/aresrun` runs the ROMs in ares and
can log every ROM read against the map's rules (`ACCESSMAP`).

## Save games

* **Save:** pause → *Save Game* → one of three slots (not while dead). A slot
  is named after its level ("E1M3 TOXIN REFINERY", "MAP10 REFUELING BASE").
* **Load:** pause → *Load Game*. The level is restarted, then everything is
  put back: monsters and objects, doors and lifts, switches, the automap,
  health, ammo, weapons, keys and the level time.
* **Storage:** a save keeps only what changed since the level started: the
  level blocks XORed with the freshly set-up level, plus the game variables,
  packed with a small LZ77 (1.2–2.7 KB). Saving restarts the level the same
  way, so the game continues exactly as after loading that save. Each slot
  has a checksum, and saves load only into the ROM build that wrote them.
* **Code:** `src/engine/savegame.asm`, `src/include/savegame.inc`; menu art by
  `tools/menus.py`.

## Cheats

* **Entry:** the pause menu passes every new joypad state to `CheatPress`
  (`src/engine/cheats.asm`, from `rlmenus.asm`); each of the three cheats
  follows its own sequence. A press that continues a cheat already begun is
  taken by it and does nothing in the menu (A and Down are menu buttons);
  the first presses (R, L, Right) do nothing there. Only in the main pause
  menu, with the joypad, and not while dead.
* **Ammo, weapons, keys:** ammo to the maximum (doubled with the backpack),
  every weapon the set has (no plasma rifle or BFG in the shareware set; the
  super shotgun in DOOM II, TNT and Plutonia), the six keys, 200% armor,
  health raised to 100%. The FX3 cartridge gives 200/50/50/300 ammo and sets
  the health to 100%.
* **Invulnerability:** 3600 VBlanks (60 s), as the sphere.
* **Map:** `ComputerMap` = 2: the computer map, and the automap draws every
  moving object (the original code for it, disabled in the 1995 source,
  `rlautomap.asm`). Reset at the next level.
* **Messages:** "VERY HAPPY AMMO ADDED", "INVULNERABILITY!", "COMPUTER AREA
  MAP", shown when the game goes on. The FX3 cartridge checks the sequences
  while playing.

## Song format

The SPC700 driver (`MUSIC_D.C`, APU `$0700`–`$1EDF`) loads one module per
song: song data and BRR samples from `$6517`, plus driver table entries
(sample addresses `$1F00`, instruments `$2156`, envelopes `$221C`, song
pointer `$25C4`). A song is a track count and a pointer per track. Timer 1
runs at 50 Hz; each tick adds the tempo to an 8-bit accumulator and the
sequencer steps on the carry.

| byte | meaning |
|---|---|
| `$00`–`$7F` | note: previous + (b >> 3) − 8, length (b & 7) + 1 |
| `$80`–`$BF` | note b − `$60`, length = next byte |
| `$C0`–`$DF` | rest b − `$BF` |
| `$F8` `$FD` `$FE` `$FF` | rest 32, 64, 128, 256 |
| `$EF` n l | note n, length l |
| `$F5` i | instrument |
| `$F2` v, `$F1` a b | volume, volume scale |
| `$ED` v | velocity |
| `$FB` p | pan offset |
| `$F3` p, `$E5` f v m, `$E6` | voice priority, voice allocation, default allocation |
| `$E9` m | voices sound effects may take |
| `$FA` t | tempo |
| `$F6` … | pattern call (address, end, count, transpose, volume scale, skip) |
| `$EB` / `$EC` … `$00` | pitch slide (`$EC`: key off first) |
| `$F4` | legato |
| `$F7` w, `$E0` w | fine pitch, detune |
| `$E1`–`$E4` x | envelope overrides |
| `$EA`, `$E7`, `$FC` f | key off, reset, flag |
| `$F9`, `$F0` | loop the track, end |

Notes are MIDI note numbers. The cartridge's songs step about once every
2.88 MUS ticks (MUS: 140 Hz); `wad2music.py` uses tempo 0, 50 steps a second,
2.8 MUS ticks a step.

## Source layout

```
doom.asm            master file: mapper, settings, module list
src/macros.inc      asar replacements for xa/xl features, project macros
src/layout.inc      section placement (generated)
src/include/        the original headers + levels.inc, savegame.inc, rumble.inc
src/engine/         the original modules + savegame.asm, cheats.asm, rumble.asm, order.asm;
                    startscreen.asm replaces legal.asm, exmy.asm the e1my/e2my/
                    e3my.asm level modules
data/               generated game data (not distributed)
tools/              build, conversion and test tools
tools/doomfx-src/   the files of the DOOM-FX source release `make data` reads
tools/rules/        the WAD conversion rules (textures to walls, wall and sprite sizes, sound effects)
tools/skies/        reworked skies (make skypng)
tools/music/        the music converter and song tools (make wadmusic)
tools/test/         test and analysis scripts (not used by the build)
tools/legacy/       the xa/xl reference assembler and the xa → asar translator
```

The first commits are the translation: with the original data it assembles
byte for byte to the original tool chain's ROM. Engine changes of this port
since then are marked `this port` in the source.

### Tools

Every script's header has the details and its usage.

| Build (`make`, `tools/build.sh`) | |
|---|---|
| `build.sh` | the build: layout, cached values, build id, graphics check, asar, ROM check |
| `layout.py` | the "linker": places the ROM sections in windows A and B (`regions.json`, `sections.json`), writes `src/layout.inc` |
| `fixup.py` | refreshes the cached alignment pads, constants and `ds` sizes the asserts guard |
| `gfxlimits.py` | checks walls and sprites against the engine's limits; holds the wall/sprite bank lists |
| `romcheck.py` | makes the 8 MB file, checks the header, sets the checksum |
| `musicpage.py` | the music chunks split into pieces of at most 32 KB (a section each, inside one page of window A) |

| Data set from your files (`make data`) | |
|---|---|
| `mkdata.py` | builds a whole data set from the FX3 cartridge, `DOOM.WAD` and `tools/doomfx-src/` |
| `rules.py` | the WAD conversion rules in `tools/rules/`: `install` into a data set (with `DOOM.WAD`'s palette and texture signatures), `export` learned ones, `check` |
| `fx3_gfx.py` | walls, sprites and colour maps from a cartridge ROM, rebuilt in the engine's format |
| `fx3_convert_levels.py` | the 36 FX3 levels as level data files and `levels.inc` |
| `menus.py` | `build`: the pause/save/load menus from the cartridge's lettering; `retouch`: puts in `tools/menus/*.png` |
| `titlemenus.py` | the title menus (New Game / Load Game, skill, episode, slots) for `title.asm`; `build.sh` runs it |
| `startscreen.py` | the start screen's text: the PC start-up log of the data set's game; `build.sh` runs it |
| `datagen/` | `mkdata.py`'s package: `fx3_art.py`, `fx3_music.py`, `rlmus.py` (the song, effect and music driver command numbers), `fx3dec.py` with `emu65816.py` and `dis65816.py` (the FX3 cartridge's own 65816 decompressor run under emulation), `tilequant.py` (full-colour screens to 4 bpp tiles and palettes), `snesgfx.py` (tiles, palettes, previews) |

| From a WAD (`make doom2set`, `swset`, `wadlevels`, `wadgfx`, ...) | |
|---|---|
| `wad2rl.py` | WAD maps to Reality Engine level data; `learn` / `compare` against the cartridge's levels |
| `wadlevels.py` | puts converted levels into the data set and fits them into the ROM (DOOM II profile) |
| `wadnodes.py` | rebuilds a map's nodes with ZokumBSP so it fits one bank |
| `rlpvs.py` | the sector visibility table (REJECT/PVS) of a map |
| `wad2gfx.py` | walls, sprites and masked middle textures |
| `skypng.py` | a 128x128 picture as one of the skies (`make skypng SKY=n PNG=...`, after the art conversions; `tools/skies/`) |
| `wallset.py`, `wallvq.py` | the wall set for a WAD's maps; wall format 3 (VQ blocks and codebooks) |
| `wad2art.py` | title screen, menus, menu skull, fonts, score screens, level names |
| `wad2cut.py` | weapon HUD frames (the CUT format; `show` renders a weapon) |
| `wad2soundfx.py` | sound effects (BRR) |
| `mk2mb.py` | `shareware`: cuts a data set down to the shareware set |

| Libraries | |
|---|---|
| `wad.py` | the WAD reader all tools use |
| `snescomp.py` | the DeCompress formats: decompressors and compressors (`comp.asm`) |
| `rlmusic.py` | reads and writes the music and sound data (`RLDATA/MUSIC`) |
| `brr.py` | BRR sample encoder/decoder (`wad2soundfx.py`) |
| `rlcompare.py` | compares two level data sets field by field (`wad2rl.py compare`) |

| Tests and analysis | |
|---|---|
| `mesenrun/` | the headless MesenCE runner (`mesenrun.cpp`, `build.sh`; `tools/mesence-doomfx.patch`: the 8 MB map, a 4 MB map and the GSU probes) |
| `aresrun/` | the headless ares runner (`main.cpp`, `build.sh`, `ares-probes.patch`); `ACCESSMAP` logs ROM reads against the 8 MB map's rules |
| `test/dettest.py` | deterministic play test: hashes, screenshots, RAM dumps, profiles |
| `test/det_suite.sh` | `dettest.py` on several levels, compared with a baseline |
| `test/savetest.py` | save and load through the pause menu, checked byte for byte |
| `test/gsuprof.py` | GSU cycles per routine from a `mesenrun` profile |
| `test/delaycheck.py` | GSU branch delay slot hazards in the sources |

| Music (`tools/music/`) | |
|---|---|
| `wad2music.py` | `convert`: a WAD's MUS music into song modules of the data set; `song`: one song as WAV |
| `musiclib.py` | the cartridge's instrument library and the song module builder |
| `mus.py` | reads DOOM's MUS lumps |
| `rlsong.py` | reads the songs: `list`, `dump`, `midi`, `compare` with the WAD's MUS |
| `spcrender.py`, `spcrender/` | renders songs to WAV through the SPC700 driver (libgme's SPC emulator) |
| `disspc700.py` | SPC700 disassembler (the music driver) |

| Legacy (`tools/legacy/`, not used by the build) | |
|---|---|
| `xasm.py` | reference re-implementation of the original xa/xl assembler and linker |
| `xa2asar.py` | translates the original sources to asar syntax |
| `mkproject.py` | generated the first asar project tree with `xa2asar.py` (do not run it on this repository) |

**Tests** need the headless MesenCE runner (`tools/mesenrun/build.sh <MesenCE
source>`; set `MESENRUN`). MesenCE continues the archived Mesen 2; its
Super FX timing differs slightly, so results from the two do not compare
frame for frame.

* `test/dettest.py`: deterministic play — pins the frame time, hashes the game
  state every rendered frame, takes screenshots and RAM dumps; options for
  menus, level, skill, joypad and mouse input, GSU profiling.
* `test/det_suite.sh`: `dettest.py` on 5 levels (`LEVELS="0 1 7"`: those a change
  touches), each level's result, and `--compare` against a baseline.
* `test/savetest.py ROM NAME LEVEL...`: save and load through the pause menu, every
  saved block checked byte for byte.
* `test/gsuprof.py`: GSU cycles per routine (`MESEN_GSU_PROF=<file>`).
  `MESEN_GSU_IDLE=<file>`: GSU time running, stopped, or waiting for the
  ROM/RAM bus, per frame and per GSU address (`MESEN_GSU_IDLE_FROM=<frame>`).
* `test/delaycheck.py`: GSU branches whose delay slot holds a prefix or a
  multi-byte instruction.
* `MESEN_RAM=random|ones`: random or set power-on RAM.
* `tools/aresrun`: runs a ROM in ares; `LEVEL=n` starts at level n,
  `ACCESSMAP=<file>` records which processor read each ROM byte and lists
  every read outside the rules of `GSU_4MB_LAYOUT_SPEC.md` (CPU reads above
  bank `$3F` or below `$8000`, GSU reads of banks `$60+`).
