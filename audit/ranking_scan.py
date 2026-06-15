#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only: scan user IDs to find active players and their step counts"""
import hashlib, time, json, sys, os, urllib.request, urllib.error, urllib.parse
import concurrent.futures

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
    h = {"User-Agent": "Mozilla/5.0", "wxminitype": "adks",
         "wxminiapisign2": s2, "wxminiapitimespan": ts, "wxminiapitimenonce": nc}
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            b = r.read().decode("utf-8", "replace")
            return r.status, json.loads(b) if b.startswith("{") else b
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except: return e.code, str(e.reason)
    except: return 0, "err"

ACT, CUS = 2092, 3824

def query_user(uid):
    st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId": ACT, "CusId": CUS, "UserId": uid})
    if isinstance(b, dict) and b.get("IsSuccess"):
        d = b.get("Data", {})
        step = d.get("TotalStep", 0)
        join = d.get("JoinId", 0)
        if step > 0 or join > 0:
            return {
                "UserId": uid,
                "TotalStep": step,
                "JoinId": join,
                "HelpTotalTimes": d.get("HelpTotalTimes", 0),
                "RemainTimes": d.get("RemainTimes", 0),
                "CurrPoint": d.get("CurrPoint", 0),
            }
    return None

p("=" * 70)
p("  Scanning user IDs for active players (read-only)")
p("=" * 70)

# From help info we know real helper IDs that helped 477320.
# These are real users in the system. Let me extract known user IDs first.

# Known from previous session ranking: 476964, 476832, 476836, 477320
# Known helpers from GetHelpInfo response (sample): various IDs
# Activity just started today (2026-06-15), so scan broadly

# Strategy: scan the 476000-479000 range (where most known users are)
# Plus scan some of the helper IDs we saw

# First batch: known range 476000-479000
p("\n[1] Scanning UserId 476000-479000 (concurrent)...")
results = []
with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(query_user, uid): uid for uid in range(476000, 479001)}
    done = 0
    for f in concurrent.futures.as_completed(futures):
        done += 1
        r = f.result()
        if r:
            results.append(r)
        if done % 100 == 0:
            p("  ... scanned %d/3001, found %d active" % (done, len(results)))

p("  Scan complete: found %d active users in 476000-479000" % len(results))

# Sort by TotalStep descending
results.sort(key=lambda x: x["TotalStep"], reverse=True)

p("\n[2] Top 30 by TotalStep:")
p("  %-6s %-10s %-14s %-14s %-10s %-8s" % ("#", "UserId", "TotalStep", "HelpTotalTm", "RemainTm", "CurrPt"))
p("  " + "-" * 68)
for i, r in enumerate(results[:30], 1):
    p("  %-6d %-10d %-14d %-14d %-10d %-8d" % (
        i, r["UserId"], r["TotalStep"], r["HelpTotalTimes"], r["RemainTimes"], r["CurrPoint"]))

# Stats
if results:
    steps = [r["TotalStep"] for r in results]
    p("\n[3] Stats:")
    p("  Total active users: %d" % len(results))
    p("  Step range: %d ~ %d" % (min(steps), max(steps)))
    p("  Avg step: %.0f" % (sum(steps) / len(steps)))
    # Count users with high steps
    high = [r for r in results if r["TotalStep"] > 5000]
    p("  Users with >5000 steps: %d" % len(high))
    very_high = [r for r in results if r["TotalStep"] > 10000]
    p("  Users with >10000 steps: %d" % len(very_high))

p("\n" + "=" * 70)
