#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deep anomaly check on test account 477320 - READ-ONLY"""
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
    params.setdefault("version","2.1.0"); params.setdefault("client","standard")
    url = API + path + "?" + urllib.parse.urlencode(params)
    s2, nc, ts = sign(params)
    h = {"User-Agent":"Mozilla/5.0","wxminitype":"adks","wxminiapisign2":s2,"wxminiapitimespan":ts,"wxminiapitimenonce":nc}
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=8) as r:
            b = r.read().decode("utf-8","replace")
            return r.status, json.loads(b) if b.startswith("{") else b
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8","replace"))
        except: return e.code, str(e.reason)
    except: return 0, "err"

ACT, CUS = 2092, 3824
TARGET = 477320

p("=" * 70)
p(f"  Test Account 477320 - Full Anomaly Audit (READ-ONLY)")
p("=" * 70)

# 1. GetMapConfig full dump
p("\n[1] GetMapConfig full response:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
mc = {}
if isinstance(b, dict) and b.get("Data"):
    mc = b["Data"]
    for k, v in sorted(mc.items()):
        p(f"  {k}: {v}")

# 2. GetHelpInfo full dump
p(f"\n[2] GetHelpInfo full response:")
st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
hi = {}
help_list = []
if isinstance(b, dict) and b.get("Data"):
    hi = b["Data"]
    for k, v in sorted(hi.items()):
        if isinstance(v, list):
            p(f"  {k}: [{len(v)} items]")
            help_list = v
        else:
            p(f"  {k}: {v}")

# 3. Leaderboard data (what others see)
p(f"\n[3] GetMapRank - what leaderboard shows for 477320:")
st, b = get("ActApi/ActivityApi/GetMapRank", {"ActId":ACT,"CusId":CUS})
if isinstance(b, dict) and b.get("Data"):
    for mod in b["Data"].get("ModuleList", []):
        mod_code = mod.get("Code", "")
        kv = mod.get("KeyValues", "")
        if mod_code == "MapRanking" and isinstance(kv, str) and kv.startswith("["):
            for item in json.loads(kv):
                if item.get("UserId") == TARGET:
                    p(f"  Leaderboard entry:")
                    for k, v in sorted(item.items()):
                        p(f"    {k}: {v}")

# 4. Analyze help list for suspicious patterns
p(f"\n[4] Help list pattern analysis:")
if help_list:
    p(f"  Total helpers: {len(help_list)}")

    # Time distribution
    times = []
    helper_ids = []
    no_nick = 0
    no_cover = 0
    for h in help_list:
        t = h.get("HelpTime", "")
        hid = h.get("HelpUserId", 0)
        nick = h.get("NickName")
        cover = h.get("CoverImg")
        times.append(t)
        helper_ids.append(hid)
        if not nick: no_nick += 1
        if not cover: no_cover += 1

    p(f"  Helpers with no nickname: {no_nick}/{len(help_list)}")
    p(f"  Helpers with no avatar: {no_cover}/{len(help_list)}")

    # Time clustering - check if votes came in bursts
    p(f"\n  Time distribution (first 20 + last 20):")
    for h in help_list[:20]:
        p(f"    {h.get('HelpTime')} | ID={h.get('HelpUserId')} | {h.get('NickName','(none)')} | cover={'Y' if h.get('CoverImg') else 'N'}")
    if len(help_list) > 40:
        p(f"    ... ({len(help_list) - 40} more) ...")
    for h in help_list[-20:]:
        p(f"    {h.get('HelpTime')} | ID={h.get('HelpUserId')} | {h.get('NickName','(none)')} | cover={'Y' if h.get('CoverImg') else 'N'}")

    # Check helper ID patterns
    p(f"\n  Helper ID analysis:")
    id_ranges = {}
    for hid in helper_ids:
        prefix = str(hid)[:3]
        id_ranges[prefix] = id_ranges.get(prefix, 0) + 1
    p(f"  ID prefix distribution (first 3 digits):")
    for prefix, count in sorted(id_ranges.items()):
        p(f"    {prefix}xxx: {count}")

    # Check if same helper appears multiple times (dedup check)
    unique_ids = set(helper_ids)
    p(f"  Unique helper IDs: {len(unique_ids)} / {len(help_list)}")
    if len(unique_ids) < len(help_list):
        dupes = len(help_list) - len(unique_ids)
        p(f"  Duplicates found: {dupes}")

    # Check time gaps - forged votes tend to have very regular intervals
    from datetime import datetime
    parsed_times = []
    for t in times:
        try:
            parsed_times.append(datetime.strptime(t, "%Y-%m-%d %H:%M:%S"))
        except:
            pass
    if len(parsed_times) > 1:
        gaps = []
        for i in range(1, len(parsed_times)):
            gap = (parsed_times[i-1] - parsed_times[i]).total_seconds()
            gaps.append(gap)
        p(f"\n  Time gaps between votes (seconds):")
        p(f"    Min gap: {min(gaps):.1f}s")
        p(f"    Max gap: {max(gaps):.1f}s")
        p(f"    Avg gap: {sum(gaps)/len(gaps):.1f}s")
        # Count very small gaps (< 2s = suspicious)
        fast = sum(1 for g in gaps if g < 2)
        p(f"    Gaps < 2s (suspicious): {fast}/{len(gaps)}")
        # Count very regular gaps
        regular = sum(1 for g in gaps if abs(g - 0.2) < 0.1 or abs(g - 0.1) < 0.05)
        p(f"    Gaps ~0.1-0.2s (bot-like): {regular}/{len(gaps)}")

# 5. Cross-check numbers
p(f"\n[5] Data consistency check:")
help_total = mc.get("HelpTotalTimes", 0)
help_count = hi.get("HelpCount", 0)
remain = mc.get("RemainTimes", 0)
total_step = mc.get("TotalStep", 0)
watch_video = mc.get("WatchVideoTotalTimes", 0)

p(f"  GetMapConfig.HelpTotalTimes: {help_total}")
p(f"  GetHelpInfo.HelpCount:       {help_count}")
p(f"  Match? {'YES' if help_total == help_count else 'NO - MISMATCH!'}")
p(f"")
p(f"  Dice accounting:")
p(f"    Dice from help (HelpTotalTimes * 10): {help_total * 10}")
p(f"    Dice from video (WatchVideo * ?):      {watch_video} (unknown per-video amount)")
p(f"    Current RemainTimes:                   {remain}")
p(f"    Dice consumed:                         {help_total * 10 - remain}")
p(f"    TotalStep:                             {total_step}")
consumed = help_total * 10 - remain
if consumed > 0:
    avg = total_step / consumed
    max_possible = consumed * 6
    p(f"    Avg steps/die:                         {avg:.2f} (max possible: 6.00)")
    p(f"    Max possible steps:                    {max_possible}")
    p(f"    Actual exceeds max?                    {'YES - IMPOSSIBLE!' if total_step > max_possible else 'NO'}")

p(f"\n{'='*70}")
p(f"ANOMALY SUMMARY FOR 477320:")
p(f"{'='*70}")
