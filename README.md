# Demo: public website to Google Sheet / CSV / Excel

Scrapes all 1,000 books from [books.toscrape.com](https://books.toscrape.com), a sandbox built for scraping practice, into a clean table: title, price, rating (1-5), stock count, category, UPC, URL.

```bash
pip install httpx beautifulsoup4 openpyxl gspread
python scrape_books.py --pages 3            # quick test: 60 books -> output/books.csv + books.xlsx
python scrape_books.py                      # all 50 pages (~18 min at the polite 1 request/sec)
python scrape_books.py --sheet-id <ID> --key <service_account.json>   # also push to Google Sheets
```

What it shows clients:
- **Polite and legal by default:** about 1 request per second, an identifying user agent, public pages only.
- **Clean, typed data:** prices as numbers, ratings as 1-5, stock as an integer, deduplicated by UPC.
- **Three output formats:** CSV (opens cleanly in Excel), XLSX with a frozen header, or straight into a Google Sheet.

---

MIT licensed. Built with AI assistance (Claude Code) and reviewed by a human.
