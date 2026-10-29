# Comic Scraper - Usage Examples

## Installation

```bash
cd comic-scraper
pip install -r comic-scraper/requirements.txt
```

## Quick Start

### 1. List supported scrapers

```bash
python3 -m comic_scraper list
```

### 2. Search for manga on MangaDex

```bash
python3 -m comic_scraper search mangadex "one piece"
```

### 3. Download a comic

```bash
# Download all chapters
python3 -m comic_scraper download "https://mangadex.org/title/..."

# Download specific chapters
python3 -m comic_scraper download "https://mangadex.org/title/..." --chapters 1 2 3

# Download as PDF
python3 -m comic_scraper download "https://mangasee123.com/manga/..." --format pdf

# Download with custom output
python3 -m comic_scraper download "https://www.webtoons.com/en/..." --output ~/comics

# Parallel downloads (faster but may hit rate limits)
python3 -m comic_scraper download <url> --parallel 10

# Resume interrupted download
python3 -m comic_scraper download <url> --resume
```

## Output Formats

- `images`: Individual image files (default)
- `pdf`: Combined PDF per chapter
- `cbz`: Comic book ZIP archive per chapter

## Tips

- Start with `--parallel 3` to avoid rate limiting
- Use `--resume` if download is interrupted
- Generic scraper works with most image-based comic sites
- Check `metadata.json` in output directory for comic info
