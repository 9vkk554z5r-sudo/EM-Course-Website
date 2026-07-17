# -*- coding: utf-8 -*-
"""OpenAlex client and citation-graph builder.

All graph edges come from OpenAlex ``referenced_works`` records. No topical or
LLM-inferred relationship is presented as a citation.
"""
from collections import Counter
from datetime import datetime, timedelta, timezone
import os
import time

import requests


BASE_URL = "https://api.openalex.org"
_TIMEOUT = 30
_MAX_RETRIES = 3


def _proxies():
    result = {}
    for name in ("HTTP_PROXY", "http_proxy"):
        if os.environ.get(name):
            result["http"] = os.environ[name]
            break
    for name in ("HTTPS_PROXY", "https_proxy"):
        if os.environ.get(name):
            result["https"] = os.environ[name]
            break
    return result or None


def _headers():
    email = os.environ.get("OPENALEX_EMAIL", "").strip()
    user_agent = "EMCourseWebsite/2.0"
    if email:
        user_agent += f" (mailto:{email})"
    return {"User-Agent": user_agent, "Accept": "application/json"}


def _safe_get(path, **kwargs):
    url = path if path.startswith("http") else BASE_URL + path
    last_error = None
    timeout = kwargs.pop("timeout", _TIMEOUT)
    headers = kwargs.pop("headers", _headers())
    configured_proxies = _proxies()
    for attempt in range(_MAX_RETRIES + 1):
        try:
            response = requests.get(
                url,
                timeout=timeout,
                headers=headers,
                proxies=configured_proxies,
                **kwargs,
            )
            if response.status_code == 200:
                return response
            if response.status_code not in {429, 500, 502, 503, 504}:
                return None
            last_error = RuntimeError(f"OpenAlex returned {response.status_code}")
        except requests.RequestException as exc:
            last_error = exc
            # A stale system/school proxy should not make the literature module
            # unusable when a direct connection is available.
            if configured_proxies:
                try:
                    session = requests.Session()
                    session.trust_env = False
                    response = session.get(url, timeout=timeout, headers=headers, **kwargs)
                    if response.status_code == 200:
                        return response
                except requests.RequestException:
                    pass
        if attempt < _MAX_RETRIES:
            time.sleep(0.4 * (2 ** attempt))
    if last_error:
        raise last_error
    return None


def normalize_doi(value):
    doi = (value or "").strip()
    for prefix in ("https://doi.org/", "http://doi.org/", "http://dx.doi.org/", "doi:"):
        if doi.lower().startswith(prefix):
            doi = doi[len(prefix):]
            break
    return doi.strip().lower()


def normalize_openalex_id(value):
    return (value or "").rstrip("/").split("/")[-1]


def _abstract_from_index(index):
    if not index:
        return ""
    positions = []
    for word, offsets in index.items():
        for offset in offsets or []:
            positions.append((offset, word))
    positions.sort(key=lambda item: item[0])
    return " ".join(word for _, word in positions)


def search_works(query, n=10):
    query = (query or "").strip()
    if not query:
        return []
    response = _safe_get(
        "/works",
        params={
            "search": query,
            "per_page": min(max(int(n), 1), 100),
            "sort": "relevance_score:desc",
        },
    )
    return response.json().get("results", []) if response else []


def get_work_by_doi(doi):
    doi = normalize_doi(doi)
    if not doi:
        return None
    response = _safe_get("/works/https://doi.org/" + doi)
    return response.json() if response else None


def get_work_by_id(openalex_id):
    openalex_id = normalize_openalex_id(openalex_id)
    if not openalex_id:
        return None
    response = _safe_get("/works/" + openalex_id)
    return response.json() if response else None


def get_works_by_ids(openalex_ids, limit=30):
    ids = []
    for value in openalex_ids or []:
        normalized = normalize_openalex_id(value)
        if normalized and normalized not in ids:
            ids.append(normalized)
        if len(ids) >= limit:
            break
    works = []
    for start in range(0, len(ids), 25):
        batch = ids[start:start + 25]
        response = _safe_get(
            "/works",
            params={"filter": "openalex_id:" + "|".join(batch), "per_page": len(batch)},
        )
        if response:
            works.extend(response.json().get("results", []))
    return works


def get_citing_works(openalex_id, n=12):
    openalex_id = normalize_openalex_id(openalex_id)
    if not openalex_id:
        return []
    response = _safe_get(
        "/works",
        params={
            "filter": "cites:" + openalex_id,
            "per_page": min(max(int(n), 1), 50),
            "sort": "cited_by_count:desc",
        },
    )
    return response.json().get("results", []) if response else []


