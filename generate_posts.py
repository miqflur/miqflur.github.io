# generate_posts.py

from roblox_limited_items import get_recent_limited_items
import os, datetime, re, json

POSTS_DIR = "_posts"
NUM_ITEMS = 50     # or however many you want per week
DAYS_BACK = 7

def slugify(name: str) -> str:
    s = re.sub(r"\s+", "-", name.strip().lower())
    return re.sub(r"[^a-z0-9\-]", "", s)

def main():
    # 1) Fetch the recent limiteds
    items = get_recent_limited_items(num_items=NUM_ITEMS,
                                     timezone_str="UTC")
    
    # 2) Ensure posts folder exists and is clean
    if not os.path.isdir(POSTS_DIR):
        os.makedirs(POSTS_DIR)
    for fn in os.listdir(POSTS_DIR):
        if fn != ".gitkeep":
            os.remove(os.path.join(POSTS_DIR, fn))
    
    # 3) Only keep those created in the last DAYS_BACK days
    cutoff = datetime.datetime.utcnow() - datetime.timedelta(days=DAYS_BACK)
    
    for it in items:
        created = datetime.datetime.fromisoformat(it["created"].replace("Z","+00:00"))
        if created < cutoff:
            continue
        
        date_str = created.date().isoformat()
        slug     = slugify(it["name"])
        fname    = f"{date_str}-{slug}.md"
        path     = os.path.join(POSTS_DIR, fname)
        
        front = f"""---
title: '{it["name"].replace("'", "''")}'
date: {date_str}T00:00:00Z
---
- **Price**: {it["price"]} Robux
- **Remaining**: {it["remaining"]}
"""
        with open(path, "w", encoding="utf-8") as f:
            f.write(front)
    print(f"✅ Generated posts for items since {cutoff.date()}")
    
if __name__ == "__main__":
    main()
