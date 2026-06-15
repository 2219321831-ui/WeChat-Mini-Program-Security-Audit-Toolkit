#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DiceThrowing via GET + try to burn 500 steps"""
import hashlib, time, json, random, sys, os, urllib.request, urllib.error, urllib.parse

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

TARGET = 477320
ACT, CUS = 2092, 3824

p("=" * 60)
p(f"  DiceThrowing Test (GET method)")
p(f"  UserId={TARGET}")
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

# 2. Try DiceThrowing as GET
p(f"\n[2] DiceThrowing via GET:")
st, b = get("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
p(f"  HTTP {st}")
if isinstance(b, dict):
    p(f"  OK={b.get('IsSuccess')} Code={b.get('Code','')} Msg={b.get('Message','')}")
    d = b.get("Data")
    if d:
        p(f"  Full: {json.dumps(d, ensure_ascii=False)[:800]}")
else:
    p(f"  Body: {b}")

# 3. Try DiceThrowing as POST (no extra params)
p(f"\n[3] DiceThrowing via POST (minimal):")
st, b = post("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
p(f"  HTTP {st}")
if isinstance(b, dict):
    p(f"  OK={b.get('IsSuccess')} Code={b.get('Code','')} Msg={b.get('Message','')}")
    d = b.get("Data")
    if d:
        p(f"  Full: {json.dumps(d, ensure_ascii=False)[:800]}")
else:
    p(f"  Body: {b}")

# 4. If GET works, burn dice to get ~500 steps (avg 3.5 per die, need ~143 rolls)
p(f"\n[4] Burn dice rolls to add ~500 steps:")
rolls_needed = 150  # ~525 steps at avg 3.5
total_steps = 0
success_rolls = 0

for i in range(rolls_needed):
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
            p(f"  [{i+1:03d}] dice={dice} point={point_now} remain={remain_now} | total_added={total_steps}")
            if total_steps >= 500:
                p(f"  Reached 500+ steps! Stopping.")
                break
        else:
            msg = b.get("Message", "") or ""
            code = b.get("Code", "") or ""
            p(f"  [{i+1:03d}] FAIL: {code} {msg[:60]}")
            if "remain" in msg.lower() or "time" in msg.lower() or code == "NoTimes":
                p(f"  No more dice rolls, stopping.")
                break
    else:
        p(f"  [{i+1:03d}] HTTP {st}")
    time.sleep(0.15)

# 5. Check state after
p(f"\n[5] State after {success_rolls} rolls:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
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
p(f"TotalStep: {total_before} -> {total_after} (delta={total_after - total_before:+d})")
p(f"{'='*60}")
