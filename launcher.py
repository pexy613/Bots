"""
Unified launcher for all bots.
Starts GangBot, GunSalesBot, and RecruitBot concurrently.
"""

import asyncio
import sys
import os

# Add the workspace root to sys.path so we can import from subfolders
WORKSPACE_ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, WORKSPACE_ROOT)


async def start_gangbot():
    """Import and run GangBot."""
    try:
        print("[LAUNCHER] Starting GangBot...")
        from GangBot_v2_real.bot import main as gangbot_main
        await gangbot_main()
    except Exception as e:
        print(f"[LAUNCHER] ❌ GangBot failed to start: {e}")
        raise


async def start_gunsalesbot():
    """Import and run GunSalesBot."""
    try:
        print("[LAUNCHER] Starting GunSalesBot...")
        from GunSalesBot_upload.bot import async_main as gunsalesbot_main
        await gunsalesbot_main()
    except Exception as e:
        print(f"[LAUNCHER] ❌ GunSalesBot failed to start: {e}")
        raise


async def start_recruitbot():
    """Import and run RecruitBot."""
    try:
        print("[LAUNCHER] Starting RecruitBot...")
        from RecruitBot.bot import main as recruitbot_main
        await recruitbot_main()
    except ImportError:
        print("[LAUNCHER] ⚠️  RecruitBot not found locally. Skipping.")
    except Exception as e:
        print(f"[LAUNCHER] ❌ RecruitBot failed to start: {e}")
        raise


async def main():
    """Start all bots concurrently."""
    print("[LAUNCHER] 🚀 Starting bot launcher...")
    
    tasks = [
        asyncio.create_task(start_gangbot()),
        asyncio.create_task(start_gunsalesbot()),
        asyncio.create_task(start_recruitbot()),
    ]
    
    # Wait for all bots (continue if one fails)
    await asyncio.gather(*tasks, return_exceptions=True)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n[LAUNCHER] 🛑 Launcher interrupted.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[LAUNCHER] ❌ Launcher error: {e}")
        sys.exit(1)
