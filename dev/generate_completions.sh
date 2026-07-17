#!/usr/bin/env bash
APP_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# fish shell completions
_ANI_BROWSE_COMPLETE=fish_source ani-browse >"$APP_DIR/completions/ani-browse.fish"

# zsh completions
_ANI_BROWSE_COMPLETE=zsh_source ani-browse >"$APP_DIR/completions/ani-browse.zsh"

# bash completions
_ANI_BROWSE_COMPLETE=bash_source ani-browse >"$APP_DIR/completions/ani-browse.bash"
