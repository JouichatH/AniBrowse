from .extractor import BaseExtractor


        # get the stream url for an episode of the defined source names
        response = self.session.get(
            f"https://{API_BASE_URL}{url.replace('clock', 'clock.json')}",
            timeout=10,
        )

        response.raise_for_status()
            case "Sak":
                logger.debug("Found streams from dropbox")
                return {
                    "server": "dropbox",
                    "headers": {"Referer": f"https://{API_BASE_URL}/"},
                    "subtitles": [],
                    "episode_title": (allanime_episode["notes"] or f"{anime_title}")
                    + f"; Episode {episode_number}",
                    "links": give_random_quality(response.json()["links"]),
                }
class DefaultExtractor(BaseExtractor):
    pass
