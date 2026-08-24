import logging
import re
from typing import List, Dict

import requests

from config.settings import Settings

logger = logging.getLogger(__name__)


class WebSearch:
    """Small optional web-search adapter using DuckDuckGo's JSON endpoint."""

    URL = "https://api.duckduckgo.com/"

    def search(self, query: str, max_results: int = None) -> List[Dict[str, str]]:
        if not Settings.WEB_SEARCH_ENABLED:
            return []
        max_results = min(max_results or Settings.WEB_SEARCH_MAX_RESULTS, 10)

        try:
            python_results = self._search_python_releases(query)
            if python_results:
                return python_results
            response = requests.get(
                self.URL,
                params={"q": query, "format": "json", "no_html": 1, "no_redirect": 1},
                timeout=Settings.WEB_SEARCH_TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            results = []
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", query),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data["AbstractText"],
                })
            for topic in data.get("RelatedTopics", []):
                if "Text" in topic and "FirstURL" in topic:
                    results.append({
                        "title": topic["Text"].split(" - ", 1)[0],
                        "url": topic["FirstURL"],
                        "snippet": topic["Text"],
                    })
                if len(results) >= max_results:
                    break
            unique_results = []
            seen_urls = set()
            for result in results:
                if result["url"] and result["url"] not in seen_urls:
                    unique_results.append(result)
                    seen_urls.add(result["url"])
            return unique_results[:max_results]
        except (requests.RequestException, ValueError) as error:
            logger.warning("Web search unavailable: %s", error)
            return []

    def _search_python_releases(self, query: str) -> List[Dict[str, str]]:
        query_lower = query.lower()
        if "python" not in query_lower or not any(
                term in query_lower for term in ("latest", "version", "release")):
            return []

        try:
            response = requests.get(
                "https://api.github.com/repos/python/cpython/tags",
                params={"per_page": 100},
                headers={"Accept": "application/vnd.github+json", "User-Agent": "capgemini-chatbot"},
                timeout=Settings.WEB_SEARCH_TIMEOUT,
            )
            response.raise_for_status()
            stable_versions = [
                tag["name"] for tag in response.json()
                if re.fullmatch(r"v\d+\.\d+\.\d+", tag.get("name", ""))
            ]
            if not stable_versions:
                return []
            stable_versions.sort(
                key=lambda version: tuple(int(part) for part in version[1:].split(".")),
                reverse=True,
            )
            return [{
                "title": "CPython releases",
                "url": "https://github.com/python/cpython/tags",
                "snippet": f"The latest stable CPython tag listed is {stable_versions[0]}.",
            }]
        except (requests.RequestException, ValueError, KeyError) as error:
            logger.warning("Python release lookup unavailable: %s", error)
            return []