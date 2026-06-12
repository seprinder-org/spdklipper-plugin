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

  # Check if libuv1t64 package exists in repository, otherwise fallback to libuv1
  local libuv_pkg="libuv1"
  if apt-cache show libuv1t64 &>/dev/null; then
    libuv_pkg="libuv1t64"
  fi

  PKGLIST="python3-virtualenv python3-numpy ${libuv_pkg} ffmpeg x264 libx264-dev libjpeg*-turbo libwebp-dev"
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


add_update_manager_config() {
  # Add Moonraker update manager configuration for SPDKlipper plugin.
  # This allows Klipper's update manager (Fluidd/Mainsail) to automatically
  # git pull and restart the plugin when updates are available.
  #
  # The config is appended to moonraker.conf if not already present.
  local moonraker_conf="${KLIPPER_CONF_DIR}/moonraker.conf"

if [ ! -f "$moonraker_conf" ]; then
  warn_msg "moonraker.conf not found at ${moonraker_conf}. Skipping update manager config."
  return 0
fi

# Check if update manager config already exists
if grep -q "\[update_manager client ${SPDKLIPPER_PLUGIN_SERVICE%.*}\]" "$moonraker_conf"; then
  ok_msg "Update manager config already exists in moonraker.conf. Skipping."
  return 0
fi

report_status "Adding update manager config to moonraker.conf..."

cat >> "$moonraker_conf" <<EOF

# SPDKlipper plugin update manager
[update_manager client ${SPDKLIPPER_PLUGIN_SERVICE%.*}]
type: git_repo
path: ${SPDKLIPPER_PLUGIN_DIR}
primary_branch: master
origin: https://github.com/seprinder-org/spdklipper-plugin.git
env: ${SPDKLIPPER_PLUGIN_ENV}/bin/python
requirements: scripts/requirements.txt
install_script: scripts/install.sh
EOF

ok_msg "Update manager config added to moonraker.conf"
report_status "NOTE: You may need to restart Moonraker for the changes to take effect:"
report_status "  sudo systemctl restart moonraker"
}


