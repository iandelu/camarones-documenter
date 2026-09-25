#!/bin/sh
# Compatibility alias. The public command is camaron.
exec "$(dirname "$0")/camaron.command" "$@"
