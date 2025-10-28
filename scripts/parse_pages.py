#!/usr/bin/env python3
"""Parse downloaded HTML pages into offers.json"""

import json
import re
from pathlib import Path

pages_dir = Path("data/pages")
offers = []
seen_links = set()

for html_file in sorted(pages_dir.glob("*.html")):
    with open(html_file, encoding="utf-8") as f:
        html = f.read()

    # Extract all job-offer links
    links = re.findall(r'job-offer/([^"<>\s]+)', html)

    for link_slug in links:
        full_link = f"https://justjoin.it/job-offer/{link_slug}"

        if full_link in seen_links:
            continue
        seen_links.add(full_link)

        # Extract title from slug (best effort)
        parts = link_slug.rsplit('-', 1)
        title = parts[0].replace('-', ' ').title() if parts else link_slug

        offers.append({
            "link": full_link,
            "title": title,
            "company": None,
            "location": None,
            "salary": None,
            "tags": []
        })

print(f"✓ Parsed {len(offers)} unique offers")

# Save to JSON
output_path = Path("data/offers.json")
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(offers, f, indent=2, ensure_ascii=False)

print(f"✓ Saved to {output_path}")
