#!/usr/bin/env python3
"""
layout.py - ROM layout ("linker") for the asar build of DOOM-FX.

asar has no linker, so section placement lives in src/layout.inc (asar is
used with the 'norom' mapper: a section's "real" value is its file offset,
its "pc" value the address the code/data is assembled for).  This tool
measures every section (assembling with the current layout) and places the
relocatable ones, up to 6 rounds until src/layout.inc stops changing; it also
writes src/layout_end.inc (PRINT_LAYOUT).  Section metadata (kind, home bank,
code or data) comes from tools/sections.json.

ROM map (8 MB file, GSU_4MB_LAYOUT_SPEC.md; README "Cartridge and memory map"):

  file $000000-$1FFFFF  window A, seen by the CPU and the GSU as LoROM:
                        $00-$3F:$8000-$FFFF (32 KB pages; the GSU also sees a
                        page at $xx:$0000-$7FFF); sections are assembled for that
  file $200000-$3FFFFF  unused ($FF)
  file $400000-$5FFFFF  window B, the GSU only: $40-$5F:$0000-$FFFF (64 KB
                        banks; a section's address is its file offset)
  file $600000-$7FFFFF  unused ($FF)

The CPU never reads window B (nor any ROM bank above $3F): what it reads is in
window A.  Window B holds what only the GSU reads (regions.json).

Placement rules
  * absolute sections (fixed LOAD/ORG in the source) stay where they are
    (all in window A: bank $00, the walls' LoROM banks)
  * sections listed in regions.json (below) as "gsu" go to window B, inside
    one 64 KB bank unless marked "crossok"; "either" (the level RAM images):
    window B, or window A (across pages) when B has no room
  * every other section goes to window A, inside one 32 KB page unless
    marked "crossok"; 65816 code sections with the same home bank (the 64 KB
    bank of the original link: they call each other with 16-bit jsr/jmp)
    share one page
  * code is placed first, then the largest sections

regions.json: tools/regions.json (a data set's data/regions.json, which the
2 MB map of the main line used, is not read).

usage:  python3 tools/layout.py [--asar asar] [--report]
"""
import os, re, sys, json, subprocess, argparse, fnmatch

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WIN_A = (0x000000, 0x200000)        # CPU + GSU, LoROM
WIN_B = (0x400000, 0x600000)        # GSU only, $40-$5F

def load_meta():
    return json.load(open(os.path.join(ROOT, 'tools', 'sections.json')))

def load_regions():
    p = os.path.join(ROOT, 'tools', 'regions.json')
    return json.load(open(p)) if os.path.exists(p) else {}

def region_of(name, regions):
    for pat, reg in regions.items():
        if pat.startswith('_comment'): continue    # (section names start with _ too: _CHARDEF*)
        if fnmatch.fnmatchcase(name, pat): return reg
    return 'cpu'

def lorom(off):
    """window A file offset -> LoROM address ($00-$3F:$8000-$FFFF)"""
    return ((off >> 15) << 16) | 0x8000 | (off & 0x7FFF)

def file_to_pc(off, kind=None):
    """file offset -> address the section is assembled for"""
    if WIN_A[0] <= off < WIN_A[1]: return lorom(off)
    if WIN_B[0] <= off < WIN_B[1]: return off          # GSU $40-$5F
    return lorom(off % 0x200000)                        # (an empty section's stale position)

def parse_layout(path):
    lay = {}
    for l in open(path):
        m = re.match(r'!sec_(\w+)_(real|pc|ram)\s*=\s*\$?([0-9A-Fa-f]+)', l)
        if m:
            n, k, v = m.groups()
            lay.setdefault(n, {})[k] = int(v, 16) if k != 'ram' else int(v)
    return lay

