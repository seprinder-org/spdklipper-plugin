# SPD Klipper Plugin - Moonraker Custom Component
#
# This component fetches Machine Info (Machine ID, Connection Status, Last Seen)
# from the SPDKlipper plugin API and stores it in Klipper's save_variables
# for display via the SPD_MACHINE_INFO macro on Fluidd/Mainsail.
#
# Architecture:
#   SPDKlipper Plugin (/machine/info) → Moonraker machine_status component
#   (Python aiohttp, every 10s) → Klipper save_variables → SPD_MACHINE_INFO
#   macro (reads save_variables, displays via RESPOND) → Fluidd Macro Group
#
# Installation:
#   Copy this file to ~/moonraker/moonraker/components/machine_status.py
#   Add [machine_status] to moonraker.conf
#   Restart Moonraker: sudo systemctl restart moonraker
#
# Configuration (moonraker.conf):
#   [machine_status]
#   # Plugin API URL (default: http://127.0.0.1:1122)
#   # plugin_url: http://127.0.0.1:1122
#   # Refresh interval in seconds (default: 10)
#   # refresh_interval: 10

from __future__ import annotations
import json
import logging
import os

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from confighelper import ConfigHelper
    from webhooks import WebRequestManager

# Default plugin API URL (SPDKlipper plugin runs on port 1122 by default)
DEFAULT_PLUGIN_URL = "http://127.0.0.1:1122"
DEFAULT_REFRESH_INTERVAL = 10  # seconds
DB_NAMESPACE = "machine_info"

logger = logging.getLogger(__name__)


class MachineStatus:
    """Moonraker component that fetches SPD Machine Info and stores it in save_variables."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()

        # Read configuration
        self.plugin_url = config.get("plugin_url", DEFAULT_PLUGIN_URL).rstrip("/")
        self.refresh_interval = config.getint("refresh_interval", DEFAULT_REFRESH_INTERVAL)

        # Cached info
        self.cached_info = {
            "machine_id": "",
            "machine_name": "",
            "status": "disconnected",
            "connected": False,
            "last_seen": "",
            "timestamp": ""
        }

        # Register API endpoint
        self.server.register_endpoint(
            "/server/machine_status/info",
            ["GET"],
            self._handle_info_request
        )

        # Register event handlers
        self.server.register_event_handler("server_startup", self._handle_startup)
        self.server.register_event_handler("server_shutdown", self._handle_shutdown)

        logger.info(
            "Machine Status component loaded. Plugin URL: %s, Interval: %ds",
            self.plugin_url, self.refresh_interval
        )

    async def _handle_startup(self) -> None:
        """Start the periodic timer when Moonraker starts."""
        # Do an immediate fetch on startup
        await self._fetch_and_store()
        # Then register the periodic timer
        self.server.register_timer(self._check_status, self.refresh_interval)

    async def _handle_shutdown(self) -> None:
        """Handle shutdown."""
        pass

    async def _check_status(self, eventtime: float) -> float:
        """Periodically fetch machine info from the plugin API."""
        await self._fetch_and_store()
        return self.refresh_interval

    async def _fetch_and_store(self) -> None:
        """Fetch machine info from the plugin API and store it everywhere."""
        try:
            import aiohttp

            url = f"{self.plugin_url}/machine/info"
            logger.debug("Fetching machine info from %s", url)

            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=5) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        self.cached_info = {
                            "machine_id": data.get("machine_id", ""),
                            "machine_name": data.get("machine_name", ""),
                            "status": data.get("status", "disconnected"),
                            "connected": data.get("connected", False),
                            "last_seen": data.get("last_seen", ""),
                            "timestamp": data.get("timestamp", "")
                        }
                        logger.debug("Machine info fetched successfully: %s", self.cached_info)
                    else:
                        logger.warning("Plugin API returned status %d", resp.status)
                        self._set_disconnected()

        except Exception as e:
            logger.error("Failed to fetch machine info from plugin API: %s", e)
            self._set_disconnected()

        # Store to Moonraker database
        await self._update_database(self.cached_info)

        # Store to Klipper save_variables
        await self._update_save_variables(self.cached_info)

    def _set_disconnected(self) -> None:
        """Set cached info to disconnected state."""
        self.cached_info = {
            "machine_id": self.cached_info.get("machine_id", ""),
            "machine_name": self.cached_info.get("machine_name", ""),
            "status": "disconnected",
            "connected": False,
            "last_seen": self.cached_info.get("last_seen", ""),
            "timestamp": ""
        }

    def _format_timestamp(self, iso_timestamp: str) -> str:
        """Convert ISO timestamp to short display format (HH:MM:SS)."""
        if not iso_timestamp:
            return "--:--:--"
        try:
            ts = iso_timestamp
            if ts.endswith('Z'):
                ts = ts[:-1] + '+00:00'
            from datetime import datetime
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            return iso_timestamp[-8:] if len(iso_timestamp) >= 8 else iso_timestamp

    async def _update_database(self, info: dict) -> None:
        """Store machine info in Moonraker's database namespace."""
        try:
            db = self.server.lookup_component("database")
            if db:
                for key, value in info.items():
                    await db.insert_item(DB_NAMESPACE, key, value)
        except Exception as e:
            logger.debug("Database update skipped (non-critical): %s", e)

    async def _update_save_variables(self, info: dict) -> None:
        """
        Store machine info into Klipper's save_variables so the
        SPD_MACHINE_INFO macro can read it via printer.save_variables.variables.

        Uses SAVE_VARIABLE G-code command sent via Moonraker's internal API.
        """
        try:
            klipper_api = self.server.lookup_component("klippy_apis")

            # Build a compact JSON string for the variable
            var_value = json.dumps({
                "machine_id": info.get("machine_id", ""),
                "machine_name": info.get("machine_name", ""),
                "status": info.get("status", "disconnected"),
                "connected": info.get("connected", False),
                "last_seen": info.get("last_seen", ""),
                "last_seen_display": self._format_timestamp(info.get("last_seen", ""))
            })

            # Escape single quotes for G-code safety
            var_value_escaped = var_value.replace("'", "'\"'\"'")

            gcode = f"SAVE_VARIABLE VARIABLE=spd_machine_info VALUE='{var_value_escaped}'"
            await klipper_api.run_gcode(gcode)

            logger.debug("save_variables updated with machine info")
        except Exception as e:
            logger.error("Failed to update save_variables: %s", e)

    async def _handle_info_request(self, web_request: WebRequestManager) -> dict:
        """Handle GET /server/machine_status/info API request."""
        return self.cached_info


def load_component(config: ConfigHelper) -> MachineStatus:
    """Entry point for Moonraker to load this component."""
    return MachineStatus(config)
