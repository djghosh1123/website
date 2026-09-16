#!/usr/bin/env python3
import html
import json
import os
import re
import sys
import unicodedata
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

AUTHOR_ID = "AAVtmXkAAAAJ"
PUBLICATIONS_FILE = Path("publications.html")
SERPAPI_ENDPOINT = "https://serpapi.com/search"

STYLE = """\n    .citation-count{display:inline-block;margin-left:.45rem;padding:.12rem .44rem;border:1px solid #eadfce;border-radius:999px;background:#fffaf2;color:#7a6548;font-size:.74rem;font-weight:800;line-height:1.35;text-decoration:none;white-space:nowrap;vertical-align:.08rem;}\n    .citation-count:hover{background:#fff4e3;color:#6a5337;}\n"""


def normalize_title(value: str) -> str:
    value = html.unescape(re.sub(r"<[^>]+>", " ", value))
    value = unicodedata.normalize("NFKD", value)
    value = value.encode("ascii", "ignore").decode("ascii").lower()
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return " ".join(value.split())


def get_scholar_articles(api_key: str):
    params = {
        "engine": "google_scholar_author",
        "author_id": AUTHOR_ID,
        "hl": "en",
        "num": 100,
        "sort": "pubdate",
        "api_key": api_key,
    }
    url = SERPAPI_ENDPOINT + "?" + urllib.parse.urlencode(params)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=60) as response:
        payload = json.load(response)
    if payload.get("error"):
        raise RuntimeError(payload["error"])
    return payload.get("articles", [])


def build_lookup(articles):
    lookup = {}
    for article in articles:
        title = article.get("title", "").strip()
        if not title:
            continue
        cited_by = article.get("cited_by") or {}
        lookup[normalize_title(title)] = {
            "title": title,
            "citations": int(cited_by.get("value", 0) or 0),
            "link": cited_by.get("link") or article.get("link") or "",
        }
    return lookup


def best_match(site_title: str, lookup):
    key = normalize_title(site_title)
    if key in lookup:
        return lookup[key]

    best_key = None
    best_score = 0.0
    second_score = 0.0
    for candidate in lookup:
        score = SequenceMatcher(None, key, candidate).ratio()
        if score > best_score:
            second_score = best_score
            best_score = score
            best_key = candidate
        elif score > second_score:
            second_score = score

    if best_key and best_score >= 0.93 and (best_score - second_score) >= 0.03:
        return lookup[best_key]
    return None


def remove_old_badges(text: str) -> str:
    return re.sub(
        r"\s*<(?:a|span) class=\"citation-count\"[^>]*>.*?</(?:a|span)>",
        "",
        text,
        flags=re.IGNORECASE | re.DOTALL,
    )


def add_style(text: str) -> str:
    if ".citation-count{" in text:
        return text
    marker = "  </style>"
    if marker not in text:
        raise RuntimeError("Could not find the inline </style> block in publications.html")
    return text.replace(marker, STYLE + marker, 1)


def enforce_publication_status(text: str) -> str:
    """Keep the Network-aware IV manuscript in Working papers without journal-status text."""
    title_html = (
        'Pal, S. &amp; <strong>Ghosh, D.</strong> '
        '<em><a href="https://arxiv.org/abs/2604.24969">Network-aware IV Regression for Causal Node Discovery and Estimation.</a></em>'
    )

    text = re.sub(
        r'\s*<li>Pal, S\. &amp; <strong>Ghosh, D\.</strong>\s*'
        r'<em><a href="https://arxiv\.org/abs/2604\.24969">Network-aware IV Regression for Causal Node Discovery and Estimation\.</a></em>'
        r'(?:\s*<(?:a|span) class="citation-count"[^>]*>.*?</(?:a|span)>)?'
        r'.*?</li>',
        '',
        text,
        count=1,
        flags=re.DOTALL,
    )

    working_entry = f'      <li>{title_html}</li>\n'
    if working_entry.strip() not in text:
        marker = (
            '      <li>† Shahid, I., Luo, S. &amp; <strong>Ghosh, D.</strong> '
            '<em>Longitudinal Rank-Sum Testing for incomplete clinical trials.</em></li>\n'
        )
        if marker in text:
            text = text.replace(marker, marker + working_entry, 1)
        else:
            raise RuntimeError("Could not locate Working papers insertion point")

    text = re.sub(
        r'(<section class="pub-section pub-section-review">.*?<span class="pub-count">)\d+(</span>)',
        r'\g<1>5\2',
        text,
        count=1,
        flags=re.DOTALL,
    )
    text = re.sub(
        r'(<section class="pub-section pub-section-working">.*?<span class="pub-count">)\d+(</span>)',
        r'\g<1>11\2',
        text,
        count=1,
        flags=re.DOTALL,
    )
    return text


