#!/bin/sh
#
# FastAnime Episode Preview Info Script Template
# This script formats and displays episode information in the FZF preview pane.
# Values are injected by python using .replace()

# --- Terminal Dimensions ---
WIDTH=${FZF_PREVIEW_COLUMNS:-80} # Set a fallback width of 80

# --- Helper function for printing a key-value pair, aligning the value to the right ---
print_kv() {
    local key="$1"
    local value="$2"
    local key_len=${#key}
    local value_len=${#value}
    local multiplier="${3:-1}"

    # Correctly calculate padding by accounting for the key, the ": ", and the value.
    local padding_len=$((WIDTH - key_len - 2 - value_len * multiplier))

    # If the text is too long to fit, just add a single space for separation.
    if [ "$padding_len" -lt 1 ]; then
        padding_len=1
        value=$(echo $value| fold -s -w "$((WIDTH - key_len - 3))")
        printf "{C_KEY}%s:{RESET}%*s%s\\n" "$key" "$padding_len" "" " $value"
    else
        printf "{C_KEY}%s:{RESET}%*s%s\\n" "$key" "$padding_len" "" " $value"
    fi
}

# --- Draw a rule across the screen ---
draw_rule() {
    local rule
    # Generate the line of '─' characters, removing the trailing newline `tr` adds.
    rule=$(printf '%*s' "$WIDTH" | tr ' ' '─' | tr -d '\n')
    # Print the rule with colors and a single, clean newline.
    printf "{C_RULE}%s{RESET}\\n" "$rule"
}

# --- Display Episode Content ---
draw_rule
print_kv "Episode" "{TITLE}"
draw_rule

# Episode-specific information
print_kv "Duration" "{GENRES}"
print_kv "Status" "{STATUS}"
draw_rule

# Episode description/summary
echo "{SYNOPSIS}" | fold -s -w "$WIDTH"
