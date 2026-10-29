"""
Webtoon scraper - Scrapes webtoons from webtoons.com
"""

import re
from typing import List
from urllib.parse import urljoin

from .base import BaseScraper, ComicInfo, ChapterInfo, ScraperError


class WebtoonScraper(BaseScraper):
    """Scraper for Webtoon (webtoons.com)"""

    DOMAIN_PATTERNS = [r"webtoons\.com"]
    BASE_URL = "https://www.webtoons.com"
    RATE_LIMIT = 2.0

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return bool(re.search(r"webtoons\.com", url))

    async def fetch_comic_info(self, url: str) -> ComicInfo:
        soup = await self._fetch_html(url)

        # Extract title
        title_elem = soup.select_one(".info h1, .title, #genreIntro h1")
        if not title_elem:
            raise ScraperError("Could not find webtoon title")
        title = title_elem.get_text(strip=True)

        # Extract author
        author = "Unknown"
        author_elem = soup.select_one(".author, .genre .author_name")
        if author_elem:
            author = author_elem.get_text(strip=True)

        # Extract description
        desc_elem = soup.select_one(".summary, #genreIntro p, .info p")
        description = ""
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Extract cover
        cover_url = None
        cover_elem = soup.select_one(".thumb img, .cover img")
        if cover_elem and cover_elem.get("src"):
            cover_url = cover_elem["src"]

        # Extract episodes (chapters)
        chapters = []
        episode_list = soup.select("#_episodeList .episode_list a, .episodelist li a")

        for idx, link in enumerate(reversed(episode_list), 1):
            episode_url = urljoin(self.BASE_URL, link["href"])
            episode_title = link.get_text(strip=True)

            chapters.append(ChapterInfo(
                number=idx,
                title=episode_title,
                url=episode_url
            ))

        return ComicInfo(
            title=title,
            author=author,
            description=description,
            cover_url=cover_url,
            chapters=chapters,
            url=url
        )

    async def fetch_chapter_images(self, chapter_url: str) -> List[str]:
        """Fetch image URLs for a webtoon episode"""
        soup = await self._fetch_html(chapter_url)

        images = []

        # Webtoon images are usually in a specific container
        img_tags = soup.select(".viewer_img img, #_imageList img, .viewer img")

        for img in img_tags:
            src = img.get("src") or img.get("data-url")
            if src:
                if src.startswith("//"):
                    src = "https:" + src
                images.append(src)

        return images

    async def search(self, query: str) -> List[ComicInfo]:
        """Search for webtoons"""
        search_url = f"{self.BASE_URL}/search?keyword={query}"
        soup = await self._fetch_html(search_url)

        results = []
        result_items = soup.select(".search_result a, .card_list li a")

        for item in result_items[:20]:
            title_elem = item.select_one(".title, .subj")
            if not title_elem:
                continue

            title = title_elem.get_text(strip=True)
            url = urljoin(self.BASE_URL, item["href"])

            results.append(ComicInfo(
                title=title,
                author="Unknown",
                url=url
            ))

        return results
