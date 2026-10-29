"""
Download Manager - Handles parallel downloads with resume support
"""

import asyncio
import json
import zipfile
from pathlib import Path
from typing import List, Optional
from datetime import datetime

from aiohttp import ClientSession
from aiolimiter import AsyncLimiter
from PIL import Image
import img2pdf
from tqdm import tqdm

from scrapers.base import BaseScraper, ComicInfo, ChapterInfo
from utils.progress import ProgressTracker


class DownloadManager:
    """
    Manage comic downloads with resume capability and multiple output formats
    """

    def __init__(
        self,
        output_dir: Path,
        format: str = "images",
        parallel: int = 5,
        resume: bool = False
    ):
        self.output_dir = Path(output_dir)
        self.format = format
        self.parallel = parallel
        self.resume = resume
        self.rate_limiter = AsyncLimiter(10, 1)  # 10 requests per second

    async def download(self, scraper: BaseScraper, comic_info: ComicInfo):
        """
        Download all chapters of a comic

        Args:
            scraper: The scraper instance
            comic_info: Comic information
        """
        # Create output directory
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Save metadata
        self._save_metadata(comic_info)

        # Download each chapter
        for chapter in comic_info.chapters:
            await self._download_chapter(scraper, chapter, comic_info.title)

        # Convert to requested format
        if self.format in ["pdf", "cbz"]:
            self._convert_format(comic_info)

    async def _download_chapter(
        self,
        scraper: BaseScraper,
        chapter: ChapterInfo,
        comic_title: str
    ):
        """Download a single chapter"""
        chapter_dir = self.output_dir / scraper.safe_filename(f"{comic_title}") / f"Chapter_{chapter.number}"
        chapter_dir.mkdir(parents=True, exist_ok=True)

        # Check for resume
        progress_file = chapter_dir / ".progress.json"
        tracker = ProgressTracker(progress_file)

        if self.resume:
            tracker.load()

        # Fetch image URLs
        if not tracker.is_complete():
            image_urls = await scraper.fetch_chapter_images(chapter.url)
            tracker.set_total(len(image_urls))
        else:
            image_urls = tracker.remaining_urls

        if not image_urls:
            print(f"[yellow]No images found for {chapter.title}[/yellow]")
            return

        # Download images
        async with ClientSession() as session:
            tasks = []
            for idx, url in enumerate(image_urls, 1):
                if tracker.is_downloaded(url):
                    continue

                task = self._download_image(
                    session,
                    url,
                    chapter_dir / f"{idx:03d}.jpg",
                    tracker
                )
                tasks.append(task)

            # Execute downloads with semaphore
            semaphore = asyncio.Semaphore(self.parallel)
            done = []

            for task in tasks:
                async def sem_task(t=task):
                    async with semaphore:
                        return await t
                done.append(asyncio.create_task(sem_task()))

            # Wait for all downloads
            for future in asyncio.as_completed(done):
                await future

            tracker.save()

        print(f"[green]✓ Downloaded: {chapter.title}[/green]")

    async def _download_image(
        self,
        session: ClientSession,
        url: str,
        output_path: Path,
        tracker: ProgressTracker
    ):
        """Download a single image"""
        async with self.rate_limiter:
            try:
                async with session.get(url, timeout=30) as response:
                    if response.status == 200:
                        content = await response.read()

                        # Save image
                        output_path.parent.mkdir(parents=True, exist_ok=True)
                        with open(output_path, "wb") as f:
                            f.write(content)

                        # Mark as downloaded
                        tracker.mark_downloaded(url)

                        # Try to convert to JPEG if needed
                        try:
                            img = Image.open(output_path)
                            if img.format != "JPEG":
                                rgb_img = img.convert("RGB")
                                rgb_img.save(output_path, "JPEG", quality=95)
                        except Exception:
                            pass  # Keep original if conversion fails

            except Exception as e:
                print(f"[red]Error downloading {url}: {e}[/red]")

    def _save_metadata(self, comic_info: ComicInfo):
        """Save comic metadata to JSON"""
        metadata = {
            "title": comic_info.title,
            "author": comic_info.author,
            "description": comic_info.description,
            "cover_url": comic_info.cover_url,
            "url": comic_info.url,
            "download_date": datetime.now().isoformat(),
            "chapters": [
                {
                    "number": ch.number,
                    "title": ch.title,
                    "url": ch.url
                }
                for ch in comic_info.chapters
            ]
        }

        metadata_path = self.output_dir / "metadata.json"
        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _convert_format(self, comic_info: ComicInfo):
        """Convert downloaded images to requested format"""
        if self.format == "pdf":
            self._create_pdf(comic_info.title)
        elif self.format == "cbz":
            self._create_cbz(comic_info.title)

    def _create_pdf(self, comic_title: str):
        """Create PDF from downloaded images"""
        from scrapers.base import BaseScraper

        # Find the comic directory
        safe_title = BaseScraper.safe_filename(comic_title)
        comic_dir = self.output_dir / safe_title

        if not comic_dir.exists():
            print(f"[yellow]Comic directory not found: {comic_dir}[/yellow]")
            return

        # Find all chapter directories
        chapter_dirs = sorted(
            comic_dir.glob("Chapter_*"),
            key=lambda p: int(p.stem.split("_")[1])
        )

        for chapter_dir in chapter_dirs:
            # Find all images (skip empty/corrupted files)
            images = sorted([img for img in chapter_dir.glob("*.jpg") if img.stat().st_size > 0])

            if not images:
                continue

            # Warn if some files were skipped
            all_jpg = list(chapter_dir.glob("*.jpg"))
            if len(images) < len(all_jpg):
                skipped = len(all_jpg) - len(images)
                print(f"[yellow]Warning: {chapter_dir.name} - skipped {skipped} empty/corrupted images[/yellow]")

            # Create PDF
            pdf_path = chapter_dir.with_suffix(".pdf")

            try:
                with open(pdf_path, "wb") as f:
                    f.write(img2pdf.convert([str(img) for img in images]))
                print(f"[green]✓ Created PDF: {pdf_path.name}[/green]")
            except Exception as e:
                print(f"[red]Error creating PDF for {chapter_dir.name}: {e}[/red]")

    def _create_cbz(self, comic_title: str):
        """Create CBZ (Comic Book ZIP) from downloaded images"""
        from scrapers.base import BaseScraper

        # Find the comic directory
        safe_title = BaseScraper.safe_filename(comic_title)
        comic_dir = self.output_dir / safe_title

        if not comic_dir.exists():
            print(f"[yellow]Comic directory not found: {comic_dir}[/yellow]")
            return

        # Find all chapter directories
        chapter_dirs = sorted(
            comic_dir.glob("Chapter_*"),
            key=lambda p: int(p.stem.split("_")[1])
        )

        for chapter_dir in chapter_dirs:
            # Find all images
            images = sorted(chapter_dir.glob("*.jpg"))

            if not images:
                continue

            # Create CBZ
            cbz_path = chapter_dir.with_suffix(".cbz")

            with zipfile.ZipFile(cbz_path, "w", zipfile.ZIP_DEFLATED) as zf:
                for img in images:
                    zf.write(img, img.name)

            print(f"[green]✓ Created CBZ: {cbz_path.name}[/green]")
