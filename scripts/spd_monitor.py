#!/usr/bin/env python3
"""
SPD Machine Info Monitor
========================
Lightweight Python script that polls the SPDKlipper plugin API
and displays Machine Info. Can be used as a standalone monitor
or integrated into other systems.

Usage:
    python3 spd_monitor.py                    # Continuous monitoring
    python3 spd_monitor.py --once             # Single check
    python3 spd_monitor.py --json             # JSON output (for scripts)
    python3 spd_monitor.py --watch            # Watch mode (like top)

Requirements:
    - requests (pip install requests)
    - SPDKlipper plugin running on localhost:1122
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime

try:
    import requests
except ImportError:
    print("ERROR: requests library not found. Install with: pip install requests")
    sys.exit(1)

SPD_API_URL = "http://localhost:1122/machine/info"
POLL_INTERVAL = 10  # seconds


def fetch_machine_info() -> dict:
    """Fetch Machine Info from SPDKlipper plugin API."""
    try:
        r = requests.get(SPD_API_URL, timeout=5)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        return {"error": "Cannot connect to SPDKlipper plugin at " + SPD_API_URL}
    except requests.exceptions.Timeout:
        return {"error": "Request timed out"}
    except requests.exceptions.RequestException as e:
        return {"error": str(e)}
    except json.JSONDecodeError:
        return {"error": "Invalid JSON response"}


def format_timestamp(iso_timestamp: str) -> str:
    """Convert ISO timestamp to readable format."""
    if not iso_timestamp:
        return "N/A"
    try:
        # Handle both 'Z' suffix and '+00:00' suffix
        if iso_timestamp.endswith('Z'):
            iso_timestamp = iso_timestamp[:-1] + '+00:00'
        dt = datetime.fromisoformat(iso_timestamp)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return iso_timestamp


def display_info(info: dict, compact: bool = False):
    """Display Machine Info in human-readable format."""
    if "error" in info:
        print(f"[ERROR] {info['error']}")
        return

    machine_id = info.get("machine_id", "N/A")
    status = info.get("status", "unknown")
    connected = info.get("connected", False)
    last_seen = format_timestamp(info.get("last_seen", ""))
    machine_name = info.get("machine_name", "")

    if compact:
        status_icon = "🟢" if connected else "🔴"
        print(f"{status_icon} [{machine_id}] {status.upper()} | Last: {last_seen}")
        return

    print("=" * 50)
    print("  SPD Machine Info")
    print("-" * 50)
    print(f"  Machine ID  : {machine_id}")
    if machine_name:
        print(f"  Machine Name: {machine_name}")
    status_display = "CONNECTED" if connected else "DISCONNECTED"
    print(f"  Status      : {status_display}")
    print(f"  Last Seen   : {last_seen}")
    print(f"  Timestamp   : {format_timestamp(info.get('timestamp', ''))}")
    print("=" * 50)


def watch_mode():
    """Continuously display Machine Info (like 'top' for SPD)."""
    try:
        while True:
            os.system('clear' if os.name == 'posix' else 'cls')
            print("SPD Machine Info Monitor (Ctrl+C to exit)")
            print(f"Polling: {SPD_API_URL}")
            print(f"Updated: {datetime.now().strftime('%H:%M:%S')}")
            print()

            info = fetch_machine_info()
            display_info(info, compact=False)

            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


def main():
    parser = argparse.ArgumentParser(
        description="SPD Machine Info Monitor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 spd_monitor.py              # Continuous monitoring
  python3 spd_monitor.py --once       # Single check
  python3 spd_monitor.py --json       # JSON output
  python3 spd_monitor.py --watch      # Watch mode
  python3 spd_monitor.py --compact    # Compact output
        """
    )
    parser.add_argument("--once", action="store_true", help="Single check only")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--watch", action="store_true", help="Watch mode (continuous)")
    parser.add_argument("--compact", action="store_true", help="Compact output")
    parser.add_argument("--interval", type=int, default=POLL_INTERVAL,
                        help=f"Poll interval in seconds (default: {POLL_INTERVAL})")

    args = parser.parse_args()

    if args.json:
        # JSON output - useful for scripts
        info = fetch_machine_info()
        print(json.dumps(info, indent=2))
        return

    if args.once:
        info = fetch_machine_info()
        display_info(info, compact=args.compact)
        return

    if args.watch:
        watch_mode()
        return

    # Default: continuous monitoring
    POLL_INTERVAL = args.interval
    try:
        while True:
            info = fetch_machine_info()
            now = datetime.now().strftime("%H:%M:%S")
            if "error" in info:
                print(f"[{now}] ERROR: {info['error']}")
            else:
                if args.compact:
                    display_info(info, compact=True)
                else:
                    display_info(info, compact=False)
            time.sleep(POLL_INTERVAL)
    except KeyboardInterrupt:
        print("\nMonitor stopped.")


if __name__ == "__main__":
    main()
