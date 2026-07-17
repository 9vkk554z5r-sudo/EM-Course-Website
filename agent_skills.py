import sys, json
try: sys.stdout.reconfigure(encoding='utf-8')
except: pass
from datetime import datetime, timezone

from openalex_client import (search_works, get_work_by_doi, extract_work_info, extract_key_points, works_to_citation_graph, citation_graph, recent_works_by_topic)


def log_activity(db, user_id, skill, action, input_data='', output_data='', status='success'):
    from models import AgentLog
    log = AgentLog(user_id=user_id, skill=skill, action=action, input_data=str(input_data)[:500], output_data=str(output_data)[:500], status=status)
    db.session.add(log)
    db.session.commit()


def skill_literature_info(db, user_id, query, query_type='title'):
    try:
        works = []
        if query_type == 'doi':
            w = get_work_by_doi(query)
            if w: works = [w]
        else:
            works = search_works(query, 3)
        if not works:
            log_activity(db, user_id, 'lit_info', f'Search: {query}', status='not_found')
            return {'found': False, 'message': 'No results'}, False
        results = []
        for w in works[:3]:
            info = extract_work_info(w)
            points = extract_key_points(info)
            results.append({'info': info, 'key_points': points})
        log_activity(db, user_id, 'lit_info', f'Search: {query}', f'Found {len(results)}')
        return {'found': True, 'results': results}, True
    except Exception as e:
        log_activity(db, user_id, 'lit_info', f'Search: {query}', status='error')
        return {'found': False, 'error': str(e)}, False


def skill_literature_subscription(db, user_id, keyword, days=7):
    try:
        works = recent_works_by_topic(keyword, days=days, per_page=10)
        results = []
        for w in works:
            info = extract_work_info(w)
            results.append({'title': info.get('title', ''), 'authors': info.get('first_author', ''), 'journal': info.get('journal', ''), 'date': info.get('publication_date', ''), 'doi': info.get('doi', '')})
    except Exception as e:
        log_activity(db, user_id, 'subscription', f'Keyword: {keyword}', status='error')
        return {'error': str(e)}, False


def skill_citation_network(db, user_id, query, query_type='keyword'):
    try:
        graph = citation_graph(query, query_type=query_type, max_nodes=35)
        if not graph.get('nodes'):
            log_activity(db, user_id, 'citation', f'Query: {query}', status='not_found')
            return {'found': False}, False
        nodes = graph.get('nodes', [])
        edges = graph.get('edges', [])
        hubs = sorted(nodes, key=lambda n: n.get('citation_count', 0), reverse=True)[:5]
        log_activity(db, user_id, 'citation', f'Query: {query}', f'Nodes: {len(nodes)}, Edges: {len(edges)}')
        return {'found': True, 'graph': graph, 'node_count': len(nodes), 'edge_count': len(edges), 'hubs': hubs, 'query': query}, True
    except Exception as e:
        log_activity(db, user_id, 'citation', f'Query: {query}', status='error')
        return {'error': str(e)}, False


def skill_method_summary(db, user_id, query, query_type='doi', save_name=''):
    """Extract experimental methods from OpenAlex, generate flowchart + protocol links."""
    try:
        work = None
        if query_type == 'doi':
            work = get_work_by_doi(query)
        if not work:
            ws2 = search_works(query, 3)
            if ws2: work = ws2[0]
        if not work:
            log_activity(db, user_id, 'method', f'Query: {query}', status='not_found')
            return {'found': False}, False
        info = extract_work_info(work)
        title = info.get('title', '')
        concepts = info.get('concepts', [])
        abstract = info.get('abstract', '')
        topic = info.get('topic', '')
        journal = info.get('journal', '')

        methods = _extract_method_statements(abstract, concepts, title)
        flowchart_steps = _generate_method_flowchart(methods, concepts, title)
        protocol_links = _build_protocol_links(concepts, topic, title)

        if save_name:
            from models import ProtocolCollection
            pc = ProtocolCollection(user_id=user_id, name=save_name, paper_title=title, paper_doi=info.get('doi', query), methods_summary='; '.join(methods), protocol_links=json.dumps(protocol_links), flowchart_steps=json.dumps(flowchart_steps))
            db.session.add(pc)
            db.session.commit()
        log_activity(db, user_id, 'method', f'Paper: {title}', f'Extracted {len(methods)}')
        return {'found': True, 'title': title, 'methods': methods, 'protocol_links': protocol_links, 'flowchart_steps': flowchart_steps, 'saved': bool(save_name)}, True
    except Exception as e:
        log_activity(db, user_id, 'method', f'Query: {query}', status='error')
        return {'error': str(e)}, False



