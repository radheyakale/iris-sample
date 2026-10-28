import re
from datetime import date
from urllib.parse import parse_qs, urljoin, urlparse

import json

from bs4 import BeautifulSoup


class NextDataParser:

    def parse(self, html: str):

        soup = BeautifulSoup(html, "html.parser")

        script = soup.find("script", id="__NEXT_DATA__")

        if script is None:
            raise Exception("__NEXT_DATA__ not found")

        return json.loads(script.string)


class HearingsHTMLDataParser:
    _MONTHS = {
        "januar": 1,
        "februar": 2,
        "märz": 3,
        "maerz": 3,
        "april": 4,
        "mai": 5,
        "juni": 6,
        "juli": 7,
        "august": 8,
        "september": 9,
        "oktober": 10,
        "november": 11,
        "dezember": 12,
    }

    _NUMERIC_DATE = re.compile(
        r"\b(\d{1,2})\.(\d{1,2})\.(\d{4})\b"
    )

    _NAMED_DATE = re.compile(
        r"\b(\d{1,2})\.?\s+"
        r"(januar|februar|märz|maerz|april|mai|juni|juli|"
        r"august|september|oktober|november|dezember)\s+"
        r"(\d{4})\b"
    )

    def __init__(self):
        self.dropped_missing_fields = 0

    def parse(self, html: str, base_url: str | None = None):
        self.dropped_missing_fields = 0
        soup = BeautifulSoup(html or "", "html.parser")
        base_tag = soup.find("base", href=True)
        base = base_tag["href"] if base_tag is not None else base_url
        if not base:
            raise ValueError(
                "Hearings HTML has no base href and no base URL was provided."
            )

        records = []
        for article in soup.select("article.teaser"):
            link = article.select_one("a.teaser__overlay-link")
            title = article.select_one(".teaser__headline .headline")
            if (
                link is None
                or title is None
                or not title.get_text(strip=True)
            ):
                self.dropped_missing_fields += 1
                continue
            source_url = urljoin(base, link["href"])
            records.append(
                self._record(
                    article,
                    title.get_text(strip=True),
                    source_url,
                )
            )

        for item in soup.select("li.link-list__item"):
            link = item.select_one("a.link-list__link")
            title = item.select_one("span.link-list__text")
            if (
                link is None
                or title is None
                or not title.get_text(strip=True)
            ):
                self.dropped_missing_fields += 1
                continue
            source_url = urljoin(base, link["href"])
            records.append(
                self._record(
                    item,
                    title.get_text(strip=True),
                    source_url,
                )
            )
        return records

    def _record(self, node, title: str, source_url: str) -> dict:
        dates = self._extract_dates(
            node.get_text(" ", strip=True)
        )
        return {
            "source_id": self._source_id(source_url),
            "title": title,
            "published_at": dates["published_at"],
            "participation_start": dates["participation_start"],
            "participation_end": dates["participation_end"],
            "source_url": source_url,
            "place_text": self._place(node),
        }

    def _extract_dates(self, text: str) -> dict:
        folded = text.casefold()
        found = []
        for pattern in (
            self._NUMERIC_DATE,
            self._NAMED_DATE,
        ):
            for match in pattern.finditer(folded):
                value = self._to_date(match)
                if value is not None:
                    found.append((match.start(), value))
        found.sort(key=lambda item: item[0])

        result = {
            "published_at": None,
            "participation_start": None,
            "participation_end": None,
        }
        for start, value in found:
            window = folded[max(0, start - 48):start]
            iso = value.isoformat()
            if re.search(
                r"veröffentlicht|bekanntmachung|publiziert",
                window,
            ):
                result["published_at"] = iso
            elif re.search(r"\bbis(?:\s+zum)?\s*$", window):
                result["participation_end"] = iso
            elif re.search(r"\b(?:vom|von|ab)\s*$", window):
                result["participation_start"] = iso
        return result

    def _to_date(self, match: re.Match) -> date | None:
        month_token = match.group(2)
        if month_token.isdigit():
            month = int(month_token)
        else:
            month = self._MONTHS[month_token]
        try:
            return date(
                int(match.group(3)),
                month,
                int(match.group(1)),
            )
        except ValueError:
            return None

    def _source_id(self, url: str) -> str:
        comment_ids = parse_qs(urlparse(url).query).get(
            "comment[searchComment]"
        )
        if comment_ids:
            return comment_ids[0]
        return urlparse(url).path.rstrip("/").rsplit("/", 1)[-1]

    def _place(self, node):
        text = node.get_text(" ", strip=True)
        for pattern in (
            r"Haushalt\s+([A-ZÄÖÜ][\w-]+)",
            r"\bin\s+([A-ZÄÖÜ][\w-]+)",
        ):
            match = re.search(pattern, text)
            if match:
                return match.group(1)
        return ""