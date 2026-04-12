#!/usr/bin/env bash

set -euo pipefail

ONOS_VERSION="${ONOS_VERSION:-2.7.0}"
INSTALL_ONOS="${INSTALL_ONOS:-1}"
WORKSHOP_USER="${WORKSHOP_USER:-${SUDO_USER:-$(id -un)}}"

if [[ "${EUID}" -eq 0 ]]; then
  SUDO=""
else
  SUDO="sudo"
fi

log() {
  printf '\n==> %s\n' "$1"
}

warn() {
  printf 'warning: %s\n' "$1" >&2
}

die() {
  printf 'error: %s\n' "$1" >&2
  exit 1
}

user_in_group() {
  local user="$1" group="$2"
  id -nG "${user}" 2>/dev/null | tr ' ' '\n' | grep -qx "${group}"
}

print_docker_access_notes() {
  if [[ "${DOCKER_GROUP_WAS_PRESENT}" -eq 1 ]]; then
    echo "  - Docker group already present for ${WORKSHOP_USER}"
    return
  fi

  echo "  - Docker access was added for ${WORKSHOP_USER}"
  echo "  - Log out and log back in before using Docker as a regular user"
}

APT_INSTALL_OPTS=(
  -y
  -o Dpkg::Options::=--force-confdef
  -o Dpkg::Options::=--force-confold
  -o Acquire::Retries=3
)

apt_update() {
  ${SUDO} apt-get update -o Acquire::Retries=3
}

