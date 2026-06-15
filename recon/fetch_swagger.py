#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fetch the Swagger API spec"""
import sys, urllib.request, ssl, json

def p(s=""): print(s); sys.stdout.flush()

ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE

def fetch(url, timeout=15):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    })
    with urllib.request.urlopen(req, timeout=timeout, context=ctx) as r:
        return r.status, r.read().decode("utf-8", "replace")

# Fetch the actual swagger spec
p("Fetching Swagger spec: /swagger/MisApi/swagger.json")
try:
    st, body = fetch("https://base2.api.bjadks.com/swagger/MisApi/swagger.json")
    p("HTTP %d, length=%d" % (st, len(body)))
    
    try:
        data = json.loads(body)
        p("Keys: %s" % list(data.keys()))
        
        # Info
        if "info" in data:
            p("\nInfo: %s" % json.dumps(data["info"], ensure_ascii=False, indent=2)[:500])
        
        # Servers/host
        for key in ["host", "basePath", "schemes", "servers"]:
            if key in data:
                p("\n%s: %s" % (key, json.dumps(data[key], ensure_ascii=False)[:300]))
        
        # Paths
        if "paths" in data:
            paths = data["paths"]
            p("\nAPI Paths (%d total):" % len(paths))
            for path in sorted(paths.keys()):
                methods = list(paths[path].keys())
                # Get summary/tags
                info = []
                for method in methods:
                    detail = paths[path][method]
                    tags = detail.get("tags", [])
                    summary = detail.get("summary", "")
                    op_id = detail.get("operationId", "")
                    info.append("%s [%s] %s" % (method.upper(), ",".join(tags), summary or op_id))
                p("  %-50s %s" % (path, " | ".join(info)))
        
        # Definitions/schemas
        defs = data.get("definitions", data.get("components", {}).get("schemas", {}))
        if defs:
            p("\nData Models (%d):" % len(defs))
            for name in sorted(defs.keys()):
                props = defs[name].get("properties", {})
                p("  %s: %s" % (name, list(props.keys())[:10]))
        
        # Security definitions
        sec = data.get("securityDefinitions", data.get("security", []))
        if sec:
            p("\nSecurity: %s" % json.dumps(sec, ensure_ascii=False)[:500])
            
    except json.JSONDecodeError:
        p("Not JSON, raw content:")
        p(body[:2000])
        
except Exception as e:
    p("Error: %s" % e)

p("\n" + "=" * 70)
