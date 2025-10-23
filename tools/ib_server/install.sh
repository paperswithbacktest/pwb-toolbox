#!/usr/bin/env bash
set -euo pipefail

# -----------------------------
# Config (edit if needed)
# -----------------------------
CONDA_DIR="${HOME}/miniconda3"
ENV_NAME="pwb"
ENV_FILE="environment.yml"
DATA_BASE="${HOME}/pwb-data"
DL_DIR="${HOME}/Downloads"

# -----------------------------
# Helpers
# -----------------------------
log()   { printf "\n\033[1;32m==> %s\033[0m\n"   "$*"; }
warn()  { printf "\n\033[1;33m[warning] %s\033[0m\n" "$*"; }

# -----------------------------
# Pre-req packages
# -----------------------------
log "Installing prerequisites (wget, git, curl, bzip2, build tools)..."
sudo apt-get update -y
sudo apt-get install -y wget git curl bzip2 build-essential

# -----------------------------
# Miniconda installation
# -----------------------------
if [ -x "${CONDA_DIR}/bin/conda" ]; then
  log "Miniconda already installed at ${CONDA_DIR}."
else
  log "Installing Miniconda to ${CONDA_DIR}..."
  mkdir -p "${CONDA_DIR}"
  mkdir -p "${DL_DIR}"
  wget -q https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh -O "${DL_DIR}/miniconda.sh"
  bash "${DL_DIR}/miniconda.sh" -b -u -p "${CONDA_DIR}"
  rm -f "${DL_DIR}/miniconda.sh"
fi

# Ensure conda is available in this shell and future shells
if ! grep -q 'conda.sh' "${HOME}/.bashrc" 2>/dev/null; then
  echo "source ${CONDA_DIR}/etc/profile.d/conda.sh" >> "${HOME}/.bashrc"
fi
# shellcheck disable=SC1091
source "${CONDA_DIR}/etc/profile.d/conda.sh"

# -----------------------------
# Conda environment setup
# -----------------------------
if conda env list | awk '{print $1}' | grep -qx "${ENV_NAME}"; then
  log "Conda env '${ENV_NAME}' already exists. Updating from ${ENV_FILE}..."
  conda env update -n "${ENV_NAME}" -f "${ENV_FILE}" --prune
else
  log "Creating conda env '${ENV_NAME}' from ${ENV_FILE}..."
  conda env create -f "${ENV_FILE}"
fi

log "Activating conda env '${ENV_NAME}'..."
conda activate "${ENV_NAME}"

# -----------------------------
# GUI: XFCE + xRDP
# -----------------------------
log "Installing XFCE desktop and xRDP..."
sudo apt-get install -y xfce4 xfce4-goodies xrdp

log "Configuring xRDP to use XFCE..."
echo "xfce4-session" > "${HOME}/.xsession"
sudo systemctl enable xrdp
sudo systemctl restart xrdp

log "Setting French keyboard layout for X session..."
echo "setxkbmap fr" > "${HOME}/.xsessionrc"

if command -v ufw >/dev/null 2>&1; then
  if sudo ufw status | grep -q "Status: active"; then
    log "Allowing RDP (3389/tcp) via UFW..."
    sudo ufw allow 3389/tcp
  else
    warn "UFW not active; skipping firewall rule for 3389."
  fi
else
  warn "UFW not installed; skipping firewall rule for 3389."
fi

# -----------------------------
# Interactive Brokers
# -----------------------------

# Determine architecture tag used by IBKR download names
ARCH="$(uname -m)"
if [[ "$ARCH" == "x86_64" || "$ARCH" == "amd64" ]]; then
  IBG_ARCH="x64"
elif [[ "$ARCH" =~ ^i[3-6]86$ ]]; then
  IBG_ARCH="x86"
else
  warn "Unrecognized arch '$ARCH'; defaulting to 64-bit installer."
  IBG_ARCH="x64"
fi

# -----------------------------
# Interactive Brokers TWS
# -----------------------------
log "Downloading Interactive Brokers TWS installer..."
TWS_CHANNEL="stable"  # change to 'latest' to track latest

TWS_INSTALLER="tws-${TWS_CHANNEL}-linux-${IBG_ARCH}.sh"
TWS_URL="https://download2.interactivebrokers.com/installers/tws/${TWS_CHANNEL}/${TWS_INSTALLER}"

mkdir -p "${DL_DIR}"
wget -q "${TWS_URL}" -O "${DL_DIR}/${TWS_INSTALLER}"
chmod +x "${DL_DIR}/${TWS_INSTALLER}"

log "Running TWS installer (may prompt interactively)..."
cd "${DL_DIR}"
./"${TWS_INSTALLER}"

rm -f "${DL_DIR}/${TWS_INSTALLER}"

# -----------------------------
# Interactive Brokers IB Gateway
# -----------------------------
log "Downloading Interactive Brokers IB Gateway installer..."
# Choose Stable or Latest channel
IBG_CHANNEL="stable-standalone"  # change to 'latest-standalone' to track latest

IBG_INSTALLER="ibgateway-${IBG_CHANNEL}-linux-${IBG_ARCH}.sh"
IBG_URL="https://download2.interactivebrokers.com/installers/ibgateway/${IBG_CHANNEL}/${IBG_INSTALLER}"

mkdir -p "${DL_DIR}"
wget -q "${IBG_URL}" -O "${DL_DIR}/${IBG_INSTALLER}"
chmod +x "${DL_DIR}/${IBG_INSTALLER}"

log "Running IB Gateway installer (may prompt interactively)..."
cd "${DL_DIR}"
./"${IBG_INSTALLER}"

rm -f "${DL_DIR}/${IBG_INSTALLER}"

# -----------------------------
# Data directories
# -----------------------------
log "Creating data directories under ${DATA_BASE} ..."
mkdir -p "${DATA_BASE}/ib/execution_logs"
mkdir -p "${DATA_BASE}/ib/monitoring_reports"

# -----------------------------
# Done
# -----------------------------
log "Setup complete."
echo "Notes:"
echo " - To use the conda env in new shells, it’s already initialized in ~/.bashrc."
echo " - To RDP in: connect to this machine on port 3389 (user: ${USER})."