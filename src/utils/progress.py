"""
Progress Tracker - Track download progress for resume capability
"""

import json
from datetime import datetime
from pathlib import Path
from typing import List, Set


class ProgressTracker:
    """
    Track download progress for resumable downloads

    Tracks which images have been downloaded and can resume
    interrupted downloads.
    """

    def __init__(self, progress_file: Path):
        self.progress_file = progress_file
        self.total: int = 0
        self.downloaded: Set[str] = set()
        self.remaining_urls: List[str] = []

    def set_total(self, total: int):
        """Set total number of images to download"""
        self.total = total

    def mark_downloaded(self, url: str):
        """Mark a URL as downloaded"""
        self.downloaded.add(url)

    def is_downloaded(self, url: str) -> bool:
        """Check if URL has been downloaded"""
        return url in self.downloaded

    def is_complete(self) -> bool:
        """Check if all images are downloaded"""
        return len(self.downloaded) >= self.total > 0

    def save(self):
        """Save progress to file"""
        data = {
            "total": self.total,
            "downloaded": list(self.downloaded),
            "timestamp": datetime.now().isoformat()
        }

        with open(self.progress_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

    def load(self):
        """Load progress from file"""
        if not self.progress_file.exists():
            return

        with open(self.progress_file, "r", encoding="utf-8") as f:
            data = json.load(f)

        self.total = data.get("total", 0)
        self.downloaded = set(data.get("downloaded", []))
