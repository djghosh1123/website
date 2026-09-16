#!/usr/bin/env python3
import datetime as dt
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

NEWS_FILE = Path("data/news.json")
CV_FILE = Path("assets/Dhrubajyoti_Ghosh_CV.pdf")
SERPAPI_ENDPOINT = "https://serpapi.com/search.json"
OPENAI_ENDPOINT = "https://api.openai.com/v1/responses"
MODEL = os.environ.get("NEWS_MODEL", "gpt-5.6-luna")
MAX_NEW_ITEMS = 10

# Never publish private/provisional academic status. Public preprint release is fine,
# but journal submission/review status and pending grant status are not news items.
BLOCKED_STATUS = re.compile(
    r"\b(under review|submitted to|major revision|minor revision|revise and resubmit|"
    r"resubmission|pending review|pending irg|not discussed|rejected|rejection|decision pending|"
    r"grant pending|proposal pending)\b",
    re.I,
)

TRUSTED_HOST_HINTS = (
    "kennesaw.edu", "arxiv.org", "amstat.org", "ieee.org", "springer.com",
    "wiley.com", "onlinelibrary.wiley.com", "sagepub.com", "tandfonline.com",
    "scitepress.org", "dblp.org", "cran.r-project.org", "r-project.org",
    "digitalcommons.kennesaw.edu", "pubmed.ncbi.nlm.nih.gov", "doi.org",
    "projecteuclid.org", "jstor.org", "sciencedirect.com", "elsevier.com",
    "nih.gov", "duke.edu", "wustl.edu", "ncsu.edu", "iisanet.org",
    "enar.org", "icmla-conference.org", "researchgate.net"
)

# Keep the query set broad enough to catch publications, talks, software, student work,
# professional service, awards, media mentions, and institutional announcements while
# staying within a modest SerpApi budget.
SEARCH_QUERIES = [
    '"Dhrubajyoti Ghosh" "Kennesaw State University"',
    '"Dhrubajyoti Ghosh" statistics publication conference invited talk award software',
    '"Dhrubajyoti Ghosh" site:kennesaw.edu',
    '"Dhrubajyoti Ghosh" site:arxiv.org OR site:doi.org OR site:pubmed.ncbi.nlm.nih.gov',
    '"Dhrubajyoti Ghosh" site:ieee.org OR site:springer.com OR site:wiley.com OR site:sciencedirect.com OR site:sagepub.com',
    '"Dhrubajyoti Ghosh" CRAN R package software',
    '"Dhrubajyoti Ghosh" invited session JSM ENAR IISA conference',
    '"Dhrubajyoti Ghosh" student research Kennesaw undergraduate masters phd',
    '"Dhrubajyoti Ghosh" LINDT lab research',
    '"Dhrubajyoti Ghosh" award honor media interview feature'
]


def http_json(url, headers=None, data=None, timeout=75):
    req = urllib.request.Request(url, headers=headers or {}, data=data)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.load(r)


def serp_search(api_key):
    rows = []
    for query in SEARCH_QUERIES:
        params = {
            "engine": "google",
            "q": query,
            "hl": "en",
            "num": 10,
            "api_key": api_key,
        }
        payload = http_json(SERPAPI_ENDPOINT + "?" + urllib.parse.urlencode(params), headers={"User-Agent": "Mozilla/5.0"})
        if payload.get("error"):
            print("SerpApi warning:", payload["error"], file=sys.stderr)
            continue
        for r in payload.get("organic_results", []):
            url = r.get("link") or ""
            title = html.unescape(r.get("title") or "").strip()
            snippet = html.unescape(r.get("snippet") or "").strip()
            date = r.get("date") or ""
            if not url or not title:
                continue
            host = urllib.parse.urlparse(url).netloc.lower()
            trusted = any(h in host for h in TRUSTED_HOST_HINTS)
            exact_identity = "dhrubajyoti ghosh" in (title + " " + snippet).lower()
            if not trusted and not exact_identity:
                continue
            if BLOCKED_STATUS.search(title + " " + snippet):
                continue
            rows.append({"title": title, "snippet": snippet, "url": url, "date_hint": date, "host": host})

    out, seen = [], set()
    for r in rows:
        key = r["url"].split("#")[0].rstrip("/")
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out[:80]


def read_cv_context():
    if not CV_FILE.exists():
        return ""
    try:
        from pypdf import PdfReader
        text = "\n".join((p.extract_text() or "") for p in PdfReader(str(CV_FILE)).pages)
    except Exception as exc:
        print(f"CV parsing warning: {exc}", file=sys.stderr)
        return ""
    safe_lines = []
    for line in text.splitlines():
        if BLOCKED_STATUS.search(line):
            continue
        safe_lines.append(line)
    text = "\n".join(safe_lines)
    return text[:22000]


def existing_fingerprints(news):
    fp = set()
    for item in news.get("items", []):
        fp.add(re.sub(r"[^a-z0-9]+", " ", item.get("title", "").lower()).strip())
        if item.get("source_url"):
            fp.add(item["source_url"].split("#")[0].rstrip("/"))
    return fp


def extract_response_text(payload):
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks = []
    for out in payload.get("output", []):
        for c in out.get("content", []) if isinstance(out, dict) else []:
            if isinstance(c, dict) and isinstance(c.get("text"), str):
                chunks.append(c["text"])
    return "\n".join(chunks)


