# -*- coding: utf-8 -*-
"""OpenAlex API Client"""
import requests, json, os
from datetime import datetime, timedelta, timezone
BASE_URL = "https://api.openalex.org"
_TIMEOUT=30; _MAX_RETRIES=2; _PROXIES={}
for k in ["HTTP_PROXY","http_proxy"]:
    v=os.environ.get(k,""); v and _PROXIES.update({"http":v})
for k in ["HTTPS_PROXY","https_proxy"]:
    v=os.environ.get(k,""); v and _PROXIES.update({"https":v})

def _safe_get(url,**kw):
    for a in range(_MAX_RETRIES+1):
        try:
            kw.setdefault("timeout",_TIMEOUT)
            kw.setdefault("headers",{"User-Agent":"EMCourseAgent/1.0"})
            if _PROXIES: kw["proxies"]=_PROXIES
            r=requests.get(url,**kw)
            if r.status_code==200: return r
        except:
            if a>=_MAX_RETRIES: raise
    return None

def search_works(q, n=10):
    try:
        r=_safe_get(BASE_URL+"/works",params={"search":q,"per_page":min(n,200),"sort":"relevance_score:desc"})
        if r: return r.json().get("results",[])
    except: pass
    return []

def get_work_by_doi(d):
    d=d.replace("https://doi.org/","").replace("http://dx.doi.org/","")
    try:
        r=_safe_get(BASE_URL+"/works/doi:"+d)
        if r: return r.json()
    except: pass
    return None

def extract_work_info(w):
    if not w: return {}
    try:
        au=w.get("authorships",[]) or []
        fa=au[0].get("author",{}).get("display_name","") if au else ""
        ca=""
        for a in au:
            if a.get("is_corresponding"): ca=a.get("author",{}).get("display_name",""); break
        if not ca and au: ca=au[-1].get("author",{}).get("display_name","")
        return {"title":w.get("title") or "","doi":w.get("doi") or "",
            "openalex_id":(w.get("id") or "").split("/")[-1],
            "publication_date":w.get("publication_date") or "",
            "journal":((w.get("primary_location") or {}) or {}).get("source",{}).get("display_name") or "",
            "cited_by_count":w.get("cited_by_count") or 0,
            "first_author":fa,"corresponding_author":ca,
            "concepts":[c.get("display_name","") for c in (w.get("concepts") or [])[:5]],
            "referenced_works":w.get("referenced_works") or []}
    except: return {}

def extract_key_points(i):
    if not i: return []
    p=[]; t=i.get("title",""); cs=i.get("concepts",[]); j=i.get("journal",""); n=i.get("cited_by_count",0)
    if t: p.append("Title: "+t[:100])
    if cs: p.append("Themes: "+", ".join(cs[:3]))
    if j: p.append("Journal: "+j)
    p.append("Cited by: "+str(n))
    return p[:5]

def works_to_citation_graph(ws):
    ns=[]; ids=set()
    for w in (ws or []):
        try:
            i=extract_work_info(w); nid=i.get("openalex_id","")
            if nid and nid not in ids:
                ns.append({"id":nid,"label":(i.get("title") or "")[:50],"title":i.get("title") or "","authors":i.get("first_author") or "","journal":i.get("journal") or "","citation_count":i.get("cited_by_count") or 0,"doi":i.get("doi") or "","openalex_id":nid})
                ids.add(nid)
        except: pass
    return {"nodes":ns,"edges":[]}

def recent_works_by_topic(t, days=7, per_page=20):
    try:
        fd=(datetime.now(timezone.utc)-timedelta(days=days)).strftime("%Y-%m-%d")
        r=_safe_get(BASE_URL+"/works",params={"search":t,"filter":"from_publication_date:"+fd,"per_page":per_page})
        if r: return r.json().get("results",[])
    except: pass
    return []