def _extract_method_statements(abstract, concepts, title):
    """Extract method-like statements from abstract + concepts."""
    methods = []
    if abstract:
        import re
        sentences = re.split(r'[.!?]+', abstract)
        method_keywords = ['method', 'technique', 'approach', 'protocol', 'sample', 'specimen',
                           'prepare', 'stain', 'fix', 'section', 'imaging', 'microscop', 'acquisition',
                           'reconstruct', 'segment', 'analyz', 'measure', 'calculat', 'experiment',
                           'embed', 'deposit', 'grow', 'culture', 'treat', 'incubat', 'purif',
                           'extract', 'isolate', 'centrifug', 'buffer', 'fixation', 'label',
                           'methodology', 'pipeline', 'workflow', 'assay', 'synthesis']
        for s in sentences:
            s = s.strip()
            if not s:
                continue
            if any(kw in s.lower() for kw in method_keywords):
                methods.append(s[:150].strip())
                if len(methods) >= 8:
                    break
    if not methods and concepts:
        for c in concepts[:5]:
            methods.append(f'Use {c} methodology')
    if not methods:
        tech_terms = [t for t in ['electron microscopy', 'cryo-EM', 'tomography', 'single particle',
                                   'microtome', 'ultramicrotome', 'negative stain', 'vitreous sectioning']
                       if t in title.lower() or any(t in c.lower() for c in concepts)]
        if tech_terms:
            methods.append(f'Prepare samples using standard {tech_terms[0]} protocols')
            methods.append(f'Acquire data with {tech_terms[0]} instrumentation')
            methods.append('Process and analyze acquired data')
        else:
            methods.append('Review relevant literature and define experimental objectives')
            methods.append('Prepare samples according to standard protocols')
            methods.append('Perform data acquisition using appropriate instrumentation')
            methods.append('Analyze results and draw conclusions')
    return methods


def _generate_method_flowchart(methods, concepts, title):
    """Generate structured flowchart steps from extracted methods."""
    steps = []
    if methods:
        if concepts:
            steps.append(f'Define research scope: {concepts[0]}')
        else:
            steps.append('Define research scope and objectives')
        for m in methods[:5]:
            clean = m.strip().rstrip('.')
            if len(clean) > 80:
                clean = clean[:77] + '...'
            steps.append(clean)
        steps.append('Data analysis and interpretation')
        steps.append('Results validation and documentation')
    else:
        steps = ['Define research scope and objectives',
                 'Design experimental protocol',
                 'Prepare samples and reagents',
                 'Conduct experimental measurements',
                 'Process and analyze data',
                 'Validate results',
                 'Document conclusions']
    return steps


def _build_protocol_links(concepts, topic, title):
    """Build protocol/video links based on concepts and topic."""
    import urllib.parse
    links = []
    seen = set()
    for c in concepts[:4]:
        q = urllib.parse.quote(c)
        url = f'https://www.protocols.io/search?q={q}'
        if url not in seen:
            seen.add(url)
            links.append({'label': f'Protocol: {c}', 'url': url})
    search_terms = concepts[:2] + [topic] if topic else concepts[:3]
    for term in search_terms:
        if term:
            q = urllib.parse.quote(term)
            url = f'https://www.jove.com/search?q={q}'
            if url not in seen:
                seen.add(url)
                links.append({'label': f'JoVE: {term}', 'url': url})
    em_terms = ['electron microscopy sample preparation', 'cryo-EM tutorial']
    for term_em in em_terms:
        q = urllib.parse.quote(term_em)
        url = f'https://www.youtube.com/results?search_query={q}'
        if url not in seen:
            seen.add(url)
            links.append({'label': f'Tutorial: {term_em}', 'url': url})
    if concepts:
        q = urllib.parse.quote(concepts[0])
        url = f'https://cshprotocols.cshlp.org/search?q={q}'
        if url not in seen:
            seen.add(url)
            links.append({'label': f'CSH Protocols: {concepts[0]}', 'url': url})
    if not links:
        links.append({'label': 'Protocols.io Search', 'url': 'https://www.protocols.io/'})
    return links


