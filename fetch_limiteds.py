# fetch_limiteds.py

import requests
import json
import datetime
import os
import re

API_URL    = "https://www.rolimons.com/itemapi/itemdetails"
KNOWN_FILE = "known_ids.json"
POSTS_DIR  = "_posts"

print("🛠️ Starting fetch_limiteds.py")

# 1) Fetch the full list of limiteds
resp = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
resp.raise_for_status()
payload = resp.json()

items = payload.get("items", {})
print(f"→ Fetched {len(items)} limiteds from itemdetails API")

# 2) Load the set of IDs we've already posted
if os.path.exists(KNOWN_FILE):
    with open(KNOWN_FILE, "r") as f:
        known_ids = set(json.load(f))
else:
    known_ids = set()

# 3) Determine which IDs are new
current_ids = set(items.keys())
new_ids     = current_ids - known_ids
print(f"→ Found {len(new_ids)} new limited(s)")

# 4) Ensure the posts directory exists
os.makedirs(POSTS_DIR, exist_ok=True)

# 5) Write a Markdown file for each new limited
for item_id in sorted(new_ids, key=int):
    # items[item_id] is [name, acronym, rap, value, default, demand, trend, projected, hyped, rare]
    name, acronym, rap, value, default, demand, trend, projected, hyped, rare = items[item_id]

    # Use today's date (no precise releaseTime available here)
    date = datetime.datetime.utcnow().date().isoformat()

    # Sanitize and slugify the name: lowercase, hyphens for spaces, strip invalid chars
    slug = re.sub(r'\s+', '-', name.strip().lower())
    slug = re.sub(r'[^a-z0-9\-]', '', slug)

    filename = f"{date}-{slug}.md"
    path = os.path.join(POSTS_DIR, filename)

    if os.path.exists(path):
        print(f"– Skipping existing post: {filename}")
        continue

    # Sanitize title for YAML: escape single quotes
    safe_name = name.replace("'", "''")
    title_line = f"title: '{safe_name}'"

    print(f"+ Writing post for ID {item_id}: {name}")
    front = f"""---
{title_line}
date: {date}T00:00:00Z
---
- **RAP**: {rap}
- **Value**: {value}
- **Demand level**: {demand}
- **Trend**: {trend}
- **Projected?**: {bool(projected)}
- **Hyped?**: {bool(hyped)}
- **Rare?**: {bool(rare)}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(front)

# 6) Update known_ids.json so we won't repost these next time
with open(KNOWN_FILE, "w", encoding="utf-8") as f:
    json.dump(list(current_ids), f, indent=2)

print("✅ Done.")
