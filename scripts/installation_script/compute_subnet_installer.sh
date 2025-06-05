#!/bin/bash
set -u
set -o history -o histexpand

##############################################################################
#                  compute_subnet_installer.sh
##############################################################################
#
# This script will:
#   1) Check / install Docker, NVIDIA drivers, NVIDIA Docker, and CUDA 12.8
#   2) Check / install Bittensor
#   3) Optionally configure compute-subnet (miner) with PM2, if user agrees
#   4) NOT create any wallets automatically. If no wallet is detected, user
#      can choose to exit and create it themselves (coldkey/hotkey).
#
# Usage:
#   ./compute_subnet_installer.sh
#   ./compute_subnet_installer.sh --automated   (non-interactive mode)
#
##############################################################################
# 0 means "no reboot needed", 1 means "reboot needed"
NEED_REBOOT=0
AUTOMATED=false
if [[ "$#" -gt 0 ]]; then
  if [[ "$1" == "--automated" ]]; then
    AUTOMATED=true
    shift
  fi
fi

# Temporary needrestart configuration
TEMP_NEEDRESTART_CONF="/tmp/needrestart-temp.conf"
TEMP_NEEDRESTART_DIR="/etc/needrestart/conf.d/99-temp.conf"

# Function to clean up temporary configuration
cleanup() {
    echo "Cleaning up temporary needrestart configuration..."
    if [ -f "$TEMP_NEEDRESTART_DIR" ]; then
        sudo rm -f "$TEMP_NEEDRESTART_DIR"
    fi
    if [ -f "$TEMP_NEEDRESTART_CONF" ]; then
        sudo rm -f "$TEMP_NEEDRESTART_CONF"
    fi
}

# Configure needrestart temporarily
setup_needrestart() {
    echo "Setting up temporary needrestart configuration..."
    sudo bash -c 'echo "\$nrconf{restart} = '\''a'\'';" > '"$TEMP_NEEDRESTART_CONF"
    sudo bash -c 'echo "\$nrconf{override_rc} = 0;" >> '"$TEMP_NEEDRESTART_CONF"
    sudo bash -c 'echo "\$nrconf{restart} = '\''a'\'';" > '"$TEMP_NEEDRESTART_DIR"
}

# Register cleanup function to run when script exits
trap cleanup EXIT INT TERM

# Set up needrestart at startup
setup_needrestart

# Function to run apt-get with non-interactive configuration
run_apt_get() {
  DEBIAN_FRONTEND=noninteractive sudo -E apt-get "$@"
}

# Function to run apt-get install with non-interactive configuration
install_package() {
  DEBIAN_FRONTEND=noninteractive sudo -E apt-get install -y "$@"
}

abort() {
  echo "ERROR: $1" >&2
  cleanup  # Ensure cleanup on error
  exit 1
}

info() {
  echo "==> $*"
}

pause_for_user() {
  if $AUTOMATED; then
    info "Skipping user confirmation (automated mode)."
  else
    echo
    echo "Press ENTER to continue or Ctrl+C to abort..."
    read -r
  fi
}

##############################################################################
#                      1) System checks and environment
##############################################################################
if [[ "$(uname)" != "Linux" ]]; then
  abort "This installer only supports Linux."
fi

# Determine user and HOME directory (especially for cloud-init / Ubuntu)
REAL_USER=$(whoami)
if [ "$REAL_USER" = "root" ]; then
  if [[ -n "${SUDO_USER:-}" ]]; then
    USER_NAME="$SUDO_USER"
    HOME_DIR=$(eval echo "~$SUDO_USER")
  else
    USER_NAME="root"
    HOME_DIR="/root"
  fi
else
  USER_NAME="$REAL_USER"
  HOME_DIR="$(eval echo "~$REAL_USER")"
fi


