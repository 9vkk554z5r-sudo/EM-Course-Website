# -*- coding: utf-8 -*-
"""
Literature Agent — simulates AI agent that fetches latest literature
for subscribed topics. In production, this would call an external
Agent platform API (e.g. the school's agent platform).
"""
import random
import requests
from datetime import datetime, timezone
from config import LITERATURE_API_URL, AGENT_API_KEY


# Sample literature data for demonstration / offline mode
SAMPLE_LITERATURE = {
    "electron microscopy": [
        {
            "title": "Advances in aberration-corrected scanning transmission electron microscopy",
            "authors": "Pennycook, S.J. et al.",
            "journal": "Nature Reviews Physics",
            "year": 2025,
            "doi": "10.1000/example.emnano.001",
            "abstract": "Recent developments in aberration correction have pushed STEM resolution below 0.5 Å, enabling direct imaging of light elements and chemical bonds.",
            "url": "https://doi.org/10.1000/example.emnano.001",
            "citation_count": 156,
            "topic": "electron microscopy"
        },
        {
            "title": "In situ TEM observation of catalytic reactions at atomic resolution",
            "authors": "Zheng, H. & Zhang, W.",
            "journal": "Science",
            "year": 2025,
            "doi": "10.1000/example.emnano.002",
            "abstract": "We report real-time atomic-scale imaging of catalytic reactions using advanced in situ TEM with graphene liquid cells.",
            "url": "https://doi.org/10.1000/example.emnano.002",
            "citation_count": 89,
            "topic": "electron microscopy"
        },
        {
            "title": "4D-STEM: A new paradigm for materials characterization",
            "authors": "Ophus, C.",
            "journal": "Annual Review of Materials Research",
            "year": 2024,
            "doi": "10.1000/example.emnano.003",
            "abstract": "This review covers the principles and applications of four-dimensional scanning transmission electron microscopy.",
            "url": "https://doi.org/10.1000/example.emnano.003",
            "citation_count": 234,
            "topic": "electron microscopy"
        },
    ],
    "cryo-EM": [
        {
            "title": "Single-particle cryo-EM at atomic resolution",
            "authors": "Yip, K.M. et al.",
            "journal": "Nature",
            "year": 2025,
            "doi": "10.1000/example.cryo.001",
            "abstract": "Advances in detector technology and image processing have enabled routine atomic resolution structure determination by single-particle cryo-EM.",
            "url": "https://doi.org/10.1000/example.cryo.001",
            "citation_count": 312,
            "topic": "cryo-EM"
        },
        {
            "title": "Time-resolved cryo-EM reveals dynamic protein conformations",
            "authors": "Frank, J. & Chen, X.",
            "journal": "PNAS",
            "year": 2025,
            "doi": "10.1000/example.cryo.002",
            "abstract": "Microfluidic mixing and rapid freezing enable capture of transient protein states at sub-second timescales.",
            "url": "https://doi.org/10.1000/example.cryo.002",
            "citation_count": 67,
            "topic": "cryo-EM"
        },
    ],
    "semiconductor characterization": [
        {
            "title": "Atomic-scale characterization of semiconductor heterostructures by STEM",
            "authors": "Muller, D.A.",
            "journal": "Nature Materials",
            "year": 2024,
            "doi": "10.1000/example.semi.001",
            "abstract": "Quantitative STEM analysis provides atomic-resolution maps of composition and strain in semiconductor devices.",
            "url": "https://doi.org/10.1000/example.semi.001",
            "citation_count": 178,
            "topic": "semiconductor characterization"
        },
    ],
}

# Citation links between sample papers (source_id, target_id, weight)
SAMPLE_CITATIONS = [
    (1, 4, 2.5),
    (1, 3, 1.8),
    (2, 1, 1.2),
    (3, 4, 3.0),
    (4, 5, 0.8),
    (2, 3, 1.5),
    (5, 1, 1.1),
    (3, 6, 2.0),
]


