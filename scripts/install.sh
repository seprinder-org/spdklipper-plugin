#!/bin/bash
# This script installs SPDKlipper plugin
set -eu

SYSTEMDDIR="/etc/systemd/system"
SPDKLIPPER_PLUGIN_SERVICE="spdklipper-plugin.service"
SPDKLIPPER_PLUGIN_ENV="${HOME}/spdklipper-plugin-env"
SPDKLIPPER_PLUGIN_DIR=$(dirname $(dirname "$(realpath $0)"))
SPDKLIPPER_PLUGIN_LOG="${HOME}/printer_data/logs/spdklipper.log"
SPDKLIPPER_PLUGIN_CONF="${HOME}/printer_data/config"
KLIPPER_CONF_DIR="${HOME}/printer_data/config"
KLIPPER_LOGS_DIR="${HOME}/printer_data/logs"
CURRENT_USER=$(whoami)

### set color variables
green=$(echo -en "\e[92m")
yellow=$(echo -en "\e[93m")
red=$(echo -en "\e[91m")
cyan=$(echo -en "\e[96m")
default=$(echo -en "\e[39m")

# Helper functions
report_status() {
  echo -e "\n\n###### $1"
}
warn_msg(){
  echo -e "${red}<!!!!> $1${default}"
}
status_msg(){
  echo; echo -e "${yellow}###### $1${default}"
}
ok_msg(){
  echo -e "${green}>>>>>> $1${default}"
}

# Check if running as root (not recommended)
check_not_root() {
  if [ "$(id -u)" -eq 0 ]; then
    warn_msg "This script should NOT be run as root. Run as a regular user with sudo privileges."
    exit 1
  fi
}

# Check if sudo is available
check_sudo() {
  if ! command -v sudo &> /dev/null; then
    warn_msg "sudo is required but not installed. Please install sudo first."
    exit 1
  fi
  if ! sudo -n true 2>/dev/null; then
    warn_msg "This script requires sudo privileges. Please ensure you have sudo access."
  fi
}

# Check if running on a Debian-based system
check_os() {
  if [ ! -f /etc/debian_version ]; then
    warn_msg "This script is designed for Debian-based systems (Raspberry Pi OS / Ubuntu)."
    warn_msg "Detected OS may not be compatible. Proceed at your own risk."
    local proceed=""
    while [[ ! ($proceed =~ ^(?i)(y|n|no|yes)(?-i)$) ]]; do
      read -p "Continue anyway? (y/N): " -e -i "n" proceed
      case "${proceed}" in
        Y|y|Yes|yes) break;;
        N|n|No|no) exit 1;;
        *) warn_msg "Invalid command!";;
      esac
    done
  fi
}

# Main functions
init_config_path() {
  report_status "SPDKlipper plugin configuration file location selection"
  echo -e "\n"
  echo "Enter the path for the configuration files location. Subfolders for multiple instances wil be created under this path."
  echo "Its recommended to store it together with the klipper configuration for easier backup and usage."
  read -p "Enter desired path: " -e -i "${KLIPPER_CONF_DIR}" klip_conf_dir
  KLIPPER_CONF_DIR=${klip_conf_dir}

  if ! [ -z ${LPATH+x} ]; then
    KLIPPER_LOGS_DIR=${LPATH}
  fi

  report_status "Plugin configuration file will be located in ${KLIPPER_CONF_DIR}"
}