docker_installed() {
  if command -v docker >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

if docker_installed; then
  info "Docker is installed. Verifying permissions..."
  if $AUTOMATED; then
    info "In automated mode, ensuring Docker permissions..."
    info "Configuring Docker permissions for ubuntu user in automated mode..."
    sudo usermod -aG docker ubuntu
    sudo chown root:docker /var/run/docker.sock
    sudo chmod 666 /var/run/docker.sock
    sudo setfacl -m user:ubuntu:rw /var/run/docker.sock
    sudo systemctl restart docker
  else
    if ! groups "$USER_NAME" | grep -q docker; then
      info "Adding user $USER_NAME to docker group..."
      sudo usermod -aG docker "$USER_NAME"
      sudo chown root:docker /var/run/docker.sock
      sudo chmod 660 /var/run/docker.sock
      sudo setfacl -m user:$USER_NAME:rw /var/run/docker.sock
      info "Docker permissions configured for $USER_NAME."
      info "⚠️ Please log out and log back in, or reboot, to apply group membership."
    else
      info "User $USER_NAME already has Docker permissions."
    fi
  fi
fi

# Define virtual environment directory
VENV_DIR="${HOME_DIR}/venv"
if [ -f "${VENV_DIR}/bin/activate" ]; then
  source "${VENV_DIR}/bin/activate"
fi

##############################################################################
#                      3) Check / Install NVIDIA Docker
##############################################################################
nvidia_docker_installed() {
  # A quick check if nvidia-container-toolkit is installed
  if dpkg -l | grep -q nvidia-container-toolkit; then
    return 0
  fi
  return 1
}

##############################################################################
#                      4) Check / Install CUDA 12.8
##############################################################################
cuda_version_installed() {
  local ver=""
  # Check /usr/local/cuda/version.txt
  if [ -f "/usr/local/cuda/version.txt" ]; then
    ver=$(grep "CUDA Version" /usr/local/cuda/version.txt | awk '{print $3}' | cut -d'.' -f1,2)
  fi
  # Check /usr/local/cuda/version.json
  if [ -z "$ver" ] && [ -f "/usr/local/cuda/version.json" ]; then
    ver=$(grep -oP '"cuda"\s*:\s*"\K[0-9]+\.[0-9]+' /usr/local/cuda/version.json)
  fi
  # Check symlink name
  if [ -z "$ver" ] && [ -L "/usr/local/cuda" ]; then
    local real_cuda
    real_cuda=$(readlink -f /usr/local/cuda)
    if [[ "$real_cuda" =~ cuda-([0-9]+\.[0-9]+) ]]; then
      ver="${BASH_REMATCH[1]}"
    fi
  fi
  # Check nvcc
  if [ -z "$ver" ] && command -v nvcc >/dev/null 2>&1; then
    ver=$(nvcc --version | grep "release" | sed 's/.*release //' | sed 's/,.*//')
  fi
  echo "$ver"
}


##############################################################################
#                      6) Check / Install btcli
##############################################################################
btcli_installed() {
  if [ -z "${VIRTUAL_ENV:-}" ]; then
    return 1
  fi

  if "${VIRTUAL_ENV}/bin/btcli" --version >/dev/null 2>&1; then
    return 0
  fi
  return 1
}

CURRENT_CUDA=$(cuda_version_installed)

if ! docker_installed || ! nvidia_docker_installed || ! [[ -n "$CURRENT_CUDA" ]] || ! btcli_installed; then
  echo
  echo "                        @@@@                                                                                        @@@@"
  echo "                       @@@@      @@@@@@@@@@@@@@@@    @@@@@@@@        @@@    @@@@@@@@@@@@@@@@    @@@@@@@@@@@@@@@      @@@@"
  echo "                       @@@      @@@@@@@@@@@@@@@@@    @@@@@@@@@       @@@    @@@@@@@@@@@@@@@@@@  @@@@@@@@@@@@@@@@      @@@"
  echo "                       @@@      @@                   @@@@   @@@      @@@                   @@@                @@@     @@@"
  echo "                       @@@      @@@@@@@@@@@@@@@@     @@@@    @@@     @@@     @@@@@@@@@@@@@@@@                 @@@     @@@"
  echo "                       @@@        @@@@@@@@@@@@@@@@   @@@@     @@@    @@@    @@@@@@@@@@@@@@@@                  @@@     @@@"
  echo "                       @@@                     @@@   @@@@      @@@   @@@   @@@                                @@@     @@@"
  echo "                       @@@      @@@@@@@@@@@@@@@@@@   @@@@       @@@@@@@@   @@@@@@@@@@@@@@@@@@                 @@@     @@@"
  echo "                       @@@@     @@@@@@@@@@@@@@@@     @@@@        @@@@@@@   @@@@@@@@@@@@@@@@@@                 @@@    @@@@"
  echo "                         @@@                                                                                        @@@"
  echo
  info "This script will install Docker, NVIDIA drivers, NVIDIA Docker, CUDA 12.8, and Bittensor if they are not present. It will then optionally set up the compute-subnet miner."
  pause_for_user

  if docker_installed; then
    info "Docker is already installed. Skipping Docker installation."
  else
    info "Installing Docker..."

    run_apt_get update || abort "Failed to update package lists."
    install_package apt-utils curl git cmake build-essential ca-certificates || abort "Failed to install basic prerequisites."

    # Set up Docker repository
    info "Setting up Docker repository..."
    sudo install -m 0755 -d /etc/apt/keyrings
    sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc || abort "Failed to download Docker GPG key."
    sudo chmod a+r /etc/apt/keyrings/docker.asc

    . /etc/os-release || abort "Cannot determine OS version."
    DOCKER_REPO="deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable"
    echo "$DOCKER_REPO" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

    run_apt_get update || abort "Failed to update package lists for Docker."
    install_package docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin || abort "Failed to install Docker packages."

    info "Adding user ${USER_NAME} to 'docker' group..."
    sudo usermod -aG docker "$USER_NAME" || abort "Failed to add user to docker group."

    info "Docker installed successfully."
    NEED_REBOOT=1
  fi

  if nvidia_docker_installed; then
    info "NVIDIA Docker support (nvidia-container-toolkit) is already installed. Skipping."
  else
    info "Installing NVIDIA Docker support..."

    curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey \
      | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg \
        || abort "Failed to download libnvidia-container gpg key."

    curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list \
      | sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' \
      | sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list

    run_apt_get update || abort "Failed to update apt after adding NVIDIA repository."
    install_package nvidia-container-toolkit || abort "Failed to install nvidia-container-toolkit."

    info "Configuring Docker to use NVIDIA Container Runtime..."
    sudo nvidia-ctk runtime configure --runtime=docker || abort "Failed to configure NVIDIA Container Runtime."
    sudo systemctl restart docker || abort "Failed to restart Docker."

    info "NVIDIA Docker support installed."
  fi

  if [[ -n "$CURRENT_CUDA" ]]; then
    info "Detected CUDA version: $CURRENT_CUDA"
  fi

  if [[ "$CURRENT_CUDA" == "12.8" ]]; then
    info "CUDA 12.8 is already installed. Skipping CUDA installation."
  elif [[ -n "$CURRENT_CUDA" ]]; then
    info "WARNING: CUDA version $CURRENT_CUDA detected, different from 12.8."
    info "Skipping installation of 12.8 to avoid conflicts."
  else
    info "No CUDA found. Installing CUDA 12.8..."

    . /etc/os-release || abort "Cannot determine Ubuntu version."
    if [[ "$VERSION_CODENAME" == "jammy" ]]; then
      # Ubuntu 22.04
      run_apt_get update
      install_package build-essential dkms linux-headers-$(uname -r) || abort "Failed to install build essentials."
      wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2204/x86_64/cuda-ubuntu2204.pin -O /tmp/cuda.pin || abort "Failed to download cuda pin file."
      sudo mv /tmp/cuda.pin /etc/apt/preferences.d/cuda-repository-pin-600
      wget https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/cuda-repo-ubuntu2204-12-8-local_12.8.0-570.86.10-1_amd64.deb -O /tmp/cuda-repo.deb || abort "Failed to download cuda repo .deb."
      sudo dpkg -i /tmp/cuda-repo.deb || abort "dpkg install of cuda repo failed."
      sudo cp /var/cuda-repo-ubuntu2204-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/ || abort "Failed to copy cuda keyring."
      run_apt_get update
      install_package cuda-toolkit-12-8 cuda-drivers || abort "Failed to install CUDA Toolkit and drivers."
    elif [[ "$VERSION_CODENAME" == "lunar" || "$VERSION_CODENAME" == "noble" ]]; then
      # For Ubuntu 23.04/24.04 if they use codename "lunar"
      run_apt_get update
      install_package build-essential dkms linux-headers-$(uname -r) || abort "Failed to install build essentials."
      wget https://developer.download.nvidia.com/compute/cuda/repos/ubuntu2404/x86_64/cuda-ubuntu2404.pin -O /tmp/cuda.pin || abort "Failed to download cuda pin file (24.04)."
      sudo mv /tmp/cuda.pin /etc/apt/preferences.d/cuda-repository-pin-600
      wget https://developer.download.nvidia.com/compute/cuda/12.8.0/local_installers/cuda-repo-ubuntu2404-12-8-local_12.8.0-570.86.10-1_amd64.deb -O /tmp/cuda-repo.deb || abort "Failed to download cuda repo .deb (24.04)."
      sudo dpkg -i /tmp/cuda-repo.deb || abort "dpkg install of cuda repo failed (24.04)."
      sudo cp /var/cuda-repo-ubuntu2404-12-8-local/cuda-*-keyring.gpg /usr/share/keyrings/ || abort "Failed to copy cuda keyring (24.04)."
      run_apt_get update
      install_package cuda-toolkit-12-8 cuda-drivers || abort "Failed to install CUDA Toolkit 12.8."
    else
      info "Automatic CUDA 12.8 installation is not supported for this Ubuntu version."
      info "Please install CUDA manually from: https://developer.nvidia.com/cuda-downloads"
      exit 1
    fi

    info "Configuring CUDA environment variables in ${HOME_DIR}/.bashrc..."
    if ! grep -q "CUDA configuration added by" "${HOME_DIR}/.bashrc"; then
      {
        echo ""
        echo "# CUDA configuration added by compute_subnet_installer.sh"
        echo "export PATH=/usr/local/cuda-12.8/bin:\$PATH"
        echo "export LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:\$LD_LIBRARY_PATH"
      } | tee -a "${HOME_DIR}/.bashrc"
      info "CUDA environment variables appended to ${HOME_DIR}/.bashrc"
    else
      info "CUDA environment variables already present in ${HOME_DIR}/.bashrc"
    fi

    info "CUDA 12.8 installation complete."
    NEED_REBOOT=1
  fi


  ##############################################################################
  # Attempt to detect or clone the compute-subnet repository
  ##############################################################################
  COMPUTE_SUBNET_GIT="https://github.com/neuralinternet/ni-compute.git"
  COMPUTE_SUBNET_DIR="compute-subnet"

  # Check if we're already inside a Git repo
  if $AUTOMATED; then
    echo "AUTOMATED mode detected. Setting up compute-subnet..."
    if [ ! -d "/home/ubuntu/compute-subnet" ]; then
      echo "Cloning compute-subnet repository..."
      git clone "$COMPUTE_SUBNET_GIT" /home/ubuntu/compute-subnet || {
        echo "ERROR: Failed to clone compute-subnet repository."
        exit 1
      }
    fi
    cd /home/ubuntu/compute-subnet || {
      echo "ERROR: Failed to change directory to /home/ubuntu/compute-subnet."
      exit 1
    }
  fi
  if REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
    info "Detected Git repository root: $REPO_ROOT"
    cd "$REPO_ROOT" || abort "Failed to cd into $REPO_ROOT"
    CS_PATH="$REPO_ROOT"

    # Check if we have setup.py / pyproject.toml inside the root
    if [ ! -f "$CS_PATH/setup.py" ] && [ ! -f "$CS_PATH/pyproject.toml" ]; then
      info "No setup.py or pyproject.toml in the detected Git root."
      info "Attempting to find or clone the compute-subnet repo..."
      # If the folder doesn't exist, clone it
      if [ ! -d "$COMPUTE_SUBNET_DIR" ]; then
        git clone "$COMPUTE_SUBNET_GIT" || abort "Failed to clone compute-subnet."
      fi
      cd "$COMPUTE_SUBNET_DIR" || abort "Failed to enter compute-subnet directory."
      CS_PATH="$(pwd)"
    fi

  else
    # We are not inside a Git repo, so let's see if we already have 'compute-subnet' folder
    CS_PATH="$(pwd)"

    if [ ! -f "$CS_PATH/setup.py" ] && [ ! -f "$CS_PATH/pyproject.toml" ]; then
      info "Could not find setup.py or pyproject.toml in current directory."
      info "Attempting to find or clone the compute-subnet repo..."

      # If no local 'compute-subnet' folder, clone it
      if [ ! -d "$COMPUTE_SUBNET_DIR" ]; then
        git clone "$COMPUTE_SUBNET_GIT" || abort "Failed to clone compute-subnet."
      fi
      cd "$COMPUTE_SUBNET_DIR" || abort "Failed to enter compute-subnet directory."
      CS_PATH="$(pwd)"

      # Double-check we have setup.py or pyproject.toml now
      if [ ! -f "$CS_PATH/setup.py" ] && [ ! -f "$CS_PATH/pyproject.toml" ]; then
        abort "Still could not find setup.py or pyproject.toml even after cloning. Please check the repo."
      fi

    else
      # If we do find them in the current directory, that means we are already in compute-subnet root
      info "Found setup.py or pyproject.toml here. Proceeding."
    fi
  fi

  if $AUTOMATED; then
    # Attempt to use /home/ubuntu/compute-subnet as the repo if it exists
    if [ -f "/home/ubuntu/compute-subnet/setup.py" ] || [ -f "/home/ubuntu/compute-subnet/pyproject.toml" ]; then
      CS_PATH="/home/ubuntu/compute-subnet"
    else
      CS_PATH="$(pwd)"
    fi
    cd "$CS_PATH" || abort "Failed to change directory to $CS_PATH"
  else
    if REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
      info "Detected repository root: $REPO_ROOT"
      cd "$REPO_ROOT" || abort "Failed to cd into $REPO_ROOT"
      CS_PATH="$REPO_ROOT"
    else
      CS_PATH="$(pwd)"
      if [ ! -f "$CS_PATH/setup.py" ] && [ ! -f "$CS_PATH/pyproject.toml" ]; then
        abort "Could not find setup.py or pyproject.toml. Please run from within compute-subnet repo root."
      fi
    fi
  fi

  VENV_DIR="${HOME_DIR}/venv"

  cat << "EOF"

  =============================================
    compute-subnet Installer - Miner Setup
  =============================================
EOF

  # Create/activate venv
  if [ -z "${VIRTUAL_ENV:-}" ] || [ "$VIRTUAL_ENV" != "$VENV_DIR" ]; then
    if [ -f "$VENV_DIR/bin/activate" ]; then
      info "Activating existing virtual environment at ${VENV_DIR}..."
      source "$VENV_DIR/bin/activate"
    else
      info "No virtual environment found. Creating one at ${VENV_DIR}..."
      if ! python3 -m ensurepip --version > /dev/null 2>&1; then
        info "ensurepip not available. Installing python-venv..."
        py_ver=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
        run_apt_get update || abort "Failed to update package lists."
        install_package python${py_ver}-venv || abort "Failed to install python${py_ver}-venv."
      fi
      python3 -m venv "$VENV_DIR" || abort "Failed to create virtual environment."
      info "Activating virtual environment..."
      source "$VENV_DIR/bin/activate"
    fi
  fi

  info "Updating system packages for compute-subnet dependencies..."
  run_apt_get update || abort "Failed to update package lists."
  install_package python3 python3-pip python3-venv build-essential dkms linux-headers-$(uname -r) at || abort "Failed to install required packages."

  info "Upgrading pip in the virtual environment..."
  pip install --upgrade pip || abort "Failed to upgrade pip."

  if [ -f "requirements.txt" ]; then
    info "Installing base dependencies from requirements.txt..."
    pip install -r requirements.txt || abort "Failed to install requirements."
  fi

  if [ -f "requirements-compute.txt" ]; then
    info "Installing compute-specific dependencies (no-deps) from requirements-compute.txt..."
    pip install --no-deps -r requirements-compute.txt || abort "Failed to install requirements-compute."
  fi

  info "Installing compute-subnet in editable mode..."
  pip install -e . || abort "Failed to install compute-subnet (editable)."

  python -c "import torch" 2>/dev/null
  if [ $? -ne 0 ]; then
    info "PyTorch not found. Installing torch, torchvision, torchaudio..."
    pip install torch torchvision torchaudio || abort "Failed to install PyTorch."
  fi

  info "Installing OpenCL libraries..."
  install_package ocl-icd-libopencl1 pocl-opencl-icd || abort "Failed to install OpenCL libraries."

  info "Installing Node.js, npm and PM2..."
  run_apt_get update

  install_package curl

  curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -

  install_package nodejs || abort "Failed to install Node.js."

  node -v

  sudo npm install -g pm2 || abort "Failed to install PM2."

  pm2 --version || echo "PM2 installation may have issues."
fi

##############################################################################
# Ensure that the 'btcli' command is recognized without a reboot
##############################################################################

# 1. Force-add $HOME/.local/bin to PATH in .bashrc if not present
if ! grep -qF "$HOME/.local/bin" "$HOME/.bashrc"; then
    echo 'export PATH="$HOME/.local/bin:$PATH"' >> "$HOME/.bashrc"
    echo "Added '$HOME/.local/bin' to PATH in .bashrc"
else
    echo "'$HOME/.local/bin' is already in PATH in .bashrc"
fi

# 2. Source .bashrc so our *current* shell process updates its PATH
if [ -f "$HOME/.bashrc" ]; then
    source "$HOME/.bashrc"
    echo "Sourced $HOME/.bashrc, PATH is now: $PATH"
fi

# 3. Test if btcli is found
if command -v btcli >/dev/null 2>&1; then
    echo "btcli is now recognized."
else
    echo "WARNING: btcli is still not recognized. Check your PATH or installation."
fi

##############################################################################
# Define function to suggest reboot only if NEED_REBOOT=1
##############################################################################
maybe_reboot_suggestion() {
    if [[ $NEED_REBOOT -eq 1 ]]; then
        echo
        echo "Some core components (Docker, CUDA, Bittensor) were installed or updated."
        echo "A reboot is strongly recommended before creating/funding your wallet or proceeding."
        read -rp "Press 'r' to reboot now, or any other key to skip: " reboot_choice
        if [[ "$reboot_choice" =~ ^[Rr]$ ]]; then
            info "Rebooting..."
            sudo reboot
        else
            info "Skipping reboot. You may do it manually later if needed."
        fi
    else
        info "No new installations were performed, so no reboot needed."
    fi
}

##############################################################################
# Prompt user if they want to set up the miner now
##############################################################################
AUTOMATED=${AUTOMATED:-false}

if $AUTOMATED; then
    SETUP_MINER="yes"
else
    echo
    echo "All base installations (Docker, NVIDIA, CUDA, Bittensor) are complete."
    echo "Would you like to set up the miner now?"
    select yn in "Yes" "No"; do
        case $yn in
            Yes)
                SETUP_MINER="yes"
                break
                ;;
            No)
                info "Skipping miner setup."
                info "You can re-run this script later if you change your mind."
                maybe_reboot_suggestion
                exit 0
                ;;
        esac
    done
