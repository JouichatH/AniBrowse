#!/bin/sh
#
# FastAnime Preview Info Script Template
# This script formats and displays the textual information in the FZF preview pane.
# Some values are injected by python those with '{name}' syntax using .replace()


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


draw_rule(){
    ll=2
    while [ $ll -le $FZF_PREVIEW_COLUMNS ];do
        echo -n -e "{C_RULE}─{RESET}"
        ((ll++))
    done
    echo
}

# --- Display Content ---
draw_rule
print_kv "Title" "{TITLE}"

draw_rule

# Key-Value Stats Section
score_multiplier=1
if ! [ "{SCORE}" = "N/A" ];then
    score_multiplier=2
fi
print_kv "Score" "{SCORE}" $score_multiplier
print_kv "Favourites" "{FAVOURITES}"
print_kv "Popularity" "{POPULARITY}"
print_kv "Status" "{STATUS}"
print_kv "Episodes" "{EPISODES}"
print_kv "Next Episode" "{NEXT_EPISODE}"

draw_rule

print_kv "Genres" "{GENRES}"
print_kv "Format" "{FORMAT}"

draw_rule

print_kv "List Status" "{USER_STATUS}"
print_kv "Progress" "{USER_PROGRESS}"

draw_rule

print_kv "Start Date" "{START_DATE}"
print_kv "End Date" "{END_DATE}"

draw_rule

print_kv "Studios" "{STUDIOS}"
print_kv "Synonymns" "{SYNONYMNS}"
print_kv "Tags" "{TAGS}"

draw_rule

# Synopsis
echo "{SYNOPSIS}" | fold -s -w "$WIDTH"
