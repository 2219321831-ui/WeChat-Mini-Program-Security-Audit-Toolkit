#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only: dump leaderboard + check all users' stats for anomalies"""
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
MY_UID = 477320

p("=" * 70)
p(f"  Leaderboard Audit (READ-ONLY)")
p(f"  ActId={ACT}  CusId={CUS}")
p("=" * 70)

# 1. GetMapRank - full leaderboard with KeyValues leak
p("\n[1] GetMapRank - Leaderboard:")
st, b = get("ActApi/ActivityApi/GetMapRank", {"ActId":ACT,"CusId":CUS})

users = []
if isinstance(b, dict) and b.get("Data"):
    for mod in b["Data"].get("ModuleList", []):
        mod_code = mod.get("Code", "")
        kv = mod.get("KeyValues", "")
        p(f"\n  Module: {mod_code}")
        if isinstance(kv, str) and kv.startswith("["):
            try:
                items = json.loads(kv)
                p(f"  {'Rank':<5} {'UserId':<10} {'Nickname':<16} {'Steps':<8} {'HelpCount':<10} {'TotalHelp'}")
                p(f"  {'-'*4} {'-'*9} {'-'*15} {'-'*7} {'-'*9} {'-'*9}")
                for item in items:
                    uid = item.get("UserId", 0)
                    nick = item.get("Nickname", "?")
                    steps = item.get("TotalSteps", 0)
                    rank = item.get("Rank", "?")
                    help_c = item.get("BeHelpCount", 0)
                    total_h = item.get("TotalHelpCount", help_c)
                    tag = " <-- YOU" if uid == MY_UID else ""
                    users.append({
                        "UserId": uid, "Nickname": nick, "Rank": rank,
                        "TotalSteps": steps, "BeHelpCount": help_c,
                        "TotalHelpCount": total_h
                    })
                    p(f"  {rank:<5} {uid:<10} {nick:<16} {steps:<8} {help_c:<10} {total_h}{tag}")
            except Exception as e:
                p(f"  Parse error: {e}")
                p(f"  Raw: {kv[:500]}")
        elif kv:
            p(f"  KeyValues: {str(kv)[:300]}")

p(f"\n  Total users on leaderboard: {len(users)}")

# 2. For each user, read their detailed stats (read-only)
p(f"\n[2] Detailed stats per user (read-only GetMapConfig + GetHelpInfo):")
p(f"  {'UserId':<10} {'Nickname':<16} {'TotalStep':<10} {'RemainTimes':<12} {'CurrPoint':<10} {'HelpCount':<10} {'Steps/Help'}")
p(f"  {'-'*9} {'-'*15} {'-'*9} {'-'*11} {'-'*9} {'-'*9} {'-'*10}")

anomalies = []
for u in users:
    uid = u["UserId"]
    nick = u["Nickname"]

    # GetMapConfig (read-only)
    st2, b2 = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":uid})
    total_step = "?"
    remain = "?"
    curr_point = "?"
    help_total = "?"
    if isinstance(b2, dict) and b2.get("Data"):
        d = b2["Data"]
        total_step = d.get("TotalStep", "?")
        remain = d.get("RemainTimes", "?")
        curr_point = d.get("CurrPoint", "?")
        help_total = d.get("HelpTotalTimes", "?")

    # GetHelpInfo (read-only)
    st3, b3 = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":uid,"CusId":CUS})
    help_count = "?"
    help_times = "?"
    if isinstance(b3, dict) and b3.get("Data"):
        hd = b3["Data"]
        help_count = hd.get("HelpCount", "?")
        help_times = hd.get("HelpTotalTimes", "?")

    # Anomaly detection
    ratio = ""
    flags = []
    try:
        s = int(total_step)
        h = int(help_count) if help_count != "?" else 0
        r = int(remain) if remain != "?" else 0
        if h > 0:
            r_val = round(s / h, 1)
            ratio = str(r_val)
            # Flag: very high steps per help (normal ~10-30 steps per help via dice)
            if r_val > 100:
                flags.append("HIGH_STEP_RATIO")
        elif s > 0:
            flags.append("STEPS_NO_HELP")
        # Flag: very high remain times
        if r > 500:
            flags.append("HIGH_REMAIN")
        # Flag: extremely high steps
        if s > 3000:
            flags.append("HIGH_STEPS")
    except:
        pass

    flag_str = " [!]" + ",".join(flags) if flags else ""
    tag = " <-- YOU" if uid == MY_UID else ""

    p(f"  {uid:<10} {nick:<16} {str(total_step):<10} {str(remain):<12} {str(curr_point):<10} {str(help_count):<10} {ratio}{flag_str}{tag}")

    if flags:
        anomalies.append({
            "UserId": uid, "Nickname": nick, "flags": flags,
            "TotalStep": total_step, "HelpCount": help_count,
            "RemainTimes": remain
        })
    time.sleep(0.15)

# 3. Cross-check: can we read arbitrary user IDs not on leaderboard?
p(f"\n[3] IDOR check - reading random user IDs not on leaderboard:")
test_ids = [1, 100, 1000, 10000, 50000]
for tid in test_ids:
    st2, b2 = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":tid})
    if isinstance(b2, dict) and b2.get("Data"):
        d = b2["Data"]
        ts = d.get("TotalStep", 0)
        if ts and ts > 0:
            p(f"  UserId={tid}: FOUND! TotalStep={ts} RemainTimes={d.get('RemainTimes')} CurrPoint={d.get('CurrPoint')}")
        else:
            p(f"  UserId={tid}: exists but TotalStep=0 (inactive)")
    else:
        msg = b2.get("Message", "") if isinstance(b2, dict) else str(b2)[:60]
        p(f"  UserId={tid}: HTTP {st2} - {msg}")
    time.sleep(0.1)

# 4. Summary
p(f"\n{'='*70}")
p(f"AUDIT SUMMARY")
p(f"{'='*70}")
p(f"Leaderboard users: {len(users)}")
p(f"Anomalies found: {len(anomalies)}")
for a in anomalies:
    p(f"  [{a['UserId']}] {a['Nickname']}: {', '.join(a['flags'])}")
    p(f"    TotalStep={a['TotalStep']} HelpCount={a['HelpCount']} RemainTimes={a['RemainTimes']}")
p(f"{'='*70}")
