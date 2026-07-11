# -*- coding: utf-8 -*-
"""Literature retrieval and citation synchronization backed by OpenAlex."""
from datetime import datetime, timezone

from openalex_client import (
    citation_graph,
    extract_work_info,
    get_work_by_doi,
    recent_works_by_topic,
    search_works,
)


# Kept for template compatibility. Production pages no longer display invented
# papers or placeholder DOI records when a real source is unavailable.
SAMPLE_LITERATURE = {}


def _paper_from_work(work, fallback_topic=""):
    info = extract_work_info(work)
    return {
        "title": info.get("title", ""),
        "authors": info.get("authors", ""),
        "journal": info.get("journal", ""),
        "year": info.get("year"),
        "doi": info.get("doi", ""),
        "openalex_id": info.get("openalex_id", ""),
        "abstract": info.get("abstract", ""),
        "url": info.get("url", ""),
        "citation_count": info.get("cited_by_count", 0),
        "topic": info.get("topic") or fallback_topic,
        "referenced_works": info.get("referenced_works", []),
    }


def fetch_literature_for_topic(topic, keywords="", limit=20):
    """Return verified OpenAlex records for a subscription.

    Recent papers are preferred. If a topic has no papers in the configured
    window, the function falls back to relevance-ranked OpenAlex results, never
    fabricated demo data.
    """
    query = " ".join(part for part in (topic.strip(), keywords.strip()) if part)
    works = recent_works_by_topic(query, days=30, per_page=limit)
    if not works:
        works = search_works(query, limit)
    return [_paper_from_work(work, topic) for work in works]


def enrich_literature(title="", doi="", url=""):
    """Resolve metadata using DOI first and title search second."""
    work = get_work_by_doi(doi) if doi else None
    if not work and title:
        matches = search_works(title, 1)
        work = matches[0] if matches else None
    if not work:
        return {}
    result = _paper_from_work(work)
    if url and not result.get("url"):
        result["url"] = url
    return result


def _find_item(node):
    from models import LiteratureItem

    openalex_id = node.get("openalex_id") or node.get("id")
    doi = node.get("doi") or ""
    item = None
    if openalex_id:
        item = LiteratureItem.query.filter_by(openalex_id=openalex_id).first()
    if not item and doi:
        item = LiteratureItem.query.filter_by(doi=doi).first()
    return item


def persist_citation_graph(graph, topic=""):
    """Upsert graph nodes and exact citation edges into the local database."""
    from models import CitationLink, LiteratureItem, db

    id_map = {}
    created = 0
    for node in graph.get("nodes", []):
        item = _find_item(node)
        if not item:
            item = LiteratureItem(
                title=node.get("title") or node.get("label") or "Untitled",
                doi=node.get("doi") or None,
                openalex_id=node.get("openalex_id") or node.get("id") or None,
            )
            db.session.add(item)
            db.session.flush()
            created += 1
        item.title = node.get("title") or item.title
        item.authors = node.get("authors") or item.authors
        item.journal = node.get("journal") or item.journal
        item.year = node.get("year") or item.year
        item.url = node.get("url") or item.url
        item.abstract = node.get("abstract") or item.abstract
        item.topic = node.get("topic") or topic or item.topic
        item.citation_count = node.get("citation_count", item.citation_count or 0)
        item.openalex_id = node.get("openalex_id") or node.get("id") or item.openalex_id
        id_map[node.get("id")] = item.id

    db.session.flush()
    edge_count = 0
    for edge in graph.get("edges", []):
        source_id = id_map.get(edge.get("source") or edge.get("from"))
        target_id = id_map.get(edge.get("target") or edge.get("to"))
        if not source_id or not target_id or source_id == target_id:
            continue
        existing = CitationLink.query.filter_by(source_id=source_id, target_id=target_id).first()
        if not existing:
            db.session.add(CitationLink(
                source_id=source_id,
                target_id=target_id,
                relationship="cites",
                weight=float(edge.get("weight") or 1.0),
            ))
            edge_count += 1
    db.session.commit()
    return {"created_nodes": created, "created_edges": edge_count}


def sync_citation_network(query, query_type="keyword", topic="", max_nodes=35):
    graph = citation_graph(query, query_type=query_type, max_nodes=max_nodes)
    stats = persist_citation_graph(graph, topic=topic or query) if graph.get("nodes") else {"created_nodes": 0, "created_edges": 0}
    return graph, stats


def generate_citation_graph(literature_items):
    """Serialize stored papers and only database-backed citation edges."""
    from models import CitationLink

    items = list(literature_items or [])
    item_ids = {item.id for item in items}
    nodes = [{
        "id": item.id,
        "label": item.title[:55],
        "title": item.title,
        "authors": item.authors,
        "year": item.year,
        "journal": item.journal,
        "citation_count": item.citation_count or 0,
        "topic": item.topic or "Uncategorized",
        "doi": item.doi or "",
        "url": item.url or "",
        "openalex_id": item.openalex_id or "",
    } for item in items]

    edges = []
    if item_ids:
        for link in CitationLink.query.filter(CitationLink.source_id.in_(item_ids)).all():
            if link.target_id not in item_ids:
                continue
            edges.append({
                "source": link.source_id,
                "target": link.target_id,
                "from": link.source_id,
                "to": link.target_id,
                "weight": link.weight or 1.0,
                "relationship": link.relationship or "cites",
            })
    return {"nodes": nodes, "edges": edges, "source": "OpenAlex"}


def run_weekly_fetch():
    from app import app
    from models import LiteratureSubscription

    with app.app_context():
        for subscription in LiteratureSubscription.query.filter_by(active=True).all():
            query = " ".join(filter(None, [subscription.topic, subscription.keywords]))
            sync_citation_network(query, topic=subscription.topic, max_nodes=30)

    try:
        from email_service import send_weekly_literature
        send_weekly_literature()
    except Exception:
        pass
    print(f"[Agent] Weekly literature fetch completed at {datetime.now(timezone.utc)}")
    return True
