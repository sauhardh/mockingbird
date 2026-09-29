#!/usr/bin/env python3
"""
Birdss Unified Runner
Starts Backend (FastAPI :8000), RAG Service (:8005), and Frontend (Vite :8080)
with a single command and unified graceful shutdown on Ctrl+C.
"""

import os
import sys
import signal
import socket
import shutil
import subprocess
import threading
from pathlib import Path

# ANSI colors
RESET = "\033[0m"
BOLD = "\033[1m"
GREEN = "\033[32m"
CYAN = "\033[36m"
MAGENTA = "\033[35m"
YELLOW = "\033[33m"
RED = "\033[31m"

ROOT_DIR = Path(__file__).resolve().parent

SERVICES = [
    {
        "name": "Backend",
        "color": CYAN,
        "cwd": ROOT_DIR / "birdss_backend",
        "cmd": ["uv", "run", "uvicorn", "app:app", "--host", "127.0.0.1", "--port", "8000", "--reload"],
        "url": "http://127.0.0.1:8000",
    },
    {
        "name": "RAG",
        "color": MAGENTA,
        "cwd": ROOT_DIR / "birdss_backend" / "dataset" / "rag",
        "cmd": ["uv", "run", "python", "-u", "app.py"],
        "url": "http://127.0.0.1:8005",
        # Force CPU-only to prevent CUDA ApproximateClock assertion crash
        "env": {"CUDA_VISIBLE_DEVICES": "", "TOKENIZERS_PARALLELISM": "false"},
    },
    {
        "name": "Frontend",
        "color": GREEN,
        "cwd": ROOT_DIR / "Birdss",
        "cmd": ["npm", "run", "dev"],
        "url": "http://localhost:8080",
    },
]

processes = []
shutdown_event = threading.Event()


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def stream_logs(pipe, prefix: str):
    try:
        for line in iter(pipe.readline, ""):
            if shutdown_event.is_set() and not line:
                break
            # Strip trailing newline for clean output
            print(f"{prefix} {line.rstrip()}", flush=True)
    except Exception:
        pass
    finally:
        pipe.close()


def stop_all_processes(signum=None, frame=None):
    if shutdown_event.is_set():
        return
    shutdown_event.set()
    print(f"\n{YELLOW}[Runner] Stopping all services...{RESET}", flush=True)

    for p in processes:
        if p.poll() is None:
            try:
                if os.name == "nt":
                    p.terminate()
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGTERM)
            except Exception:
                pass

    # Wait for child processes with timeout
    for p in processes:
        try:
            p.wait(timeout=3)
        except subprocess.TimeoutExpired:
            try:
                if os.name == "nt":
                    p.kill()
                else:
                    os.killpg(os.getpgid(p.pid), signal.SIGKILL)
            except Exception:
                pass

    print(f"{GREEN}[Runner] All services stopped cleanly.{RESET}\n", flush=True)
    sys.exit(0)


def pre_flight_checks():
    # Check uv
    if not shutil.which("uv"):
        print(f"{RED}[Error] 'uv' is not installed or not in PATH.{RESET}")
        print("Please install uv: curl -LsSf https://astral.sh/uv/install.sh | sh")
        sys.exit(1)

    # Check npm
    if not shutil.which("npm") and not shutil.which("bun"):
        print(f"{RED}[Error] Neither 'npm' nor 'bun' found in PATH.{RESET}")
        sys.exit(1)

    # Check ports
    ports_to_check = [(8000, "Backend"), (8005, "RAG Service")]
    for port, name in ports_to_check:
        if is_port_in_use(port):
            print(f"{YELLOW}[Warning] Port {port} is already in use (needed by {name}).{RESET}")


def main():
    pre_flight_checks()

    # Register signal handlers
    signal.signal(signal.SIGINT, stop_all_processes)
    signal.signal(signal.SIGTERM, stop_all_processes)

    print(f"{BOLD}{GREEN}========================================{RESET}")
    print(f"{BOLD}{GREEN}  Starting Mockingbird / Birdss Services {RESET}")
    print(f"{BOLD}{GREEN}========================================{RESET}")
    print(f" {CYAN}• Backend:{RESET}   http://127.0.0.1:8000")
    print(f" {MAGENTA}• RAG API:{RESET}   http://127.0.0.1:8005")
    print(f" {GREEN}• Frontend:{RESET}  http://localhost:8080 (or see Vite log below)")
    print(f"{YELLOW}Press Ctrl+C at any time to stop all services.{RESET}\n")

    threads = []
    for svc in SERVICES:
        name = svc["name"]
        color = svc["color"]
        prefix = f"{color}[{name:<8}]{RESET}"

        # Setup process group on Unix so child subprocesses can be killed cleanly
        # Merge any per-service env overrides with the current process environment
        svc_env = os.environ.copy()
        svc_env.update(svc.get("env", {}))

        popen_kwargs = {
            "cwd": svc["cwd"],
            "stdout": subprocess.PIPE,
            "stderr": subprocess.STDOUT,
            "text": True,
            "bufsize": 1,
            "env": svc_env,
        }
        if os.name != "nt":
            popen_kwargs["preexec_fn"] = os.setsid

        p = subprocess.Popen(svc["cmd"], **popen_kwargs)
        processes.append(p)

        t = threading.Thread(target=stream_logs, args=(p.stdout, prefix), daemon=True)
        t.start()
        threads.append(t)

    # Monitor processes
    while not shutdown_event.is_set():
        for p in processes:
            ret = p.poll()
            if ret is not None and not shutdown_event.is_set():
                # One process exited unexpectedly
                stop_all_processes()
        try:
            signal.pause() if hasattr(signal, "pause") else threading.Event().wait(1)
        except (KeyboardInterrupt, SystemExit):
            stop_all_processes()


if __name__ == "__main__":
    main()
