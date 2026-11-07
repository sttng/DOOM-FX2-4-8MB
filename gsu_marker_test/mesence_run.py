#!/usr/bin/env python3
"""Run the GSU v2 test ROM headless in the MesenCE core and print the result bytes.

usage: mesence_run.py <MesenCore.so> <rom.sfc> <home folder> [seconds]
The ROM keeps its 20 result bytes in WRAM $0100-$0113 (see marker.s, RES).
"""
import ctypes, sys, time

lib_path, rom, home = sys.argv[1], sys.argv[2], sys.argv[3]
secs = float(sys.argv[4]) if len(sys.argv) > 4 else 3.0

SNES_WORK_RAM = 15     # MemoryType::SnesWorkRam
GSU_WORK_RAM = 28      # MemoryType::GsuWorkRam
SNES_SAVE_RAM = 16     # MemoryType::SnesSaveRam

lib = ctypes.CDLL(lib_path)
lib.InitializeEmu.argtypes = [ctypes.c_char_p, ctypes.c_void_p, ctypes.c_void_p,
                              ctypes.c_bool, ctypes.c_bool, ctypes.c_bool, ctypes.c_bool]
lib.LoadRom.argtypes = [ctypes.c_char_p, ctypes.c_char_p]
lib.LoadRom.restype = ctypes.c_bool
lib.GetMemoryValue.argtypes = [ctypes.c_int, ctypes.c_uint32]
lib.GetMemoryValue.restype = ctypes.c_uint8
lib.GetMemorySize.argtypes = [ctypes.c_int]
lib.GetMemorySize.restype = ctypes.c_uint32
lib.GetMesenVersion.restype = ctypes.c_uint32
lib.IsRunning.restype = ctypes.c_bool

lib.InitDll()
lib.InitializeEmu(home.encode(), None, None, True, True, True, True)
v = lib.GetMesenVersion()
print(f"MesenCE core version {v >> 16}.{(v >> 8) & 0xFF}.{v & 0xFF}")
ok = lib.LoadRom(rom.encode(), None)
print("LoadRom:", ok, "running:", lib.IsRunning())
time.sleep(secs)

names = ["C1", "C2", "C3", "C4", "G1", "G2", "G3", "G4", "G5", "DONE", "ROMBR", "VCR",
         "R1", "R2", "R3", "R4", "R5", "R6", "B1", "B2"]
vals = [lib.GetMemoryValue(SNES_WORK_RAM, 0x100 + i) for i in range(len(names))]
for n, x in zip(names, vals):
    print(f"{n:6s} {x:02X}")
print("GsuWorkRam size:", hex(lib.GetMemorySize(GSU_WORK_RAM)),
      "SnesSaveRam size:", hex(lib.GetMemorySize(SNES_SAVE_RAM)))

lib.Stop()
lib.Release()
