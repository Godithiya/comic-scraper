"""
Base scraper class - All scrapers inherit from this
"""

import re
import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

import aiohttp
from bs4 import BeautifulSoup
from fake_useragent import UserAgent


class ScraperError(Exception):
    """Base exception for scraper errors"""
    pass


class ScraperRateLimitError(ScraperError):
    """Raised when rate limit is hit"""
    pass


class ScraperNotFoundError(ScraperError):
    """Raised when content is not found"""
    pass


@dataclass
class ChapterInfo:
    """Information about a chapter"""
    number: int
    title: str
    url: str
    page_urls: List[str] = field(default_factory=list)
    published_date: Optional[str] = None


@dataclass
class ComicInfo:
    """Information about a comic"""
    title: str
    author: str
    description: str = ""
    cover_url: Optional[str] = None
    chapters: List[ChapterInfo] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    url: str = ""


class BaseScraper(ABC):
    """
    Base scraper class

    All site-specific scrapers must inherit from this and implement:
    - can_handle(url) - static method to check if URL matches
    - fetch_comic_info(url) - get comic metadata and chapter list
    - fetch_chapter_images(chapter_url) - get image URLs for a chapter
    - search(query) - search for comics (optional)
    """

    # Site-specific patterns
    DOMAIN_PATTERNS: List[str] = []
    BASE_URL: str = ""

    # Rate limiting (requests per second)
    RATE_LIMIT: float = 2.0

    # Request timeout
    TIMEOUT: int = 30

    def __init__(self):
        self.session: Optional[aiohttp.ClientSession] = None
        self.user_agent = UserAgent()
        self._rate_limit_semaphore = asyncio.Semaphore(int(self.RATE_LIMIT))

    @classmethod
    @abstractmethod
    def can_handle(cls, url: str) -> bool:
        """
        Check if this scraper can handle the given URL

        Args:
            url: The URL to check

        Returns:
            True if this scraper supports the URL
        """
        pass

    @abstractmethod
    async def fetch_comic_info(self, url: str) -> ComicInfo:
        """
        Fetch comic information including chapters

        Args:
            url: The comic URL

        Returns:
            ComicInfo object with comic metadata and chapter list
        """
        pass

    @abstractmethod
    async def fetch_chapter_images(self, chapter_url: str) -> List[str]:
        """
        Fetch image URLs for a chapter

        Args:
            chapter_url: The chapter URL

        Returns:
            List of image URLs
        """
        pass

    async def search(self, query: str) -> List[ComicInfo]:
        """
        Search for comics (optional, default: not supported)

        Args:
            query: Search query

        Returns:
            List of ComicInfo results
        """
        raise NotImplementedError(f"{self.__class__.__name__} does not support search")

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create HTTP session"""
        if self.session is None or self.session.closed:
            headers = {
                "User-Agent": self.user_agent.random,
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.5",
                "Accept-Encoding": "gzip, deflate",
                "Connection": "keep-alive",
            }
            timeout = aiohttp.ClientTimeout(total=self.TIMEOUT)
            self.session = aiohttp.ClientSession(headers=headers, timeout=timeout)
        return self.session

    async def _fetch_html(self, url: str) -> BeautifulSoup:
        """
        Fetch URL and return BeautifulSoup object

        Args:
            url: URL to fetch

        Returns:
            BeautifulSoup parsed HTML
        """
        async with self._rate_limit_semaphore:
            session = await self._get_session()

            async with session.get(url) as response:
                if response.status == 404:
                    raise ScraperNotFoundError(f"Not found: {url}")
                elif response.status == 429:
                    retry_after = int(response.headers.get("Retry-After", 60))
                    raise ScraperRateLimitError(f"Rate limited. Retry after {retry_after}s")
                elif response.status >= 400:
                    raise ScraperError(f"HTTP {response.status}: {url}")

                html = await response.text()
                return BeautifulSoup(html, "lxml")

    async def _fetch_json(self, url: str) -> Dict[str, Any]:
        """
        Fetch URL and return JSON

        Args:
            url: URL to fetch

        Returns:
            Parsed JSON data
        """
        async with self._rate_limit_semaphore:
            session = await self._get_session()

            async with session.get(url) as response:
                if response.status == 404:
                    raise ScraperNotFoundError(f"Not found: {url}")
                elif response.status == 429:
                    raise ScraperRateLimitError(f"Rate limited")
                elif response.status >= 400:
                    raise ScraperError(f"HTTP {response.status}: {url}")

                return await response.json()

    async def close(self):
        """Close HTTP session"""
        if self.session and not self.session.closed:
            await self.session.close()

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    @staticmethod
    def safe_filename(name: str) -> str:
        """
        Convert string to safe filename

        Args:
            name: String to convert

        Returns:
            Safe filename string
        """
        # Remove invalid characters
        name = re.sub(r'[<>:"/\\|?*]', '', name)
        # Replace whitespace with underscore
        name = re.sub(r'\s+', '_', name)
        # Limit length
        return name[:200].strip()

    @staticmethod
    def extract_number(text: str) -> int:
        """
        Extract first number from text

        Args:
            text: Text to extract from

        Returns:
            Extracted number or 0
        """
        match = re.search(r'\d+', text)
        return int(match.group()) if match else 0
