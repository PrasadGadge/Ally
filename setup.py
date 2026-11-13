#!/usr/bin/env python3
"""
Setup script for Vivie.
  python setup.py          # core dependencies (recommended)
  python setup.py --full   # core + optional (automation, vision, torch)
"""

import argparse
import subprocess
import sys


def check_python_version() -> None:
    if sys.version_info < (3, 10):
        print(f"Python 3.10+ recommended. You have {sys.version}")
        if sys.version_info < (3, 8):
            sys.exit(1)
    print(f"Python {sys.version_info.major}.{sys.version_info.minor}")


def install_file(path: str) -> bool:
    print(f"\nInstalling from {path}...")
    try:
        subprocess.run(
            [sys.executable, "-m", "pip", "install", "-r", path],
            check=True,
        )
        print(f"OK: {path}")
        return True
    except subprocess.CalledProcessError:
        print(f"FAILED: {path}")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="Install Vivie dependencies")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Install optional packages (automation, vision, torch)",
    )
    args = parser.parse_args()

    print("Setting up Vivie\n")
    check_python_version()

    ok = install_file("requirements-core.txt")
    if args.full:
        ok = install_file("requirements-optional.txt") and ok

    if not ok:
        print("\nSetup incomplete. Fix pip errors and retry.")
        sys.exit(1)

    print("\nRun: python validate_deps.py")
    print("Then: python validate_deps.py --health")
    print("Then: python Vivie.py")


if __name__ == "__main__":
    main()
