#!/usr/bin/env bash
# Renders spikes/agent-a/.claude/settings.json (gitignored: it holds absolute paths) from the committed template.
set -euo pipefail
cd "$(dirname "$0")"
sed "s#{{SPIKES_DIR}}#$PWD#g" agent-a/.claude/settings.template.json > agent-a/.claude/settings.json
echo "rendered spikes/agent-a/.claude/settings.json"
