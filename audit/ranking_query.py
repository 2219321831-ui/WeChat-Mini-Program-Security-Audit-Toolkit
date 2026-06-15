#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only: query leaderboard ranking data (no modifications)"""
import hashlib, time, json, sys, os, urllib.request, urllib.error, urllib.parse

def p(s=""): print(s); sys.stdout.flush()

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import SIGN_KEY, API_BASE
API = API_BASE

def sign(params):
    ts = str(int(time.time() * 1000))
    keys = sorted(params.keys(), key=lambda k: k.lower())
    vals = "".join(str(params[k]) for k in keys)
    raw = vals + ts + SIGN_KEY
    s2 = hashlib.md5(raw.encode("utf-8")).hexdigest().upper()
    nc = hashlib.md5((ts + SIGN_KEY).encode("utf-8")).hexdigest().upper()
    return s2, nc, ts

def get(path, params):
    params.setdefault("version", "2.1.0")
    params.setdefault("client", "standard")
    url = API + path + "?" + urllib.parse.urlencode(params)
    s2, nc, ts = sign(params)
    h = {
        "User-Agent": "Mozilla/5.0",
        "wxminitype": "adks",
        "wxminiapisign2": s2,
        "wxminiapitimespan": ts,
        "wxminiapitimenonce": nc,
    }
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            b = r.read().decode("utf-8", "replace")
            return r.status, json.loads(b) if b.startswith("{") else b
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except:
            return e.code, str(e.reason)
    except Exception as ex:
        return 0, str(ex)

ACT, CUS = 2092, 3824

p("=" * 70)
p("  READ-ONLY: Leaderboard Query (ActId=%d, CusId=%d)" % (ACT, CUS))
p("=" * 70)

# 1. Activity info
p("\n[1] Activity Details:")
st, b = get("ActApi/ActivityApi/GetActivityDetailsV2", {"ActId": ACT, "CusId": CUS})
if isinstance(b, dict) and b.get("IsSuccess"):
    data = b.get("Data", {}) or {}
    info = data.get("ActInfo", {}) or {}
    p("  Name: %s" % info.get("ActName"))
    p("  State: %s  TemplateId: %s" % (info.get("ActState"), info.get("TemplateId")))
    modules = [m.get("ModuleName") for m in (data.get("Modules") or [])]
    p("  Modules: %s" % modules)
else:
    p("  Failed: %s" % b)

# 2. Ranking - try multiple page sizes to get full top list
p("\n[2] MapRanking (Top players):")
all_ranks = []
for page in range(1, 6):  # pages 1-5
    st, b = get("ActApi/ActivityApi/GetMapRanking", {
        "ActId": ACT, "CusId": CUS, "PageIndex": page, "PageSize": 50
    })
    if isinstance(b, dict) and b.get("IsSuccess"):
        data = b.get("Data") or []
        if not data:
            break
        all_ranks.extend(data)
        if len(data) < 50:
            break
    else:
        p("  Page %d failed: %s" % (page, b))
        break

if all_ranks:
    p("  Total fetched: %d players\n" % len(all_ranks))
    p("  %-6s %-8s %-20s %-10s %-10s %-10s %-10s" % (
        "Rank", "UserId", "Nickname", "TotalStep", "HelpCount", "HelpTotal", "RemainTm"))
    p("  " + "-" * 86)
    for i, r in enumerate(all_ranks, 1):
        uid = r.get("UserId", "?")
        nick = r.get("NickName", "") or ""
        if len(nick) > 18:
            nick = nick[:16] + ".."
        step = r.get("TotalStep", r.get("BeHelpCount", "?"))
        hc = r.get("HelpCount", "?")
        ht = r.get("HelpTotalTimes", "?")
        rt = r.get("RemainTimes", "?")
        p("  %-6d %-8s %-20s %-10s %-10s %-10s %-10s" % (i, uid, nick, step, hc, ht, rt))

    # 3. Dump raw JSON for the first 10 for deeper inspection
    p("\n[3] Raw JSON (top 10):")
    for i, r in enumerate(all_ranks[:10], 1):
        p("  #%d: %s" % (i, json.dumps(r, ensure_ascii=False)))
else:
    p("  No ranking data returned")

p("\n" + "=" * 70)
p("  DONE (read-only, no data modified)")
p("=" * 70)
