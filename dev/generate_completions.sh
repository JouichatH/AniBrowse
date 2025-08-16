#!/usr/bin/env bash
APP_DIR="$(
  cd -- "$(dirname "$0")" >/dev/null 2>&1
  pwd -P
)"

# fish shell completions
_VIU_COMPLETE=fish_source viu >"$APP_DIR/completions/viu.fish"

# zsh completions
_VIU_COMPLETE=zsh_source viu >"$APP_DIR/completions/viu.zsh"

# bash completions
_VIU_COMPLETE=bash_source viu >"$APP_DIR/completions/viu.bash"
