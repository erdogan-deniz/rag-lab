"""Download the experiment corpus from English Wikipedia.

Each page is pinned to a revision id, so a later run fetches exactly the same text.
Rendered HTML is saved as is (it keeps tables that the plain-text export drops);
`corpus_text.py` turns it into Markdown with tables.

    python scripts/download_corpus.py            # fetch the latest revisions
    python scripts/download_corpus.py --pinned   # fetch the revisions from corpus/manifest.json
"""

import argparse
import hashlib
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from corpus_text import html_to_markdown

API = "https://en.wikipedia.org/w/api.php"
# Wikimedia asks for a descriptive User-Agent with a way to reach the project.
HEADERS = {"User-Agent": "rag-lab/0.1 (https://github.com/erdogan-deniz/rag-lab; research experiment)"}

TITLES = [
    "2025–26 La Liga",
    "2025–26 FC Barcelona season",
    "2025–26 Real Madrid CF season",
    "2025–26 Atlético Madrid season",
]

ROOT = Path(__file__).resolve().parent.parent
CORPUS = ROOT / "corpus"
MANIFEST = CORPUS / "manifest.json"


def api_get(session: requests.Session, **params) -> dict:
    response = session.get(API, params={"format": "json", "formatversion": 2, **params}, timeout=60)
    response.raise_for_status()
    data = response.json()
    if "error" in data:
        raise RuntimeError(f"Wikipedia API error: {data['error']}")
    return data


def latest_revisions(session: requests.Session) -> dict[str, dict]:
    data = api_get(
        session,
        action="query",
        prop="revisions",
        rvprop="ids|timestamp",
        titles="|".join(TITLES),
        redirects=1,
    )
    found = {}
    for page in data["query"]["pages"]:
        if page.get("missing"):
            raise RuntimeError(f"page not found: {page['title']}")
        revision = page["revisions"][0]
        found[page["title"]] = {
            "pageid": page["pageid"],
            "revid": revision["revid"],
            "revision_timestamp": revision["timestamp"],
        }
    missing = [title for title in TITLES if title not in found]
    if missing:
        raise RuntimeError(f"titles not returned by the API: {missing}")
    return found


def pinned_revisions() -> dict[str, dict]:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    return {page["title"]: page for page in manifest["pages"]}


def slug(title: str) -> str:
    return title.replace("–", "-").replace("é", "e").replace(" ", "_")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--pinned", action="store_true", help="reuse the revisions recorded in corpus/manifest.json")
    args = parser.parse_args()

    (CORPUS / "html").mkdir(parents=True, exist_ok=True)
    (CORPUS / "text").mkdir(parents=True, exist_ok=True)

    session = requests.Session()
    session.headers.update(HEADERS)
    revisions = pinned_revisions() if args.pinned else latest_revisions(session)

    pages = []
    for title in TITLES:
        revid = revisions[title]["revid"]
        data = api_get(
            session,
            action="parse",
            oldid=revid,
            prop="text",
            disableeditsection=1,
            disablelimitreport=1,
            disabletoc=1,
        )
        html = data["parse"]["text"]
        name = slug(title)
        (CORPUS / "html" / f"{name}.html").write_text(html, encoding="utf-8", newline="\n")
        markdown = html_to_markdown(html, title)
        (CORPUS / "text" / f"{name}.md").write_text(markdown, encoding="utf-8", newline="\n")
        pages.append(
            {
                "title": title,
                "pageid": revisions[title]["pageid"],
                "revid": revid,
                "revision_timestamp": revisions[title]["revision_timestamp"],
                "url": f"https://en.wikipedia.org/w/index.php?title={title.replace(' ', '_')}&oldid={revid}",
                "html_sha256": hashlib.sha256(html.encode("utf-8")).hexdigest(),
                "text_chars": len(markdown),
            }
        )
        print(f"{title}: revid {revid}, html {len(html):,} chars, text {len(markdown):,} chars")
        time.sleep(1)  # be polite to the API

    manifest = {
        "license": "CC BY-SA 4.0",
        "source": "https://en.wikipedia.org/",
        "fetched_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pages": pages,
    }
    MANIFEST.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
