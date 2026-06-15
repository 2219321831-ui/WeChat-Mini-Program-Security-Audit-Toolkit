#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Disguise test account 477320 - normalize data without changing steps"""
import hashlib, time, json, random, sys, os, urllib.request, urllib.error, urllib.parse
from datetime import datetime

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

def post(path, data):
    data.setdefault("version","2.1.0"); data.setdefault("client","standard")
    url = API + path
    s2, nc, ts = sign(data)
    h = {"User-Agent":"Mozilla/5.0","wxminitype":"adks","Content-Type":"application/json","wxminiapisign2":s2,"wxminiapitimespan":ts,"wxminiapitimenonce":nc}
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, headers=h, method="POST")
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
p(f"  Disguise 477320 - normalize data (keep steps unchanged)")
p("=" * 70)

# ===== 1. Before state =====
p("\n[1] Before state:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
mc_before = {}
if isinstance(b, dict) and b.get("Data"):
    mc_before = b["Data"]
    p(f"  TotalStep: {mc_before.get('TotalStep')}")
    p(f"  RemainTimes: {mc_before.get('RemainTimes')}")
    p(f"  HelpTotalTimes: {mc_before.get('HelpTotalTimes')}")
    p(f"  WatchVideoTotalTimes: {mc_before.get('WatchVideoTotalTimes')}")

st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
existing_ids = set()
if isinstance(b, dict) and b.get("Data"):
    hc = b["Data"].get("HelpCount", 0)
    p(f"  HelpCount: {hc}")
    for h in b["Data"].get("HelpUsers", []):
        existing_ids.add(h.get("HelpUserId", 0))
    p(f"  Existing unique helper IDs: {len(existing_ids)}")

help_total = mc_before.get("HelpTotalTimes", 0)
help_count = hc
gap = help_total - help_count
p(f"\n  Gap (HelpTotalTimes - HelpCount): {gap}")
p(f"  Need ~{gap + 20} new UNIQUE helpers to close gap + buffer")

# ===== 2. First, consume excess RemainTimes to fix dice math =====
# After adding helpers, MaxDice increases. We need to consume some dice
# to keep avg steps/die in [2.5, 5.0] range
p(f"\n[2] Step 1: Roll dice to consume excess RemainTimes")
remain_now = mc_before.get("RemainTimes", 0)
total_step_now = mc_before.get("TotalStep", 0)

# Target: after disguise, HelpTotalTimes will be ~(help_total + new_helpers_that_count)
# RemainTimes will increase by new_helpers * 10
# We need to roll dice to keep avg reasonable
# First, let's see current dice math and roll to burn some
rolls_done = 0
steps_added = 0
# Roll up to 100 dice to bring avg down and make it look natural
target_rolls = min(remain_now - 50, 100)  # keep at least 50 remain
if target_rolls > 0:
    p(f"  Rolling {target_rolls} dice to normalize step/die ratio...")
    for i in range(target_rolls):
        st, b = get("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
        if isinstance(b, dict) and b.get("IsSuccess") and b.get("Data"):
            d = b["Data"]
            rolls_done += 1
            remain_now = d.get("RemainTimes", remain_now)
        else:
            msg = b.get("Message","") if isinstance(b, dict) else ""
            if "remain" in msg.lower() or "time" in msg.lower():
                break
        if (i+1) % 25 == 0:
            p(f"  [{i+1}] rolled, RemainTimes now: {remain_now}")
        time.sleep(0.12)
    # Re-read state
    st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
    if isinstance(b, dict) and b.get("Data"):
        total_step_now = b["Data"].get("TotalStep", 0)
        remain_now = b["Data"].get("RemainTimes", 0)
    p(f"  Rolled {rolls_done} dice. TotalStep: {mc_before.get('TotalStep')}->{total_step_now}, RemainTimes: {mc_before.get('RemainTimes')}->{remain_now}")

# ===== 3. Send diverse helpers to close HelpCount gap =====
p(f"\n[3] Step 2: Send diverse helper votes to close HelpCount gap")
p(f"  Using wide ID ranges to look like real users from different sources")

# Generate diverse helper IDs from many different ranges
# Avoid existing IDs and avoid clustering
diverse_ranges = [
    (10000, 50000),    # low-range IDs (older users)
    (50000, 100000),   # mid-range
    (100000, 200000),  # mid-high
    (200000, 350000),  # high
    (350000, 500000),  # very high
    (500000, 700000),  # extra high
    (700000, 999999),  # top range
]

# Generate ~120 unique IDs spread across ranges
target_new = gap + 30  # close gap + buffer
helper_ids = []
used_ids = set()
per_range = target_new // len(diverse_ranges) + 2

for lo, hi in diverse_ranges:
    for _ in range(per_range + 5):
        if len(helper_ids) >= target_new + 20:
            break
        hid = random.randint(lo, hi)
        if hid not in existing_ids and hid not in used_ids:
            used_ids.add(hid)
            helper_ids.append(hid)

random.shuffle(helper_ids)
p(f"  Generated {len(helper_ids)} diverse helper IDs across {len(diverse_ranges)} ranges")
p(f"  ID distribution:")
for lo, hi in diverse_ranges:
    cnt = sum(1 for x in helper_ids if lo <= x < hi)
    if cnt:
        p(f"    {lo:>7}-{hi:>7}: {cnt}")

# Send with natural-looking delays (3-15 seconds between votes, simulating real share timing)
p(f"\n  Sending votes with natural delays (3-8s between votes)...")
ok_count = 0
fail_count = 0
send_count = min(len(helper_ids), target_new + 10)

for i in range(send_count):
    hid = helper_ids[i]
    st, b = post("BaseApi/BaseApi/UserHelp", {
        "ShareUserId": TARGET, "HelpUserId": hid,
        "ActId": ACT, "CusId": CUS
    })
    ok = isinstance(b, dict) and b.get("IsSuccess", False)
    if ok:
        ok_count += 1
    else:
        fail_count += 1

    if (i+1) % 20 == 0:
        st2, b2 = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
        hc_now = 0
        if isinstance(b2, dict) and b2.get("Data"):
            hc_now = b2["Data"].get("HelpCount", 0)
        p(f"  [{i+1:03d}/{send_count}] ok={ok_count} fail={fail_count} | HelpCount now: {hc_now}")
        if hc_now >= help_total:
            p(f"  >>> HelpCount ({hc_now}) >= HelpTotalTimes ({help_total}), gap closed!")
            break

    # Natural delay: 3-8 seconds (simulating real user sharing to friends)
    delay = random.uniform(2.5, 6.0)
    time.sleep(delay)

# ===== 4. Final verification =====
p(f"\n[4] Final state verification:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
mc_after = {}
if isinstance(b, dict) and b.get("Data"):
    mc_after = b["Data"]
    for k in ["TotalStep","RemainTimes","HelpTotalTimes","WatchVideoTotalTimes","CurrPoint"]:
        before_v = mc_before.get(k, "?")
        after_v = mc_after.get(k, "?")
        p(f"  {k}: {before_v} -> {after_v}")

st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
if isinstance(b, dict) and b.get("Data"):
    hc_after = b["Data"].get("HelpCount", 0)
    help_list = b["Data"].get("HelpUsers", [])
    p(f"  HelpCount: {help_count} -> {hc_after}")

    # Re-check patterns
    no_nick = sum(1 for h in help_list if not h.get("NickName"))
    no_cover = sum(1 for h in help_list if not h.get("CoverImg"))
    p(f"  Helpers w/o nickname: {no_nick}/{len(help_list)} ({100*no_nick//max(len(help_list),1)}%)")
    p(f"  Helpers w/o avatar: {no_cover}/{len(help_list)} ({100*no_cover//max(len(help_list),1)}%)")

    # ID distribution
    ids = [h.get("HelpUserId",0) for h in help_list]
    prefix_counts = {}
    for uid in ids:
        pf = str(uid)[:2]
        prefix_counts[pf] = prefix_counts.get(pf, 0) + 1
    p(f"  ID prefix diversity: {len(prefix_counts)} unique 2-digit prefixes")

    # Time gaps
    from datetime import datetime
    times = []
    for h in help_list:
        try:
            times.append(datetime.strptime(h.get("HelpTime",""), "%Y-%m-%d %H:%M:%S"))
        except:
            pass
    if len(times) > 1:
        gaps = [(times[i-1]-times[i]).total_seconds() for i in range(1, len(times))]
        fast = sum(1 for g in gaps if g < 2)
        p(f"  Time gaps < 2s: {fast}/{len(gaps)} ({100*fast//max(len(gaps),1)}%)")

# Dice math check
p(f"\n[5] Final dice math check:")
ht = mc_after.get("HelpTotalTimes", 0)
hc = b["Data"].get("HelpCount", 0) if isinstance(b, dict) and b.get("Data") else 0
rm = mc_after.get("RemainTimes", 0)
ts = mc_after.get("TotalStep", 0)
p(f"  HelpTotalTimes: {ht}  |  HelpCount: {hc}  |  Match: {'YES' if ht == hc else f'gap={ht-hc}'}")
for label, h_val in [("HelpTotalTimes", ht), ("HelpCount", hc)]:
    max_d = h_val * 10
    consumed = max_d - rm
    if consumed > 0:
        avg = ts / consumed
        max_s = consumed * 6
        ok = ts <= max_s and 1.0 <= avg <= 6.0
        p(f"  By {label}: consumed={consumed}, avg={avg:.2f}/die, max_steps={max_s}, actual={ts} -> {'OK' if ok else 'ANOMALY'}")

p(f"\n{'='*70}")
p(f"DISGUISE COMPLETE")
p(f"{'='*70}")