fi

##############################################################################
# Check if user has a wallet. If not, offer to exit
##############################################################################
WALLET_DIR="${HOME}/.bittensor/wallets"
have_wallets=false
if [ -d "${WALLET_DIR}" ] && [ -n "$(ls -A "${WALLET_DIR}" 2>/dev/null)" ]; then
  have_wallets=true
fi

if ! $have_wallets; then
  info "No wallets detected in ${WALLET_DIR}."
  echo "Miner setup requires an existing coldkey/hotkey wallet with funds."
  echo "Please create/fund your wallet using btcli, for example:"
  echo "  btcli w new_coldkey --wallet.name mycold"
  echo "  btcli w new_hotkey --wallet.name mycold --wallet.hotkey myhot"
  echo
  if $AUTOMATED; then
    info "Exiting in automated mode so you can create/fund your wallet."
    exit 0
  else
    echo "Would you like to exit now so you can create/fund your wallet first?"
    select yn in "Yes" "No"; do
      case $yn in
        Yes )
          info "Exiting so you can create/fund your wallet. Please re-run the script afterward."

          # Suggest reboot if needed, then exit
          maybe_reboot_suggestion
          exit 0
          ;;
        No )
          info "Continuing without a wallet. The miner will likely fail unless you add a wallet."
          break
          ;;
      esac
    done
  fi
