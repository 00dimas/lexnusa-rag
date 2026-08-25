from __future__ import annotations

import argparse
import logging
from pathlib import Path

from lexnusa.scraping.peraturan import PeraturanScraper


def main() -> None:
    parser = argparse.ArgumentParser(description="Ambil sampel UU/PP dari peraturan.go.id")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--output", type=Path, default=Path("data/raw"))
    parser.add_argument("--delay", type=float, default=2.0, help="Jeda minimum antar-request (detik)")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    with PeraturanScraper(args.output, delay_seconds=args.delay) as scraper:
        documents = scraper.scrape(limit=args.limit)
    print(f"Selesai: {len(documents)} dokumen tersimpan di {args.output}")


if __name__ == "__main__":
    main()