def measure(asar):
    """assemble (with every assert removed: cached constants / GSU pads may be
    stale while sections move, tools/fixup.py refreshes them) and collect the
    section end positions printed with PRINT_LAYOUT"""
    import tempfile, shutil, glob
    tmp = tempfile.mkdtemp(prefix='doomfx_lay_')
    try:
        # sections may sit at stale positions while measuring: no bank-border checks
        top = open(os.path.join(ROOT, 'doom.asm'), encoding='latin1').read()
        open(os.path.join(tmp, 'doom.asm'), 'w', encoding='latin1').write(
            top.replace('norom', 'norom\ncheck bankcross off', 1))
        for f in glob.glob(os.path.join(ROOT, 'src', '**', '*'), recursive=True):
            if os.path.isdir(f): continue
            rel = os.path.relpath(f, ROOT); dst = os.path.join(tmp, rel)
            os.makedirs(os.path.dirname(dst), exist_ok=True)
            txt = open(f, encoding='latin1').read()
            txt = re.sub(r'(?m)^(\s*)assert\b.*$', r'\1; (assert removed for layout measurement)', txt)
            txt = re.sub(r'(?m)^(\s*)check bankcross full', r'\1check bankcross off', txt)
            open(dst, 'w', encoding='latin1').write(txt)
        os.symlink(os.path.realpath(os.path.join(ROOT, 'data')), os.path.join(tmp, 'data'))
        out = subprocess.run([asar, '-I.', '--define', 'PRINT_LAYOUT=1', '--fix-checksum=off',
                              'doom.asm', os.path.join(tmp, '_measure.sfc')], cwd=tmp, capture_output=True, text=True)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
    ends = {}
    for l in out.stdout.splitlines() + out.stderr.splitlines():
        m = re.match(r'SECEND (\w+) ([0-9A-Fa-f]+) ([0-9A-Fa-f]+)', l.strip())
        if m: ends[m.group(1)] = (int(m.group(2), 16), int(m.group(3), 16))
    return ends, out

def place(meta, sizes, regions):
    used = []  # (start, end, name)
    def free(a, b):
        for s, e, n in used:
            if a < e and s < b: return False
        return True
    for n, m in meta.items():
        if m['kind'] == 'fixed' and not m['ram']:
            off = m['file']; sz = sizes.get(n, m.get('size', 0))
            if sz: used.append((off, off + sz, n))
    placement = {}
    reloc = [n for n, m in meta.items() if m['kind'] in ('reloc', 'lorom') and sizes.get(n, 0) > 0]
    def span(off):
        return 0x8000 if off < WIN_A[1] else 0x10000
    def try_fit(n, lo, hi, align=1, size=None, crossok=False):
        sz = sizes[n] if size is None else size
        sp = span(lo)
        cands = sorted(set([lo] + [e for s, e, _ in used if lo <= e < hi] + list(range(lo - lo % sp + sp, hi, sp))))
        mib = meta[n].get('min_in_bank', 0)      # e.g. colourmaps: address in the bank >= $8000
        for c in cands:
            c = (c + align - 1) // align * align
            if file_to_pc(c) & 0xFFFF < mib: c = c - c % 0x10000 + mib
            w1 = 1 << 24 if crossok else c - c % sp + sp
            if c + sz <= min(hi, w1) and free(c, c + sz):
                return c
        return None
    # 65816 code: the sections of one home bank go to one 32 KB page of window A, in a row
    groups = {}
    for n in reloc:
        m = meta[n]
        if m['code']: groups.setdefault(m['home_file'] >> 16, []).append(n)
    for hb, names in sorted(groups.items(), key=lambda g: -sum(sizes[x] for x in g[1])):
        names.sort(key=lambda x: -sizes[x])
        total = sum(sizes[x] for x in names)
        if total > 0x8000:
            raise SystemExit('code of home bank $%02X: $%X bytes, more than a 32 KB page' % (0x40 + hb, total))
        c = None
        for page in range(WIN_A[0], WIN_A[1], 0x8000):
            # a free run of TOTAL bytes in this page
            c = try_fit(names[0], page, page + 0x8000, 1, size=total)
            if c is not None: break
        if c is None:
            raise SystemExit('ROM full: window A has no 32 KB page with $%X bytes for the code of home bank $%02X' % (total, 0x40 + hb))
        for x in names:
            used.append((c, c + sizes[x], x)); placement[x] = c; c += sizes[x]
    data = [n for n in reloc if not meta[n]['code']]
    # window B's first (they can go nowhere else), then those for either window, then window A's; largest first
    data.sort(key=lambda n: ({'gsu': 0, 'either': 1}.get(region_of(n, regions), 2), -sizes[n]))
    for n in data:
        m = meta[n]; sz = sizes[n]; align = m.get('align', 1); cross = bool(m.get('crossok'))
        reg = region_of(n, regions)
        if reg == 'gsu':
            c = try_fit(n, WIN_B[0], WIN_B[1], align, crossok=cross)
            if c is None: raise SystemExit('ROM full: window B (GSU) cannot place %s ($%X bytes)' % (n, sz))
        elif reg == 'either':
            # (the level RAM images: window B in one bank; else anywhere in window A,
            #  across pages: the GSU copies them page by page, rllevels.asm)
            c = try_fit(n, WIN_B[0], WIN_B[1], align, crossok=cross)
            if c is None: c = try_fit(n, WIN_A[0], WIN_A[1], align, crossok=True)
            if c is None: raise SystemExit('ROM full: windows A and B cannot place %s ($%X bytes)' % (n, sz))
        else:
            c = try_fit(n, WIN_A[0], WIN_A[1], align, crossok=cross)
            if c is None: raise SystemExit('ROM full: window A (CPU) cannot place %s ($%X bytes)' % (n, sz))
        used.append((c, c + sz, n)); placement[n] = c
    return placement, used

