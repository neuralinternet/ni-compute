#!/bin/bash
set -euo pipefail

# 1) Force PATH so we can find 'btcli' if installed in ~/.local/bin
export PATH="/home/ubuntu/.local/bin:$PATH"

if [ -f "/home/ubuntu/venv/bin/activate" ]; then
  source /home/ubuntu/venv/bin/activate
  echo "Activated virtual environment at /home/ubuntu/venv"
else
  echo "ERROR: Virtual environment not found at /home/ubuntu/venv"
  exit 1
fi

echo "==> wallet_creator.sh starting..."
echo "DEBUG: whoami=$(whoami), HOME=$HOME, PATH=$PATH"

COLDKEY_SEED="${1:-}"
HOTKEY_SEED="${2:-}"

BTCLI="btcli"  # Rely on the forced PATH

PASSWORD="Neuralinternet2025!"
coldkey="default"
hotkey="default"
netuid=15

# Confirm 'btcli' is now visible
if ! command -v "$BTCLI" >/dev/null 2>&1; then
  echo "ERROR: 'btcli' is still not found in PATH. Check that Bittensor is installed."
  exit 1
fi

# Ensure 'expect' is installed
if ! command -v expect >/dev/null 2>&1; then
  echo "==> Installing 'expect'..."
  sudo apt-get update && sudo apt-get install -y expect || {
    echo "Error: Failed to install expect." >&2
    exit 1
  }
fi

echo "==> Starting wallet creation (regen_coldkey) using expect..."

expect <<EOF
  set timeout -1
  spawn $BTCLI w regen_coldkey --mnemonic "$COLDKEY_SEED"
  expect "Enter the path for the wallets directory"
  send "\r"
  expect "Enter the name of the "
  send "\r"
  expect "Enter your password:"
  send "$PASSWORD\r"
  expect "Retype your password:"
  send "$PASSWORD\r"
  expect "Encrypting..."
  catch { expect eof }
EOF

echo "==> Coldkey creation done."

############################################################
# HOTKEY
############################################################
echo "==> Creating hotkey"
printf "\n\n\n12\n" | "$BTCLI" wallet new-hotkey
echo "==> Hotkey creation done."

echo "==> wallet_creator.sh finished."

###########################################
# Subnet Registration
###########################################
echo "==> Starting subnet registration..."
expect -c "
  spawn ${BTCLI} subnet register --wallet.name ${coldkey} --wallet.hotkey ${hotkey} --subtensor.network test --netuid ${netuid}
  expect -re \"want to continue\\?\" { send \"y\r\"; }
  expect -re \"Enter your password:\" { send \"${PASSWORD}\r\"; }
  expect -re \"register on subnet:${netuid}\" { send \"y\r\"; interact }
"
echo "==> Subnet registration process completed."

echo "==> wallet_creator.sh completed successfully!"
