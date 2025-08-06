import requests
import datetime
import os

# 1) fetch data
resp = requests.get("https://api.rolimons.com/itemapi/limited")
data = resp.json().get("data", [])

# 2) sort by newest
newest = sorted(data, key=lambda x: x["releaseTime"], reverse=True)[:5]

# 3) write posts
posts_dir = "_posts"
os.makedirs(posts_dir, exist_ok=True)

for item in newest:
    name = item["name"].replace("/", "-")
    date = datetime.datetime.utcfromtimestamp(item["releaseTime"])
    slug = name.lower().replace(" ", "-")
    filename = f"{date.strftime('%Y-%m-%d')}-{slug}.md"
    path = os.path.join(posts_dir, filename)

    if os.path.exists(path):
        continue  # skip if already there

    front = f"""---
title: "{item['name']}"
date: {date.isoformat()}Z
---
![{item['name']}]({item['thumbnail']})
- RAP: {item['recentAveragePrice']}
- Release: {date.strftime('%b %-d, %Y')}
"""
    with open(path, "w", encoding="utf-8") as f:
        f.write(front)
