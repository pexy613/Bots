import asyncio
import os
import subprocess
import sys


def run_command(command, cwd=None):
    result = subprocess.run(command, cwd=cwd, shell=True, capture_output=True, text=True)
    print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")
    if result.returncode != 0:
        raise SystemExit(f"Command failed with exit code {result.returncode}: {command}")


def main():
    root = os.path.dirname(os.path.abspath(__file__))
    os.chdir(root)

    if os.path.isdir(os.path.join(root, ".git")):
        print("[STARTUP] Pulling latest code from GitHub...")
        run_command("git pull origin main", cwd=root)

    print("[STARTUP] Installing dependencies...")
    run_command(f"{sys.executable} -m pip install -r requirements.txt", cwd=root)

    print("[STARTUP] Starting launcher.py...")
    from launcher import main as launcher_main
    asyncio.run(launcher_main())


if __name__ == "__main__":
    main()
