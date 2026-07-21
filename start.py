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


def find_repository_root(start_dir):
    start_dir = os.path.abspath(start_dir)

    if os.path.exists(os.path.join(start_dir, "bot.py")) and os.path.isdir(os.path.join(start_dir, "GunSalesBot")):
        return start_dir

    for alt_name in ("GangBot_v2_real", "Bots"):
        alt_dir = os.path.join(start_dir, alt_name)
        if os.path.exists(os.path.join(alt_dir, "bot.py")) and os.path.isdir(os.path.join(alt_dir, "GunSalesBot")):
            return alt_dir

    for root, dirs, files in os.walk(start_dir):
        if "bot.py" in files and "GunSalesBot" in dirs:
            return root

    return start_dir


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    root = find_repository_root(script_dir)

    print(f"[STARTUP] start.py location: {script_dir}")
    print(f"[STARTUP] repository root: {root}")
    print(f"[STARTUP] root contents: {sorted(os.listdir(root))}")

    os.chdir(root)
    sys.path.insert(0, root)

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
