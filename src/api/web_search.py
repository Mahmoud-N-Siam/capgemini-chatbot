import html
import logging
import re
from typing import Dict, List, Optional
from urllib.parse import parse_qs, unquote, urlparse

import requests

from config.settings import Settings

logger = logging.getLogger(__name__)


class WebSearch:
    """Web-search adapter backed by DuckDuckGo's HTML results page.

    The Instant Answer endpoint (api.duckduckgo.com) only returns curated
    answers and is empty for most real questions, so the HTML endpoint is used
    to obtain ranked organic results.
    """

    URL = "https://html.duckduckgo.com/html/"
    HEADERS = {
        "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                       "AppleWebKit/537.36 (KHTML, like Gecko) "
                       "Chrome/122.0 Safari/537.36"),
        "Accept-Language": "en-US,en;q=0.9",
    }

    _RESULT_PATTERN = re.compile(
        r'<a[^>]+class="[^"]*result__a[^"]*"[^>]+href="(?P<url>[^"]+)"[^>]*>(?P<title>.*?)</a>'
        r'(?P<rest>.*?)(?=<a[^>]+class="[^"]*result__a|\Z)',
        re.IGNORECASE | re.DOTALL,
    )
    _SNIPPET_PATTERN = re.compile(
        r'class="[^"]*result__snippet[^"]*"[^>]*>(?P<snippet>.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    _TAG_PATTERN = re.compile(r"<[^>]+>")

    @classmethod
    def _clean(cls, markup: str) -> str:
        return html.unescape(cls._TAG_PATTERN.sub("", markup)).strip()

    @staticmethod
    def _normalise_url(raw_url: str) -> str:
        """Unwrap DuckDuckGo's /l/?uddg= redirect wrapper."""
        if raw_url.startswith("//"):
            raw_url = f"https:{raw_url}"
        parsed = urlparse(raw_url)
        if "duckduckgo.com" in parsed.netloc and parsed.path.startswith("/l/"):
            target = parse_qs(parsed.query).get("uddg", [])
            if target:
                return unquote(target[0])
        return raw_url

    def search(self, query: str, max_results: Optional[int] = None) -> List[Dict[str, str]]:
        if not Settings.WEB_SEARCH_ENABLED:
            return []
        max_results = min(max_results or Settings.WEB_SEARCH_MAX_RESULTS, 10)
        if max_results <= 0:
            return []

        try:
            response = requests.post(
                self.URL,
                data={"q": query, "kl": "wt-wt"},
                headers=self.HEADERS,
                timeout=Settings.WEB_SEARCH_TIMEOUT,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            logger.warning("Web search unavailable: %s", error)
            return []

        results: List[Dict[str, str]] = []
        seen_urls = set()
        for match in self._RESULT_PATTERN.finditer(response.text):
            url = self._normalise_url(html.unescape(match.group("url")))
            title = self._clean(match.group("title"))
            if not url or not title or url in seen_urls:
                continue
            snippet_match = self._SNIPPET_PATTERN.search(match.group("rest") or "")
            snippet = self._clean(snippet_match.group("snippet")) if snippet_match else ""
            seen_urls.add(url)
            results.append({"title": title, "url": url, "snippet": snippet or title})
            # Deduplicate before capping so the caller always gets the full count
            # when enough distinct results exist.
            if len(results) >= max_results:
                break

        if not results:
            logger.warning("Web search returned no parsable results for %r", query)
        return results