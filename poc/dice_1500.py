#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DiceThrowing: burn dice rolls to add ~1500 steps to UserId=477320"""
import hashlib, time, json, sys, os, urllib.request, urllib.error, urllib.parse

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import SIGN_KEY, API_BASE

def p(s=""): print(s); sys.stdout.flush()

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

TARGET = 477320
ACT, CUS = 2092, 3824
TARGET_STEPS = 1500
MAX_ROLLS = 600

p("=" * 60)
p(f"  DiceThrowing: +{TARGET_STEPS} steps")
p(f"  UserId={TARGET}  ActId={ACT}  CusId={CUS}")
p("=" * 60)

# 1. Current state
p("\n[1] Current state:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
remain = 0
total_before = 0
if isinstance(b, dict) and b.get("Data"):
    d = b["Data"]
    remain = d.get("RemainTimes", 0)
    total_before = d.get("TotalStep", 0)
    p(f"  TotalStep: {total_before}")
    p(f"  RemainTimes: {remain}")
    p(f"  CurrPoint: {d.get('CurrPoint')}")
else:
    p("  Failed to get state, continuing anyway...")

if remain < TARGET_STEPS // 6 + 10:
    p(f"  WARNING: RemainTimes ({remain}) may not be enough for {TARGET_STEPS} steps")

# 2. Burn dice
p(f"\n[2] Burning up to {MAX_ROLLS} dice rolls (target: +{TARGET_STEPS} steps):")
total_steps = 0
success_rolls = 0
fail_streak = 0

for i in range(MAX_ROLLS):
    st, b = get("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
    if isinstance(b, dict):
        ok = b.get("IsSuccess", False)
        d = b.get("Data")
        if ok and d and isinstance(d, dict):
            dice = d.get("DiceNum", 0) or d.get("Step", 0) or 0
            if isinstance(dice, (int, float)):
                total_steps += int(dice)
                success_rolls += 1
            remain_now = d.get("RemainTimes", "?")
            point_now = d.get("Point", "?")
            fail_streak = 0
            # Print every 10th or when close to target
            if (i+1) % 10 == 0 or total_steps >= TARGET_STEPS - 20:
                p(f"  [{i+1:03d}] dice={dice} point={point_now} remain={remain_now} | +{total_steps}/{TARGET_STEPS}")
            if total_steps >= TARGET_STEPS:
                p(f"  >>> Reached {TARGET_STEPS}+ steps! Stopping.")
                break
        else:
            msg = b.get("Message", "") or ""
            code = b.get("Code", "") or ""
            fail_streak += 1
            p(f"  [{i+1:03d}] FAIL: {code} {msg[:80]}")
            if "remain" in msg.lower() or "time" in msg.lower() or code == "NoTimes":
                p(f"  No more dice rolls available, stopping.")
                break
            if fail_streak >= 10:
                p(f"  10 consecutive failures, stopping.")
                break
    else:
        fail_streak += 1
        p(f"  [{i+1:03d}] HTTP {st}")
        if fail_streak >= 10:
            p(f"  10 consecutive failures, stopping.")
            break
    time.sleep(0.12)

# 3. Check state after
p(f"\n[3] State after {success_rolls} rolls:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
total_after = 0
if isinstance(b, dict) and b.get("Data"):
    d = b["Data"]
    total_after = d.get("TotalStep", 0)
    p(f"  TotalStep: {total_before} -> {total_after} (delta={total_after - total_before:+d})")
    p(f"  RemainTimes: {d.get('RemainTimes')}")
    p(f"  CurrPoint: {d.get('CurrPoint')}")

# Rank check
st, b = get("ActApi/ActivityApi/GetMapRank", {"ActId":ACT,"CusId":CUS})
if isinstance(b, dict) and b.get("Data"):
    for mod in b["Data"].get("ModuleList", []):
        kv = mod.get("KeyValues", "")
        if isinstance(kv, str) and kv.startswith("["):
            try:
                for item in json.loads(kv):
                    if item.get("UserId") == TARGET:
                        p(f"  Rank: #{item.get('Rank')} Steps={item.get('TotalSteps')}")
            except: pass

p(f"\n{'='*60}")
p(f"SUMMARY: {success_rolls} dice rolls, +{total_steps} steps from dice")
if total_after:
    p(f"TotalStep: {total_before} -> {total_after} (delta={total_after - total_before:+d})")
p(f"{'='*60}")
