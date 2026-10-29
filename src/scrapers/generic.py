"""
Generic comic scraper - Works with any site that has sequential images
"""

import re
from typing import List
from urllib.parse import urljoin, urlparse

from .base import BaseScraper, ComicInfo, ChapterInfo, ScraperError


class GenericComicScraper(BaseScraper):
    """
    Generic scraper for sites with sequential image pages

    This scraper tries to find:
    - A list of chapter/episode links
    - Images within chapter pages
    - Next/Previous navigation
    """

    DOMAIN_PATTERNS = []  # Matches all domains as fallback
    RATE_LIMIT = 1.0  # Conservative rate limit

    @classmethod
    def can_handle(cls, url: str) -> bool:
        """Generic scraper can handle any valid URL"""
        return bool(urlparse(url).scheme in ["http", "https"])

    async def fetch_comic_info(self, url: str) -> ComicInfo:
        soup = await self._fetch_html(url)

        # Extract title from various common selectors
        title_selectors = [
            "h1", "h2", ".title", ".comic-title", ".manga-title",
            "[itemprop='name']", ".entry-title", ".post-title"
        ]

        title = "Unknown Comic"
        for selector in title_selectors:
            elem = soup.select_one(selector)
            if elem:
                title = elem.get_text(strip=True)
                break

        # Extract author
        author = "Unknown"
        author_selectors = [".author", ".manga-author", "[itemprop='author']", ".creator"]
        for selector in author_selectors:
            elem = soup.select_one(selector)
            if elem:
                author = elem.get_text(strip=True)
                break

        # Extract description
        description = ""
        desc_selectors = [".description", ".summary", ".manga-summary", "[itemprop='description']"]
        for selector in desc_selectors:
            elem = soup.select_one(selector)
            if elem:
                description = elem.get_text(strip=True, separator=" ")[:500]
                break

        # Find chapter/episode links
        chapters = self._extract_chapters(soup, url)

        return ComicInfo(
            title=title,
            author=author,
            description=description,
            chapters=chapters,
            url=url
        )

    def _extract_chapters(self, soup, base_url: str) -> List[ChapterInfo]:
        """Extract chapter links from various patterns"""
        chapters = []

        # Common chapter list selectors
        chapter_selectors = [
            "a[href*='chapter']", "a[href*='ep']", "a.chapter-link",
            ".chapter-list a", ".chapters a", ".episode-list a",
            "table.chapters td a", ".listing a", "tbody tr td a"
        ]

        for selector in chapter_selectors:
            links = soup.select(selector)
            if links and len(links) > 1:  # Found a chapter list
                for idx, link in enumerate(reversed(links), 1):
                    href = link.get("href")
                    if href:
                        chapter_url = urljoin(base_url, href)
                        chapter_title = link.get_text(strip=True)

                        # Try to extract chapter number
                        match = re.search(r"(?:ch|chapter|ep|episode)\s*(\d+)", chapter_title, re.I)
                        chapter_num = int(match.group(1)) if match else idx

                        chapters.append(ChapterInfo(
                            number=chapter_num,
                            title=chapter_title,
                            url=chapter_url
                        ))
                break

        # If no chapter list found, treat the URL itself as a single chapter
        if not chapters:
            chapters.append(ChapterInfo(
                number=1,
                title="Chapter 1",
                url=base_url
            ))

        return chapters

    async def fetch_chapter_images(self, chapter_url: str) -> List[str]:
        """Fetch images from a chapter page"""
        soup = await self._fetch_html(chapter_url)

        images = []

        # Find all images
        img_selectors = [
            ".comic-page img", ".manga-page img", ".reader img",
            ".chapter-content img", ".entry-content img", "article img",
            "#images img", ".viewer img", ".page img"
        ]

        for selector in img_selectors:
            img_tags = soup.select(selector)
            if img_tags:
                for img in img_tags:
                    src = img.get("src") or img.get("data-src")
                    if src and not self._is_icon(src):
                        images.append(self._normalize_url(src, chapter_url))
                if images:
                    break

        # If no images found in specific containers, get all images
        if not images:
            for img in soup.find_all("img"):
                src = img.get("src") or img.get("data-src")
                if src and not self._is_icon(src):
                    images.append(self._normalize_url(src, chapter_url))

        # Filter for actual comic images (not icons, buttons, etc.)
        images = [img for img in images if self._is_comic_image(img)]

        return images

    def _is_icon(self, src: str) -> bool:
        """Check if URL points to an icon or button"""
        icon_patterns = [
            "icon", "button", "logo", "avatar", "favicon",
            "sprite", "arrow", "navigation", "social"
        ]
        src_lower = src.lower()
        return any(pattern in src_lower for pattern in icon_patterns)

    def _is_comic_image(self, src: str) -> bool:
        """Check if URL looks like a comic image"""
        # Must have image extension
        if not re.search(r"\.(jpg|jpeg|png|gif|webp|bmp)(?:\?|$)", src, re.I):
            return False

        # Filter small dimensions in query string
        if re.search(r"[?&](w|h|width|height)=\d{1,2}(?:&|$)", src):
            return False

        return True

    def _normalize_url(self, src: str, base_url: str) -> str:
        """Normalize URL to absolute"""
        if src.startswith("//"):
            parsed = urlparse(base_url)
            return f"{parsed.scheme}:{src}"
        elif not src.startswith("http"):
            return urljoin(base_url, src)
        return src

    async def search(self, query: str) -> List[ComicInfo]:
        """Generic search - returns empty list"""
        return []  # Generic scraper doesn't support search
