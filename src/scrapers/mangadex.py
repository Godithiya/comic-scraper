"""
MangaDex scraper - Uses MangaDex API
"""

import re
from typing import List, Optional
from urllib.parse import urljoin

from .base import BaseScraper, ComicInfo, ChapterInfo, ScraperError


class MangaDexScraper(BaseScraper):
    """Scraper for MangaDex (mangadex.org)"""

    DOMAIN_PATTERNS = [r"mangadex\.org"]
    BASE_URL = "https://api.mangadex.org"
    RATE_LIMIT = 5.0  # 5 requests per second

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return bool(re.search(r"mangadex\.org", url))

    def _extract_id(self, url: str) -> str:
        """Extract manga/chapter ID from URL"""
        # Match patterns like /title/{id} or /chapter/{id}
        match = re.search(r"/(?:title|chapter)/([a-f0-9-]+)", url)
        if not match:
            raise ScraperError(f"Invalid MangaDex URL: {url}")
        return match.group(1)

    async def fetch_comic_info(self, url: str) -> ComicInfo:
        manga_id = self._extract_id(url)

        # Fetch manga details
        api_url = f"{self.BASE_URL}/manga/{manga_id}"
        data = await self._fetch_json(api_url)

        if data.get("result") != "ok":
            raise ScraperError(f"Failed to fetch manga: {data}")

        manga_data = data["data"]

        # Extract attributes
        attrs = manga_data["attributes"]
        title = attrs["title"].get("en") or list(attrs["title"].values())[0]

        # Get author from relationships
        author = "Unknown"
        for rel in manga_data.get("relationships", []):
            if rel["type"] == "author":
                author = rel["attributes"]["name"]
                break

        description = attrs.get("description", {}).get("en", "")

        # Get cover art
        cover_url = None
        for rel in manga_data.get("relationships", []):
            if rel["type"] == "cover_art":
                cover_filename = rel["attributes"]["fileName"]
                cover_url = f"https://uploads.mangadex.org/covers/{manga_id}/{cover_filename}"
                break

        # Fetch chapters
        chapters = await self._fetch_chapters(manga_id)

        return ComicInfo(
            title=title,
            author=author,
            description=description,
            cover_url=cover_url,
            chapters=chapters,
            url=url
        )

    async def _fetch_chapters(self, manga_id: str) -> List[ChapterInfo]:
        """Fetch chapter list for manga"""
        chapters = []
        offset = 0
        limit = 500

        while True:
            # Fetch chapters with pagination
            api_url = (
                f"{self.BASE_URL}/manga/{manga_id}/feed"
                f"?limit={limit}&offset={offset}"
                f"&order[chapter]=asc&translatedLanguage[]=en"
            )

            data = await self._fetch_json(api_url)

            if data.get("result") != "ok":
                break

            for chapter_data in data.get("data", []):
                attrs = chapter_data["attributes"]
                chapter_num = attrs.get("chapter")

                if chapter_num is None:
                    continue  # Skip non-chapter entries

                try:
                    chapter_num = float(chapter_num)
                except (ValueError, TypeError):
                    continue

                chapter_id = chapter_data["id"]
                chapter_title = attrs.get("title", f"Chapter {chapter_num}")
                chapter_url = f"https://mangadex.org/chapter/{chapter_id}"

                chapters.append(ChapterInfo(
                    number=int(chapter_num) if chapter_num.is_integer() else chapter_num,
                    title=chapter_title,
                    url=chapter_url
                ))

            # Check pagination
            total = data.get("total", 0)
            offset += limit
            if offset >= total:
                break

        return chapters

    async def fetch_chapter_images(self, chapter_url: str) -> List[str]:
        """Fetch image URLs for a chapter"""
        chapter_id = self._extract_id(chapter_url)

        # Get chapter data with home URL
        api_url = f"{self.BASE_URL}/at-home/server/{chapter_id}"
        data = await self._fetch_json(api_url)

        if data.get("result") != "ok":
            raise ScraperError(f"Failed to fetch chapter images")

        base_url = data["baseUrl"]
        hash = data["chapter"]["hash"]
        files = data["chapter"]["data"]

        # Construct full image URLs (use dataSaver for smaller files)
        image_urls = []
        for file in files:
            image_urls.append(f"{base_url}/data-saver/{hash}/{file}")

        return image_urls

    async def search(self, query: str) -> List[ComicInfo]:
        """Search for manga on MangaDex"""
        api_url = f"{self.BASE_URL}/manga?title={query}&limit=20"
        data = await self._fetch_json(api_url)

        if data.get("result") != "ok":
            raise ScraperError(f"Search failed")

        results = []
        for manga_data in data.get("data", []):
            attrs = manga_data["attributes"]
            title = attrs["title"].get("en") or list(attrs["title"].values())[0]

            # Get author
            author = "Unknown"
            for rel in manga_data.get("relationships", []):
                if rel["type"] == "author":
                    author = rel["attributes"]["name"]
                    break

            manga_id = manga_data["id"]
            url = f"https://mangadex.org/title/{manga_id}"

            # Create ComicInfo with minimal data
            info = ComicInfo(
                title=title,
                author=author,
                url=url
            )
            results.append(info)

        return results
