#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
# Copyright 2026 Matthew C. Tedder
#
# Install the daily rates load as a *user* timer -- no root, no system units.
#
#   ./deploy/systemd/install.sh [DSN] [PATH_TO_ETOOLS]
#
# Defaults to postgresql:///etools_rates and the etools on PATH. User timers
# only fire while the user has a session unless lingering is enabled; the
# script checks and tells you the one command to fix it.
set -euo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo="$(cd "$here/../.." && pwd)"

dsn="${1:-postgresql:///etools_rates}"
bin="${2:-$(command -v etools || true)}"

if [[ -z "$bin" ]]; then
    echo "install.sh: no 'etools' on PATH; pass its full path as the 2nd argument" >&2
    echo "            e.g. $repo/.venv/bin/etools" >&2
    exit 1
fi
[[ -x "$bin" ]] || { echo "install.sh: $bin is not executable" >&2; exit 1; }

units="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
mkdir -p "$units"

sed -e "s|@BIN@|$bin|g" \
    -e "s|@DSN@|$dsn|g" \
    -e "s|@WORKDIR@|$repo|g" \
    "$here/etools-rates.service.in" > "$units/etools-rates.service"
cp "$here/etools-rates.timer" "$units/etools-rates.timer"

systemctl --user daemon-reload
systemctl --user enable --now etools-rates.timer

echo "installed: $units/etools-rates.{service,timer}"
echo "  binary : $bin"
echo "  target : $dsn"

if [[ "$(loginctl show-user "$USER" --property=Linger --value 2>/dev/null)" != "yes" ]]; then
    echo
    echo "NOTE: lingering is off, so this timer stops when you log out."
    echo "      Enable it with:  sudo loginctl enable-linger $USER"
fi

echo
systemctl --user list-timers etools-rates.timer --no-pager
