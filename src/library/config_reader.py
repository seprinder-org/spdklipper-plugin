"""
Config Reader for SPDKlipper Plugin
====================================
Reads the spdklipper.conf file (INI-style) to extract credentials
for auto-login on startup.

The config file path is passed via the -c / --config CLI argument.
Default search paths:
  1. Value from -c argument
  2. ./spdklipper.conf (current working directory)
  3. ../spdklipper.conf (project root relative to plugin/main.py)
"""

import configparser
import sys
import os
from pathlib import Path
from typing import Optional, Dict


# Default config filename
CONFIG_FILENAME = "spdklipper.conf"


def resolve_config_path(custom_path: Optional[str] = None) -> Optional[Path]:
    """
    Resolve the config file path with the following priority:
    1. Custom path from -c argument
    2. ./spdklipper.conf (current working directory)
    3. ../spdklipper.conf (project root relative to plugin/main.py)

    Returns None if no config file is found.
    """
    # Priority 1: Custom path from -c argument
    if custom_path:
        p = Path(custom_path)
        if p.exists() and p.is_file():
            return p.resolve()

    # Priority 2: Current working directory
    cwd_path = Path(os.getcwd()) / CONFIG_FILENAME
    if cwd_path.exists() and cwd_path.is_file():
        return cwd_path.resolve()

    # Priority 3: Project root (parent of plugin/ directory)
    script_dir = Path(__file__).resolve().parent.parent.parent
    project_path = script_dir / CONFIG_FILENAME
    if project_path.exists() and project_path.is_file():
        return project_path.resolve()

    return None


def read_credentials(config_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Read [credentials] section from spdklipper.conf.

    Returns a dict with keys: username, password, machine_id
    All values default to empty string if not found.
    """
    result = {
        'username': '',
        'password': '',
        'machine_id': '',
    }

    if config_path is None or not config_path.exists():
        return result

    try:
        config = configparser.ConfigParser()
        config.read(str(config_path))

        if config.has_section('credentials'):
            result['username'] = config.get('credentials', 'username', fallback='').strip()
            result['password'] = config.get('credentials', 'password', fallback='').strip()
            result['machine_id'] = config.get('credentials', 'machine_id', fallback='').strip()

    except Exception as e:
        print(f"[ConfigReader] Error reading config file {config_path}: {e}")

    return result


def read_server_config(config_path: Optional[Path] = None) -> Dict[str, str]:
    """
    Read [server] section from spdklipper.conf.

    Returns a dict with keys: host_server, host_connect
    Both default to empty string if not found (meaning use hardcoded defaults).
    """
    result = {
        'host_server': '',
        'host_connect': '',
    }

    if config_path is None or not config_path.exists():
        return result

    try:
        config = configparser.ConfigParser()
        config.read(str(config_path))

        if config.has_section('server'):
            result['host_server'] = config.get('server', 'host_server', fallback='').strip()
            result['host_connect'] = config.get('server', 'host_connect', fallback='').strip()

    except Exception as e:
        print(f"[ConfigReader] Error reading server config from {config_path}: {e}")

    return result


def has_valid_credentials(creds: Dict[str, str]) -> bool:
    """Check if both username and password are non-empty."""
    return bool(creds['username'] and creds['password'])


def parse_cli_args() -> Dict[str, Optional[str]]:
    """
    Parse CLI arguments for -c (config path) and -l (log path).

    Expected format:
        python plugin/main.py -c /path/to/spdklipper.conf -l /path/to/logfile

    Returns a dict with keys: config_path, log_path
    """
    args = {
        'config_path': None,
        'log_path': None,
    }

    i = 1
    while i < len(sys.argv):
        if sys.argv[i] in ('-c', '--config') and i + 1 < len(sys.argv):
            args['config_path'] = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] in ('-l', '--log') and i + 1 < len(sys.argv):
            args['log_path'] = sys.argv[i + 1]
            i += 2
        else:
            i += 1

    return args
