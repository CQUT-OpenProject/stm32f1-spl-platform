#!/usr/bin/env python3
"""Verify upstream files, then patch disposable build copies. SPDX-License-Identifier: MIT."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path


def verify_vendor(root):
    vendor = root / "vendor/st"
    manifest = json.loads((vendor / "manifest.json").read_text())
    for name, expected in manifest["files"].items():
        actual = hashlib.sha256((vendor / name).read_bytes()).hexdigest()
        if actual != expected:
            raise SystemExit(f"Upstream source changed: {name}")
    return vendor


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    root = args.root.resolve()
    vendor = verify_vendor(root)
    if args.output is None:
        print("Upstream source checksums verified")
        return
    output = args.output.resolve()
    if output == vendor or vendor in output.parents:
        raise SystemExit("Patched files must not be written into vendor/st")
    output.mkdir(parents=True, exist_ok=True)
    git = shutil.which("git")
    if git is None:
        raise SystemExit("git is required to apply compatibility patches")
    files = (
        ("Libraries/CMSIS/CM3/CoreSupport/core_cm3.c", "cmsis-compiler.patch"),
        ("Libraries/CMSIS/CM3/DeviceSupport/ST/STM32F10x/system_stm32f10x.c", "system-clock.patch"),
    )
    for source, patch in files:
        # Normalize only the generated copy. Original vendor bytes are preserved.
        destination = output / Path(source).name
        destination.write_bytes((vendor / source).read_text().encode("utf-8"))
        subprocess.run([git, "apply", "--no-index", "--whitespace=nowarn",
                        str(root / "patches" / patch)], cwd=output, check=True)


if __name__ == "__main__":
    main()