fi

##############################################################################
#      8) Install/Update compute-subnet environment and set up the miner
##############################################################################
info "Components already installed, proceeding with miner creation..."

##############################################################################
#                      9) Configure firewall (UFW)
##############################################################################
info "Installing and configuring UFW..."
install_package ufw || abort "Failed to install ufw."
info "Allowing SSH (22) in UFW..."
sudo ufw allow 22/tcp
info "Allowing validator port 4444 in UFW..."
sudo ufw allow 4444/tcp

# Decide netuid, network, axon port
if $AUTOMATED; then
  NETUID="${NETUID:-15}"
  if [[ "$NETUID" -eq 27 ]]; then
    SUBTENSOR_NETWORK_DEFAULT="subvortex.info:9944"
  else
    SUBTENSOR_NETWORK_DEFAULT="test"
  fi
  SUBTENSOR_NETWORK="${SUBTENSOR_NETWORK:-$SUBTENSOR_NETWORK_DEFAULT}"
  AXON_PORT="${AXON_PORT:-8091}"
else
  echo
  echo "Configure your miner for Bittensor."
  echo "Select the network (netuid):"
  echo "  1) Main Network (netuid 27)"
  echo "  2) Test Network (netuid 15)"
  read -rp "Your choice [1 or 2]: " network_choice
  if [[ "$network_choice" == "1" ]]; then
    NETUID=27
    SUBTENSOR_NETWORK_DEFAULT="subvortex.info:9944"
  elif [[ "$network_choice" == "2" ]]; then
    NETUID=15
    SUBTENSOR_NETWORK_DEFAULT="test"
  else
    echo "Invalid choice. Defaulting to Main Network (27)."
    NETUID=27
    SUBTENSOR_NETWORK_DEFAULT="subvortex.info:9944"
  fi
  read -rp "Enter your --subtensor.network (default: ${SUBTENSOR_NETWORK_DEFAULT}): " SUBTENSOR_NETWORK
  SUBTENSOR_NETWORK=${SUBTENSOR_NETWORK:-$SUBTENSOR_NETWORK_DEFAULT}
  read -rp "Enter the axon port (default: 8091): " AXON_PORT
  AXON_PORT=${AXON_PORT:-8091}
