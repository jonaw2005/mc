#!/usr/bin/env bash
set -Eeuo pipefail
ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
    echo 'Aufruf: sudo bash install.sh [--version VERSION] [--snapshots] [--accept-eula] [--memory 2G] [--port 25565] [--bind 0.0.0.0] [--configure-only]'
    echo 'Ohne --version startet die interaktive Versionsauswahl. Docker-Installation nur nach Rueckfrage.'
    exit 0
fi
if [[ "$(uname -s)" != Linux ]]; then
    echo 'Dieses Installationsskript benoetigt Linux.' >&2
    exit 1
fi
if [[ $EUID -ne 0 ]]; then
    echo 'Bitte mit sudo bash install.sh starten.' >&2
    exit 1
fi

confirm() {
    local answer
    read -r -p "$1 [ja/NEIN]: " answer
    [[ "$answer" == ja ]]
}

if ! command -v python3 >/dev/null || ! command -v curl >/dev/null; then
    if ! command -v apt-get >/dev/null; then
        echo 'Bitte Python 3, curl und CA-Zertifikate installieren.' >&2
        exit 1
    fi
    confirm 'Python 3, curl und CA-Zertifikate mit apt installieren?' || exit 1
    apt-get update
    apt-get install -y python3 curl ca-certificates
fi

if ! command -v docker >/dev/null; then
    # Only native Debian/Ubuntu; do not guess the base of derivative distributions.
    . /etc/os-release
    case "${ID:-}" in
        debian|ubuntu) ;;
        *) echo 'Bitte Docker Engine und das Compose-Plugin selbst installieren.' >&2; exit 1 ;;
    esac
    : "${VERSION_CODENAME:?Kein Distributions-Codename vorhanden}"
    for package in docker.io docker-compose docker-doc docker-buildx podman-docker containerd runc; do
        if [[ "$(dpkg-query -W -f='${Status}' "$package" 2>/dev/null || true)" == 'install ok installed' ]]; then
            echo "Konfliktpaket $package vorhanden. Bitte Docker manuell einrichten; es wird nichts entfernt." >&2
            exit 1
        fi
    done
    if [[ -e /etc/apt/sources.list.d/docker.sources || -e /etc/apt/sources.list.d/docker.list ]]; then
        echo 'Docker-Paketquelle bereits vorhanden. Bitte Docker-Installation manuell abschliessen.' >&2
        exit 1
    fi
    confirm 'Docker Engine und Compose aus dem offiziellen Docker-Repository installieren?' || exit 1
    apt-get update
    apt-get install -y ca-certificates curl
    install -m 0755 -d /etc/apt/keyrings
    curl --fail --silent --show-error --location --retry 3 "https://download.docker.com/linux/$ID/gpg" -o /etc/apt/keyrings/docker.asc
    chmod a+r /etc/apt/keyrings/docker.asc
    cat > /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/$ID
Suites: $VERSION_CODENAME
Components: stable
Architectures: $(dpkg --print-architecture)
Signed-By: /etc/apt/keyrings/docker.asc
EOF
    apt-get update
    apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
    systemctl enable --now docker
fi
docker compose version >/dev/null || { echo 'Docker Compose-Plugin fehlt.' >&2; exit 1; }
docker info >/dev/null || { echo 'Docker-Daemon nicht erreichbar. Bitte Dienst und Berechtigungen pruefen.' >&2; exit 1; }
exec python3 "$ROOT/scripts/install.py" "$@"