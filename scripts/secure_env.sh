#!/bin/bash
# SPDKlipper Plugin - Secure .env File Manager
# ==============================================
# This script helps encrypt and decrypt the .env file to protect
# sensitive keys (HOST_CONNECT, HOST_SERVER, etc.) on disk.
#
# Usage:
#   ./scripts/secure_env.sh lock     - Encrypt .env to .env.enc (removes plaintext .env)
#   ./scripts/secure_env.sh unlock   - Decrypt .env.enc back to .env
#   ./scripts/secure_env.sh status   - Check if .env is encrypted or plaintext
#
# REQUIREMENTS: openssl must be installed (default on Raspberry Pi OS)
#
# SECURITY NOTES:
# - Uses AES-256-CBC encryption with a passphrase you provide
# - The encrypted file (.env.enc) is safe to store on disk
# - You MUST remember the passphrase! There is no recovery.
# - For automated startups, keep .env plaintext but with chmod 600
# - For maximum security, use both: chmod 600 .env AND encrypt with this script

set -e

SCRIPT_DIR="$(cd "$(dirname "$(realpath "$0")")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="${PROJECT_DIR}/.env"
ENV_ENC_FILE="${PROJECT_DIR}/.env.enc"

# Color helpers
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

warn_msg() { echo -e "${RED}<!!!!> $1${NC}"; }
ok_msg()   { echo -e "${GREEN}>>>>>> $1${NC}"; }
info_msg() { echo -e "${CYAN}###### $1${NC}"; }

# Check if openssl is available
check_openssl() {
    if ! command -v openssl &> /dev/null; then
        warn_msg "openssl is required but not installed."
        warn_msg "Install it with: sudo apt-get install openssl"
        exit 1
    fi
}

# Generate a random salt for key derivation
generate_salt() {
    openssl rand -hex 16
}

# Derive encryption key from passphrase and salt (PBKDF2)
derive_key() {
    local passphrase="$1"
    local salt="$2"
    echo -n "$passphrase" | openssl dgst -sha256 -hmac "$salt" | awk '{print $2}'
}

cmd_lock() {
    check_openssl

    if [ ! -f "$ENV_FILE" ]; then
        warn_msg ".env file not found at ${ENV_FILE}"
        exit 1
    fi

    if [ -f "$ENV_ENC_FILE" ]; then
        warn_msg ".env.enc already exists! Decrypt it first or remove it."
        exit 1
    fi

    echo -e "${YELLOW}You will now set a passphrase to encrypt your .env file.${NC}"
    echo -e "${YELLOW}WARNING: If you lose this passphrase, you CANNOT recover the file!${NC}"
    echo

    # Read passphrase (twice for confirmation)
    read -s -p "Enter encryption passphrase: " PASSPHRASE1
    echo
    read -s -p "Confirm passphrase: " PASSPHRASE2
    echo

    if [ "$PASSPHRASE1" != "$PASSPHRASE2" ]; then
        warn_msg "Passphrases do not match!"
        exit 1
    fi

    if [ -z "$PASSPHRASE1" ]; then
        warn_msg "Passphrase cannot be empty!"
        exit 1
    fi

    # Generate salt and encrypt
    local salt
    salt=$(generate_salt)
    local key
    key=$(derive_key "$PASSPHRASE1" "$salt")

    # Encrypt: AES-256-CBC with salt prepended to output
    openssl enc -aes-256-cbc -salt -pbkdf2 -iter 100000 \
        -in "$ENV_FILE" \
        -out "$ENV_ENC_FILE" \
        -pass pass:"$key" 2>/dev/null

    if [ $? -eq 0 ]; then
        # Store the salt alongside (needed for decryption)
        echo "$salt" > "${ENV_ENC_FILE}.salt"
        # Securely remove plaintext .env
        shred -u "$ENV_FILE" 2>/dev/null || rm -f "$ENV_FILE"
        # Restrict permissions on encrypted file
        chmod 600 "$ENV_ENC_FILE" 2>/dev/null || true
        chmod 600 "${ENV_ENC_FILE}.salt" 2>/dev/null || true
        ok_msg ".env has been encrypted to .env.enc"
        info_msg "To decrypt later, run: ./scripts/secure_env.sh unlock"
        info_msg "The plaintext .env has been securely deleted."
    else
        warn_msg "Encryption failed!"
        rm -f "$ENV_ENC_FILE" "${ENV_ENC_FILE}.salt"
        exit 1
    fi
}