add_restart_macro() {
  # Add RESTART_SPDK and FIRMWARE_RESTART+ macros to printer.cfg
  # and configure Moonraker authorization.
  #
  # RESTART_SPDK: Standalone macro to restart the SPDKlipper plugin service
  #   from the Klipper console (Fluidd/Mainsail) via Moonraker API.
  #
  # FIRMWARE_RESTART+: Overrides the default FIRMWARE_RESTART so that
  #   clicking "Restart Firmware" in Fluidd/Mainsail also restarts the
  #   SPDKlipper plugin service automatically.
  local printer_cfg="${KLIPPER_CONF_DIR}/printer.cfg"
  local moonraker_conf="${KLIPPER_CONF_DIR}/moonraker.conf"

# --- Step 1: Add [authorization] to moonraker.conf if missing ---
if [ -f "$moonraker_conf" ]; then
  if ! grep -q "\[authorization\]" "$moonraker_conf"; then
    report_status "Adding [authorization] to moonraker.conf for restart_service API..."
    cat >> "$moonraker_conf" <<EOF

# Allow Klipper macros to call Moonraker APIs (e.g. restart_service)
[authorization]
enabled: false
EOF
    ok_msg "[authorization] added to moonraker.conf"
    report_status "NOTE: You need to restart Moonraker for this to take effect:"
    report_status "  sudo systemctl restart moonraker"
  else
    ok_msg "[authorization] already exists in moonraker.conf"
  fi
fi

# --- Step 2: Add macros to printer.cfg ---
if [ ! -f "$printer_cfg" ]; then
  warn_msg "printer.cfg not found at ${printer_cfg}. Skipping SPDKlipper macros."
  return 0
fi

# --- Step 2a: Include spd_machine_info.cfg ---
if ! grep -q "spd_machine_info.cfg" "$printer_cfg"; then
  report_status "Adding [include spd_machine_info.cfg] to printer.cfg..."
  printf "\n[include spd_machine_info.cfg]\n" >> "$printer_cfg"
  ok_msg "[include spd_machine_info.cfg] added to printer.cfg"
else
  ok_msg "[include spd_machine_info.cfg] already exists in printer.cfg. Skipping."
fi

# Copy spd_machine_info.cfg to Klipper config directory
local macro_source="${SPDKLIPPER_PLUGIN_DIR}/scripts/spd_machine_info.cfg"
if [ -f "$macro_source" ]; then
  report_status "Copying spd_machine_info.cfg to ${KLIPPER_CONF_DIR}..."
  cp "$macro_source" "${KLIPPER_CONF_DIR}/spd_machine_info.cfg"
  ok_msg "spd_machine_info.cfg copied to ${KLIPPER_CONF_DIR}"
else
  warn_msg "spd_machine_info.cfg not found at ${macro_source}. Skipping."
fi

# --- Step 2b: Add RESTART_SPDK macro (standalone) ---
if ! grep -q "\[gcode_macro RESTART_SPDK\]" "$printer_cfg"; then
  report_status "Adding RESTART_SPDK macro to printer.cfg..."

  cat >> "$printer_cfg" << 'EOF'

[gcode_macro RESTART_SPDK]
description: Restart SPDKlipper plugin service
gcode:
    {action_call_remote_method("restart_service", service_name="spdklipper-plugin")}
EOF

  ok_msg "RESTART_SPDK macro added to printer.cfg"
else
  ok_msg "RESTART_SPDK macro already exists in printer.cfg. Skipping."
fi

# --- Step 2c: Override FIRMWARE_RESTART to also restart SPDKlipper ---
if ! grep -q "\[gcode_macro FIRMWARE_RESTART\]" "$printer_cfg"; then
  report_status "Adding FIRMWARE_RESTART+ macro to printer.cfg (restarts firmware + SPDKlipper)..."

  cat >> "$printer_cfg" << 'EOF'

[gcode_macro FIRMWARE_RESTART]
description: Firmware restart + SPDKlipper plugin restart
gcode:
    # Step 1: Restart SPDKlipper plugin service first
    {action_call_remote_method("restart_service", service_name="spdklipper-plugin")}
    # Step 2: Wait briefly for the plugin to stop cleanly
    G4 P2000
    # Step 3: Perform the actual firmware restart
    FIRMWARE_RESTART
EOF

  ok_msg "FIRMWARE_RESTART+ macro added to printer.cfg"
else
  ok_msg "FIRMWARE_RESTART+ macro already exists in printer.cfg. Skipping."
fi

report_status ""
report_status "SPDKlipper macros installed:"
report_status "  - spd_machine_info.cfg : Machine Info display macros (included)"
report_status "  - RESTART_SPDK         : Restart SPDKlipper only (run from console)"
report_status "  - FIRMWARE_RESTART     : Restarts firmware + SPDKlipper (Fluidd/Mainsail button)"
report_status ""
report_status "Services will be restarted automatically at the end of installation."
}


