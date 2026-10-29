#!/usr/bin/env python3
"""
Comic Scraper CLI - Main entry point
"""

import sys
import argparse
import asyncio
from pathlib import Path
from typing import Optional, List

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from scrapers.base import BaseScraper, ScraperError
from scrapers.mangadex import MangaDexScraper
from scrapers.mangasee import MangaSeeScraper
from scrapers.webtoon import WebtoonScraper
from scrapers.kiryuu import KiryuuScraper
from scrapers.generic import GenericComicScraper
from downloader import DownloadManager
from utils.config import Config

console = Console()

SCRAPERS = {
    "mangadex": MangaDexScraper,
    "mangasee": MangaSeeScraper,
    "webtoon": WebtoonScraper,
    "kiryuu": KiryuuScraper,
    "generic": GenericComicScraper,
}


def print_banner():
    """Print application banner"""
    banner = Panel.fit(
        "[bold cyan]Comic Scraper[/bold cyan]\n"
        "[dim]Download manga and comics from various sites[/dim]\n"
        "[yellow]Version 1.0.0[/yellow]",
        border_style="cyan"
    )
    console.print(banner)


def list_scrapers():
    """List all supported scrapers"""
    table = Table(title="Supported Scrapers")
    table.add_column("Site", style="cyan")
    table.add_column("Description", style="white")
    table.add_column("Example URL", style="dim")

    scrapers_info = {
        "mangadex": ("MangaDex", "https://mangadex.org/title/..."),
        "mangasee": ("MangaSee", "https://mangasee123.com/manga/..."),
        "webtoon": ("Webtoon", "https://www.webtoons.com/en/..."),
        "kiryuu": ("Kiryuu", "https://v6.kiryuu.to/manga/..."),
        "generic": ("Generic image-based", "Any site with sequential images"),
    }

    for key, (desc, example) in scrapers_info.items():
        table.add_row(key, desc, example)

    console.print(table)


async def search_comic(scraper_name: str, query: str):
    """Search for a comic"""
    scraper_class = SCRAPERS.get(scraper_name)
    if not scraper_class:
        console.print(f"[red]Error: Unknown scraper '{scraper_name}'[/red]")
        return

    scraper = scraper_class()
    try:
        results = await scraper.search(query)
        if results:
            table = Table(title=f"Search Results for '{query}'")
            table.add_column("#")
            table.add_column("Title")
            table.add_column("URL")

            for idx, result in enumerate(results, 1):
                table.add_row(str(idx), result.title, result.url)

            console.print(table)
        else:
            console.print("[yellow]No results found[/yellow]")
    except ScraperError as e:
        console.print(f"[red]Error: {e}[/red]")


async def download_comic(
    url: str,
    output: Optional[Path] = None,
    chapters: Optional[List[int]] = None,
    format: str = "images",
    parallel: int = 5,
    resume: bool = False,
    username: Optional[str] = None,
    password: Optional[str] = None
):
    """Download a comic"""
    # Auto-detect scraper from URL
    scraper = None
    for scraper_class in SCRAPERS.values():
        if scraper_class.can_handle(url):
            # Pass credentials if Kiryuu scraper
            if scraper_class.__name__ == "KiryuuScraper":
                scraper = scraper_class(username=username, password=password)
            else:
                scraper = scraper_class()
            break

    if not scraper:
        console.print("[red]Error: URL not supported by any scraper[/red]")
        console.print("\n[yellow]Try using the 'generic' scraper with --scraper generic[/yellow]")
        return

    console.print(f"[cyan]Detected scraper: {scraper.__class__.__name__}[/cyan]")

    # Fetch comic info
    try:
        comic_info = await scraper.fetch_comic_info(url)
        console.print(Panel.fit(
            f"[bold]{comic_info.title}[/bold]\n"
            f"Author: {comic_info.author}\n"
            f"Chapters: {len(comic_info.chapters)}",
            title="Comic Info"
        ))
    except ScraperError as e:
        console.print(f"[red]Error fetching comic info: {e}[/red]")
        return

    # Filter chapters
    if chapters:
        comic_info.chapters = [
            ch for ch in comic_info.chapters
            if ch.number in chapters
        ]
        if not comic_info.chapters:
            console.print("[red]Error: No chapters match the specified numbers[/red]")
            return

    # Set output directory
    if output is None:
        output = Path.cwd() / scraper.safe_filename(comic_info.title)
    else:
        output = Path(output)

    # Download
    manager = DownloadManager(
        output_dir=output,
        format=format,
        parallel=parallel,
        resume=resume
    )

    await manager.download(scraper, comic_info)

    console.print(f"[green]✓ Download complete: {output}[/green]")


def main():
    """Main CLI entry point"""
    parser = argparse.ArgumentParser(
        description="Comic Scraper - Download manga and comics from various sites",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s search mangadex "one piece"
  %(prog)s download https://mangadex.org/title/...
  %(prog)s download https://mangadex.org/title/... --chapters 1 2 3
  %(prog)s download https://mangasee123.com/manga/... --format pdf
  %(prog)s download https://example.com/comic --scraper generic
        """
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version="Comic Scraper 1.0.0"
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Search command
    search_parser = subparsers.add_parser("search", help="Search for comics")
    search_parser.add_argument(
        "scraper",
        choices=list(SCRAPERS.keys()),
        help="Scraper to use for search"
    )
    search_parser.add_argument("query", help="Search query")

    # Download command
    download_parser = subparsers.add_parser("download", help="Download a comic")
    download_parser.add_argument("url", help="Comic URL")
    download_parser.add_argument(
        "--output", "-o",
        type=Path,
        help="Output directory"
    )
    download_parser.add_argument(
        "--chapters", "-c",
        nargs="+",
        type=int,
        help="Chapter numbers to download"
    )
    download_parser.add_argument(
        "--format", "-f",
        choices=["images", "pdf", "cbz"],
        default="images",
        help="Output format"
    )
    download_parser.add_argument(
        "--parallel", "-p",
        type=int,
        default=5,
        help="Parallel downloads (default: 5)"
    )
    download_parser.add_argument(
        "--resume", "-r",
        action="store_true",
        help="Resume interrupted downloads"
    )
    download_parser.add_argument(
        "--scraper", "-s",
        choices=list(SCRAPERS.keys()),
        help="Force specific scraper"
    )
    download_parser.add_argument(
        "--username", "-u",
        help="Username for sites requiring login"
    )
    download_parser.add_argument(
        "--password", "-P",
        help="Password for sites requiring login"
    )

    # List command
    list_parser = subparsers.add_parser("list", help="List supported scrapers")

    args = parser.parse_args()

    print_banner()

    if args.command == "list":
        list_scrapers()
        return 0

    if args.command == "search":
        asyncio.run(search_comic(args.scraper, args.query))
        return 0

    if args.command == "download":
        asyncio.run(download_comic(
            url=args.url,
            output=args.output,
            chapters=args.chapters,
            format=args.format,
            parallel=args.parallel,
            resume=args.resume,
            username=getattr(args, 'username', None),
            password=getattr(args, 'password', None)
        ))
        return 0

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
