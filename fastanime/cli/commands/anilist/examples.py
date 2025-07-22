main = """
\b
\b\bExamples:
  # ---- search ----  
\b
  # get anime with the tag of isekai
  fastanime anilist search -T isekai
\b
  # get anime of 2024 and sort by popularity
  # that has already finished airing or is releasing
  # and is not in your anime lists
  fastanime anilist search -y 2024 -s POPULARITY_DESC --status RELEASING --status FINISHED --not-on-list
\b
  # get anime of 2024 season WINTER
  fastanime anilist search -y 2024 --season WINTER
\b
  # get anime genre action and tag isekai,magic
  fastanime anilist search -g Action -T Isekai -T Magic
\b
  # get anime of 2024 thats finished airing
  fastanime anilist search -y 2024 -S FINISHED
\b
  # get the most favourite anime movies
  fastanime anilist search -f MOVIE -s FAVOURITES_DESC
\b
  # ---- login ----
\b
  # To sign in just run 
  fastanime anilist login
\b
  # To view your login status 
  fastanime anilist login --status
\b
  # To erase login data
  fastanime anilist login --erase
\b
  # ---- notifier ----  
\b
  # basic form
  fastanime anilist notifier
\b
  # with logging to stdout
  fastanime --log anilist notifier
\b
  # with logging to a file. stored in the same place as your config
  fastanime --log-file anilist notifier
"""