create_initial_config() {
  if [[ $INSTANCE_COUNT -eq 1 ]]; then
    SPDKLIPPER_PLUGIN_CONF=${KLIPPER_CONF_DIR}
    # check in config exists!
    if [[ ! -f "${SPDKLIPPER_PLUGIN_CONF}"/spdklipper.conf ]]; then
      report_status "Creating base config file"
      if [[ ! -f "${SPDKLIPPER_PLUGIN_DIR}"/scripts/base_install_template ]]; then
        warn_msg "Base install template not found at ${SPDKLIPPER_PLUGIN_DIR}/scripts/base_install_template"
        return 1
      fi
      cp -n "${SPDKLIPPER_PLUGIN_DIR}"/scripts/base_install_template "${SPDKLIPPER_PLUGIN_CONF}"/spdklipper.conf

    fi

    create_service
    ok_msg "Single Spdklipper plugin instance created!"

  else
    manual_paths=""
    while [[ ! ($manual_paths =~ ^(?i)(y|n|no|yes)(?-i)$) ]]; do
      read -p "Use automatic paths? (Y/n): " -e -i y manual_paths
      case "${manual_paths}" in
        Y|y|Yes|yes)
          echo -e "###### > Yes"
          manual_paths="y"
          break;;
        N|n|No|no)
          echo -e "###### > No"
          manual_paths="n"
          break;;
        *)
          warn_msg "Invalid command!";;
      esac
    done
    i=1
    while [[ $i -le $INSTANCE_COUNT ]]; do
      ### rewrite default variables for multi instance cases
      if [ "${manual_paths}" == "n" ]; then
        report_status "SPDKlipper plugin instance name selection for instance ${i}"
        read -p "Enter plugin instance name: " -e -i "printer_${i}" instance_name
        SPDKLIPPER_PLUGIN_SERVICE="spdklipper-plugin-${instance_name}.service"
        SPDKLIPPER_PLUGIN_CONF="${KLIPPER_CONF_DIR}/${instance_name}"
        SPDKLIPPER_PLUGIN_LOG="${KLIPPER_LOGS_DIR}/spdklipper-${instance_name}.log"
      else
        SPDKLIPPER_PLUGIN_SERVICE="spdklipper-plugin-$i.service"
        SPDKLIPPER_PLUGIN_CONF="${KLIPPER_CONF_DIR}/printer_$i"
        SPDKLIPPER_PLUGIN_LOG="${KLIPPER_LOGS_DIR}/spdklipper-$i.log"
      fi

      report_status "Creating base config file"
      mkdir -p "${SPDKLIPPER_PLUGIN_CONF}"
      if [[ ! -f "${SPDKLIPPER_PLUGIN_DIR}"/scripts/base_install_template ]]; then
        warn_msg "Base install template not found at ${SPDKLIPPER_PLUGIN_DIR}/scripts/base_install_template"
        return 1
      fi
      cp -n "${SPDKLIPPER_PLUGIN_DIR}"/scripts/base_install_template "${SPDKLIPPER_PLUGIN_CONF}"/spdklipper.conf
      mkdir -p "${KLIPPER_LOGS_DIR}"
      create_service
      ### raise values by 1
      i=$((i+1))
    done
    unset i
  fi
}

#Todo: stop multiple?
stop_service() {
  serviceName="spdklipper-plugin"
  if sudo systemctl --all --type service --no-legend | grep "$serviceName" | grep -q running; then
    ## stop existing instance
    report_status "Stopping spdklipper-plugin instance ..."
    sudo systemctl stop spdklipper-plugin*
  else
    report_status "$serviceName service does not exist or is not running."
  fi
}

install_packages() {
  PKGLIST=""
  report_status "Running apt-get update..."
  sudo apt-get update --allow-releaseinfo-change
  PKGLIST="python3-virtualenv python3-numpy libuv1t64 ffmpeg x264 libx264-dev libjpeg*-turbo libwebp-dev"
  report_status "Installing packages..."
  sudo apt-get install --yes ${PKGLIST}
}

fix_permissions() {
  echo "kernel.dmesg_restrict = 0" | sudo tee /etc/sysctl.d/51-dmesg-restrict.conf > /dev/null
  sudo sysctl kernel.dmesg_restrict=0
}

# Secure sensitive files by restricting permissions to owner-only.
# This prevents other users/processes on the Raspberry Pi from reading
# your .env (which contains HOST_CONNECT, HOST_SERVER) and db.sqlite3
# (which contains encrypted access/refresh tokens).
secure_sensitive_files() {
  report_status "Securing sensitive file permissions..."

  # .env file: owner read/write only (prevents other users from reading secrets)
  if [ -f "${SPDKLIPPER_PLUGIN_DIR}/.env" ]; then
    chmod 600 "${SPDKLIPPER_PLUGIN_DIR}/.env"
    ok_msg ".env permissions set to 600 (owner read/write only)"
  fi

  # .env.example is safe (no real secrets), leave as default

  # Database file (will be created on first run, but secure it if it exists)
  local db_path="${SPDKLIPPER_PLUGIN_DIR}/db.sqlite3"
  if [ -f "$db_path" ]; then
    chmod 600 "$db_path"
    ok_msg "db.sqlite3 permissions set to 600 (owner read/write only)"
  fi

  # Project config directory
  if [ -d "${SPDKLIPPER_PLUGIN_CONF}" ]; then
    chmod 700 "${SPDKLIPPER_PLUGIN_CONF}"
    ok_msg "Config directory permissions set to 700 (owner only)"
  fi

  # Detection model directory (contains downloaded ONNX models)
  # local detection_dir="${SPDKLIPPER_PLUGIN_DIR}/detection"
  # if [ -d "$detection_dir" ]; then
  #   chmod -R 700 "$detection_dir"
  #   ok_msg "Detection directory permissions set to 700 (owner only)"
  # fi

  # Secure the encrypted env salt file if it exists
  if [ -f "${SPDKLIPPER_PLUGIN_DIR}/.env.enc.salt" ]; then
    chmod 600 "${SPDKLIPPER_PLUGIN_DIR}/.env.enc.salt"
    ok_msg ".env.enc.salt permissions set to 600"
  fi

  report_status "File permission hardening complete."
}

