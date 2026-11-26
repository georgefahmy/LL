from __future__ import annotations

from functools import lru_cache
from urllib.parse import quote

import httpx

_LOOKUP_HEADERS = {
    "User-Agent": "LearnedLeaguePracticeTool/9.0 (https://github.com/georgefahmy/LL)"
}


@lru_cache(maxsize=256)
def lookup_term(term: str) -> dict[str, str]:
    """Look up a single word (Dictionary API -> Wiki fallback) or phrase (Wikipedia REST API)."""
    cleaned = " ".join(term.strip().split())
    if not cleaned:
        return {"term": "", "source": "none", "summary": "No text selected."}

    words = cleaned.split(" ")
    if len(words) == 1:
        dict_result = _lookup_dictionary(words[0])
        if dict_result is not None:
            return dict_result

    wiki_result = _lookup_wikipedia(cleaned)
    if wiki_result is not None:
        return wiki_result

    return {
        "term": cleaned,
        "source": "none",
        "summary": "No dictionary or Wikipedia results found for this selection.",
    }


def _lookup_dictionary(word: str) -> dict[str, str] | None:
    clean_word = word.strip(".,!?;:\"'()[]{}")
    if not clean_word:
        return None
    url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{quote(clean_word)}"
    try:
        resp = httpx.get(url, headers=_LOOKUP_HEADERS, timeout=6.0)
        if resp.status_code != 200:
            return None
        entries = resp.json()
        if not isinstance(entries, list) or not entries:
            return None
        lines: list[str] = []
        for meaning in entries[0].get("meanings", [])[:4]:
            pos = meaning.get("partOfSpeech", "")
            defs = [d.get("definition", "") for d in meaning.get("definitions", [])[:2]]
            defs = [d for d in defs if d]
            if defs:
                lines.append(f"{pos}: " + "; ".join(defs))
        if not lines:
            return None
        return {
            "term": entries[0].get("word", clean_word),
            "source": "dictionary",
            "summary": "\n".join(lines),
        }
    except Exception:
        return None


def _lookup_wikipedia(query: str) -> dict[str, str] | None:
    slug = quote(query.replace(" ", "_"))
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{slug}"
    try:
        resp = httpx.get(url, headers=_LOOKUP_HEADERS, timeout=6.0, follow_redirects=True)
        if resp.status_code == 200:
            data = resp.json()
            extract = str(data.get("extract", "")).strip()
            if extract:
                return {
                    "term": str(data.get("title", query)),
                    "source": "wikipedia",
                    "summary": extract,
                }
        # Fallback to Wikipedia opensearch for closest matching page title
        search_resp = httpx.get(
            "https://en.wikipedia.org/w/api.php",
            params={
                "action": "opensearch",
                "search": query,
                "limit": "1",
                "namespace": "0",
                "format": "json",
            },
            headers=_LOOKUP_HEADERS,
            timeout=6.0,
        )
        if search_resp.status_code == 200:
            arr = search_resp.json()
            if isinstance(arr, list) and len(arr) >= 2 and arr[1]:
                best_title = str(arr[1][0])
                best_slug = quote(best_title.replace(" ", "_"))
                resp2 = httpx.get(
                    f"https://en.wikipedia.org/api/rest_v1/page/summary/{best_slug}",
                    headers=_LOOKUP_HEADERS,
                    timeout=6.0,
                    follow_redirects=True,
                )
                if resp2.status_code == 200:
                    data2 = resp2.json()
                    extract2 = str(data2.get("extract", "")).strip()
                    if extract2:
                        return {
                            "term": str(data2.get("title", best_title)),
                            "source": "wikipedia",
                            "summary": extract2,
                        }
    except Exception:
        return None
    return None
