# SPD Klipper Plugin - Moonraker Custom Component
#
# This component reads the SPD status file (spd_status.json) written by
# the SPD Klipper Plugin and displays the connection status on
# Fluidd/Mainsail using M117 (display message).
#
# Installation:
#   Copy this file to ~/moonraker/moonraker/components/spd_status.py
#   Add [spd_status] to moonraker.conf
#   Restart Moonraker: sudo systemctl restart moonraker
#
# How it works:
#   1. SPD Klipper Plugin writes ~/printer_data/config/spd_status.json
#      with machine_id and connection status
#   2. This component reads the file every 5 seconds
#   3. Sends M117 command to Klipper via Moonraker's internal API
#   4. Fluidd/Mainsail displays the message automatically

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

logger = logging.getLogger(__name__)


class SpdStatus:
    """Moonraker component that displays SPD connection status via M117."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.last_status = None
        self.last_machine_id = None
        self.last_message = ""

        # Register a timer to periodically check the status file
        self.server.register_event_handler("server_startup", self._handle_startup)
        self.server.register_event_handler("server_shutdown", self._handle_shutdown)

        logger.info("SPD Status component loaded. Monitoring: %s", SPD_STATUS_FILE)

    async def _handle_startup(self) -> None:
        """Start the periodic timer when Moonraker starts."""
        self.server.register_timer(self._check_status, REFRESH_INTERVAL)

    async def _handle_shutdown(self) -> None:
        """Clear the display message on shutdown."""
        await self._send_m117("")

    async def _check_status(self, eventtime: float) -> float:
        """Periodically check the status file and update M117 if changed."""
        try:
            if not os.path.exists(SPD_STATUS_FILE):
                if self.last_status is not None:
                    self.last_status = None
                    self.last_machine_id = None
                    await self._send_m117("SPD: Disconnected")
                return REFRESH_INTERVAL

            with open(SPD_STATUS_FILE, 'r') as f:
                data = json.load(f)

            is_connected = data.get("connected", False)
            machine_id = data.get("machine_id", "N/A")
            status_text = data.get("status", "unknown")

            # Only update if status changed
            if is_connected != self.last_status or machine_id != self.last_machine_id:
                self.last_status = is_connected
                self.last_machine_id = machine_id

                if is_connected:
                    message = f"SPD ID:{machine_id} | ACTIVE"
                else:
                    message = f"SPD ID:{machine_id} | INACTIVE"

                await self._send_m117(message)
                logger.debug("SPD status updated: %s", message)

        except Exception as e:
            logger.error("SPD Status error: %s", e)

        return REFRESH_INTERVAL

    async def _send_m117(self, message: str) -> None:
        """Send M117 command to Klipper via Moonraker's internal API."""
        if message == self.last_message:
            return  # Skip duplicate messages
        self.last_message = message

        try:
            # Use Moonraker's internal gcode API (no REST call needed)
            klipper_api = self.server.lookup_component("klippy_apis")
            await klipper_api.run_gcode(f"M117 {message}")
        except Exception as e:
            logger.error("Failed to send M117: %s", e)


def load_component(config: ConfigHelper) -> SpdStatus:
    """Entry point for Moonraker to load this component."""
    return SpdStatus(config)
