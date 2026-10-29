# Comic Scraper

Command-line tool to download manga and comics from various sites.

## Features

- **Multiple site support**: MangaDex, MangaSee, Webtoon, and generic image-based sites
- **Async downloads**: Parallel downloading with configurable concurrency
- **Resume capability**: Resume interrupted downloads
- **Multiple formats**: Save as images, PDF, or CBZ (comic book archive)
- **Search functionality**: Search for comics across supported sites
- **Progress tracking**: Visual progress bars and JSON progress files

## Installation

```bash
# Clone the repository
git clone <repo-url>
cd comic-scraper

# Install dependencies
pip install -r requirements.txt
```

## Usage

### Basic Commands

```bash
# List supported scrapers
python -m comic_scraper list

# Search for a comic
python -m comic_scraper search mangadex "one piece"

# Download a comic
python -m comic_scraper download https://mangadex.org/title/...

# Download specific chapters
python -m comic_scraper download https://mangadex.org/title/... --chapters 1 2 3

# Download as PDF
python -m comic_scraper download https://mangasee123.com/manga/... --format pdf

# Download with custom output directory
python -m comic_scraper download <url> --output ~/my-comics

# Resume interrupted download
python -m comic_scraper download <url> --resume
```

### Options

- `--output, -o`: Output directory (default: current directory / comic title)
- `--chapters, -c`: Specific chapter numbers to download
- `--format, -f`: Output format: `images`, `pdf`, `cbz` (default: images)
- `--parallel, -p`: Parallel downloads (default: 5)
- `--resume, -r`: Resume interrupted downloads
- `--scraper, -s`: Force specific scraper

## Supported Sites

| Site | Description | Example URL |
|------|-------------|--------------|
| MangaDex | Large manga aggregator | https://mangadex.org/title/... |
| MangaSee | Manga reader site | https://mangasee123.com/manga/... |
| Webtoon | Webcomic platform | https://www.webtoons.com/en/... |
| Kiryuu | Indonesian manga site | https://v6.kiryuu.to/manga/... |
| Generic | Any site with sequential images | Any URL |

## Output Structure

```
output_dir/
├── metadata.json              # Comic metadata
└── Comic_Title/
    ├── Chapter_1/
    │   ├── 001.jpg
    │   ├── 002.jpg
    │   └── ...
    ├── Chapter_2/
    │   └── ...
    └── ...
```

## Configuration

Create `~/.comic-scraper/config.yaml`:

```yaml
rate_limit: 2.0
output_dir: "./downloads"
default_format: "images"
parallel_downloads: 5
timeout: 30
```

## Development

### Project Structure

```
comic-scraper/
├─src/
│   ├── __init__.py
│   ├── __main__.py          # Entry point
│   ├── cli.py               # CLI interface
│   ├── downloader.py        # Download manager
│   ├── requirements.txt
│   ├── scrapers/
│   │   ├── __init__.py
│   │   ├── base.py          # Base scraper class
│   │   ├── mangadex.py      # MangaDex scraper
│   │   ├── mangasee.py      # MangaSee scraper
│   │   ├── webtoon.py       # Webtoon scraper
│   │   └── generic.py       # Generic scraper
│   └── utils/
│       ├── __init__.py
│       ├── config.py        # Configuration manager
│       └── progress.py      # Progress tracker
└── README.md
```

### Adding a New Scraper

1. Create a new file in `scrapers/`
2. Inherit from `BaseScraper`
3. Implement required methods:
   - `can_handle(url)` - Check if URL matches
   - `fetch_comic_info(url)` - Get comic metadata
   - `fetch_chapter_images(chapter_url)` - Get image URLs
4. Add to `SCRAPERS` dict in `cli.py`

Example:

```python
from .base import BaseScraper, ComicInfo, ChapterInfo

class MyScraper(BaseScraper):
    DOMAIN_PATTERNS = [r"example\.com"]

    @classmethod
    def can_handle(cls, url: str) -> bool:
        return bool(re.search(r"example\.com", url))

    async def fetch_comic_info(self, url: str) -> ComicInfo:
        # Implementation
        pass

    async def fetch_chapter_images(self, chapter_url: str) -> List[str]:
        # Implementation
        pass
```

## License

MIT
