#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Probe for backend admin panel on bjadks.com infrastructure"""
import sys, json, urllib.request, urllib.error, urllib.parse, ssl, socket

def p(s=""): print(s); sys.stdout.flush()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def probe_url(url, timeout=6):
    """Try to fetch a URL, return (status_code, content_type, snippet)"""
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }, method="GET")
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
            ct = r.headers.get("Content-Type", "")
            body = r.read(2048).decode("utf-8", "replace")
            return r.status, ct, body[:300]
    except urllib.error.HTTPError as e:
        try:
            body = e.read(1024).decode("utf-8", "replace")
            return e.code, e.headers.get("Content-Type", ""), body[:200]
        except:
            return e.code, "", ""
    except Exception as ex:
        return 0, "", str(ex)[:100]

def probe_subdomain(sub, domain="bjadks.com"):
    """Check if a subdomain resolves and responds to HTTP(S)"""
    host = "%s.%s" % (sub, domain)
    try:
        ip = socket.getaddrinfo(host, 443, socket.AF_INET)[0][4][0]
    except:
        return None
    # Try HTTPS
    url = "https://%s/" % host
    st, ct, body = probe_url(url)
    if st > 0:
        return {"host": host, "ip": ip, "status": st, "ct": ct, "body": body[:150]}
    # Try HTTP
    url2 = "http://%s/" % host
    st2, ct2, body2 = probe_url(url2)
    if st2 > 0:
        return {"host": host, "ip": ip, "status": st2, "ct": ct2, "body": body2[:150]}
    return {"host": host, "ip": ip, "status": 0, "ct": "", "body": "DNS resolves but no HTTP response"}

p("=" * 70)
p("  Backend admin panel discovery")
p("=" * 70)

# 1. Known infrastructure
p("\n[1] Known bjadks.com infrastructure:")
known = [
    ("wxmini.api.bjadks.com", "Production API"),
    ("wxmini7.api.bjadks.com", "Dev API"),
    ("base2.api.bjadks.com", "Logging API"),
    ("oss.bjadks.com", "Object Storage"),
    ("img.cdn.bjadks.com", "CDN Images"),
]
for host, desc in known:
    try:
        ip = socket.getaddrinfo(host, 443, socket.AF_INET)[0][4][0]
        p("  %-30s -> %s (%s)" % (host, ip, desc))
    except:
        p("  %-30s -> DNS FAIL (%s)" % (host, desc))

# 2. Subdomain brute-force (common admin-related)
p("\n[2] Subdomain enumeration (admin-related):")
subdomains = [
    "admin", "manage", "management", "console", "cms", "panel",
    "dashboard", "backend", "web", "www", "api", "wxmini.api",
    "oa", "system", "sys", "portal", "app", "mobile", "h5",
    "mini", "wechat", "wx", "test", "dev", "uat", "staging",
    "demo", "preview", "static", "file", "upload", "download",
    "login", "auth", "sso", "cas", "user", "account",
    "data", "report", "stat", "analytics", "monitor",
    "miniapp", "miniadmin", "wxadmin", "actadmin",
    "adks", "adksadmin", "loveadi", "adi",
    "base", "base2", "base1", "wxmini1", "wxmini2",
]

found_hosts = []
for sub in subdomains:
    result = probe_subdomain(sub)
    if result:
        status_info = ""
        if result["status"] > 0:
            # Check if it looks like an admin panel
            body_lower = result["body"].lower()
            is_admin = any(kw in body_lower for kw in ["login", "admin", "manage", "password", "username", "console", "dashboard"])
            status_info = "HTTP %d | %s" % (result["status"], ">>> ADMIN PANEL?" if is_admin else result["ct"][:40])
        else:
            status_info = "DNS only (no HTTP)"
        p("  %-30s -> %-16s %s" % (result["host"], result["ip"], status_info))
        found_hosts.append(result)

# 3. Path probing on known API host
p("\n[3] Common admin paths on wxmini.api.bjadks.com:")
admin_paths = [
    "/", "/index.html", "/admin", "/admin/", "/admin/index",
    "/admin/login", "/manage", "/manage/", "/login", "/login/",
    "/swagger", "/swagger/index.html", "/swagger/ui",
    "/api-docs", "/docs", "/help", "/api",
    "/api/v1", "/api/v2", "/api/admin",
    "/Hangfire", "/elmah", "/trace",
    "/.well-known/openid-configuration",
    "/actuator", "/actuator/health", "/actuator/info",
    "/health", "/healthcheck", "/status",
    "/signalr/hubs", "/hub",
    "/Admin", "/Admin/Login", "/Manage", "/Login",
    "/Home", "/Home/Index", "/Account/Login",
    "/Identity/Account/Login", "/api/Account",
]

for path in admin_paths:
    url = "https://wxmini.api.bjadks.com" + path
    st, ct, body = probe_url(url)
    if st != 404 and st != 0:
        snippet = body[:80].replace("\n", " ").replace("\r", "")
        p("  %-50s HTTP %-4d %s" % (path, st, snippet))

# 4. Try the same paths on base2.api.bjadks.com
p("\n[4] Common admin paths on base2.api.bjadks.com:")
for path in admin_paths[:20]:
    url = "https://base2.api.bjadks.com" + path
    st, ct, body = probe_url(url)
    if st != 404 and st != 0:
        snippet = body[:80].replace("\n", " ").replace("\r", "")
        p("  %-50s HTTP %-4d %s" % (path, st, snippet))

p("\n" + "=" * 70)
p("  Discovery complete")
p("=" * 70)
