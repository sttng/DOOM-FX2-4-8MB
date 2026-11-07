// ares-headless: run a Super Famicom ROM in ares without a window, script the
// joypad, count the game's rendered frames (DOOM-FX: non-zero writes of
// FrameDone in WRAM) per 600 emulated frames.
// usage: ares-headless ROM FRAMES "frame:button[@hold],...;..." [shot frames,...] [outdir]
//   buttons: Up Down Left Right A B X Y L R Select Start (held 6 frames unless @hold);
//   EXIT finishes the level (DOOM-FX ExitLevel = 11, in GSU RAM and its WRAM copy).
//   The addresses of FrameDone and ExitLevel come from ROM.sym (the build's symbol
//   file next to the ROM; without it, those of the current builds).  A shot frame writes
//   ares_NNNNN.ppm, gsuram_NNNNN.bin (GSU RAM), wram_NNNNN.bin and apuram_NNNNN.bin (sound RAM).
// environment (hooks from ares-probes.patch): GSUTRACE=frame [GSUTRACEN=n, default 100000] (GSU registers
//   per instruction -> /tmp/ares_gsu_trace.txt), IOLOG=frame [IOLEN=n, default 20] (reads of
//   $4016-$4017/$4212-$421F), RWATCH=hex (GSU RAM word reads/writes after frame 1000),
//   WWATCH=1 (non-zero WRAM writes of $0BCC/$0BD1/$0BD2), PORT2_PAD=1 (joypad in port 2)
//   ACCESSMAP=file: which processor read each ROM byte, one flag byte per file offset (8 MB):
//     1 CPU $00-$3F:8000 (LoROM), 2 CPU any other ROM bank, 4 GSU $00-$3F, 8 GSU $40-$5F, 16 GSU code fetch;
//     with ACCESSMODE=old the 2/4 MB map (CPU and GSU $40-$5F = file 0-2 MB, CPU $E0-$FF = file 2-4 MB),
//     else the 8 MB map (GSU_4MB_LAYOUT_SPEC.md: $40-$5F = window B, file 4-6 MB).
//     Reads outside that map's rules are listed on stderr ("VIOLATION": CPU ROM reads outside
//     $00-$3F:8000-FFFF, GSU reads of banks $60-$6F/$72-$FF), each CPU PC/GSU PBR:R15 once.
//   LEVEL=n: the game starts at level n (the WRAM word Level, from ROM.sym, reads n until the first
//     rendered frame)
#include <ares/ares.hpp>
#include <sfc/sfc.hpp>
#include <mia/mia.hpp>
#include <cstdio>
#include <map>
#include <vector>
#include <string>
namespace ares::SuperFamicom { extern void (*ares_gsu_read_hook)(u32, int); extern int ares_gsu_fetch; extern void (*ares_wram_write_hook)(u32, u8); extern void (*ares_io_read_hook)(u32, u32, u32, u8); extern FILE* ares_gsu_trace; extern long ares_gsu_trace_left; extern void (*ares_gsuram_hook)(int, u32, u8); }
using ares::SuperFamicom::ares_wram_write_hook;

static u64 g_frame = 0, g_rendered = 0, g_firstRender = 0;
static u32 g_level = 0x06D1; static int g_forceLevel = -1;
static u32 g_frameDone = 0x0033, g_exitGsu = 0x01E8, g_exitWram = 0x072E;   // (WRAM, GSU RAM, WRAM offsets)

// FrameDone, ExitLevel and ExitLevel's WRAM copy (RLSNESGSUXVars + ExitLevel - RLGSUXVars)
// from ROM.sym ("bb:aaaa name" lines)
static void readSymbols(const char* rom) {
  std::string p = rom; size_t d = p.rfind('.'); if(d != std::string::npos) p = p.substr(0, d); p += ".sym";
  FILE* f = fopen(p.c_str(), "r");
  if(!f) { fprintf(stderr, "%s missing: built-in FrameDone/ExitLevel addresses\n", p.c_str()); return; }
  std::map<std::string, u32> sym; char line[512], name[256]; unsigned b, a;
  while(fgets(line, sizeof line, f)) if(sscanf(line, "%x:%x %255s", &b, &a, name) == 3) sym[name] = b << 16 | a;
  fclose(f);
  if(sym.count("Level")) g_level = sym["Level"] & 0x1FFF;
  if(sym.count("FrameDone")) g_frameDone = sym["FrameDone"] & 0x1FFFF;
  if(sym.count("ExitLevel")) g_exitGsu = sym["ExitLevel"] & 0x1FFFF;
  if(sym.count("ExitLevel") && sym.count("RLGSUXVars") && sym.count("RLSNESGSUXVars"))
    g_exitWram = (sym["RLSNESGSUXVars"] + sym["ExitLevel"] - sym["RLGSUXVars"]) & 0x1FFFF;
}
static std::map<std::string, bool> g_buttons;