def extract_work_info(work):
    if not work:
        return {}
    authorships = work.get("authorships") or []
    author_names = [
        (entry.get("author") or {}).get("display_name", "")
        for entry in authorships
        if (entry.get("author") or {}).get("display_name")
    ]
    corresponding = next(
        ((entry.get("author") or {}).get("display_name", "") for entry in authorships if entry.get("is_corresponding")),
        "",
    )
    primary_location = work.get("primary_location") or {}
    source = primary_location.get("source") or {}
    primary_topic = work.get("primary_topic") or {}
    topic_name = primary_topic.get("display_name") or ""
    if not topic_name:
        topics = work.get("topics") or work.get("concepts") or []
        topic_name = (topics[0] or {}).get("display_name", "") if topics else ""
    doi = normalize_doi(work.get("doi"))
    openalex_id = normalize_openalex_id(work.get("id"))
    return {
        "title": work.get("title") or work.get("display_name") or "",
        "doi": doi,
        "openalex_id": openalex_id,
        "publication_date": work.get("publication_date") or "",
        "date": work.get("publication_date") or "",
        "year": work.get("publication_year"),
        "journal": source.get("display_name") or "",
        "cited_by_count": work.get("cited_by_count") or 0,
        "authors": ", ".join(author_names),
        "first_author": author_names[0] if author_names else "",
        "corresponding_author": corresponding or (author_names[-1] if author_names else ""),
        "topic": topic_name,
        "concepts": [
            item.get("display_name", "")
            for item in (work.get("topics") or work.get("concepts") or [])[:5]
            if item.get("display_name")
        ],
        "abstract": _abstract_from_index(work.get("abstract_inverted_index")),
        "url": primary_location.get("landing_page_url") or ("https://doi.org/" + doi if doi else work.get("id") or ""),
        "referenced_works": [normalize_openalex_id(value) for value in work.get("referenced_works") or []],
    }


def extract_key_points(info):
    if not info:
        return []
    points = []
    if info.get("title"):
        points.append("Title: " + info["title"][:140])
    if info.get("concepts"):
        points.append("Themes: " + ", ".join(info["concepts"][:3]))
    if info.get("journal"):
        points.append("Journal: " + info["journal"])
    points.append("Cited by: " + str(info.get("cited_by_count", 0)))
    return points[:5]


def works_to_citation_graph(works):
    nodes = []
    work_by_id = {}
    for work in works or []:
        info = extract_work_info(work)
        node_id = info.get("openalex_id")
        if not node_id or node_id in work_by_id:
            continue
        work_by_id[node_id] = info
        nodes.append({
            "id": node_id,
            "label": (info.get("title") or "")[:55],
            "title": info.get("title") or "",
            "authors": info.get("authors") or info.get("first_author") or "",
            "journal": info.get("journal") or "",
            "year": info.get("year"),
            "citation_count": info.get("cited_by_count") or 0,
            "doi": info.get("doi") or "",
            "url": info.get("url") or "",
            "abstract": info.get("abstract") or "",
            "topic": info.get("topic") or "Uncategorized",
            "openalex_id": node_id,
        })

    edges = []
    seen = set()
    for source_id, info in work_by_id.items():
        for target_id in info.get("referenced_works") or []:
            if target_id not in work_by_id or target_id == source_id:
                continue
            edge_key = (source_id, target_id)
            if edge_key in seen:
                continue
            seen.add(edge_key)
            edges.append({
                "source": source_id,
                "target": target_id,
                "from": source_id,
                "to": target_id,
                "weight": 1.0,
                "relationship": "cites",
            })
    return {"nodes": nodes, "edges": edges, "source": "OpenAlex"}


def citation_graph(query, query_type="keyword", max_nodes=35):
    if query_type == "doi":
        root = get_work_by_doi(query)
        if not root:
            return {"nodes": [], "edges": [], "source": "OpenAlex"}
        root_id = normalize_openalex_id(root.get("id"))
        reference_ids = (root.get("referenced_works") or [])[:12]
        works = [root] + get_works_by_ids(reference_ids, limit=12) + get_citing_works(root_id, n=12)
        return works_to_citation_graph(works[:max_nodes])

    seeds = search_works(query, min(20, max_nodes))
    reference_frequency = Counter()
    seed_ids = {normalize_openalex_id(work.get("id")) for work in seeds}
    for work in seeds:
        for reference in work.get("referenced_works") or []:
            reference_id = normalize_openalex_id(reference)
            if reference_id and reference_id not in seed_ids:
                reference_frequency[reference_id] += 1
    remaining = max(0, max_nodes - len(seeds))
    connector_ids = [item[0] for item in reference_frequency.most_common(remaining)]
    works = seeds + get_works_by_ids(connector_ids, limit=remaining)
    return works_to_citation_graph(works[:max_nodes])


def recent_works_by_topic(topic, days=7, per_page=20):
    from_date = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    response = _safe_get(
        "/works",
        params={
            "search": topic,
            "filter": "from_publication_date:" + from_date,
            "per_page": min(max(int(per_page), 1), 100),
            "sort": "publication_date:desc",
        },
    )
    return response.json().get("results", []) if response else []
