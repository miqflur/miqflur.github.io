# fetch_limiteds.py

import requests
import json
import datetime
import os
import re

# Use the documented www.rolimons.com host for itemdetails
API_URL    = "https://www.rolimons.com/itemapi/itemdetails"
KNOWN_FILE = "known_ids.json"
POSTS_DIR  = "_posts"
DAYS_BACK  = 7

def slugify(name: str) -> str:
    s = re.sub(r'\s+', '-', name.strip().lower())
    return re.sub(r'[^a-z0-9\-]', '', s)

print("🛠️ Starting fetch_limiteds.py")

# 1) Fetch all item details
resp = requests.get(API_URL, headers={"User-Agent": "Mozilla/5.0"})
resp.raise_for_status()
items = resp.json().get("items", {})
print(f"→ Fetched {len(items)} limiteds")

# 2) Load or initialize known_ids (ID → first_seen_date)
if os.path.exists(KNOWN_FILE):
    with open(KNOWN_FILE, "r", encoding="utf-8") as f:
        known = json.load(f)
        if not isinstance(known, dict):
            known = {}
else:
    known = {}

today_str = datetime.date.today().isoformat()

# 3) Mark any brand-new IDs with today’s date
for item_id in items.keys():
    if item_id not in known:
        known[item_id] = today_str

# 4) Save updated known_ids.json
with open(KNOWN_FILE, "w", encoding="utf-8") as f:
    json.dump(known, f, indent=2)

# 5) Compute cutoff for “this week”
cutoff = datetime.date.today() - datetime.timedelta(days=DAYS_BACK)

# 6) Recreate the posts folder (keep .gitkeep if present)
if os.path.isdir(POSTS_DIR):
    for fn in os.listdir(POSTS_DIR):
        if fn not in (".gitkeep",):
            os.remove(os.path.join(POSTS_DIR, fn))
else:
    os.makedirs(POSTS_DIR, exist_ok=True)

# 7) Generate a post for each ID first seen within the last week
count = 0
for item_id, first_seen in known.items():
    first_date = datetime.date.fromisoformat(first_seen)
    if first_date < cutoff:
        continue

    # unpack the tuple: [name, acronym, rap, value, default, demand, trend, projected, hyped, rare]
    name, _, rap, value, *_ = items[item_id]

    date = first_date.isoformat()
    slug = slugify(name)
    filename = f"{date}-{slug}.md"
    path = os.path.join(POSTS_DIR, filename)

    # sanitize title
    safe_name = name.replace("'", "''")
    title_line = f"title: '{safe_name}'"

    front = f"""---
{title_line}
date: {date}T00:00:00Z
---
- **RAP**: {rap}
- **Value**: {value}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(front)

    count += 1

print(f"✅ Generated {count} post(s) for the last {DAYS_BACK} days.")
