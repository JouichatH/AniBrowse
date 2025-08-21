import re

ANIMEUNITY = "animeunity.so"
ANIMEUNITY_BASE = f"https://www.{ANIMEUNITY}"

MAX_TIMEOUT = 10

TOKEN_REGEX = re.compile(r'<meta.*?name="csrf-token".*?content="([^"]*)".*?>')
DOWNLOAD_URL_REGEX = r"window.downloadUrl\s*=\s*'([^']*)'"
