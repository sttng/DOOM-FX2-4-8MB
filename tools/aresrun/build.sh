#!/bin/bash
# build.sh ARES_DIR : build the headless ares runner (main.cpp -> build-headless/headless/ares-headless)
# in an ares source tree (github.com/ares-emulator/ares) for speed/compatibility tests.  ares maps
# the 8 MB ROMs of this branch as GSU_4MB_LAYOUT_SPEC.md describes (its generic GSU-RAM board).
# Applies ares-probes.patch (probe hooks, no timing change: ROM reads of the CPU and the GSU for
# ACCESSMAP, GSU RAM accesses, I/O reads) and leaves the GUI (ruby, hiro, desktop-ui) out of the build.
set -e
A=$(cd "$1" && pwd); HERE=$(cd "$(dirname "$0")" && pwd)
cd "$A"
git apply --check "$HERE/ares-probes.patch" 2>/dev/null && git apply "$HERE/ares-probes.patch" || echo "(patch already applied?)"
mkdir -p headless && cp "$HERE/main.cpp" "$HERE/CMakeLists.txt" headless/
sed -e '/add_subdirectory(ruby)/d' -e '/add_subdirectory(hiro)/d' -e 's/add_subdirectory(desktop-ui)/add_subdirectory(headless)/' \
    -e '/add_subdirectory(.github)/d' CMakeLists.txt > CMakeLists.headless.txt
cp CMakeLists.txt CMakeLists.gui.txt; cp CMakeLists.headless.txt CMakeLists.txt
cmake -S . -B build-headless -G Ninja -DARES_CORES=sfc -DARES_SKIP_DEPS=ON -DENABLE_CCACHE=OFF -DENABLE_IPO=OFF \
      -DARES_ENABLE_CHD=OFF -DCMAKE_BUILD_TYPE=Release -Wno-dev
ninja -C build-headless ares-headless
cp CMakeLists.gui.txt CMakeLists.txt
mkdir -p build-headless/headless/Database && cp mia/Database/* build-headless/headless/Database/
echo "built $A/build-headless/headless/ares-headless"