add_moonraker_spd_status_component() {
  # Install Moonraker SPD status component.
  #
  # This copies scripts/moonraker_spd_status.py to the Moonraker components
  # directory and adds [spd_status] to moonraker.conf so that the connection
  # status is displayed on Fluidd/Mainsail via M117.
  local moonraker_dir="${HOME}/moonraker"
  local component_dest="${moonraker_dir}/moonraker/components/spd_status.py"
  local source_file="${SPDKLIPPER_PLUGIN_DIR}/scripts/moonraker_spd_status.py"
  local moonraker_conf="${KLIPPER_CONF_DIR}/moonraker.conf"

  # Check if Moonraker is installed
  if [ ! -d "$moonraker_dir" ]; then
    warn_msg "Moonraker directory not found at ${moonraker_dir}. Skipping SPD status component."
    return 0
  fi

  # Copy the component file
  if [ ! -f "$source_file" ]; then
    warn_msg "Source file ${source_file} not found. Skipping SPD status component."
    return 0
  fi

  report_status "Installing Moonraker SPD status component..."
  mkdir -p "$(dirname "$component_dest")"
  cp "$source_file" "$component_dest"
  ok_msg "SPD status component installed to ${component_dest}"

  # Add [spd_status] to moonraker.conf if not already present
  if [ -f "$moonraker_conf" ]; then
    if grep -q "\[spd_status\]" "$moonraker_conf"; then
      ok_msg "[spd_status] already exists in moonraker.conf. Skipping."
    else
      report_status "Adding [spd_status] to moonraker.conf..."
      printf "\n# SPD Klipper connection status display\n[spd_status]\n" >> "$moonraker_conf"
      ok_msg "[spd_status] added to moonraker.conf"
    fi
  else
    warn_msg "moonraker.conf not found at ${moonraker_conf}."
    warn_msg "After creating moonraker.conf, add the following:"
    warn_msg "  [spd_status]"
  fi

  # Add [http_client] to moonraker.conf if not already present
  # Required by spd_machine_info.cfg macros to call SPDKlipper plugin API
  if [ -f "$moonraker_conf" ]; then
    if grep -q "\[http_client\]" "$moonraker_conf"; then
      ok_msg "[http_client] already exists in moonraker.conf. Skipping."
    else
      report_status "Adding [http_client] to moonraker.conf (required for SPD Machine Info macros)..."
      printf "\n# HTTP client for SPD Machine Info macros\n[http_client]\n" >> "$moonraker_conf"
      ok_msg "[http_client] added to moonraker.conf"
    fi
  fi

  report_status "NOTE: Moonraker will be restarted automatically at the end of installation."
}


add_to_moonraker_asvc() {
  # Add spdklipper-plugin to moonraker.asvc if not already present.
  # This ensures Moonraker allows the plugin service to be managed.
  local asvc_path="${HOME}/printer_data/moonraker.asvc"

  report_status "Checking moonraker.asvc at ${asvc_path}..."

  # Create the file if it doesn't exist
  if [ ! -f "$asvc_path" ]; then
    report_status "moonraker.asvc not found. Creating it..."
    mkdir -p "$(dirname "$asvc_path")"
    touch "$asvc_path"
  fi

  if grep -q "spdklipper-plugin" "$asvc_path"; then
    ok_msg "spdklipper-plugin already exists in moonraker.asvc. Skipping."
    return 0
  fi

  report_status "Adding spdklipper-plugin to moonraker.asvc..."
  echo "spdklipper-plugin" >> "$asvc_path"
  ok_msg "spdklipper-plugin added to moonraker.asvc"
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

  # Add Moonraker update manager config
  add_update_manager_config

  # Add RESTART_SPDK and FIRMWARE_RESTART+ macros to printer.cfg
  add_restart_macro

  # Install Moonraker SPD status component (reads spd_status.json and sends M117)
  add_moonraker_spd_status_component

  # Add spdklipper-plugin to moonraker.asvc
  echo ""
  echo "###### Checking moonraker.asvc..."
  ASVC_PATH="${HOME}/printer_data/moonraker.asvc"
  if [ ! -f "$ASVC_PATH" ]; then
    echo "###### moonraker.asvc not found. Creating it..."
    mkdir -p "$(dirname "$ASVC_PATH")"
    touch "$ASVC_PATH"
  fi
  if grep -q "spdklipper-plugin" "$ASVC_PATH"; then
    echo -e "${green}>>>>>> spdklipper-plugin already exists in moonraker.asvc. Skipping.${default}"
  else
    echo "###### Adding spdklipper-plugin to moonraker.asvc..."
    echo "spdklipper-plugin" >> "$ASVC_PATH"
    echo -e "${green}>>>>>> spdklipper-plugin added to moonraker.asvc${default}"
  fi

  # Secure sensitive files after installation
  secure_sensitive_files

  # Restart Moonraker and Klipper services to apply all changes
  restart_services

}

