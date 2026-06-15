#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deep read-only analysis: 476832 vs 476964 - are they normal or manipulated?"""
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
TARGETS = [
    {"uid": 476832, "name": "Rank#2"},
    {"uid": 476964, "name": "Rank#3"},
    # Reference users for baseline comparison
    {"uid": 476836, "name": "Rank#4 (baseline)"},
    {"uid": 477693, "name": "Rank#5 (baseline)"},
    {"uid": 477523, "name": "Rank#8 (baseline)"},
]

p("=" * 70)
p(f"  Deep Analysis: 476832 & 476964 anomaly check (READ-ONLY)")
p(f"  ActId={ACT}  CusId={CUS}")
p("=" * 70)

# ===== 1. Full GetMapConfig dump for each =====
p("\n[1] GetMapConfig full response per user:")
for t in TARGETS:
    uid = t["uid"]
    label = t["name"]
    st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":uid})
    p(f"\n  --- {uid} ({label}) ---")
    if isinstance(b, dict) and b.get("Data"):
        d = b["Data"]
        for k, v in sorted(d.items()):
            p(f"    {k}: {v}")
    else:
        p(f"    No data (HTTP {st})")
    time.sleep(0.1)

# ===== 2. GetHelpInfo full dump =====
p(f"\n[2] GetHelpInfo full response per user:")
for t in TARGETS:
    uid = t["uid"]
    label = t["name"]
    st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":uid,"CusId":CUS})
    p(f"\n  --- {uid} ({label}) ---")
    if isinstance(b, dict) and b.get("Data"):
        d = b["Data"]
        for k, v in sorted(d.items()):
            if isinstance(v, list):
                p(f"    {k}: [{len(v)} items]")
                for item in v[:5]:
                    p(f"      {item}")
                if len(v) > 5:
                    p(f"      ... and {len(v)-5} more")
            else:
                p(f"    {k}: {v}")
    else:
        p(f"    No data (HTTP {st})")
    time.sleep(0.1)

# ===== 3. GetActivityDetailsV2 - check activity info =====
p(f"\n[3] Activity details (for time context):")
st, b = get("ActApi/ActivityApi/GetActivityDetailsV2", {"ActId":ACT,"CusId":CUS})
if isinstance(b, dict) and b.get("Data"):
    info = b["Data"].get("ActInfo", {})
    if info:
        for k in ["ActName","StartTime","EndTime","ActState"]:
            p(f"  {k}: {info.get(k)}")

# ===== 4. Cross-check: compute expected values =====
p(f"\n[4] Statistical analysis:")
p(f"  Normal gameplay model:")
p(f"    - Each Help vote = 10 dice (RemainTimes)")
p(f"    - Each dice roll = 1~6 steps (avg 3.5)")
p(f"    - Max steps from N HelpCount = N * 10 * 6 (all sixes)")
p(f"    - Expected steps from N HelpCount = N * 10 * 3.5")
p(f"    - Min steps from N HelpCount = N * 10 * 1 (all ones)")
p(f"    - Unused dice still sit in RemainTimes")
p(f"    - Formula: TotalStep + RemainTimes * 3.5 ~ HelpCount * 10 * 3.5")
p(f"    - Or: TotalStep <= HelpCount * 60 (absolute max if all sixes)")
p(f"    - Dice consumed = (HelpCount * 10) - RemainTimes")
p(f"    - Avg steps per consumed die = TotalStep / dice_consumed")
p(f"")

p(f"  {'User':<14} {'Help':<6} {'MaxDice':<9} {'Remain':<8} {'Used':<8} {'Steps':<8} {'Avg/Die':<8} {'MinExp':<8} {'MaxExp':<8} {'Verdict'}")
p(f"  {'-'*13} {'-'*5} {'-'*8} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*7} {'-'*15}")

# Re-fetch for all leaderboard users for comparison
all_users = [
    (477320, "477320(YOU)"),
    (476832, "476832"),
    (476964, "476964"),
    (476836, "476836"),
    (477693, "477693"),
    (450874, "450874"),
    (477319, "477319"),
    (477523, "477523"),
    (476977, "476977"),
    (477541, "477541"),
]

results = []
for uid, label in all_users:
    st2, b2 = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":uid})
    st3, b3 = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":uid,"CusId":CUS})

    ts = remain = help_count = 0
    if isinstance(b2, dict) and b2.get("Data"):
        d = b2["Data"]
        ts = d.get("TotalStep", 0) or 0
        remain = d.get("RemainTimes", 0) or 0
    if isinstance(b3, dict) and b3.get("Data"):
        help_count = b3["Data"].get("HelpCount", 0) or 0

    max_dice = help_count * 10
    used_dice = max_dice - remain if max_dice >= remain else 0
    avg_per_die = round(ts / used_dice, 2) if used_dice > 0 else 0
    min_expected = round(used_dice * 1)
    max_expected = round(used_dice * 6)

    verdict = ""
    # Check anomalies
    issues = []
    if used_dice > 0 and avg_per_die > 6.0:
        issues.append(f"avg>{6}!")
    if used_dice > 0 and avg_per_die < 1.0:
        issues.append(f"avg<{1}!")
    if ts > max_expected and used_dice > 0:
        issues.append("steps>max!")
    if ts < min_expected and used_dice > 0:
        issues.append("steps<min!")
    if remain > max_dice:
        issues.append("remain>max_dice!")

    if issues:
        verdict = " ".join(issues)
    else:
        verdict = "NORMAL"

    results.append({
        "uid": uid, "label": label, "help": help_count,
        "max_dice": max_dice, "remain": remain, "used": used_dice,
        "steps": ts, "avg": avg_per_die, "verdict": verdict
    })

    p(f"  {label:<14} {help_count:<6} {max_dice:<9} {remain:<8} {used_dice:<8} {ts:<8} {avg_per_die:<8} {min_expected:<8} {max_expected:<8} {verdict}")
    time.sleep(0.15)

# ===== 5. Focus analysis on the two targets =====
p(f"\n[5] Focused verdict:")
for r in results:
    if r["uid"] in (476832, 476964):
        p(f"\n  === {r['uid']} ===")
        p(f"    HelpCount (real unique helpers): {r['help']}")
        p(f"    Max possible dice (Help*10):       {r['max_dice']}")
        p(f"    Current RemainTimes (unused):      {r['remain']}")
        p(f"    Dice consumed:                     {r['used']}")
        p(f"    TotalStep:                         {r['steps']}")
        p(f"    Avg steps per consumed die:        {r['avg']} (expected ~3.5)")
        p(f"    Theoretical min steps (all 1s):    {r['used'] * 1}")
        p(f"    Theoretical max steps (all 6s):    {r['used'] * 6}")
        if r['used'] > 0:
            within = r['used'] * 1 <= r['steps'] <= r['used'] * 6
            p(f"    Steps within [min, max]?           {'YES' if within else 'NO'}")
        p(f"    Verdict:                           {r['verdict']}")

p(f"\n{'='*70}")