fi

info "Allowing Axon port ${AXON_PORT} in UFW..."
sudo ufw allow "${AXON_PORT}/tcp"
info "Enabling UFW..."
sudo ufw --force enable
info "UFW is enabled. Allowed ports: 22 (SSH), 4444 (validator), ${AXON_PORT} (Axon)."

##############################################################################
#                      10) WANDB configuration
##############################################################################

# Verify and set CS_PATH if not defined
if [ -z "${CS_PATH:-}" ]; then
  if $AUTOMATED; then
    if [ -f "/home/ubuntu/compute-subnet/setup.py" ] || [ -f "/home/ubuntu/compute-subnet/pyproject.toml" ]; then
      CS_PATH="/home/ubuntu/compute-subnet"
    else
      CS_PATH="$(pwd)"
    fi
  else
    if REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null); then
      CS_PATH="$REPO_ROOT"
    else
      CS_PATH="$(pwd)"
      if [ ! -f "$CS_PATH/setup.py" ] && [ ! -f "$CS_PATH/pyproject.toml" ]; then
        abort "Could not find setup.py or pyproject.toml. Please run from within compute-subnet repo root."
      fi
    fi
  fi
fi

ask_user_for_wandb() {
  read -rp "Enter your WANDB_API_KEY (leave blank if none): " WANDB_API_KEY
}

