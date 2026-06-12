# SPD Machine Info - Klipper extra module
#
# Reads spd_status.json (written by the SPDKlipper plugin) and exposes
# machine_id, machine_name, and connection status to Klipper's printer
# objects. Fluidd/Mainsail will automatically display these values.
#
# Installation:
#   1. Copy to Klipper's extras directory:
#      cp spd_machine_info.py ~/klipper/klippy/extras/spd_machine_info.py
#
#   2. Add to printer.cfg:
#      [spd_machine_info]
#
#   3. Restart Klipper
#
# Usage in macros:
#   {printer["spd_machine_info"].machine_id}
#   {printer["spd_machine_info"].status}
#   {printer["spd_machine_info"].connected}

import json
import logging
import os

STATUS_FILE = os.path.expanduser("~/printer_data/config/spd_status.json")
REFRESH_INTERVAL = 5.0


class SPDMachineInfo:
    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.name = config.get_name().split()[-1]

        # Default values
        self.machine_id = "N/A"
        self.machine_name = ""
        self.status = "disconnected"
        self.connected = False

        # Register event handler
        self.printer.register_event_handler("klippy:ready", self._handle_ready)

        # Register this object so macros can read it
        self.printer.add_object("spd_machine_info", self)

        # Register gcode command
        self.gcode = self.printer.lookup_object("gcode")
        self.gcode.register_mux_command(
            "SPD_MACHINE_INFO",
            "INFO",
            None,
            self.cmd_SPD_MACHINE_INFO,
            desc=self.cmd_SPD_MACHINE_INFO_help,
        )

    cmd_SPD_MACHINE_INFO_help = "Display SPD Machine Info"

    def cmd_SPD_MACHINE_INFO(self, gcmd):
        """Display machine info via RESPOND."""
        server_name = "N/A"
        try:
            server_name = self.printer.lookup_object("system_stats").sysname
        except Exception:
            pass

        icon = "●" if self.connected else "○"
        status_label = "CONNECTED" if self.connected else "DISCONNECTED"

        gcmd.respond_info("========================================")
        gcmd.respond_info("  SPD Machine Info")
        gcmd.respond_info("----------------------------------------")
        gcmd.respond_info(f"  Machine ID  : {self.machine_id}")
        gcmd.respond_info(f"  Name        : {self.machine_name}")
        gcmd.respond_info(f"  Status      : {icon} {status_label}")
        gcmd.respond_info(f"  Server      : {server_name}")
        gcmd.respond_info("========================================")

    def _handle_ready(self):
        """Start periodic file check when Klipper is ready."""
        self.reactor.register_timer(self._refresh_data, self.reactor.NOW)

    def _refresh_data(self, eventtime):
        """Read spd_status.json and update values."""
        try:
            if os.path.exists(STATUS_FILE):
                with open(STATUS_FILE, 'r') as f:
                    data = json.load(f)
                self.machine_id = data.get("machine_id", "N/A") or "N/A"
                self.machine_name = data.get("machine_name", "") or ""
                self.connected = data.get("connected", False)
                self.status = data.get("status", "disconnected") or "disconnected"
            else:
                logging.debug("SPD Machine Info: status file not found")
        except Exception as e:
            logging.warning("SPD Machine Info: error reading file: %s", str(e))

        return eventtime + REFRESH_INTERVAL

    def get_status(self, eventtime):
        """Return current status for Klipper's API (read by Fluidd/Mainsail)."""
        return {
            "machine_id": self.machine_id,
            "machine_name": self.machine_name,
            "status": self.status,
            "connected": self.connected,
        }


def load_config(config):
    return SPDMachineInfo(config)