def fetch_literature_for_topic(topic, keywords=""):
    """
    Fetch latest literature for a given topic.
    In production, this calls the school's Agent platform API.
    Falls back to sample data for demonstration.
    """
    try:
        resp = requests.post(
            LITERATURE_API_URL,
            json={"topic": topic, "keywords": keywords, "limit": 10},
            headers={"Authorization": f"Bearer {AGENT_API_KEY}"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json().get("results", [])
    except requests.RequestException:
        pass  # Fall through to sample data

    # Return sample data that matches the topic
    for key, papers in SAMPLE_LITERATURE.items():
        if key.lower() in topic.lower() or topic.lower() in key.lower():
            return papers

    # Return generic sample
    return [
        {
            "title": f"Recent developments in electron microscopy ({topic})",
            "authors": "Various authors",
            "journal": "Ultramicroscopy",
            "year": 2025,
            "doi": f"10.1000/example.{topic.lower().replace(' ', '')}.001",
            "abstract": f"A comprehensive review of recent advances related to {topic} in the field of electron microscopy.",
            "url": f"https://doi.org/10.1000/example.{topic.lower().replace(' ', '')}.001",
            "citation_count": random.randint(20, 200),
            "topic": topic
        } for _ in range(3)
    ]


def generate_citation_graph(literature_items):
    """
    Generate citation relationship data for the nebula visualization.
    Takes a list of LiteratureItem db objects and returns nodes/edges.
    """
    nodes = []
    edges = []

    for item in literature_items:
        nodes.append({
            "id": item.id,
            "label": item.title[:50] + "..." if len(item.title) > 50 else item.title,
            "title": item.title,
            "authors": item.authors,
            "year": item.year,
            "journal": item.journal,
            "citation_count": item.citation_count or 0,
            "topic": item.topic,
        })

    # Generate citation links using sample data + inferred relationships
    from models import CitationLink
    # Use real citation links if available
    for link in CitationLink.query.filter(
        CitationLink.source_id.in_([i.id for i in literature_items])
    ).all():
        edges.append({
            "source": link.source_id,
            "target": link.target_id,
            "weight": link.weight or 1.0,
        })

    # If no real links, infer based on shared topics and keywords
    if not edges and len(nodes) > 1:
        for i in range(len(nodes)):
            for j in range(i + 1, len(nodes)):
                if nodes[i]["topic"] == nodes[j]["topic"]:
                    edges.append({
                        "source": nodes[i]["id"],
                        "target": nodes[j]["id"],
                        "weight": 0.5,
                    })

    return {"nodes": nodes, "edges": edges}


def run_weekly_fetch():
    """
    Called by scheduler every Monday 9:00 AM.
    Fetches literature for all active subscriptions and stores results.
    """
    from app import create_app
    from models import db, LiteratureSubscription, LiteratureItem

    app = create_app()
    with app.app_context():
        subs = LiteratureSubscription.query.filter_by(active=True).all()
        for sub in subs:
            results = fetch_literature_for_topic(sub.topic, sub.keywords)
            for paper in results:
                existing = LiteratureItem.query.filter_by(doi=paper.get("doi")).first()
                if not existing:
                    item = LiteratureItem(
                        title=paper.get("title", ""),
                        authors=paper.get("authors", ""),
                        journal=paper.get("journal", ""),
                        year=paper.get("year"),
                        doi=paper.get("doi", ""),
                        abstract=paper.get("abstract", ""),
                        url=paper.get("url", ""),
                        topic=sub.topic,
                        citation_count=paper.get("citation_count", 0),
                    )
                    db.session.add(item)
        db.session.commit()

    # Send emails to users
    try:
        from email_service import send_weekly_literature
        send_weekly_literature()
    except Exception:
        pass

    print(f"[Agent] Weekly literature fetch completed at {datetime.now(timezone.utc)}")
    return True



def enrich_literature(title="", doi="", url=""):
    """
    Simulate Agent enriching literature metadata from a title/doi/url.
    In production, this would call CrossRef API, Semantic Scholar, or the school Agent platform.
    """
    import random
    # Simulated Agent response
    sample_data = {
        "title": title or "AI-Generated Literature Entry",
        "authors": "Generated by EM Course Agent",
        "journal": random.choice(["Ultramicroscopy", "Nature Materials", "Science", "Advanced Materials", "ACS Nano"]),
        "year": 2025,
        "doi": doi or f"10.1000/agent.{random.randint(10000, 99999)}",
        "abstract": f"Agent-enriched abstract for: {title or 'untitled paper'}. This paper discusses recent advances in electron microscopy techniques and their applications.",
        "url": url or f"https://doi.org/10.1000/agent.{random.randint(10000, 99999)}",
        "citation_count": random.randint(5, 300),
    }
    return sample_data