check_existing_wandb_key() {
  if grep -q "^WANDB_API_KEY=" "$env_path"; then
    read -rp "WANDB_API_KEY already exists in .env. Do you want to update it? (y/n): " update_choice
    if [[ "$update_choice" == "y" ]]; then
      ask_user_for_wandb
    else
      # If the user chooses not to update, do not modify WANDB_API_KEY
      WANDB_API_KEY=""
    fi
  else
    ask_user_for_wandb
  fi
}

inject_wandb_env() {
  local env_example="${CS_PATH}/.env.example"
  local env_path="${CS_PATH}/.env"
  info "Configuring .env for compute-subnet..."

  if [[ ! -f "$env_path" && -f "$env_example" ]]; then
    info "Copying .env.example to .env"
    cp "$env_example" "$env_path" || abort "Failed to copy .env.example to .env"
  fi

  if [[ -n "$WANDB_API_KEY" ]]; then
    info "Injecting WANDB_API_KEY into .env"
    sed -i "s@^WANDB_API_KEY=.*@WANDB_API_KEY=\"$WANDB_API_KEY\"@" "$env_path" 2>/dev/null \
      || info "Note: Could not update WANDB_API_KEY line in .env (it might not exist)."
  else
    info "WANDB_API_KEY is empty, leaving .env as is."
  fi

  # Configure SQLITE_DB_PATH
  info "Configuring SQLITE_DB_PATH in .env"
  sed -i "s@^SQLITE_DB_PATH=.*@SQLITE_DB_PATH=\"${CS_PATH}/database.db\"@" "$env_path" 2>/dev/null \
    || info "Note: Could not update SQLITE_DB_PATH line in .env (it might not exist)."

  info "Finished .env configuration."
}

