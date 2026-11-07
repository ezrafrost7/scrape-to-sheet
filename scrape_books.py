"""Demo for Gig A: scrape a public site into CSV / Excel / Google Sheets.

Target: books.toscrape.com, a sandbox built specifically for scraping practice
(no robots.txt restrictions, no personal data).

    python scrape_books.py                     # CSV + XLSX into ./output
    python scrape_books.py --pages 3           # quick run
    python scrape_books.py --sheet-id ID --key path/to/service_account.json
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE = "https://books.toscrape.com/catalogue/"
RATINGS = {"One": 1, "Two": 2, "Three": 3, "Four": 4, "Five": 5}
USER_AGENT = "demo-scraper/1.0 (portfolio demo; polite: 1 request/sec)"
FIELDS = ["title", "price_gbp", "rating", "in_stock", "category", "upc", "url"]


def parse_list_page(html: str, page_url: str) -> tuple[list[str], str | None]:
    soup = BeautifulSoup(html, "html.parser")
    links = [urljoin(page_url, a["href"]) for a in soup.select("article.product_pod h3 a")]
    nxt = soup.select_one("li.next a")
    return links, (urljoin(page_url, nxt["href"]) if nxt else None)


def parse_book(html: str, url: str) -> dict:
    soup = BeautifulSoup(html, "html.parser")
    table = {th.get_text(strip=True): td.get_text(strip=True)
             for th, td in zip(soup.select("table.table th"), soup.select("table.table td"))}
    rating_cls = soup.select_one("p.star-rating")["class"]
    crumbs = soup.select("ul.breadcrumb li a")
    return {
        "title": soup.select_one("div.product_main h1").get_text(strip=True),
        "price_gbp": float(re.search(r"\d+(?:\.\d+)?", soup.select_one("p.price_color").get_text()).group()),
        "rating": next((RATINGS[c] for c in rating_cls if c in RATINGS), None),
        "in_stock": int("".join(ch for ch in table.get("Availability", "") if ch.isdigit()) or 0),
        "category": crumbs[-1].get_text(strip=True) if crumbs else "",
        "upc": table.get("UPC", ""),
        "url": url,
    }


def get(client: httpx.Client, url: str, attempts: int = 3) -> httpx.Response:
    """GET with up to 2 retries on 5xx/network errors, so one bad page doesn't kill a long run."""
    for i in range(attempts):
        try:
            r = client.get(url)
            if r.status_code < 500:
                r.raise_for_status()
                r.encoding = "utf-8"  # the site serves UTF-8; don't let charset guessing mangle the pound sign
                return r
        except (httpx.TransportError,) as e:
            if i == attempts - 1:
                raise
        if i < attempts - 1:
            time.sleep(2 ** (i + 1))
    r.raise_for_status()
    return r


def scrape(max_pages: int, delay: float = 1.0) -> list[dict]:
    books: list[dict] = []
    with httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=30, follow_redirects=True) as client:
        page_url: str | None = urljoin(BASE, "page-1.html")
        pages = 0
        while page_url and pages < max_pages:
            r = get(client, page_url)
            links, page_url = parse_list_page(r.text, str(r.url))
            pages += 1
            for link in links:
                time.sleep(delay)
                br = get(client, link)
                books.append(parse_book(br.text, link))
            print(f"page {pages}: {len(books)} books so far", file=sys.stderr)
            time.sleep(delay)
    return books


def dedupe(books: list[dict]) -> list[dict]:
    seen, out = set(), []
    for b in books:
        if b["upc"] not in seen:
            seen.add(b["upc"])
            out.append(b)
    return out


def write_outputs(books: list[dict], outdir: Path) -> None:
    outdir.mkdir(parents=True, exist_ok=True)
    with open(outdir / "books.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        w.writeheader()
        w.writerows(books)
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    ws.title = "books"
    ws.append(FIELDS)
    for b in books:
        ws.append([b[k] for k in FIELDS])
    ws.freeze_panes = "A2"
    wb.save(outdir / "books.xlsx")


def push_to_sheet(books: list[dict], sheet_id: str, key_path: str) -> None:
    import gspread

    gc = gspread.service_account(filename=key_path)
    ws = gc.open_by_key(sheet_id).sheet1
    ws.clear()
    ws.update([FIELDS] + [[b[k] for k in FIELDS] for b in books], "A1", value_input_option="RAW")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--pages", type=int, default=50)
    ap.add_argument("--delay", type=float, default=1.0, help="seconds between requests (be polite)")
    ap.add_argument("--out", default="output")
    ap.add_argument("--sheet-id")
    ap.add_argument("--key", help="path to a service-account JSON key (keep it outside the repo)")
    args = ap.parse_args()

    books = dedupe(scrape(args.pages, args.delay))
    write_outputs(books, Path(args.out))
    summary = {"rows": len(books), "columns": len(FIELDS),
               "avg_price_gbp": round(sum(b["price_gbp"] for b in books) / max(len(books), 1), 2)}
    if args.sheet_id:
        if not args.key:
            sys.exit("--key is required with --sheet-id")
        push_to_sheet(books, args.sheet_id, args.key)
        summary["sheet"] = f"https://docs.google.com/spreadsheets/d/{args.sheet_id}"
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