// ACCESSMAP (see the top)
static std::vector<u8> g_amap; static bool g_old = false; static std::map<u64, u32> g_viol;
static void violation(const char* who, u32 pc, u32 a) {
  u64 k = (u64)(who[0]) << 48 | (u64)pc << 24 | (a >> 16);
  if(g_viol[k]++ == 0 && g_viol.size() < 2000) fprintf(stderr, "VIOLATION f%llu %s pc %06X read %06X\n", (unsigned long long)g_frame, who, pc, a);
}
static void cpuRead(u32 a) {
  u32 b = a >> 16 & 0xFF, o = a & 0xFFFF;
  if(g_forceLevel >= 0 && !g_rendered && (o == g_level || o == g_level + 1) && ((b & 0x40) == 0 || b == 0x7E)) {
    ares::SuperFamicom::cpu.wram[g_level] = g_forceLevel; ares::SuperFamicom::cpu.wram[g_level + 1] = 0; }
  if(!g_amap.size()) return;
  if((b & 0x40) == 0) {                      // $00-$3F, $80-$BF
    if(o < 0x8000) return;                   // (WRAM, I/O, GSU RAM window)
    u32 f = (b & 0x3F) << 15 | (o & 0x7FFF);
    if(b & 0x80) { g_amap[f] |= 2; violation("CPU", (u32)ares::SuperFamicom::cpu.r.pc.d, a); } else g_amap[f] |= 1;
    return;
  }
  if(b >= 0x7E && b <= 0x7F) return;         // WRAM
  if((b & 0x7E) == 0x70) return;             // GSU RAM ($70-$71, $F0-$F1)
  if(g_old) {
    if((b & 0x60) == 0x40) g_amap[(b & 0x1F) << 16 | o] |= 2;
    else if(b >= 0xE0) g_amap[0x200000 + ((b - 0xE0) << 16 | o)] |= 2;
    else violation("CPU", (u32)ares::SuperFamicom::cpu.r.pc.d, a);
    return;
  }
  if((b & 0x60) == 0x40) g_amap[0x400000 + ((b & 0x1F) << 16 | o)] |= 2;
  violation("CPU", (u32)ares::SuperFamicom::cpu.r.pc.d, a);
}
static void gsuRead(u32 a, int fetch) {
  u32 b = a >> 16 & 0xFF, o = a & 0xFFFF;
  auto& r = ares::SuperFamicom::superfx.regs;
  u32 pc = (u32)r.pbr << 16 | (u32)r.r[15].data;
  if(b < 0x40) { u32 f = b << 15 | (o & 0x7FFF); g_amap[f] |= fetch ? 16 : 4; return; }
  if(b < 0x60) { u32 f = (g_old ? 0 : 0x400000) + ((b - 0x40) << 16 | o); g_amap[f] |= fetch ? 16 : 8; return; }
  if(b == 0x70 || b == 0x71) return;
  violation("GSU", pc, a);
}
static std::vector<u8> g_shot; static u32 g_w = 0, g_h = 0;

struct Headless : ares::Platform {
  std::shared_ptr<mia::Pak> game, system;
  ares::Node::System root;
  auto attach(ares::Node::Object) -> void override {}
  auto pak(ares::Node::Object node) -> std::shared_ptr<vfs::directory> override {
    if(node->name() == "Super Famicom") return system->pak;
    if(node->name() == "Super Famicom Cartridge") return game->pak;
    return {};
  }
  auto video(ares::Node::Video::Screen, const u32* data, u32 pitch, u32 width, u32 height) -> void override {
    g_w = width; g_h = height; g_shot.resize(width * height * 3);
    for(u32 y = 0; y < height; y++) for(u32 x = 0; x < width; x++) {
      u32 c = data[y * (pitch / 4) + x];
      g_shot[(y * width + x) * 3 + 0] = c >> 16; g_shot[(y * width + x) * 3 + 1] = c >> 8; g_shot[(y * width + x) * 3 + 2] = c;
    }
  }
  auto audio(ares::Node::Audio::Stream stream) -> void override {
    f64 buf[2]; while(stream->pending()) stream->read(buf);
  }
  auto input(ares::Node::Input::Input node) -> void override {
    if(auto b = node->cast<ares::Node::Input::Button>()) b->setValue(g_buttons[(const char*)node->name()]);
  }
};

