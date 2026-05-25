#!/bin/bash
# This script uninstalls SPDKlipper plugin
set -eu

SYSTEMDDIR="/etc/systemd/system"
SPDKLIPPER_PLUGIN_ENV="${HOME}/spdklipper-plugin-env"
SPDKLIPPER_PLUGIN_DIR=$(dirname $(dirname "$(realpath $0)"))
SPDKLIPPER_PLUGIN_CONF="${HOME}/printer_data/config"
KLIPPER_LOGS_DIR="${HOME}/printer_data/logs"

echo "======================================================"
echo "   UNINSTALL SPDKLIPPER PLUGIN"
echo "======================================================"

# Confirmation prompt
confirm_uninstall() {
  local confirm=""
  echo -e "\nThis will remove all SPDKlipper plugin components including:"
  echo -e "  - Systemd services"
  echo -e "  - Python virtual environment (${SPDKLIPPER_PLUGIN_ENV})"
  echo -e "  - Configuration files (${SPDKLIPPER_PLUGIN_CONF}/spdklipper*.conf)"
  echo -e "  - Log files (${KLIPPER_LOGS_DIR}/spdklipper*)"
  echo -e "  - Sysctl configuration (/etc/sysctl.d/51-dmesg-restrict.conf)"
  echo -e "  - Sensitive files (.env, .env.enc, .env.enc.salt, db.sqlite3)"
  echo -e "\nThe project source directory (${SPDKLIPPER_PLUGIN_DIR}) will NOT be removed.\n"
  while [[ ! ($confirm =~ ^(?i)(y|n|no|yes)(?-i)$) ]]; do
    read -p "Are you sure you want to uninstall SPDKlipper plugin? (y/N): " -e -i "n" confirm
    case "${confirm}" in
      Y|y|Yes|yes)
        echo -e "###### > Yes"
        return 0;;
      N|n|No|no)
        echo -e "###### > No"
        warn_msg "Uninstall cancelled."
        exit 0;;
      *)
        echo -e "Invalid command!";;
    esac
  done
}

### set color variables
green=$(echo -en "\e[92m")
yellow=$(echo -en "\e[93m")
red=$(echo -en "\e[91m")
cyan=$(echo -en "\e[96m")
default=$(echo -en "\e[39m")

warn_msg(){
  echo -e "${red}<!!!!> $1${default}"
}
ok_msg(){
  echo -e "${green}>>>>>> $1${default}"
}

remove_all(){
  echo -e "Stopping services"

  # List and stop all spdklipper-plugin services
  services_list=($(sudo systemctl list-units -t service --full --no-legend 2>/dev/null | grep 'spdklipper-plugin' | awk '{print $1}' || true))
  if [ ${#services_list[@]} -eq 0 ]; then
    echo -e "No spdklipper-plugin services found."
  else
    echo -e "Found services: ${services_list[@]}"
    for service in "${services_list[@]}"
    do
      echo -e "Removing $service ..."
      sudo systemctl stop "$service" 2>/dev/null || true
      sudo systemctl disable "$service" 2>/dev/null || true
      sudo rm -f "$SYSTEMDDIR/$service"
      echo -e "Done!"
    done
  fi

  # Remove log files
  echo -e "Removing log files ..."
  rm -f "${KLIPPER_LOGS_DIR}/spdklipper"*
  echo -e "Done!"

  # Remove config files
  echo -e "Removing configuration files ..."
  rm -f "${SPDKLIPPER_PLUGIN_CONF}/spdklipper"*.conf
  echo -e "Done!"

  sudo systemctl daemon-reload
  sudo systemctl reset-failed

  ### remove SPDKlipper plugin VENV dir
  if [ -d "$SPDKLIPPER_PLUGIN_ENV" ]; then
    echo -e "Removing SPDKlipper plugin VENV directory ..."
    rm -rf "${SPDKLIPPER_PLUGIN_ENV}" && echo -e "Directory removed!"
  fi

  ### remove sysctl config created by install.sh
  if [ -f /etc/sysctl.d/51-dmesg-restrict.conf ]; then
    echo -e "Removing sysctl configuration ..."
    sudo rm -f /etc/sysctl.d/51-dmesg-restrict.conf
    sudo sysctl kernel.dmesg_restrict=1 2>/dev/null || true
    echo -e "Done!"
  fi

  ### remove sensitive files (.env, encrypted env, database)
  echo -e "Removing sensitive files ..."
  rm -f "${SPDKLIPPER_PLUGIN_DIR}/.env"
  rm -f "${SPDKLIPPER_PLUGIN_DIR}/.env.enc"
  rm -f "${SPDKLIPPER_PLUGIN_DIR}/.env.enc.salt"
  rm -f "${SPDKLIPPER_PLUGIN_DIR}/db.sqlite3"
  echo -e "Done!"

}

confirm_uninstall
remove_all

echo ""
echo "======================================================"
echo "  Uninstall complete."
echo "  Project source directory kept at: ${SPDKLIPPER_PLUGIN_DIR}"
echo "  To fully remove, delete it manually: rm -rf ${SPDKLIPPER_PLUGIN_DIR}"
echo "======================================================"
