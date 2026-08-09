#!/usr/bin/env bash
# Wrapper for Git Bash — same as scripts/start.sh
exec "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/scripts/start.sh" "$@"