cmd_unlock() {
    check_openssl

    if [ ! -f "$ENV_ENC_FILE" ]; then
        warn_msg ".env.enc not found at ${ENV_ENC_FILE}"
        exit 1
    fi

    if [ ! -f "${ENV_ENC_FILE}.salt" ]; then
        warn_msg "Salt file not found (${ENV_ENC_FILE}.salt)"
        warn_msg "Cannot decrypt without the salt."
        exit 1
    fi

    if [ -f "$ENV_FILE" ]; then
        warn_msg ".env already exists! Remove it first or backup."
        exit 1
    fi

    echo -e "${YELLOW}Enter the passphrase to decrypt .env.enc${NC}"
    read -s -p "Enter decryption passphrase: " PASSPHRASE
    echo

    local salt
    salt=$(cat "${ENV_ENC_FILE}.salt")
    local key
    key=$(derive_key "$PASSPHRASE" "$salt")

    # Decrypt
    openssl enc -aes-256-cbc -d -salt -pbkdf2 -iter 100000 \
        -in "$ENV_ENC_FILE" \
        -out "$ENV_FILE" \
        -pass pass:"$key" 2>/dev/null

    if [ $? -eq 0 ]; then
        chmod 600 "$ENV_FILE" 2>/dev/null || true
        ok_msg ".env.enc has been decrypted to .env"
        info_msg "File permissions set to 600 (owner read/write only)."
    else
        warn_msg "Decryption failed! Wrong passphrase or corrupted file."
        rm -f "$ENV_FILE"
        exit 1
    fi
}

cmd_status() {
    echo "=========================================="
    echo "  SPDKlipper .env Security Status"
    echo "=========================================="
    echo

    if [ -f "$ENV_FILE" ] && [ -f "$ENV_ENC_FILE" ]; then
        echo -e "  ${YELLOW}Both .env and .env.enc exist${NC}"
        echo "  .env is plaintext (accessible)"
        echo "  .env.enc is encrypted"
        echo "  Recommendation: Remove one of them."
    elif [ -f "$ENV_FILE" ]; then
        local perms
        perms=$(stat -c "%a" "$ENV_FILE" 2>/dev/null || echo "unknown")
        echo -e "  ${GREEN}.env is PLAINTEXT${NC}"
        echo "  Permissions: ${perms}"
        if [ "$perms" = "600" ]; then
            echo -e "  ${GREEN}Permissions are secure (owner-only)${NC}"
        else
            echo -e "  ${YELLOW}WARNING: Permissions should be 600! Run: chmod 600 .env${NC}"
        fi
    elif [ -f "$ENV_ENC_FILE" ]; then
        echo -e "  ${GREEN}.env is ENCRYPTED (.env.enc)${NC}"
        echo "  Run './scripts/secure_env.sh unlock' to decrypt."
    else
        echo -e "  ${YELLOW}No .env or .env.enc found${NC}"
        echo "  Copy .env.example to .env and configure it."
    fi
    echo
}

# --- Main ---
case "${1:-}" in
    lock)
        cmd_lock
        ;;
    unlock)
        cmd_unlock
        ;;
    status)
        cmd_status
        ;;
    *)
        echo "Usage: $0 {lock|unlock|status}"
        echo
        echo "  lock     Encrypt .env to .env.enc (removes plaintext .env)"
        echo "  unlock   Decrypt .env.enc back to .env"
        echo "  status   Check encryption status of .env"
        exit 1
        ;;
esac
