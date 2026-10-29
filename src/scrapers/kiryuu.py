"""
Kiryuu scraper - Scrapes manga from v6.kiryuu.to
"""

import re
from typing import List
from urllib.parse import urljoin

from .base import BaseScraper, ComicInfo, ChapterInfo, ScraperError


class KiryuuScraper(BaseScraper):
    """Scraper for Kiryuu (v6.kiryuu.to)"""

    DOMAIN_PATTERNS = [r"kiryuu\.to", r"kiryuu\.id"]
    BASE_URL = "https://v6.kiryuu.to"
    RATE_LIMIT = 1.5

    def __init__(self, username: str = None, password: str = None):
        super().__init__()
        self.username = username
        self.password = password
        self._authenticated = False

    async def _ensure_authenticated(self):
        """Ensure user is logged in if credentials provided"""
        if self._authenticated or not self.username or not self.password:
            return

        session = await self._get_session()

        # First, get the login page to find the form
        login_url = f"{self.BASE_URL}/auth/"
        async with session.get(login_url) as response:
            if response.status != 200:
                raise ScraperError("Could not access login page")

        # Post login credentials
        login_data = {
            "username": self.username,
            "password": self.password,
            "action": "login",
            "redirect": ""
        }

        async with session.post(
            f"{self.BASE_URL}/auth/login/",
            data=login_data,
            headers={"Referer": login_url}
        ) as response:
            if response.status == 200:
                self._authenticated = True
            else:
                raise ScraperError(f"Login failed: {response.status}")

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return bool(re.search(r"kiryuu\.(to|id|club|net)", url))

    async def fetch_comic_info(self, url: str) -> ComicInfo:
        await self._ensure_authenticated()
        soup = await self._fetch_html(url)

        # Extract title - Kiryuu uses specific selectors
        title_elem = (
            soup.select_one(".titlemod, .entry-title, h1.title") or
            soup.select_one(".thumb img") and soup.select_one(".thumb img").get("alt") and
            soup.select_one(f"[alt='{soup.select_one('.thumb img')['alt']}']") or
            soup.select_one("h1")
        )

        if not title_elem:
            raise ScraperError("Could not find manga title")

        if title_elem.name == "img":
            title = title_elem.get("alt", "Unknown")
        else:
            title = title_elem.get_text(strip=True)

        # Extract author/info
        author = "Unknown"
        author_elem = soup.select_one(".author, .m-author, span:-soup-contains('Author')")
        if author_elem:
            author_text = author_elem.get_text(strip=True)
            author = author_text.replace("Author:", "").replace("Mangaka:", "").strip()

        # Extract description
        description = ""
        desc_selectors = [
            ".desc, .summary, .entry-content",
            ".sinopsis, .synopsis",
            ".m-desc"
        ]

        for selector in desc_selectors:
            desc_elem = soup.select_one(selector)
            if desc_elem:
                description = desc_elem.get_text(strip=True, separator=" ")[:1000]
                break

        # Extract cover
        cover_url = None
        cover_elem = soup.select_one(".thumb img, .manga-cover img")
        if cover_elem:
            cover_url = cover_elem.get("src") or cover_elem.get("data-src")

        # Extract chapters
        chapters = self._extract_chapters(soup, url)

        return ComicInfo(
            title=title,
            author=author,
            description=description,
            cover_url=cover_url,
            chapters=chapters,
            url=url
        )

    def _extract_chapters(self, soup, base_url: str) -> List[ChapterInfo]:
        """Extract chapter links from Kiryuu page"""
        chapters = []

        # Kiryuu uses div[data-chapter-number] for chapters
        chapter_divs = soup.select("div[data-chapter-number] a")

        if chapter_divs:
            for idx, link in enumerate(reversed(chapter_divs), 1):
                href = link.get("href")
                if not href:
                    continue

                chapter_url = urljoin(self.BASE_URL, href.strip())
                chapter_title = link.get_text(strip=True)

                # Extract chapter number - prioritize URL for accuracy
                # URL pattern: /chapter-875.775275/ where 875 is chapter, 775275 is post ID
                url_match = re.search(r"/chapter-(\d+)", chapter_url)
                if url_match:
                    chapter_num = int(url_match.group(1))
                else:
                    # Fallback to text extraction
                    match = re.search(r"chapter\s+(\d+(?:\.\d+)?)", chapter_title, re.I)
                    if match:
                        chapter_num = float(match.group(1))
                        chapter_num = int(chapter_num) if chapter_num.is_integer() else chapter_num
                    else:
                        chapter_num = idx

                chapters.append(ChapterInfo(
                    number=chapter_num,
                    title=chapter_title,
                    url=chapter_url
                ))
            return chapters

        # Fallback to other selectors
        chapter_selectors = [
            ".chapterlist li a",
            ".chapters li a",
            ".chapter-list li a",
            ".episodelist li a",
            "#chapterlist li a",
            "div[data-cat=chapter] a",
            "table.chapter tr td a"
        ]

        chapter_links = []
        for selector in chapter_selectors:
            links = soup.select(selector)
            if links:
                chapter_links = links
                break

        # Process chapters in reverse order (newest first, reverse to get chronological)
        for idx, link in enumerate(reversed(chapter_links), 1):
            href = link.get("href")
            if not href:
                continue

            chapter_url = urljoin(self.BASE_URL, href)
            chapter_title = link.get_text(strip=True)

            # Extract chapter number
            match = re.search(r"chapter\s*(\d+(?:\.\d+)?)", chapter_title, re.I)
            if match:
                chapter_num = float(match.group(1))
                chapter_num = int(chapter_num) if chapter_num.is_integer() else chapter_num
            else:
                chapter_num = idx

            chapters.append(ChapterInfo(
                number=chapter_num,
                title=chapter_title,
                url=chapter_url
            ))

        return chapters

    async def fetch_chapter_images(self, chapter_url: str) -> List[str]:
        """Fetch image URLs for a chapter"""
        await self._ensure_authenticated()

        # Fetch raw HTML to parse embedded img tags
        session = await self._get_session()
        async with session.get(chapter_url) as response:
            html = await response.text()

        images = []

        # Method 1: Parse img tags from raw HTML
        # Kiryuu embeds images like: <img src='url'> without proper closing
        img_matches = re.findall(r"<img\s+src=['\"]([^'\"]+)['\"]", html)
        for img_url in img_matches:
            normalized = self._normalize_url(img_url, chapter_url)
            if self._is_comic_image(normalized):
                images.append(normalized)

        # Method 2: Also look for img tags with src= (no quotes)
        img_matches2 = re.findall(r"<img\s+src=([^\s'\"]+)(?:\s|>)", html)
        for img_url in img_matches2:
            normalized = self._normalize_url(img_url, chapter_url)
            if self._is_comic_image(normalized):
                images.append(normalized)

        # Method 3: Fallback to BeautifulSoup parsing
        if not images:
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html, "lxml")

            img_selectors = [
                ".reader-content img",
                ".chapter-content img",
                ".entry-content img",
                ".reading-content img",
                "#readerarea img",
                ".reader-area img",
                ".post-content img",
                ".manga-reading img"
            ]

            for selector in img_selectors:
                img_tags = soup.select(selector)
                if img_tags:
                    for img in img_tags:
                        src = img.get("src") or img.get("data-src") or img.get("data-lazy-src")
                        if src and self._is_comic_image(src):
                            images.append(self._normalize_url(src, chapter_url))
                    if images:
                        break

        # Filter and deduplicate
        seen = set()
        filtered_images = []
        for img in images:
            if img not in seen and self._is_comic_image(img):
                seen.add(img)
                filtered_images.append(img)

        # Sort images by filename number for correct order
        filtered_images.sort(key=lambda x: self._extract_image_number(x))

        return filtered_images

    def _extract_image_number(self, url: str) -> int:
        """Extract page number from image URL for sorting"""
        # Look for patterns like chapter-06/1-xxx.jpg or chapter-06/2-xxx.jpg
        match = re.search(r"/chapter-\d+/(\d+)", url)
        if match:
            return int(match.group(1))
        return 0

    def _normalize_url(self, src: str, base_url: str) -> str:
        """Normalize URL to absolute"""
        # Remove any leading/trailing quotes and whitespace
        src = src.strip().strip('"\'')

        if src.startswith("//"):
            parsed = base_url.split("://")[0]
            return f"{parsed}:{src}"
        elif not src.startswith("http"):
            return urljoin(base_url, src)
        return src

    def _is_comic_image(self, src: str) -> bool:
        """Check if URL looks like a comic image"""
        # Must have image extension
        if not re.search(r"\.(jpg|jpeg|png|gif|webp|bmp)(?:\?|$)", src, re.I):
            # Some sites don't have extensions, check for content patterns
            if not any(pattern in src.lower() for pattern in ["img", "image", "comic", "manga", "wp-content"]):
                return False

        # Kiryuu-specific: Only include images from yuucdn.com or ky.uqni.net (manga CDNs)
        # and filter out ads/banners
        if "yuucdn.com" not in src.lower() and "ky.uqni.net" not in src.lower():
            return False

        # Must be from the chapter images directory (new format: /imgsc/, old: /chapter-, /images/)
        if "/chapter-" not in src and "/images/" not in src and "/imgsc/" not in src:
            return False

        # Filter small dimensions in query string
        if re.search(r"[?&](w|h|width|height)=(\d{1,2})(?:&|$)", src):
            return False

        # Filter non-image URLs
        exclude_patterns = ["icon", "button", "logo", "avatar", "favicon", ".css", ".js", "gif"]
        if any(pattern in src.lower() for pattern in exclude_patterns):
            return False

        return True

    async def search(self, query: str) -> List[ComicInfo]:
        """Search for manga on Kiryuu"""
        search_url = f"{self.BASE_URL}?s={query}"
        soup = await self._fetch_html(search_url)

        results = []
        result_selectors = [
            ".bsx a", ".thumb a", ".manga-list a",
            ".result-item a", ".search-results a",
            "article a", ".post a"
        ]

        for selector in result_selectors:
            items = soup.select(selector)[:20]
            if items:
                for item in items:
                    href = item.get("href")
                    if not href:
                        continue

                    title_elem = item.select_one(".tt, h3, h4, .title")
                    title = title_elem.get_text(strip=True) if title_elem else "Unknown"

                    url = urljoin(self.BASE_URL, href)

                    results.append(ComicInfo(
                        title=title,
                        author="Unknown",
                        url=url
                    ))
                break

        return results