def write_layout(meta, placement, path):
    lines = [';', ';\tSECTION PLACEMENT  (generated by tools/layout.py - do not edit by hand)', ';',
             ';\treal = file offset (asar norom), pc = address the section is assembled for;',
             ';\tfile/cpu/gsu = file offset, CPU address (window A only) and GSU address of the',
             ';\tsection\'s ROM start (_real/_pc are advanced to the section end while assembling)', ';']
    for n, m in meta.items():
        if m['ram']:
            real, pc = 0, m['pc']          # RAM: skip only, nothing is emitted
        elif m['kind'] == 'fixed':
            real = m['file']; pc = file_to_pc(real)
        else:
            real = placement.get(n, m['home_file'])
            pc = file_to_pc(real) if not m.get('runpc') else m['runpc']
        lines.append('!sec_%s_real = $%06X\t\t; %s' % (n, real, 'RAM' if m['ram'] else
                     ('window B (GSU)' if WIN_B[0] <= real < WIN_B[1] else 'window A')))
        lines.append('!sec_%s_pc = $%06X' % (n, pc))
        lines.append('!sec_%s_ram = %d' % (n, 1 if m['ram'] else 0))
        if not m['ram']:
            rom = file_to_pc(real)
            lines.append('!sec_%s_file = $%06X' % (n, real))
            lines.append('!sec_%s_gsu = $%06X' % (n, rom))
            if not WIN_B[0] <= real < WIN_B[1]:
                lines.append('!sec_%s_cpu = $%06X' % (n, rom))
    open(path, 'w').write('\n'.join(lines) + '\n')
    # end-of-assembly section positions for the next measurement
    pr = [';', ';\tSECTION END POSITIONS (generated by tools/layout.py), printed with PRINT_LAYOUT', ';']
    for n in meta:
        pr.append('print "SECEND %s ",hex(!sec_%s_real)," ",hex(!sec_%s_pc)' % (n, n, n))
    open(os.path.join(os.path.dirname(path), 'layout_end.inc'), 'w').write('\n'.join(pr) + '\n')

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--asar', default=os.environ.get('ASAR', 'asar'), help='asar binary (default $ASAR or asar)')
    ap.add_argument('--report', action='store_true', help='list every placed section')
    a = ap.parse_args()
    meta = load_meta(); regions = load_regions()
    lay = parse_layout(os.path.join(ROOT, 'src', 'layout.inc'))
    if any(n not in lay for n in meta) or not os.path.exists(os.path.join(ROOT, 'src', 'layout_end.inc')) \
            or '_gsu = ' not in open(os.path.join(ROOT, 'src', 'layout.inc')).read():
        # new sections (or a layout.inc of the 4 MB map): start from their home positions, then measure
        cur = {n: lay[n]['real'] for n in lay if n in meta and not meta[n]['ram']}
        write_layout(meta, cur, os.path.join(ROOT, 'src', 'layout.inc'))
        lay = parse_layout(os.path.join(ROOT, 'src', 'layout.inc'))
    os.makedirs(os.path.join(ROOT, 'build'), exist_ok=True)
    for it in range(6):
        ends, out = measure(a.asar)
        if not ends:
            print(out.stdout[-3000:], out.stderr[-3000:]); raise SystemExit('measure failed')
        sizes = {}
        for n, (endreal, endpc) in ends.items():
            if n not in meta or meta[n]['ram']: continue
            sizes[n] = endreal - lay[n]['real'] if n in lay else 0
        placement, used = place(meta, sizes, regions)
        old = open(os.path.join(ROOT, 'src', 'layout.inc')).read()
        write_layout(meta, placement, os.path.join(ROOT, 'src', 'layout.inc'))
        new = open(os.path.join(ROOT, 'src', 'layout.inc')).read()
        lay = parse_layout(os.path.join(ROOT, 'src', 'layout.inc'))
        if old == new:
            break
    ua = sum(e - s for s, e, n in used if s < WIN_A[1])
    ub = sum(e - s for s, e, n in used if WIN_B[0] <= s < WIN_B[1])
    print('layout: %d sections; window A (CPU+GSU) %d bytes used, %d free; window B (GSU) %d bytes used, %d free'
          % (len(used), ua, WIN_A[1] - WIN_A[0] - ua, ub, WIN_B[1] - WIN_B[0] - ub))
    if a.report:
        for s, e, n in sorted(used):
            print('  %06X-%06X %6X %s' % (s, e, e - s, n))

if __name__ == '__main__':
    main()