static int run(int argc, char** argv) {
  if(argc < 4) { fprintf(stderr, "usage: ares-headless ROM FRAMES INPUT [SHOTS] [OUTDIR]\n"); return 2; }
  u64 frames = atoll(argv[2]);
  std::map<u64, std::vector<std::string>> script;
  { std::string s = argv[3]; size_t p = 0;
    while(p < s.size()) { size_t e = s.find(';', p); if(e == std::string::npos) e = s.size();
      std::string part = s.substr(p, e - p); size_t c = part.find(':');
      if(c != std::string::npos) { u64 f = atoll(part.substr(0, c).c_str()); std::string b = part.substr(c + 1); size_t q = 0;
        while(q <= b.size()) { size_t k = b.find(',', q); if(k == std::string::npos) k = b.size(); script[f].push_back(b.substr(q, k - q)); q = k + 1; } }
      p = e + 1; } }
  std::vector<u64> shots;
  if(argc > 4) { std::string s = argv[4]; size_t p = 0; while(p < s.size()) { size_t e = s.find(',', p); if(e == std::string::npos) e = s.size(); shots.push_back(atoll(s.substr(p, e - p).c_str())); p = e + 1; } }
  std::string outdir = argc > 5 ? argv[5] : ".", rom = argv[1];
  { char buf[4096]; if(realpath(outdir.c_str(), buf)) outdir = buf; if(realpath(argv[1], buf)) rom = buf; }   // (absolute: the cwd may change while loading)
  readSymbols(rom.c_str());

  ares::Memory::FixedAllocator::get();
  Headless h; ares::platform = &h;
  mia::setHomeLocation([] { return string{"/tmp/ares-headless/"}; });
  mia::setSaveLocation([] { return string{"/tmp/ares-headless/saves/"}; });
  h.game = mia::Medium::create("Super Famicom");
  auto r = h.game->load(rom.c_str());
  if(r != successful) { fprintf(stderr, "game load failed (%d)\n", (int)r.result); return 3; }
  h.system = mia::System::create("Super Famicom");
  r = h.system->load();
  if(r != successful) { fprintf(stderr, "system load failed (%d)\n", (int)r.result); return 3; }
  fprintf(stderr, "manifest:\n%s\n", (const char*)h.game->pak->attribute("board"));
  ares::SuperFamicom::option("Pixel Accuracy", true);
  ares::SuperFamicom::option("Deterministic Entropy", true);
  if(!ares::SuperFamicom::load(h.root, "[Nintendo] Super Famicom (NTSC)")) { fprintf(stderr, "core load failed\n"); return 3; }
  if(auto port = h.root->find<ares::Node::Port>("Cartridge Slot")) { port->allocate(); port->connect(); }
  if(auto port = h.root->find<ares::Node::Port>("Controller Port 1")) { port->allocate("Gamepad"); port->connect(); }
  if(getenv("PORT2_PAD")) if(auto port = h.root->find<ares::Node::Port>("Controller Port 2")) { port->allocate("Gamepad"); port->connect(); }
  h.root->power();

  ares_wram_write_hook = [](u32 a, u8 d) { if(getenv("WWATCH") && (a == 0xBD1 || a == 0xBD2 || a == 0xBCC) && d) fprintf(stderr, "f%llu wram %04X <- %02X\n", (unsigned long long)g_frame, a, d); if(a == g_frameDone && d) { if(!g_rendered) g_firstRender = g_frame; g_rendered++; } };
  if(getenv("IOLOG")) { static u64 from = atoll(getenv("IOLOG")), to = from + (getenv("IOLEN") ? atoll(getenv("IOLEN")) : 20);
    ares::SuperFamicom::ares_io_read_hook = [](u32 a, u32 v, u32 hc, u8 d) { if(g_frame >= from && g_frame < to) fprintf(stderr, "f%llu v%u h%u read %04X = %02X\n", (unsigned long long)g_frame, v, hc, a, d); }; }
  if(getenv("RWATCH")) ares::SuperFamicom::ares_gsuram_hook = [](int who, u32 a, u8 d) { static u32 w = strtoul(getenv("RWATCH"), 0, 16); if((a & ~1u) == w && g_frame > 1000) fprintf(stderr, "f%llu %s %05X %02X\n", (unsigned long long)g_frame, who == 0 ? "CPU write" : who == 1 ? "GSU write" : "GSU read", a, d); };
  if(getenv("LEVEL")) { g_forceLevel = atoi(getenv("LEVEL")); ares::SuperFamicom::ares_bus_read_hook = cpuRead; }
  if(getenv("ACCESSMAP")) { g_amap.assign(0x800000, 0); g_old = getenv("ACCESSMODE") && !strcmp(getenv("ACCESSMODE"), "old");
    ares::SuperFamicom::ares_bus_read_hook = cpuRead; ares::SuperFamicom::ares_gsu_read_hook = gsuRead; }
  std::map<std::string, u64> held;
  u64 r0 = 0, f0 = 0;
  for(g_frame = 0; g_frame < frames; g_frame++) {
    if(script.count(g_frame)) for(auto& b : script[g_frame]) {
      if(b == "EXIT") {   // DOOM-FX: finish the level (ExitLevel = 11 in GSU RAM and its WRAM copy)
        ares::SuperFamicom::superfx.ram.write(g_exitGsu, 11); ares::SuperFamicom::superfx.ram.write(g_exitGsu + 1, 0);
        ares::SuperFamicom::cpu.wram[g_exitWram] = 11; ares::SuperFamicom::cpu.wram[g_exitWram + 1] = 0; continue; }
      u64 hold = 6; std::string n = b; size_t at = b.find('@'); if(at != std::string::npos) { n = b.substr(0, at); hold = atoll(b.substr(at + 1).c_str()); }
      held[n] = g_frame + hold; }
    for(auto& [b, until] : held) g_buttons[b] = g_frame < until;
    if(getenv("GSUTRACE") && g_frame == (u64)atoll(getenv("GSUTRACE"))) { ares::SuperFamicom::ares_gsu_trace = fopen("/tmp/ares_gsu_trace.txt", "w"); ares::SuperFamicom::ares_gsu_trace_left = getenv("GSUTRACEN") ? atol(getenv("GSUTRACEN")) : 100000; }
    h.root->run();
    for(auto s : shots) if(s == g_frame) fprintf(stderr, "shot %llu w=%u h=%u\n", (unsigned long long)s, g_w, g_h);
    for(auto s : shots) if(s == g_frame && g_w) {
      char fn[512]; snprintf(fn, sizeof fn, "%s/ares_%05llu.ppm", outdir.c_str(), (unsigned long long)g_frame);
      FILE* f = fopen(fn, "wb"); fprintf(f, "P6 %u %u 255\n", g_w, g_h); fwrite(g_shot.data(), 1, g_shot.size(), f); fclose(f);
      snprintf(fn, sizeof fn, "%s/gsuram_%05llu.bin", outdir.c_str(), (unsigned long long)g_frame);
      f = fopen(fn, "wb"); fwrite(ares::SuperFamicom::superfx.ram.data(), 1, ares::SuperFamicom::superfx.ram.size(), f); fclose(f);
      snprintf(fn, sizeof fn, "%s/wram_%05llu.bin", outdir.c_str(), (unsigned long long)g_frame);
      f = fopen(fn, "wb"); fwrite(&ares::SuperFamicom::cpu.wram[0], 1, 128 * 1024, f); fclose(f);
      snprintf(fn, sizeof fn, "%s/apuram_%05llu.bin", outdir.c_str(), (unsigned long long)g_frame);
      f = fopen(fn, "wb"); fwrite(&ares::SuperFamicom::dsp.apuram[0], 1, 64 * 1024, f); fclose(f);
    }
    if(g_frame % 600 == 599) {
      printf("frame %llu: %llu rendered in the last 600 frames (%.2f fps, %.2f VBlanks per frame)\n", (unsigned long long)g_frame + 1,
        (unsigned long long)(g_rendered - r0), (g_rendered - r0) / 10.0, g_rendered > r0 ? 600.0 / (g_rendered - r0) : 0.0);
      fflush(stdout); r0 = g_rendered;
    }
  }
  printf("total: %llu emulated frames, %llu rendered (first at frame %llu)\n", (unsigned long long)frames, (unsigned long long)g_rendered, (unsigned long long)g_firstRender);
  if(getenv("ACCESSMAP")) { FILE* f = fopen(getenv("ACCESSMAP"), "wb"); fwrite(g_amap.data(), 1, g_amap.size(), f); fclose(f);
    u64 n = 0; for(auto& [k, c] : g_viol) n += c; fprintf(stderr, "access map: %zu distinct violations, %llu reads\n", g_viol.size(), (unsigned long long)n); }
  h.root->unload();
  return 0;
}

// (a plain main, not nall::main: nall's Arguments replace an existing directory argument by
// its parent, which put the OUTDIR files one directory up)
int main(int argc, char** argv) {
  int rc = run(argc, argv);
  fflush(stdout); return rc;
}
namespace nall { auto main(Arguments) -> void {} }   // (unused; nall's main.cpp, linked in, refers to it)
