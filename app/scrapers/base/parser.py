import re
from urllib.parse import parse_qs, urljoin, urlparse

from dateutil.parser import ParserError, parse as parse_date

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
    def parse(self, html: str, base_url: str | None = None):
        soup = BeautifulSoup(html, "html.parser")
        base_tag = soup.find("base", href=True)
        base = base_tag["href"] if base_tag is not None else base_url
        if not base:
            raise ValueError(
                "Hearings HTML has no base href and no base URL was provided."
            )

        records = []
        for article in soup.select("article.teaser"):
            link = article.select_one("a.teaser__overlay-link")
            title = article.select_one("h3.headline")
            if link is None or title is None:
                continue
            source_url = urljoin(base, link["href"])
            records.append(
                {
                    "source_id": self._source_id(source_url),
                    "title": title.get_text(strip=True),
                    "published_at": self._published_at(article),
                    "source_url": source_url,
                    "place_text": self._place(article),
                }
            )

        for item in soup.select("li.link-list__item"):
            link = item.select_one("a.link-list__link")
            title = item.select_one("span.link-list__text")
            if link is None or title is None:
                continue
            source_url = urljoin(base, link["href"])
            records.append(
                {
                    "source_id": self._source_id(source_url),
                    "title": title.get_text(strip=True),
                    "published_at": None,
                    "source_url": source_url,
                    "place_text": self._place(item),
                }
            )
        return records

    def _published_at(self, article):
        node = article.select_one("div.teaser__text")
        if node is None:
            return None
        text = node.get_text(" ", strip=True)
        if re.search(r"\b\d{4}\b", text) is None:
            return None
        try:
            return parse_date(
                text,
                fuzzy=True,
            ).date().isoformat()
        except ParserError:
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