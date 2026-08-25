from __future__ import annotations

import hashlib
import json
import logging
import re
import time
import urllib.robotparser
from dataclasses import replace
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

from lexnusa.models import DocumentMetadata

LOGGER = logging.getLogger(__name__)
DEFAULT_BASE_URL = "https://peraturan.go.id"
USER_AGENT = "LexNusaBot/0.1 (+research; respectful public-document indexer)"
TITLE_PATTERN = re.compile(
    r"(?P<type>Undang-Undang|Peraturan Pemerintah)\s+Nomor\s+(?P<number>\S+)\s+Tahun\s+(?P<year>\d{4})",
    re.IGNORECASE,
)
STATUS_PATTERN = re.compile(r"Status\s*:?\s*(Berlaku|Dicabut|Tidak Berlaku|Diubah)", re.IGNORECASE)


class RobotsDeniedError(RuntimeError):
    pass


class PeraturanScraper:
    def __init__(
        self,
        output_dir: Path,
        *,
        base_url: str = DEFAULT_BASE_URL,
        delay_seconds: float = 2.0,
        timeout_seconds: float = 30.0,
        client: httpx.Client | None = None,
    ) -> None:
        self.output_dir = output_dir
        self.base_url = base_url.rstrip("/")
        self.delay_seconds = max(delay_seconds, 1.0)
        self._last_request_at = 0.0
        self.client = client or httpx.Client(
            headers={"User-Agent": USER_AGENT}, timeout=timeout_seconds, follow_redirects=True
        )
        self._owns_client = client is None
        self.robots = urllib.robotparser.RobotFileParser()
        self._robots_loaded = False

    def __enter__(self) -> "PeraturanScraper":
        return self

    def __exit__(self, *_: object) -> None:
        if self._owns_client:
            self.client.close()

    def _wait(self) -> None:
        remaining = self.delay_seconds - (time.monotonic() - self._last_request_at)
        if self._last_request_at and remaining > 0:
            time.sleep(remaining)

    def _request(self, url: str) -> httpx.Response:
        self._wait()
        response = self.client.get(url)
        self._last_request_at = time.monotonic()
        response.raise_for_status()
        return response

    def load_robots(self) -> None:
        robots_url = f"{self.base_url}/robots.txt"
        response = self._request(robots_url)
        self.robots.set_url(robots_url)
        self.robots.parse(response.text.splitlines())
        self._robots_loaded = True

    def _ensure_allowed(self, url: str) -> None:
        if not self._robots_loaded:
            self.load_robots()
        if not self.robots.can_fetch(USER_AGENT, url):
            raise RobotsDeniedError(f"robots.txt melarang akses ke {url}")

    def fetch(self, url: str) -> httpx.Response:
        self._ensure_allowed(url)
        return self._request(url)

    def parse_listing(self, html: str) -> list[DocumentMetadata]:
        soup = BeautifulSoup(html, "html.parser")
        documents: list[DocumentMetadata] = []
        seen: set[str] = set()
        for detail_link in soup.select('a[title="lihat detail"]'):
            container = detail_link.find_parent("div", class_="col-md-12")
            if container is None:
                continue
            descriptor = container.find(string=TITLE_PATTERN)
            pdf_link = container.select_one('a[href$=".pdf"]')
            if descriptor is None or pdf_link is None:
                continue
            match = TITLE_PATTERN.search(str(descriptor))
            if match is None:
                continue
            detail_url = urljoin(self.base_url, str(detail_link.get("href", "")))
            source_url = urljoin(self.base_url, str(pdf_link.get("href", "")))
            if source_url in seen:
                continue
            seen.add(source_url)
            doc_type = "UU" if match.group("type").lower().startswith("undang") else "PP"
            number = match.group("number")
            year = int(match.group("year"))
            document_id = f"{doc_type.lower()}-{number}-{year}".replace("/", "-")
            documents.append(
                DocumentMetadata(
                    document_id=document_id,
                    document_type=doc_type,
                    number=number,
                    year=year,
                    title=detail_link.get_text(" ", strip=True),
                    detail_url=detail_url,
                    source_url=source_url,
                )
            )
        return documents

    def parse_detail_metadata(self, html: str) -> dict[str, str]:
        """Extract legal status and document relations from a regulation detail page."""
        soup = BeautifulSoup(html, "html.parser")
        page_text = soup.get_text(" ", strip=True)
        status_match = STATUS_PATTERN.search(page_text)
        result = {"status": status_match.group(1).casefold().replace(" ", "_") if status_match else "tidak_diketahui"}
        relations: dict[str, set[str]] = {"amends": set(), "repeals": set()}
        for link in soup.find_all("a", href=True):
            context = link.parent.get_text(" ", strip=True) if link.parent else link.get_text(" ", strip=True)
            target = TITLE_PATTERN.search(context)
            if target is None:
                continue
            doc_type = "uu" if target.group("type").lower().startswith("undang") else "pp"
            document_id = f"{doc_type}-{target.group('number')}-{target.group('year')}".replace("/", "-")
            lowered = context.casefold()
            if "mencabut" in lowered:
                relations["repeals"].add(document_id)
            elif "mengubah" in lowered or "perubahan" in lowered:
                relations["amends"].add(document_id)
        result.update({key: ",".join(sorted(values)) for key, values in relations.items()})
        return result

    def scrape(self, limit: int = 100, categories: tuple[str, ...] = ("uu", "pp")) -> list[DocumentMetadata]:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        results: list[DocumentMetadata] = []
        seen_urls: set[str] = set()
        pages = {category: 1 for category in categories}
        exhausted: set[str] = set()
        while len(results) < limit and len(exhausted) < len(categories):
            for category in categories:
                if category in exhausted or len(results) >= limit:
                    continue
                page = pages[category]
                listing_url = f"{self.base_url}/{category}?page={page}"
                documents = self.parse_listing(self.fetch(listing_url).text)
                new_documents = [doc for doc in documents if doc.source_url not in seen_urls]
                if not new_documents:
                    exhausted.add(category)
                    continue
                for document in new_documents:
                    if len(results) >= limit:
                        break
                    seen_urls.add(document.source_url)
                    try:
                        detail = self.parse_detail_metadata(self.fetch(document.detail_url).text)
                        document = replace(document, **detail)
                        response = self.fetch(document.source_url)
                        if not response.content.startswith(b"%PDF"):
                            LOGGER.warning("Melewati respons non-PDF: %s", document.source_url)
                            continue
                        pdf_path = self.output_dir / f"{document.document_id}.pdf"
                        pdf_path.write_bytes(response.content)
                        checksum = hashlib.sha256(response.content).hexdigest()
                        stored = DocumentMetadata(**{**document.to_dict(), "pdf_path": str(pdf_path)})
                        (self.output_dir / f"{document.document_id}.json").write_text(
                            json.dumps({**stored.to_dict(), "sha256": checksum}, ensure_ascii=False, indent=2),
                            encoding="utf-8",
                        )
                        results.append(stored)
                        LOGGER.info("Tersimpan %s (%d/%d)", document.document_id, len(results), limit)
                    except httpx.HTTPError as exc:
                        LOGGER.warning("Gagal mengunduh %s: %s", document.source_url, exc)
                pages[category] += 1
        return results
