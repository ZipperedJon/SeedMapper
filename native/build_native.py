"""Compile cubiomes + the SeedMapper interface into cubiomes.dll using ziglang.

Run:  .venv\\Scripts\\python.exe native\\build_native.py

The output DLL is written to seedmapper/lib/cubiomes.dll and is loaded at
runtime by seedmapper/engine.py.
"""

import glob
import os
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
CUB = os.path.join(HERE, "cubiomes")
OUT_DIR = os.path.join(ROOT, "seedmapper", "lib")
OUT = os.path.join(OUT_DIR, "cubiomes.dll")


def main() -> int:
    os.makedirs(OUT_DIR, exist_ok=True)
    sources = [os.path.join(HERE, "sm_interface.c")]
    sources += sorted(glob.glob(os.path.join(CUB, "*.c")))

    cmd = [
        sys.executable, "-m", "ziglang", "cc",
        "-O2",
        "-shared",
        "-fno-sanitize=undefined",   # cubiomes relies on defined wraparound
        "-I", CUB,
        "-o", OUT,
        *sources,
        "-lm",
    ]
    print("Compiling", len(sources), "C files ->", OUT)
    subprocess.check_call(cmd)
    size = os.path.getsize(OUT)
    print(f"OK: {OUT} ({size/1024:.0f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
