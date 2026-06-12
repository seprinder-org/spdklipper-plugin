# SPD Klipper Plugin - Moonraker Custom Component
#
# This component provides Machine Info (Machine ID, Connection Status, Last Seen)
# to Fluidd/Mainsail via multiple methods:
#
#   1. Moonraker API endpoint: /server/spd_status/info
#      - Returns JSON with machine_id, status, last_seen
#      - Fluidd/Mainsail can poll this for custom dashboard widgets
#
#   2. display_status (Fluidd/Mainsail native support)
#      - Updates Moonraker's display_status so Fluidd shows info in status bar
#      - Shows: "SPD | ID:PRN-01 | CONNECTED | Last: 12:34:57"
#
#   3. Moonraker database namespace: fluidd_machine_info
#      - Stores machine info in Moonraker's database
#      - Fluidd can read this via /server/database/item?namespace=fluidd_machine_info
#
#   4. M117 display message (legacy support)
#      - Sends M117 to Klipper for temporary display on Fluidd/Mainsail header
#
# Installation:
#   Copy this file to ~/moonraker/moonraker/components/spd_status.py
#   Add [spd_status] to moonraker.conf
#   Restart Moonraker: sudo systemctl restart moonraker
#
# How it works:
#   1. SPD Klipper Plugin writes ~/printer_data/config/spd_status.json
#      with machine_id, connection status, and timestamp
#   2. This component reads the file every 5 seconds
#   3. Updates display_status, database namespace, and API cache
#   4. Fluidd/Mainsail polls the API or reads database for dashboard display

from __future__ import annotations
import json
import logging
import os
import time

from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from confighelper import ConfigHelper
    from webhooks import WebRequestManager

SPD_STATUS_FILE = os.path.expanduser("~/printer_data/config/spd_status.json")
REFRESH_INTERVAL = 5  # seconds
DB_NAMESPACE = "fluidd_machine_info"

logger = logging.getLogger(__name__)