if $AUTOMATED; then
  WANDB_API_KEY="${WANDB_KEY:-}"
else
  env_path="${CS_PATH}/.env"
  check_existing_wandb_key
fi

inject_wandb_env

##############################################################################
#                      11) PM2 miner launch
##############################################################################

# Ensure VENV_DIR is defined
VENV_DIR="${HOME_DIR}/venv"

if [ ! -f "${CS_PATH}/neurons/miner.py" ]; then
  abort "miner.py not found in ${CS_PATH}/neurons. Please check the repository structure."
fi

if [ ! -x "${CS_PATH}/neurons/miner.py" ]; then
  info "Making miner.py executable..."
  chmod +x "${CS_PATH}/neurons/miner.py" || abort "Failed to chmod +x miner.py."
fi

info "Starting miner with PM2..."
cd "${CS_PATH}" && \
source "${VENV_DIR}/bin/activate" && \
pm2 start "${VENV_DIR}/bin/python3" \
  --name "subnet${NETUID}_miner" \
  -- \
  "${CS_PATH}/neurons/miner.py" \
  --netuid "${NETUID}" \
  --subtensor.network "${SUBTENSOR_NETWORK}" \
  --wallet.name "default" \
  --wallet.hotkey "default" \
  --axon.port "${AXON_PORT}" \
  --logging.debug \
  --miner.blacklist.force_validator_permit \
  --auto_update yes \
  --env "HOME=${HOME_DIR}" \
  --env "PATH=/usr/local/cuda-12.8/bin:${PATH}" \
  --env "LD_LIBRARY_PATH=/usr/local/cuda-12.8/lib64:${LD_LIBRARY_PATH:-}" \
  --output "${CS_PATH}/pm2_out.log" \
  --error "${CS_PATH}/pm2_error.log" \
  || abort "Failed to start miner process in PM2."

