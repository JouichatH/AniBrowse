import re

ANIMEUNITY = "animeunity.so"
ANIMEUNITY_BASE = f"https://www.{ANIMEUNITY}"

MAX_TIMEOUT = 10

REPLACEMENT_WORDS = {"Season ": "", "Cour": "Part"}

TOKEN_REGEX = re.compile(r'<meta.*?name="csrf-token".*?content="([^"]*)".*?>')
DOWNLOAD_URL_REGEX = re.compile(r"window.downloadUrl\s*=\s*'([^']*)'")