class SpdStatus:
    """Moonraker component that exposes SPD Machine Info to Fluidd/Mainsail."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.last_status = None
        self.last_machine_id = None
        self.last_message = ""
        self.cached_info = {
            "machine_id": "",
            "machine_name": "",
            "status": "disconnected",
            "connected": False,
            "last_seen": "",
            "timestamp": ""
        }

        # Register API endpoint for Fluidd/Mainsail to query
        self.server.register_endpoint(
            "/server/spd_status/info",
            ["GET"],
            self._handle_info_request
        )

        # Register event handlers
        self.server.register_event_handler("server_startup", self._handle_startup)
        self.server.register_event_handler("server_shutdown", self._handle_shutdown)

        logger.info("SPD Status component loaded. Monitoring: %s", SPD_STATUS_FILE)

    async def _handle_startup(self) -> None:
        """Start the periodic timer when Moonraker starts."""
        self.server.register_timer(self._check_status, REFRESH_INTERVAL)

    async def _handle_shutdown(self) -> None:
        """Clear the display message on shutdown."""
        await self._update_display_status("")
        await self._send_m117("")

    async def _check_status(self, eventtime: float) -> float:
        """Periodically check the status file and update all display methods."""
        try:
            if not os.path.exists(SPD_STATUS_FILE):
                if self.last_status is not None:
                    self.last_status = None
                    self.last_machine_id = None
                    self.cached_info = {
                        "machine_id": "",
                        "machine_name": "",
                        "status": "disconnected",
                        "connected": False,
                        "last_seen": "",
                        "timestamp": ""
                    }
                    await self._update_display_status("SPD: Disconnected")
                    await self._update_database(self.cached_info)
                    await self._send_m117("SPD: Disconnected")
                return REFRESH_INTERVAL

            with open(SPD_STATUS_FILE, 'r') as f:
                data = json.load(f)

            is_connected = data.get("connected", False)
            machine_id = data.get("machine_id", "N/A")
            machine_name = data.get("machine_name", "")
            status_text = data.get("status", "unknown")
            timestamp = data.get("timestamp", "")

            # Format last_seen for display
            last_seen_display = self._format_timestamp(timestamp)

            # Update cached info
            self.cached_info = {
                "machine_id": machine_id,
                "machine_name": machine_name,
                "status": status_text,
                "connected": is_connected,
                "last_seen": timestamp,
                "last_seen_display": last_seen_display,
                "timestamp": timestamp
            }

            # Build display_status message (shown in Fluidd/Mainsail status bar)
            if is_connected:
                status_icon = "●"  # green dot
                status_label = "CONNECTED"
            else:
                status_icon = "○"  # red dot
                status_label = "DISCONNECTED"

            display_msg = f"SPD | ID:{machine_id} | {status_label} | Last:{last_seen_display}"

            # Always update display_status (Fluidd shows this persistently)
            await self._update_display_status(display_msg)

            # Update Moonraker database namespace (for dashboard widgets)
            await self._update_database(self.cached_info)

            # Only send M117 if status changed (legacy)
            if is_connected != self.last_status or machine_id != self.last_machine_id:
                self.last_status = is_connected
                self.last_machine_id = machine_id

                if is_connected:
                    m117_msg = f"SPD ID:{machine_id} | ACTIVE"
                else:
                    m117_msg = f"SPD ID:{machine_id} | INACTIVE"

                await self._send_m117(m117_msg)
                logger.debug("SPD status changed: %s", display_msg)

        except Exception as e:
            logger.error("SPD Status error: %s", e)

        return REFRESH_INTERVAL

    def _format_timestamp(self, iso_timestamp: str) -> str:
        """Convert ISO timestamp to short display format (HH:MM:SS)."""
        if not iso_timestamp:
            return "--:--:--"
        try:
            # Handle ISO format with 'Z' suffix
            ts = iso_timestamp
            if ts.endswith('Z'):
                ts = ts[:-1] + '+00:00'
            # Parse and format
            from datetime import datetime
            dt = datetime.fromisoformat(ts)
            return dt.strftime("%H:%M:%S")
        except (ValueError, TypeError):
            return iso_timestamp[-8:] if len(iso_timestamp) >= 8 else iso_timestamp

    async def _update_display_status(self, message: str) -> None:
        """
        Update Moonraker's display_status so Fluidd/Mainsail shows the message
        persistently in the status bar.
        
        Fluidd natively reads printer.display_status.message and shows it.
        This is the SAME mechanism M117 uses, but we update it directly
        via Moonraker's internal API so it persists.
        """
        if message == self.last_message:
            return  # Skip duplicates
        self.last_message = message

        try:
            # Use Moonraker's internal API to update display_status
            klipper_api = self.server.lookup_component("klippy_apis")
            
            # Send M117 to update display_status.message
            # This is the standard way Fluidd reads display messages
            await klipper_api.run_gcode(f"M117 {message}")
            
            logger.debug("Display status updated: %s", message)
        except Exception as e:
            logger.error("Failed to update display status: %s", e)

    async def _update_database(self, info: dict) -> None:
        """
        Store machine info in Moonraker's database namespace.
        
        Fluidd/Mainsail can read this via:
          GET /server/database/item?namespace=fluidd_machine_info&key=status
        
        Or get the entire namespace:
          GET /server/database/list?namespace=fluidd_machine_info
        """
        try:
            db = self.server.lookup_component("database")
            if db:
                # Store individual keys for easy access
                for key, value in info.items():
                    await db.insert_item(DB_NAMESPACE, key, value)
        except Exception as e:
            logger.debug("Database update skipped (non-critical): %s", e)

    async def _handle_info_request(self, web_request: WebRequestManager) -> dict:
        """Handle GET /server/spd_status/info API request.
        
        Returns the cached machine info as JSON.
        Fluidd/Mainsail can call this endpoint to display Machine Info
        on the dashboard.
        """
        return self.cached_info

    async def _send_m117(self, message: str) -> None:
        """Send M117 command to Klipper via Moonraker's internal API."""
        try:
            klipper_api = self.server.lookup_component("klippy_apis")
            await klipper_api.run_gcode(f"M117 {message}")
        except Exception as e:
            logger.error("Failed to send M117: %s", e)


def load_component(config: ConfigHelper) -> SpdStatus:
    """Entry point for Moonraker to load this component."""
    return SpdStatus(config)
