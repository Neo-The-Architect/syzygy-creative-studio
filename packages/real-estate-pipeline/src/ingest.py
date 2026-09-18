"""Small, dependency-light property ingestion helpers.

The URL parser is intentionally conservative: it reads JSON-LD and OpenGraph
metadata when available and never treats arbitrary page text as authoritative.
Use an authorized feed or exported record as the preferred production source.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen


class _MetaParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.meta: dict[str, str] = {}
        self.json_ld: list[str] = []
        self._script_type = ""
        self._script_chunks: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "meta":
            key = attrs_map.get("property") or attrs_map.get("name")
            value = attrs_map.get("content")
            if key and value:
                self.meta[key.lower()] = value
        if tag.lower() == "script":
            self._script_type = attrs_map.get("type", "").lower()
            self._script_chunks = []

    def handle_data(self, data: str) -> None:
        if self._script_type == "application/ld+json":
            self._script_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._script_type == "application/ld+json":
            payload = "".join(self._script_chunks).strip()
            if payload:
                self.json_ld.append(payload)
            self._script_type = ""
            self._script_chunks = []


def _first(value: Any) -> Any:
    if isinstance(value, list):
        return value[0] if value else None
    return value


def parse_listing_html(html: str, source_url: str = "local://fixture") -> dict[str, Any]:
    parser = _MetaParser()
    parser.feed(html)
    records: list[dict[str, Any]] = []
    for raw in parser.json_ld:
        try:
            decoded = json.loads(raw)
        except json.JSONDecodeError:
            continue
        candidates = decoded if isinstance(decoded, list) else [decoded]
        records.extend(item for item in candidates if isinstance(item, dict))

    structured = next(
        (
            item
            for item in records
            if item.get("@type") in {"RealEstateListing", "SingleFamilyResidence", "Residence", "Product"}
            or "address" in item
            or "floorSize" in item
        ),
        {},
    )
    address = structured.get("address")
    if isinstance(address, dict):
        address = ", ".join(
            part for part in [address.get("streetAddress"), address.get("addressLocality"), address.get("addressRegion")]
            if part
        )
    images = structured.get("image") or parser.meta.get("og:image")
    if isinstance(images, str):
        images = [images]
    images = images or []

    price = structured.get("offers", {}).get("price") if isinstance(structured.get("offers"), dict) else None
    return {
        "source_url": source_url,
        "address": address or parser.meta.get("og:title") or "",
        "price": price,
        "beds": structured.get("numberOfBedrooms"),
        "baths": structured.get("numberOfBathroomsTotal"),
        "area_sqft": (structured.get("floorSize") or {}).get("value") if isinstance(structured.get("floorSize"), dict) else None,
        "description": structured.get("description") or parser.meta.get("description", ""),
        "features": structured.get("amenityFeature", []),
        "image_urls": images,
        "source_kind": "jsonld_or_opengraph",
    }


def ingest_url(url: str, timeout: int = 20) -> dict[str, Any]:
    request = Request(url, headers={"User-Agent": "RealEstatePipeline/0.1 (authorized research)"})
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8", errors="replace")
    return parse_listing_html(html, source_url=url)


def ingest_path(path: str | Path) -> dict[str, Any]:
    value = Path(path)
    if value.suffix.lower() in {".html", ".htm"}:
        return parse_listing_html(value.read_text(encoding="utf-8"), source_url=value.resolve().as_uri())
    return json.loads(value.read_text(encoding="utf-8"))