create_virtualenv() {
  report_status "Installing python virtual environment..."

  ### If venv exists and user prompts a rebuild, then do so
  if [ -d "$SPDKLIPPER_PLUGIN_ENV" ]; then
    status_msg "SPDKlipper plugin python virtualenv already exists."
    REBUILD_VENV=""
    while [[ ! ($REBUILD_VENV =~ ^(?i)(y|n|no|yes)(?-i)$) ]]; do
      read -p "Rebuild python virtualenv? (Y/n): " -e -i "y" REBUILD_VENV
      case "${REBUILD_VENV}" in
        Y|y|Yes|yes)
          echo -e "###### > Yes"
          echo "Removing old virtualenv"
          rm -rf "$SPDKLIPPER_PLUGIN_ENV"
          break;;
        N|n|No|no)
          echo -e "###### > No"
          break;;
        *)
          warn_msg "Invalid command!";;
      esac
    done
  fi

  mkdir -p "${HOME}"/space
  virtualenv -p /usr/bin/python3 --system-site-packages "${SPDKLIPPER_PLUGIN_ENV}"
  export TMPDIR=${HOME}/space
  "${SPDKLIPPER_PLUGIN_ENV}"/bin/pip install --no-cache-dir -r "${SPDKLIPPER_PLUGIN_DIR}"/scripts/requirements.txt
}

create_service() {
  ### create systemd service file
  sudo /bin/sh -c "cat > ${SYSTEMDDIR}/${SPDKLIPPER_PLUGIN_SERVICE}" <<EOF
#Systemd service file for SPDKlipper plugin
[Unit]
Description=Starts SPDKlipper Plugin on startup
After=network-online.target moonraker.service

[Install]
WantedBy=multi-user.target

[Service]
Type=simple
User=${CURRENT_USER}
ExecStart=${SPDKLIPPER_PLUGIN_ENV}/bin/python ${SPDKLIPPER_PLUGIN_DIR}/plugin/main.py -c ${SPDKLIPPER_PLUGIN_CONF}/spdklipper.conf -l ${SPDKLIPPER_PLUGIN_LOG}
Restart=always
RestartSec=5
EOF

  ### enable instance
  sudo systemctl enable ${SPDKLIPPER_PLUGIN_SERVICE}
  report_status "${SPDKLIPPER_PLUGIN_SERVICE} instance created!"

  ### launching instance
  report_status "Launching spdklipper-plugin instance ..."
  sudo systemctl start ${SPDKLIPPER_PLUGIN_SERVICE}
}


install_instances(){
  INSTANCE_COUNT=$1

  sudo systemctl stop spdklipper-plugin* || true
  status_msg "Installing dependencies"
  install_packages
  fix_permissions
  create_virtualenv

  init_config_path
  create_initial_config

  # Secure sensitive files after installation
  secure_sensitive_files

}

setup_dialog(){
    ### count amount of moonraker services
    SERVICE_FILES=$(find "$SYSTEMDDIR" -regextype posix-extended -regex "$SYSTEMDDIR/spdklipper-plugin(-[a-zA-Z0-9]+)*.service" 2>/dev/null || true)
    if [ -f /etc/init.d/moonraker ] || [ -f /etc/systemd/system/moonraker.service ]; then
      MOONRAKER_COUNT=1
    elif [ -n "$SERVICE_FILES" ]; then
      MOONRAKER_COUNT=$(echo "$SERVICE_FILES" | wc -l)
    else
      MOONRAKER_COUNT=0
    fi

    echo -e "/=======================================================\\"
    if [[ $MOONRAKER_COUNT -eq 0 ]]; then
      printf "|${yellow}%-55s${default}|\n" " No Moonraker instance was found!"
    elif [[ $MOONRAKER_COUNT -eq 1 ]]; then
      printf "|${green}%-55s${default}|\n" " 1 Moonraker instance was found!"
    elif [[ $MOONRAKER_COUNT -gt 1 ]]; then
      printf "|${green}%-55s${default}|\n" "${MOONRAKER_COUNT} Moonraker instances were found!"
    else
      echo -e "| ${yellow}INFO: No existing Moonraker installation found!${default}        |"
      init_config_path
    fi
    echo -e "| Usually you need one SPDKlipper plugin instance per Moonraker   |"
    echo -e "| instance. Though you can install as many as you wish. |"
    echo -e "\=======================================================/"
    echo
    count=""
    while [[ ! ($count =~ ^[1-9]+((0)+)?$) ]]; do
      read -p "${cyan}###### Number of SPDKlipper plugin instances to set up:${default} " count
      if [[ ! ($count =~ ^[1-9]+((0)+)?$) ]]; then
        echo -e "Invalid Input!\n"
      else
        echo
        read -p "${cyan}###### Install $count instance(s)? (Y/n):${default} " yn
        case "$yn" in
          Y|y|Yes|yes|"")
            echo -e "###### > Yes"
            status_msg "Installing SPDKlipper plugin ...\n"
            install_instances "$count"
            break;;
          N|n|No|no)
            echo -e "###### > No"
            warn_msg "Exiting SPDKlipper plugin setup ...\n"
            break;;
          *)
            warn_msg "Invalid command!";;
        esac
      fi
    done
}


# --- Main execution ---
check_not_root
check_sudo
check_os
setup_dialog