restart_services() {
  # Restart Moonraker and Klipper services with a progress/waiting UI.
  # This ensures all new components, macros, and config changes are loaded.
  local moonraker_service="moonraker"
  local klipper_service="klipper"

  echo ""
  echo -e "${yellow}========================================${default}"
  echo -e "${yellow}  Restarting Services...${default}"
  echo -e "${yellow}========================================${default}"
  echo ""

  # --- Restart Moonraker ---
  echo -e "${cyan}[1/2] Restarting Moonraker...${default}"
  sudo systemctl restart "$moonraker_service" 2>/dev/null || true

  # Wait for Moonraker to become active with a spinner
  echo -n "  Waiting for Moonraker to become ready "
  local moonraker_ready=false
  local moonraker_timeout=60
  local moonraker_elapsed=0
  while [ $moonraker_elapsed -lt $moonraker_timeout ]; do
    if systemctl is-active --quiet "$moonraker_service" 2>/dev/null; then
      moonraker_ready=true
      break
    fi
    # Spinner animation
    case $((moonraker_elapsed % 4)) in
      0) echo -ne "${green}⠋${default}" ;;
      1) echo -ne "${green}⠙${default}" ;;
      2) echo -ne "${green}⠹${default}" ;;
      3) echo -ne "${green}⠸${default}" ;;
    esac
    sleep 1
    moonraker_elapsed=$((moonraker_elapsed + 1))
    # Backspace the spinner character
    echo -ne "\b"
  done

  if [ "$moonraker_ready" = true ]; then
    echo -e "${green} ✓${default}"
    ok_msg "Moonraker restarted successfully (${moonraker_elapsed}s)"
  else
    echo -e "${red} ✗${default}"
    warn_msg "Moonraker restart timed out after ${moonraker_timeout}s."
    warn_msg "Check manually: sudo systemctl status $moonraker_service"
  fi

  # --- Restart Klipper ---
  echo -e "${cyan}[2/2] Restarting Klipper...${default}"
  sudo systemctl restart "$klipper_service" 2>/dev/null || true

  # Wait for Klipper to become active with a spinner
  echo -n "  Waiting for Klipper to become ready "
  local klipper_ready=false
  local klipper_timeout=60
  local klipper_elapsed=0
  while [ $klipper_elapsed -lt $klipper_timeout ]; do
    if systemctl is-active --quiet "$klipper_service" 2>/dev/null; then
      klipper_ready=true
      break
    fi
    # Spinner animation
    case $((klipper_elapsed % 4)) in
      0) echo -ne "${green}⠋${default}" ;;
      1) echo -ne "${green}⠙${default}" ;;
      2) echo -ne "${green}⠹${default}" ;;
      3) echo -ne "${green}⠸${default}" ;;
    esac
    sleep 1
    klipper_elapsed=$((klipper_elapsed + 1))
    echo -ne "\b"
  done

  if [ "$klipper_ready" = true ]; then
    echo -e "${green} ✓${default}"
    ok_msg "Klipper restarted successfully (${klipper_elapsed}s)"
  else
    echo -e "${red} ✗${default}"
    warn_msg "Klipper restart timed out after ${klipper_timeout}s."
    warn_msg "Check manually: sudo systemctl status $klipper_service"
  fi

  echo ""
  echo -e "${green}========================================${default}"
  echo -e "${green}  All services restarted successfully!${default}"
  echo -e "${green}========================================${default}"
  echo ""
  echo -e "  ${cyan}SPDKlipper Plugin${default}  : ${green}✓${default} Installed"
  echo -e "  ${cyan}Moonraker${default}           : ${green}✓${default} Restarted (with spd_status component)"
  echo -e "  ${cyan}Klipper${default}             : ${green}✓${default} Restarted (with Machine Info macros)"
  echo ""
  echo -e "  ${yellow}Next steps:${default}"
  echo -e "  1. Open Fluidd/Mainsail"
  echo -e "  2. Check the status bar for Machine Info (M117 messages)"
  echo -e "  3. Run ${cyan}DISPLAY_SPD_INFO${default} from the console to test"
  echo -e "  4. Visit ${cyan}http://<your-pi-ip>:1122${default} for the SPDKlipper web UI"
  echo ""
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
