#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch admin login page and Swagger docs"""
import sys, urllib.request, urllib.error, ssl, json

def p(s=""): print(s); sys.stdout.flush()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url, timeout=10):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, r.read().decode("utf-8", "replace")

p("=" * 70)
p("  Fetching admin panel & Swagger details")
p("=" * 70)

# 1. Login page on wxmini.api.bjadks.com
p("\n[1] wxmini.api.bjadks.com login page:")
try:
    st, body = fetch("https://wxmini.api.bjadks.com/")
    p("  HTTP %d, length=%d" % (st, len(body)))
    # Extract key parts of the HTML
    p("  --- HTML content ---")
    p(body[:3000])
except Exception as e:
    p("  Error: %s" % e)

# 2. Swagger on base2.api.bjadks.com
p("\n[2] base2.api.bjadks.com Swagger API docs:")
try:
    st, body = fetch("https://base2.api.bjadks.com/swagger/index.html")
    p("  HTTP %d, length=%d" % (st, len(body)))
    p("  First 1000 chars:")
    p(body[:1000])
except Exception as e:
    p("  Error: %s" % e)

# 3. Try to get swagger.json for full API listing
p("\n[3] Trying swagger.json / swagger/v1/swagger.json:")
swagger_urls = [
    "https://base2.api.bjadks.com/swagger/v1/swagger.json",
    "https://base2.api.bjadks.com/swagger/swagger.json",
    "https://base2.api.bjadks.com/swagger/v2/swagger.json",
    "https://base2.api.bjadks.com/swagger/doc.json",
    "https://base2.api.bjadks.com/swagger/v1",
    "https://wxmini.api.bjadks.com/swagger/v1/swagger.json",
    "https://wxmini.api.bjadks.com/swagger/swagger.json",
    "https://wxmini.api.bjadks.com/swagger/index.html",
]
for url in swagger_urls:
    try:
        st, body = fetch(url)
        p("  %-60s HTTP %d len=%d" % (url, st, len(body)))
        if len(body) > 100:
            # Check if it's JSON
            try:
                data = json.loads(body)
                if isinstance(data, dict):
                    p("    JSON keys: %s" % list(data.keys())[:10])
                    if "paths" in data:
                        paths = list(data["paths"].keys())
                        p("    API paths: %d" % len(paths))
                        for path in paths[:30]:
                            p("      %s" % path)
                    if "info" in data:
                        p("    Info: %s" % json.dumps(data["info"], ensure_ascii=False)[:200])
            except:
                p("    Snippet: %s" % body[:200])
    except Exception as e:
        p("  %-60s Error: %s" % (url, str(e)[:80]))

# 4. Check test and demo sites
p("\n[4] Other discovered sites:")
other_sites = [
    "https://test.bjadks.com/",
    "https://demo.bjadks.com/",
    "https://app.bjadks.com/",
    "https://base.bjadks.com/",
    "https://login.bjadks.com/",
]
for url in other_sites:
    try:
        st, body = fetch(url)
        # Extract title
        title = ""
        if "<title>" in body.lower():
            idx = body.lower().index("<title>")
            end = body.lower().index("</title>", idx)
            title = body[idx+7:end].strip()
        p("  %-40s HTTP %d | title: %s" % (url, st, title))
    except Exception as e:
        p("  %-40s Error: %s" % (url, str(e)[:80]))

p("\n" + "=" * 70)
