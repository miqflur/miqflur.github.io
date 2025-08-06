import requests, json, datetime, os

API_URL    = "https://www.rolimons.com/itemapi/itemdetails"
KNOWN_FILE = "known_ids.json"
POSTS_DIR  = "_posts"

print("🛠️ Starting fetch_limiteds.py")
resp = requests.get(API_URL, headers={"User-Agent":"Mozilla/5.0"})
resp.raise_for_status()
payload = resp.json()

items: dict = payload.get("items", {})
print(f"→ Fetched {len(items)} limiteds from itemdetails API")

# Load the set of IDs we've already posted
if os.path.exists(KNOWN_FILE):
    with open(KNOWN_FILE, "r") as f:
        known_ids = set(json.load(f))
else:
    known_ids = set()

# Figure out which IDs are truly new
current_ids = set(items.keys())
new_ids     = current_ids - known_ids
print(f"→ Found {len(new_ids)} new limited(s)")

# Make sure our posts folder exists
os.makedirs(POSTS_DIR, exist_ok=True)

for item_id in sorted(new_ids):
    name, acronym, rap, value, default, demand, trend, projected, hyped, rare = items[item_id]
    # Use today’s date since we don’t have a releaseTime
    date = datetime.datetime.utcnow().date().isoformat()
    slug = name.replace("/", "-").lower().replace(" ", "-")
    filename = f"{date}-{slug}.md"
    path = os.path.join(POSTS_DIR, filename)

    print(f"+ Writing post for ID {item_id}: {name}")
    front = f"""---
title: "{name}"
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

# Update our known-IDs file
with open(KNOWN_FILE, "w", encoding="utf-8") as f:
    json.dump(list(current_ids), f, indent=2)

print("✅ Done.")
