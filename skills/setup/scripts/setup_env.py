#!/usr/bin/env python3
from __future__ import annotations

import argparse
import platform
import re
import shutil
import subprocess
import os
from pathlib import Path


def run(cmd: list[str]) -> tuple[int, str]:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    out = (proc.stdout or "") + (proc.stderr or "")
    return proc.returncode, out


def print_cmd(title: str, cmd: list[str]) -> None:
    print(f"\n== {title} ==")
    print("$ " + " ".join(cmd))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Install/check Maribro environment (host + export + runtime verification).",
    )
    parser.add_argument(
        "--probe-file",
        default="games/_template.html",
        help="Game file used to probe runtime verification.",
    )
    return parser.parse_args()


def linux_hint_for_missing_lib(lib: str) -> str:
    package_map = {
        "libasound.so.2": "libasound2",
        "libgbm.so.1": "libgbm1",
        "libnss3.so": "libnss3",
        "libatk-bridge-2.0.so.0": "libatk-bridge2.0-0",
        "libxkbcommon.so.0": "libxkbcommon0",
    }
    specific = package_map.get(lib)
    if specific:
        return f"sudo apt-get install -y {specific}"
    return (
        "sudo apt-get install -y libasound2 libgbm1 libnss3 "
        "libatk-bridge2.0-0 libxkbcommon0"
    )


def resolve_uv() -> str | None:
    direct = shutil.which("uv")
    if direct:
        return direct
    home_uv = Path.home() / ".local" / "bin" / "uv"
    if home_uv.exists():
        os.environ["PATH"] = f"{home_uv.parent}:{os.environ.get('PATH', '')}"
        return str(home_uv)
    return None


def ensure_uv() -> str | None:
    uv_bin = resolve_uv()
    if uv_bin:
        return uv_bin

    print("uv not found. Attempting install...")
    system = platform.system().lower()
    if system not in {"linux", "darwin"}:
        print(
            "ACTION_REQUIRED: uv is missing. Install uv from https://docs.astral.sh/uv/ "
            "then run this setup script again."
        )
        return None
    if not shutil.which("curl"):
        print(
            "ACTION_REQUIRED: uv is missing and `curl` is unavailable. Install curl, then run:\n"
            "curl -LsSf https://astral.sh/uv/install.sh | sh"
        )
        return None

    cmd = ["bash", "-lc", "curl -LsSf https://astral.sh/uv/install.sh | sh"]
    print_cmd("Install uv", cmd)
    code, out = run(cmd)
    print(out.strip())
    if code != 0:
        print(
            "\nACTION_REQUIRED: uv installation failed. Install manually from "
            "https://docs.astral.sh/uv/ then run this setup script again."
        )
        return None

    uv_bin = resolve_uv()
    if uv_bin:
        return uv_bin
    print(
        "\nACTION_REQUIRED: uv was installed but not found in PATH. "
        "Open a new shell or add ~/.local/bin to PATH, then run this script again."
    )
    return None


def main() -> int:
    args = parse_args()
    probe_file = Path(args.probe_file)
    if not probe_file.exists():
        print(f"ERROR: probe file not found: {probe_file}")
        return 2

    verifier = Path("skills/verify-game/scripts/verify.py")
    if not verifier.exists():
        print("ERROR: verifier not found at skills/verify-game/scripts/verify.py")
        return 2

    print("Maribro environment setup")
    print(f"Platform: {platform.system()} {platform.release()}")

    uv_bin = ensure_uv()
    if not uv_bin:
        return 1

    server_file = Path("backend/server.py")
    export_file = Path("backend/export.sh")
    if not server_file.exists():
        print("ERROR: missing backend/server.py")
        return 2
    if not export_file.exists():
        print("ERROR: missing backend/export.sh")
        return 2

    if not shutil.which("curl"):
        print(
            "ACTION_REQUIRED: `curl` is required for export/upload flow. "
            "Install curl, then run this setup script again."
        )
        return 1

    sync_core_cmd = [uv_bin, "sync", "--extra", "verify"]
    print_cmd("Install core + verifier deps", sync_core_cmd)
    code, out = run(sync_core_cmd)
    print(out.strip())
    if code != 0:
        print("\nACTION_REQUIRED: `uv sync --extra verify` failed. Resolve this first.")
        return 1

    host_import_cmd = [uv_bin, "run", "python3", "-c", "import backend.server; print('backend.server import OK')"]
    print_cmd("Host import check", host_import_cmd)
    code, out = run(host_import_cmd)
    print(out.strip())
    if code != 0:
        print("\nACTION_REQUIRED: host import check failed. Resolve backend/server.py issues, then retry.")
        return 1

    export_help_cmd = [str(export_file), "--help"]
    print_cmd("Export script check", export_help_cmd)
    code, out = run(export_help_cmd)
    print(out.strip())
    if code != 0:
        print("\nACTION_REQUIRED: backend/export.sh failed to run. Resolve and retry.")
        return 1

    install_browser_cmd = [uv_bin, "run", "playwright", "install", "chromium"]
    print_cmd("Install Playwright Chromium", install_browser_cmd)
    code, out = run(install_browser_cmd)
    print(out.strip())
    if code != 0:
        print("\nACTION_REQUIRED: Chromium install failed. Re-run the command above and fix errors.")
        return 1

    verify_cmd = [
        uv_bin,
        "run",
        "python3",
        "skills/verify-game/scripts/verify.py",
        str(probe_file),
    ]
    print_cmd("Runtime verification probe", verify_cmd)
    code, out = run(verify_cmd)
    print(out.strip())
    if code == 0:
        print("\nREADY: environment setup is working.")
        return 0

    missing_lib_match = re.search(r"browser runtime dependency missing:\s*([^\.\s]+)", out)
    if missing_lib_match:
        missing_lib = missing_lib_match.group(1)
        system = platform.system().lower()
        if system == "linux":
            cmd = linux_hint_for_missing_lib(missing_lib)
            print(
                f"\nACTION_REQUIRED: missing runtime library {missing_lib}.\n"
                f"Run: {cmd}\n"
                "Then run this setup script again."
            )
            return 1
        if system == "darwin":
            print(
                f"\nACTION_REQUIRED: missing runtime library {missing_lib}.\n"
                "On macOS, ensure Xcode Command Line Tools are installed (`xcode-select --install`) "
                "and re-run `uv run playwright install chromium`, then this setup script again."
            )
            return 1

    if "chromium binary is missing" in out:
        print(
            "\nACTION_REQUIRED: Chromium still missing. Run `uv run playwright install chromium`, "
            "then run this setup script again."
        )
        return 1

    print(
        "\nACTION_REQUIRED: runtime verification still fails for another reason. "
        "Inspect the probe output above and fix that issue, then run this setup script again."
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
