fzf_preview = r"""
fzf_preview() {
  file=$1

  dim=${FZF_PREVIEW_COLUMNS}x${FZF_PREVIEW_LINES}
  if [ "$dim" = x ]; then
    dim=$(stty size </dev/tty | awk "{print \$2 \"x\" \$1}")
  fi
  if ! [ "$FASTANIME_IMAGE_RENDERER" = "icat" ] && [ -z "$KITTY_WINDOW_ID" ] && [ "$((FZF_PREVIEW_TOP + FZF_PREVIEW_LINES))" -eq "$(stty size </dev/tty | awk "{print \$1}")" ]; then
    dim=${FZF_PREVIEW_COLUMNS}x$((FZF_PREVIEW_LINES - 1))
  fi

  if [ "$FASTANIME_IMAGE_RENDERER" = "icat" ] && [ -z "$GHOSTTY_BIN_DIR" ]; then
    if command -v kitten >/dev/null 2>&1; then
      kitten icat --clear --transfer-mode=memory --unicode-placeholder --stdin=no --place="$dim@0x0" "$file" | sed "\$d" | sed "$(printf "\$s/\$/\033[m/")"
    elif command -v icat >/dev/null 2>&1; then
      icat --clear --transfer-mode=memory --unicode-placeholder --stdin=no --place="$dim@0x0" "$file" | sed "\$d" | sed "$(printf "\$s/\$/\033[m/")"
    else
      kitty icat --clear --transfer-mode=memory --unicode-placeholder --stdin=no --place="$dim@0x0" "$file" | sed "\$d" | sed "$(printf "\$s/\$/\033[m/")"
    fi

  elif [ -n "$GHOSTTY_BIN_DIR" ]; then
    if command -v kitten >/dev/null 2>&1; then
      kitten icat --clear --transfer-mode=memory --unicode-placeholder --stdin=no --place="$dim@0x0" "$file" | sed "\$d" | sed "$(printf "\$s/\$/\033[m/")"
    elif command -v icat >/dev/null 2>&1; then
      icat --clear --transfer-mode=memory --unicode-placeholder --stdin=no --place="$dim@0x0" "$file" | sed "\$d" | sed "$(printf "\$s/\$/\033[m/")"
    else
      chafa -s "$dim" "$file"
    fi
  elif command -v chafa >/dev/null 2>&1; then
    case "$PLATFORM" in
    android) chafa -s "$dim" "$file" ;;
    windows) chafa -f sixel -s "$dim" "$file" ;;
    *) chafa -s "$dim" "$file" ;;
    esac
    echo

  elif command -v imgcat >/dev/null; then
    imgcat -W "${dim%%x*}" -H "${dim##*x}" "$file"

  else
    echo please install a terminal image viewer
    echo either icat for kitty terminal and wezterm or imgcat or chafa
  fi
}
"""
