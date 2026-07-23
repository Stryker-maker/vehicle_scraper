from __future__ import annotations

import hashlib
from typing import Any

from bs4 import BeautifulSoup

BLOCK_MARKERS = (
    "access denied",
    "captcha",
    "cloudflare",
    "datadome",
    "incapsula",
    "perimeterx",
    "px-captcha",
    "robot check",
    "verify you are human",
)


def summarize_kijiji_html(html: str) -> dict[str, Any]:
    text = str(html or "")
    encoded = text.encode("utf-8", errors="replace")
    lowered = text.casefold()
    soup = BeautifulSoup(text, "html.parser")
    scripts = soup.find_all("script")
    listing_links = {
        str(anchor.get("href"))
        for anchor in soup.find_all("a", href=True)
        if "/v-cars-trucks/" in str(anchor.get("href"))
    }
    return {
        "response_bytes": len(encoded),
        "response_sha256": hashlib.sha256(encoded).hexdigest(),
        "page_title": soup.title.get_text(" ", strip=True) if soup.title else None,
        "script_count": len(scripts),
        "script_types": sorted({str(script.get("type") or "") for script in scripts}),
        "json_ld_script_count": sum(
            str(script.get("type") or "").casefold() == "application/ld+json"
            for script in scripts
        ),
        "next_data_present": soup.find("script", id="__NEXT_DATA__") is not None,
        "item_list_marker_present": "itemlistelement" in lowered,
        "listing_link_count": len(listing_links),
        "block_markers": [marker for marker in BLOCK_MARKERS if marker in lowered],
        "text_sample": " ".join(soup.stripped_strings)[:1000],
    }