apt_install() {
  local log_file status retry_status
  log_file="$(mktemp)"

  set +e
  ${SUDO} apt-get install "${APT_INSTALL_OPTS[@]}" "$@" 2>&1 | tee "${log_file}"
  status=${PIPESTATUS[0]}
  set -e

  if [[ "${status}" -eq 0 ]]; then
    rm -f "${log_file}"
    return 0
  fi

  if grep -Eq '404  Not Found|Unable to fetch some archives|Failed to fetch' "${log_file}"; then
    warn "apt returned missing archives; refreshing package metadata and retrying once"
    ${SUDO} apt-get clean
    ${SUDO} rm -rf /var/lib/apt/lists/*
    apt_update
    set +e
    ${SUDO} apt-get install "${APT_INSTALL_OPTS[@]}" --fix-missing "$@"
    retry_status=$?
    set -e
    rm -f "${log_file}"
    return "${retry_status}"
  fi

  rm -f "${log_file}"
  return "${status}"
}

install_docker_from_ubuntu() {
  apt_install docker.io
}

install_docker_from_official_repo() {
  local arch
  arch="$(dpkg --print-architecture)"

  log "Installing Docker from the official Docker repository"
  ${SUDO} install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    ${SUDO} gpg --batch --yes --dearmor -o /etc/apt/keyrings/docker.gpg
  ${SUDO} chmod a+r /etc/apt/keyrings/docker.gpg
  echo \
    "deb [arch=${arch} signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/ubuntu ${VERSION_CODENAME} stable" | \
    ${SUDO} tee /etc/apt/sources.list.d/docker.list >/dev/null

  apt_update
  apt_install containerd.io docker-ce docker-ce-cli docker-buildx-plugin docker-compose-plugin
}

install_docker_packages() {
  if install_docker_from_ubuntu; then
    return 0
  fi

  warn "Ubuntu mirror could not provide docker.io after a refresh; falling back to Docker's official repository"
  install_docker_from_official_repo
}

pip_install() {
  local pip_args=()
  if python3 -m pip install --help 2>/dev/null | grep -q -- '--break-system-packages'; then
    pip_args+=(--break-system-packages)
  fi
  ${SUDO} python3 -m pip install "${pip_args[@]}" "$@"
}

onos_api() {
  curl -fsS -u onos:rocks "$@"
}

onos_activate_app() {
  local app="$1"
  onos_api -X POST "http://localhost:8181/onos/v1/applications/${app}/active" >/dev/null
}

onos_configure_component() {
  local component="$1" payload="$2" status body_file
  body_file="$(mktemp)"
  status="$(curl -sS -u onos:rocks \
    -o "${body_file}" \
    -w '%{http_code}' \
    -X POST \
    -H "Content-Type: application/json" \
    "http://localhost:8181/onos/v1/configuration/${component}?preset=true" \
    -d "${payload}")"

  case "${status}" in
    200|204)
      rm -f "${body_file}"
      return 0
      ;;
    *)
      cat "${body_file}" >&2 || true
      rm -f "${body_file}"
      return 1
      ;;
  esac
}

onos_component_property_equals() {
  local component="$1" property="$2" expected="$3"
  onos_api "http://localhost:8181/onos/v1/configuration/${component}" | \
    grep -Fq "\"${property}\":\"${expected}\""
}

srv6_supported() {
  if ip -6 route add help 2>&1 | grep -qi seg6; then
    return 0
  fi

  for module in seg6_iptunnel seg6_local; do
    if ${SUDO} modinfo "${module}" >/dev/null 2>&1; then
      return 0
    fi
  done

  if grep -qi seg6 /proc/modules 2>/dev/null; then
    return 0
  fi

  if grep -qE '^CONFIG_IPV6_SEG6.*=y' "/boot/config-$(uname -r)" 2>/dev/null; then
    return 0
  fi

  return 1
}

write_srv6_sysctl_file() {
  ${SUDO} tee /etc/sysctl.d/90-srv6.conf >/dev/null <<'EOF'
net.ipv6.conf.all.forwarding = 1
net.ipv6.conf.default.forwarding = 1
net.ipv6.conf.all.seg6_enabled = 1
net.ipv6.conf.default.seg6_enabled = 1
EOF

  if [[ -e /proc/sys/net/ipv6/seg6_require_hmac ]]; then
    echo "net.ipv6.seg6_require_hmac = 0" | ${SUDO} tee -a /etc/sysctl.d/90-srv6.conf >/dev/null
  else
    warn "net.ipv6.seg6_require_hmac is not available on this kernel; skipping"
  fi
}

usage() {
  cat <<EOF
Usage:
  scripts/setup.sh

Environment variables:
  WORKSHOP_USER  User to add to docker/wireshark groups. Default: ${WORKSHOP_USER}
  ONOS_VERSION   ONOS Docker image tag. Default: ${ONOS_VERSION}
  INSTALL_ONOS   Set to 0 to skip ONOS container setup. Default: ${INSTALL_ONOS}

What this installs:
  - Base workshop tools: git, vim, tmux, curl, wget, ssh client
  - Python 3 and the Python packages used in Labs 2-4
  - Mininet, Open vSwitch, iproute2, tcpdump, tshark, iperf3, iptables
  - Docker and an ONOS container for Lab 2
  - SRv6 sysctl settings for Labs 3-4

Examples:
  scripts/setup.sh
  WORKSHOP_USER=ubuntu scripts/setup.sh
  INSTALL_ONOS=0 scripts/setup.sh
EOF
}

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -f /etc/os-release ]]; then
  die "cannot determine operating system"
fi

# shellcheck disable=SC1091
source /etc/os-release

if [[ "${ID:-}" != "ubuntu" ]]; then
  die "this script currently supports Ubuntu only"
fi

if ! id "${WORKSHOP_USER}" >/dev/null 2>&1; then
  die "user '${WORKSHOP_USER}' does not exist"
fi

if ! command -v apt-get >/dev/null 2>&1; then
  die "apt-get is required"
fi

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a

DOCKER_GROUP_WAS_PRESENT=0
if user_in_group "${WORKSHOP_USER}" docker; then
  DOCKER_GROUP_WAS_PRESENT=1
fi

log "Pre-seeding package configuration for unattended install"
echo "wireshark-common wireshark-common/install-setuid boolean true" | ${SUDO} debconf-set-selections
echo "iperf3 iperf3/start_daemon boolean false" | ${SUDO} debconf-set-selections
echo "iperf3 iperf3/public boolean false" | ${SUDO} debconf-set-selections

log "Updating apt metadata"
apt_update

log "Installing base system packages"
apt_install \
  apt-transport-https \
  build-essential \
  ca-certificates \
  curl \
  git \
  gnupg \
  hping3 \
  iperf \
  iperf3 \
  iproute2 \
  iptables \
  iputils-ping \
  libffi-dev \
  libssl-dev \
  lsb-release \
  mininet \
  net-tools \
  openvswitch-common \
  openvswitch-switch \
  openssh-client \
  procps \
  python3 \
  python3-dev \
  python3-pip \
  python3-requests \
  python3-scapy \
  python3-venv \
  software-properties-common \
  tar \
  tcpdump \
  tmux \
  tshark \
  unzip \
  vim \
  wget

log "Installing Docker packages"
install_docker_packages

# termshark is helpful but not guaranteed to exist in every Ubuntu repo.
if apt-cache show termshark >/dev/null 2>&1; then
  log "Installing optional termshark"
  apt_install termshark
else
  warn "termshark package not found in apt repositories; skipping"
fi

log "Installing Python workshop packages"
pip_install --upgrade pip
pip_install \
  black \
  matplotlib \
  networkx \
  pylint \
  pyyaml

log "Configuring Wireshark capture permissions"
${SUDO} usermod -aG wireshark "${WORKSHOP_USER}" || true

log "Enabling and starting required services"
${SUDO} systemctl enable --now containerd
${SUDO} systemctl enable --now docker
${SUDO} systemctl enable --now openvswitch-switch
${SUDO} systemctl stop openvswitch-testcontroller >/dev/null 2>&1 || true
${SUDO} systemctl disable openvswitch-testcontroller >/dev/null 2>&1 || true

if [[ "${DOCKER_GROUP_WAS_PRESENT}" -eq 1 ]]; then
  log "${WORKSHOP_USER} is already in docker group"
else
  log "Adding ${WORKSHOP_USER} to docker group"
  ${SUDO} usermod -aG docker "${WORKSHOP_USER}"
fi

log "Configuring SRv6 sysctls"
write_srv6_sysctl_file
${SUDO} sysctl -p /etc/sysctl.d/90-srv6.conf >/dev/null

log "Checking SRv6 kernel support"
if srv6_supported; then
  echo "SRv6 support detected"
else
  warn "SRv6 support was not detected; Labs 3-4 may not work"
fi

for module in seg6_iptunnel seg6_local; do
  ${SUDO} modprobe "${module}" >/dev/null 2>&1 || true
done

if [[ "${INSTALL_ONOS}" == "1" ]]; then
  log "Pulling ONOS Docker image"
  ${SUDO} docker pull "onosproject/onos:${ONOS_VERSION}"

  if ${SUDO} docker ps -a --format '{{.Names}}' | grep -qx onos; then
    log "Starting existing ONOS container"
    ${SUDO} docker start onos >/dev/null || true
  else
    log "Creating ONOS container"
    ${SUDO} docker volume create onos_data >/dev/null
    ${SUDO} docker run -d \
      --name onos \
      --restart unless-stopped \
      -p 6640:6640 \
      -p 6653:6653 \
      -p 8101:8101 \
      -p 8181:8181 \
      -p 9876:9876 \
      -v onos_data:/root/onos/apache-karaf-4.2.14/data \
      -e ONOS_APPS=drivers,openflow,fwd,proxyarp,segmentrouting,tunnel \
      "onosproject/onos:${ONOS_VERSION}" >/dev/null
  fi

  log "Waiting for ONOS REST API"
  ready=0
  for _ in $(seq 1 40); do
    if onos_api http://localhost:8181/onos/v1/applications >/dev/null 2>&1; then
      ready=1
      break
    fi
    sleep 5
  done

  if [[ "${ready}" != "1" ]]; then
    warn "ONOS did not become ready in time; check: sudo docker logs onos"
  else
    log "Activating ONOS apps"
    for app in \
      org.onosproject.openflow \
      org.onosproject.fwd \
      org.onosproject.proxyarp; do
      onos_activate_app "${app}" || warn "failed to activate ONOS app: ${app}"
    done

    log "Configuring ONOS reactive forwarding for IPv6"
    onos_configure_component \
      org.onosproject.fwd.ReactiveForwarding \
      '{"ipv6Forwarding":"true"}' \
      || warn "failed to request org.onosproject.fwd.ReactiveForwarding ipv6Forwarding=true"

    configured=0
    for _ in $(seq 1 10); do
      if onos_component_property_equals \
        org.onosproject.fwd.ReactiveForwarding \
        ipv6Forwarding \
        true; then
        configured=1
        break
      fi
      sleep 1
    done

    if [[ "${configured}" != "1" ]]; then
      warn "ONOS fwd ipv6Forwarding did not become true; check: onos> cfg get org.onosproject.fwd.ReactiveForwarding"
    fi
  fi
fi

log "Version summary"
python3 --version || true
mn --version || true
ovs-vsctl --version | head -1 || true
docker --version || true
tshark --version 2>/dev/null | head -1 || true

cat <<EOF

Workshop setup complete.

Key notes:
  - User configured: ${WORKSHOP_USER}
$(print_docker_access_notes)
  - ONOS REST API: http://localhost:8181/onos/v1/  (onos / rocks)
  - ONOS CLI:      ssh -p 8101 -o HostKeyAlgorithms=+ssh-rsa onos@localhost

EOF