def add_quadratic_prediction_summary(text: str) -> str:
    old = '      <li>McElroy, T. S., <strong>Ghosh, D.</strong> &amp; Lahiri, S. <em><a href="https://link.springer.com/article/10.1007/s13171-023-00326-6">Quadratic Prediction of Time Series via Auto-Cumulants.</a></em> Sankhya A 86, 431–463 (2024).</li>'
    new = '''      <li class="pub-expandable"><details><summary>McElroy, T. S., <strong>Ghosh, D.</strong> &amp; Lahiri, S. <em>Quadratic Prediction of Time Series via Auto-Cumulants.</em> Sankhya A 86, 431–463 (2024).</summary><div class="pub-expand-body">
        <p><strong>Summary.</strong> This paper develops a general nonlinear forecasting framework based on quadratic predictors for stationary time series. The predictor extends the classical linear Yule–Walker equations by incorporating second-, third-, and fourth-order auto-cumulants, allowing nonlinear and non-Gaussian dependence to contribute directly to prediction.</p>
        <p>The theory characterizes when a process is <em>second-order forecastable</em>—that is, when quadratic prediction can improve on the best linear forecast—and connects that condition to spectral and bispectral structure. Numerical studies show substantial prediction gains in nonlinear settings, while applications to U.S. unemployment and Wolfer sunspot data reduce mean-squared prediction error by 16.5% and 29.2%, respectively.</p>
        <div class="pub-tags"><span class="pub-tag">Nonlinear time series</span><span class="pub-tag">Quadratic prediction</span><span class="pub-tag">Auto-cumulants</span><span class="pub-tag">Polyspectra</span><span class="pub-tag">Yule–Walker equations</span><span class="pub-tag">Forecasting</span></div>
        <a class="pub-open-link" href="https://link.springer.com/article/10.1007/s13171-023-00326-6">Read the article →</a>
      </div></details></li>'''
    return text.replace(old, new, 1)


def enforce_news_navigation():
    """Rename the site navigation item from Blog to News and point it to /news/."""
    old = '<a href="/blog/index.html">Blog</a>'
    new = '<a href="/news/index.html">News</a>'
    changed = 0
    for path in Path('.').rglob('*.html'):
        if '.git' in path.parts:
            continue
        text = path.read_text(encoding='utf-8')
        updated = text.replace(old, new)
        if updated != text:
            path.write_text(updated, encoding='utf-8')
            changed += 1
    return changed


def update_html(text: str, lookup):
    text = remove_old_badges(text)
    text = enforce_publication_status(text)
    text = add_quadratic_prediction_summary(text)
    text = add_style(text)
    matched = 0
    unmatched = []

    pattern = re.compile(r"(<em>)(.*?)(</em>)", re.IGNORECASE | re.DOTALL)

    def repl(match):
        nonlocal matched
        inner = match.group(2)
        site_title = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        article = best_match(site_title, lookup)
        if not article:
            if len(site_title) > 18:
                unmatched.append(site_title)
            return match.group(0)

        matched += 1
        count = article["citations"]
        label = f"Cited by {count}"
        tooltip = "Google Scholar citations; refreshed daily"
        if article["link"]:
            badge = (
                f'<a class="citation-count" href="{html.escape(article["link"], quote=True)}" '
                f'target="_blank" rel="noopener" title="{tooltip}">{label}</a>'
            )
        else:
            badge = f'<span class="citation-count" title="{tooltip}">{label}</span>'
        return match.group(0) + badge

    text = pattern.sub(repl, text)
    return text, matched, unmatched


def main():
    api_key = os.environ.get("SERPAPI_KEY")
    if not api_key:
        print("SERPAPI_KEY is not set", file=sys.stderr)
        sys.exit(1)
    if not PUBLICATIONS_FILE.exists():
        print(f"{PUBLICATIONS_FILE} not found", file=sys.stderr)
        sys.exit(1)

    articles = get_scholar_articles(api_key)
    if not articles:
        raise RuntimeError("SerpApi returned no Google Scholar articles")

    lookup = build_lookup(articles)
    original = PUBLICATIONS_FILE.read_text(encoding="utf-8")
    updated, matched, unmatched = update_html(original, lookup)
    PUBLICATIONS_FILE.write_text(updated, encoding="utf-8")
    nav_changed = enforce_news_navigation()

    print(f"Scholar articles returned: {len(articles)}")
    print(f"Website publications matched: {matched}")
    print(f"HTML files updated for News navigation: {nav_changed}")
    if unmatched:
        print("Unmatched website titles (no badge added):")
        for title in sorted(set(unmatched)):
            print(f"  - {title}")


if __name__ == "__main__":
    main()