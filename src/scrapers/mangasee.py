"""
MangaSee scraper - Scrapes manga from mangasee123.com
"""

import re
from typing import List
from urllib.parse import urljoin

from .base import BaseScraper, ComicInfo, ChapterInfo, ScraperError


class MangaSeeScraper(BaseScraper):
    """Scraper for MangaSee (mangasee123.com)"""

    DOMAIN_PATTERNS = [r"mangasee123\.com"]
    BASE_URL = "https://mangasee123.com"
    RATE_LIMIT = 2.0

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return bool(re.search(r"mangasee123\.com", url))

    async def fetch_comic_info(self, url: str) -> ComicInfo:
        # Extract manga slug from URL
        match = re.search(r"/manga/([^/]+)", url)
        if not match:
            raise ScraperError(f"Invalid MangaSee URL: {url}")

        slug = match.group(1)

        # Fetch manga page
        soup = await self._fetch_html(url)

        # Extract title
        title_elem = soup.select_one(".entry-title, .post-title, h1")
        if not title_elem:
            raise ScraperError("Could not find manga title")
        title = title_elem.get_text(strip=True)

        # Extract author
        author = "Unknown"
        author_elem = soup.select_one(".author, .manga-author")
        if author_elem:
            author = author_elem.get_text(strip=True).replace("Author:", "").strip()

        # Extract description
        desc_elem = soup.select_one(".manga-summary, .entry-content, .description")
        description = ""
        if desc_elem:
            description = desc_elem.get_text(strip=True)

        # Extract cover
        cover_url = None
        cover_elem = soup.select_one(".manga-cover img, .entry-content img")
        if cover_elem and cover_elem.get("src"):
            cover_url = cover_elem["src"]

        # Extract chapters
        chapters = []
        chapter_list = soup.select(".chapter-list a, .chapters a, .listing-chapters_wrap a")

        for idx, link in enumerate(reversed(chapter_list), 1):  # Reverse to get chronological order
            chapter_url = urljoin(self.BASE_URL, link["href"])
            chapter_title = link.get_text(strip=True)

            # Extract chapter number
            match = re.search(r"chapter\s*(\d+)", chapter_title, re.I)
            if match:
                chapter_num = int(match.group(1))
            else:
                chapter_num = idx

            chapters.append(ChapterInfo(
                number=chapter_num,
                title=chapter_title,
                url=chapter_url
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
        """Fetch image URLs for a chapter"""
        soup = await self._fetch_html(chapter_url)

        # MangaSee uses a specific structure
        images = []

        # Try to find images in the reader
        img_tags = soup.select(".read-content img, .chapter-content img, .reader-content img")

        for img in img_tags:
            src = img.get("src") or img.get("data-src")
            if src:
                # Convert protocol-relative URLs
                if src.startswith("//"):
                    src = "https:" + src
                images.append(src)

        if not images:
            # Alternative: look for image URLs in scripts
            scripts = soup.find_all("script")
            for script in scripts:
                if script.string:
                    # Look for image arrays in JS
                    matches = re.findall(r'["\']([^"\']*://[^"\']*\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', script.string)
                    images.extend(matches)

        return images

    async def search(self, query: str) -> List[ComicInfo]:
        """Search for manga on MangaSee"""
        search_url = f"{self.BASE_URL}/?s={query}"
        soup = await self._fetch_html(search_url)

        results = []
        result_items = soup.select(".manga-list-item, .entry-title, .post-title a")

        for item in result_items[:20]:  # Limit to 20 results
            link = item if item.name == "a" else item.find("a")
            if not link or not link.get("href"):
                continue

            title = link.get_text(strip=True)
            url = link["href"]

            if not url.startswith("http"):
                url = urljoin(self.BASE_URL, url)

            results.append(ComicInfo(
                title=title,
                author="Unknown",
                url=url
            ))

        return results
