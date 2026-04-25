#!/usr/bin/env python3
"""TaskMaster CLI — `tw` entry point."""
import os
import signal
import subprocess
import sys
import threading
import time
import webbrowser
import tomllib
from pathlib import Path


def _load_cfg() -> dict:
    for p in [Path.cwd() / "tw.toml", Path(__file__).parent / "tw.toml"]:
        if p.exists():
            with open(p, "rb") as f:
                return tomllib.load(f)
    return {}


def _kill_port(port: int) -> None:
    """Kill any process already listening on the given port."""
    try:
        if sys.platform == "win32":
            out = subprocess.check_output(
                "netstat -ano -p TCP", shell=True, text=True, stderr=subprocess.DEVNULL
            )
            for line in out.splitlines():
                parts = line.split()
                if len(parts) >= 5 and f":{port}" in parts[1] and parts[3] == "LISTENING":
                    pid = int(parts[4])
                    os.kill(pid, signal.SIGTERM)
                    time.sleep(0.4)
                    break
        else:
            out = subprocess.check_output(
                ["lsof", "-ti", f"TCP:{port}", "-sTCP:LISTEN"],
                text=True, stderr=subprocess.DEVNULL,
            )
            for pid_str in out.strip().splitlines():
                os.kill(int(pid_str), signal.SIGTERM)
            time.sleep(0.4)
    except Exception:
        pass


def main() -> None:
    cfg  = _load_cfg()
    port = cfg.get("server", {}).get("port", 7755)
    host = cfg.get("server", {}).get("host", "127.0.0.1")
    args = sys.argv[1:]

    if args:
        # Headless mode — no server needed
        from taskmaster import taskwarrior as tw
        from taskmaster.parser import parse_quick_add

        tw.BACKEND    = cfg.get("taskwarrior", {}).get("backend", "wsl")
        tw.WSL_DISTRO = cfg.get("taskwarrior", {}).get("wsl_distro", "")
        tw._build_cmd()

        cmd = args[0]
        if cmd == "add" and len(args) > 1:
            parsed = parse_quick_add(" ".join(args[1:]))
            tw.add(**parsed)
            print("Task added.")
        elif cmd == "done" and len(args) > 1:
            tw.done(int(args[1]))
            print(f"Task {args[1]} marked done.")
        else:
            print("Usage:")
            print("  tw                              — open dashboard")
            print("  tw add '!h Fix bug @work due:fri'")
            print("  tw done <ID>")
            sys.exit(1)
        return

    # Server + browser mode
    import uvicorn

    _kill_port(port)

    if cfg.get("server", {}).get("auto_open_browser", True):
        def _open():
            time.sleep(1.0)
            webbrowser.open(f"http://{host}:{port}")
        threading.Thread(target=_open, daemon=True).start()

    print(f"  TaskMaster  →  http://{host}:{port}")
    print("  Ctrl+C to stop.\n")
    uvicorn.run(
        "taskmaster.main:app",
        host=host,
        port=port,
        reload=cfg.get("server", {}).get("reload", False),
        log_level="warning",
    )


if __name__ == "__main__":
    main()
