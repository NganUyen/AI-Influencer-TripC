#!/usr/bin/env bash

set -euo pipefail

if [[ "${EUID}" -ne 0 ]]; then
    echo "Run this script as root or with sudo."
    exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_SRC="${SCRIPT_DIR}/systemd/ai-influencer-docker-cleanup.service"
TIMER_SRC="${SCRIPT_DIR}/systemd/ai-influencer-docker-cleanup.timer"
SERVICE_DST="/etc/systemd/system/ai-influencer-docker-cleanup.service"
TIMER_DST="/etc/systemd/system/ai-influencer-docker-cleanup.timer"

install -m 0644 "${SERVICE_SRC}" "${SERVICE_DST}"
install -m 0644 "${TIMER_SRC}" "${TIMER_DST}"

systemctl daemon-reload
systemctl enable --now ai-influencer-docker-cleanup.timer

echo "Installed and enabled ai-influencer-docker-cleanup.timer"
systemctl list-timers ai-influencer-docker-cleanup.timer --all
