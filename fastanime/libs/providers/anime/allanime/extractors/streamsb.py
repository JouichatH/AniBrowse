from .extractor import BaseExtractor

                # TODO: requires some serious work i think : )
                response = self.session.get(
                    url,
                    timeout=10,
                )
                response.raise_for_status()
                embed_html = response.text.replace(" ", "").replace("\n", "")
                logger.debug("Found streams from Ss-Hls")
                return {
                    "server": "StreamSb",
                    "headers": {"Referer": f"https://{API_BASE_URL}/"},
                    "subtitles": [],
                    "episode_title": (allanime_episode["notes"] or f"{anime_title}")
                    + f"; Episode {episode_number}",
                    "links": give_random_quality(response.json()["links"]),
                }

class SsHlsExtractor(BaseExtractor):
    pass