def ask_llm(api_key, candidates, cv_context, current_items):
    candidate_json = json.dumps(candidates, ensure_ascii=False)
    current_json = json.dumps(current_items, ensure_ascii=False)
    prompt = f"""
You are curating the public News page for Dhrubajyoti Ghosh, Assistant Professor of Data Science and Analytics at Kennesaw State University. His research includes longitudinal/clinical-trial methods, causal inference, nonlinear time series, biomedical imaging, neurodegenerative disease, and data science.

Your job is to identify genuinely newsworthy NEW public updates about this specific researcher. Reject homonyms. Use the CV only as identity/background context and to recognize his collaborators, students, software, papers, talks, and research themes.

Look broadly. Newsworthy items may include:
- newly published or accepted papers and public preprints;
- invited talks, conference presentations, session organization, or professional service;
- undergraduate, master's, or doctoral student research achievements;
- software/package releases or substantial public software updates;
- awards, honors, media coverage, interviews, institutional features, public workshops, or research showcases;
- publicly confirmed funded grants or awards;
- significant public lab or collaboration announcements.

Allowed categories: Publication, Student research, Invited talk, Conference, Software, Award, Lab news, Media, Service, Funding.

STRICT PRIVACY/STATUS RULES:
- Never mention journal submission, under-review status, revision status, peer-review decisions, pending grants, application status, rejected work, or any non-public/private status.
- A public preprint release itself may be news, but do not mention where it has been submitted or its review status.
- Do not infer acceptance, funding, awards, or talks unless a supplied public source explicitly supports it.
- Do not use the CV as evidence for confidential status. It is identity/background context only.
- Every news item MUST be grounded in one supplied candidate URL. Never invent a URL.
- Prefer institutional, publisher, conference, CRAN, arXiv, DOI, DBLP, or professional-society sources.
- Do not repeat an existing news item.
- Keep each summary factual, compact, and suitable for an academic website. No hype and no source-attribution language such as “according to...” or “the source says...”.
- Do not mention the name of the website/source in the summary unless it is intrinsically part of the event itself (for example, “published in Bernoulli” or “presented at JSM”).

Existing news items:
{current_json}

CV/background context (status-sensitive lines have been removed):
{cv_context}

Public web candidates:
{candidate_json}

Return ONLY a JSON array, with at most {MAX_NEW_ITEMS} objects. If nothing clearly qualifies, return []. Each object must have exactly:
{{"date":"YYYY-MM-DD","date_display":"Month YYYY","category":"...","title":"...","summary":"2-3 factual sentences","source_url":"exact candidate URL","source_label":"internal source name","featured":false}}
The source_url and source_label are internal metadata only and are NOT displayed publicly. Use conservative dates. If the exact day is unsupported, use the first day of the supported month and make date_display just Month YYYY. Do not add an item just because a page mentions his name.
"""
    body = json.dumps({
        "model": MODEL,
        "input": prompt,
        "reasoning": {"effort": "low"},
        "max_output_tokens": 4200,
    }).encode("utf-8")
    payload = http_json(
        OPENAI_ENDPOINT,
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        data=body,
        timeout=120,
    )
    text = extract_response_text(payload).strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text, flags=re.I | re.S).strip()
    return json.loads(text)


def validate_items(items, candidates, news):
    candidate_urls = {c["url"]: c for c in candidates}
    existing = existing_fingerprints(news)
    valid = []
    allowed = {"Publication","Student research","Invited talk","Conference","Software","Award","Lab news","Media","Service","Funding"}
    for item in items if isinstance(items, list) else []:
        if not isinstance(item, dict):
            continue
        required = {"date", "date_display", "category", "title", "summary", "source_url", "source_label", "featured"}
        if set(item.keys()) != required:
            continue
        if item["source_url"] not in candidate_urls:
            continue
        combined = f'{item["title"]} {item["summary"]}'
        if BLOCKED_STATUS.search(combined):
            continue
        title_fp = re.sub(r"[^a-z0-9]+", " ", item["title"].lower()).strip()
        url_fp = item["source_url"].split("#")[0].rstrip("/")
        if title_fp in existing or url_fp in existing:
            continue
        if item["category"] not in allowed:
            continue
        if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", item["date"]):
            continue
        item["id"] = re.sub(r"[^a-z0-9]+", "-", title_fp).strip("-")[:80]
        item["featured"] = bool(item["featured"])
        valid.append(item)
        existing.add(title_fp)
        existing.add(url_fp)
        if len(valid) >= MAX_NEW_ITEMS:
            break
    return valid


def main():
    serp_key = os.environ.get("SERPAPI_KEY", "").strip()
    openai_key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not serp_key:
        print("SERPAPI_KEY missing; skipping news update.")
        return 0
    if not openai_key:
        print("OPENAI_API_KEY missing; curated page remains active, but LLM auto-discovery is paused.")
        return 0
    if not NEWS_FILE.exists():
        raise RuntimeError("data/news.json not found")

    news = json.loads(NEWS_FILE.read_text(encoding="utf-8"))
    candidates = serp_search(serp_key)
    print(f"Public source candidates: {len(candidates)}")
    if not candidates:
        return 0

    cv_context = read_cv_context()
    proposed = ask_llm(openai_key, candidates, cv_context, news.get("items", []))
    additions = validate_items(proposed, candidates, news)
    print(f"Validated new news items: {len(additions)}")

    if additions:
        news.setdefault("items", []).extend(additions)
        news["items"].sort(key=lambda x: x.get("date", ""), reverse=True)
    news["last_updated"] = dt.date.today().isoformat()
    NEWS_FILE.write_text(json.dumps(news, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