def skill_presentation_assist(db, user_id, paper_title, paper_doi, template_id=None):
    """AI-assisted presentation: generate PPT design suggestions, Q&A predictions, scoring."""
    try:
        # Find the paper
        work = None
        if paper_doi:
            work = get_work_by_doi(paper_doi)
        if not work and paper_title:
            ws = search_works(paper_title, 1)
            if ws: work = ws[0]
        if not work:
            log_activity(db, user_id, 'presentation', f'Search: {paper_title or paper_doi}', status='not_found')
            return {'found': False, 'message': 'Paper not found'}, False

        info = extract_work_info(work)
        title = info.get('title', 'Unknown')
        authors = info.get('first_author', 'Unknown')
        journal = info.get('journal', 'Unknown')
        year = info.get('publication_date', 'Unknown')[:4] if info.get('publication_date') else 'Unknown'
        doi = info.get('doi', paper_doi or '')
        abstract = info.get('abstract', '')
        key_points = extract_key_points(info)

        # Load template if specified
        template_data = None
        from models import PresentationTemplate
        if template_id:
            t = db.session.get(PresentationTemplate, int(template_id))
            if t:
                import json as _json
                try: template_data = {'id': t.id, 'title': t.title, 'description': t.description, 'criteria': _json.loads(t.criteria) if t.criteria else {}}
                except: template_data = {'id': t.id, 'title': t.title, 'description': t.description, 'criteria': {}}

        # Generate suggestions
        suggestions = [
            f'Slide 1: Title slide — {title}',
            f'Slide 2-3: Background — Research context and motivation for this study',
            f'Slide 4-5: Methods — Key experimental techniques ({key_points[0] if key_points else "EM"})',
            f'Slide 6-8: Results — Main findings and data analysis',
            f'Slide 9: Discussion — Implications and limitations',
            f'Slide 10: Conclusions & Future Work — Summary and next steps',
        ]

        # Q&A predictions
        qa_predictions = [
            {'question': 'What is the main innovation of this study?', 'answer': 'Focus on the novel methodology or discovery presented in the paper.'},
            {'question': 'How reliable are the experimental results?', 'answer': 'Discuss sample size, controls, and reproducibility.'},
            {'question': 'What are the limitations of this study?', 'answer': 'Consider sample size, technical constraints, and scope.'},
            {'question': 'How does this work compare to previous studies?', 'answer': 'Highlight key differences and improvements.'},
            {'question': 'What are the future research directions?', 'answer': 'Suggest follow-up experiments or applications.'},
        ]

        # Scoring criteria
        if template_data and template_data.get('criteria'):
            scoring = template_data['criteria']
        else:
            scoring = [
                {'dimension': 'Content Completeness', 'weight': '30%', 'standard': 'Cover all key points of the paper'},
                {'dimension': 'Logical Clarity', 'weight': '25%', 'standard': 'Clear structure, sound arguments'},
                {'dimension': 'Visual Presentation', 'weight': '20%', 'standard': 'Quality figures, clean layout'},
                {'dimension': 'Time Control', 'weight': '15%', 'standard': '1 slide per ~2 minutes'},
                {'dimension': 'Q&A Quality', 'weight': '10%', 'standard': 'Accurate answers to questions'},
            ]

        log_activity(db, user_id, 'presentation', f'Paper: {title}', f'Generated suggestions')
        return {
            'found': True,
            'info': {'title': title, 'first_author': authors, 'journal': journal, 'publication_date': year, 'doi': doi, 'abstract': abstract},
            'key_points': key_points,
            'suggestions': suggestions,
            'qa_predictions': qa_predictions,
            'scoring': scoring,
            'template': template_data,
            'templates': PresentationTemplate.query.all() if not template_id else None,
        }, True
    except Exception as e:
        log_activity(db, user_id, 'presentation', f'Search: {paper_title or paper_doi}', status='error')
        return {'found': False, 'error': str(e)}, False

