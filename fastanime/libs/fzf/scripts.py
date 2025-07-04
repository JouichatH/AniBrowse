FETCH_ANIME_SCRIPT = r"""
fetch_anime_for_fzf() {
  local search_term="$1"
  if [ -z "$search_term" ]; then exit 0; fi

  local query='
  query ($search: String) {
    Page(page: 1, perPage: 25) {
      media(search: $search, type: ANIME, sort: [SEARCH_MATCH]) {
        id
        title { romaji english }
        meanScore
        format
        status
      }
    }
  }
  '

  local json_payload
  json_payload=$(jq -n --arg query "$query" --arg search "$search_term" \
                    '{query: $query, variables: {search: $search}}')

  curl --silent \
       --header "Content-Type: application/json" \
       --header "Accept: application/json" \
       --request POST \
       --data "$json_payload" \
       https://graphql.anilist.co | \
  jq -r '.data.Page.media[]? | select(.title.romaji) |
         "\(.title.english // .title.romaji) | Score: \(.meanScore // "N/A") | ID: \(.id)"'
}
fetch_anime_details() {
  local anime_id
  anime_id=$(echo "$1" | sed -n 's/.*ID: \([0-9]*\).*/\1/p')
  if [ -z "$anime_id" ]; then echo "Select an item to see details..."; return; fi

  local query='
  query ($id: Int) {
    Media(id: $id, type: ANIME) {
      title { romaji english }
      description(asHtml: false)
      genres
      meanScore
      episodes
      status
      format
      season
      seasonYear
      studios(isMain: true) { nodes { name } }
    }
  }
  '
  local json_payload
  json_payload=$(jq -n --arg query "$query" --argjson id "$anime_id" \
                    '{query: $query, variables: {id: $id}}')

  # Fetch and format details for the preview window
  curl --silent \
       --header "Content-Type: application/json" \
       --header "Accept: application/json" \
       --request POST \
       --data "$json_payload" \
       https://graphql.anilist.co | \
  jq -r '
    .data.Media |
    "Title: \(.title.english // .title.romaji)\n" +
    "Score: \(.meanScore // "N/A") | Episodes: \(.episodes // "N/A")\n" +
    "Status: \(.status // "N/A") | Format: \(.format // "N/A")\n" +
    "Season: \(.season // "N/A") \(.seasonYear // "")\n" +
    "Genres: \(.genres | join(", "))\n" +
    "Studio: \(.studios.nodes[0].name // "N/A")\n\n" +
    "\(.description | gsub("<br><br>"; "\n\n") | gsub("<[^>]*>"; "") | gsub("&quot;"; "\""))"
  '
}
"""