echo
info "Miner process started under PM2."
echo "Use 'source ${VENV_DIR}/bin/activate && pm2 logs subnet${NETUID}_miner' to see logs, or check ${CS_PATH}/pm2_out.log / pm2_error.log."

if $AUTOMATED; then
  source "${VENV_DIR}/bin/activate" && pm2 save
  PM2_PATH=$(which pm2)
  sudo env PATH=$PATH:/usr/bin $PM2_PATH startup systemd -u $USER --hp /home/$USER
else
  echo "To ensure that your miner automatically restarts after a system reboot,"
  echo "It will configure PM2 to save the current process list and resurrect it upon system start."
  echo "Would you like to enable this feature?(Yes/No)"
  select yn in "Yes" "No"; do
    case $yn in
      Yes )
        source "${VENV_DIR}/bin/activate" && pm2 save
        PM2_PATH=$(which pm2)
        sudo env PATH=$PATH:/usr/bin $PM2_PATH startup systemd -u $USER --hp /home/$USER
        break
        ;;
      No )
        break
        ;;
    esac
  done
fi
echo
echo "NOTE: If you have not yet created and funded a wallet (coldkey/hotkey),"
echo "the miner will fail to serve until you do so and specify those keys."
echo
echo "Installation and miner setup is complete!"
echo "If needed, you can rerun this script or manually manage PM2 processes."
echo
