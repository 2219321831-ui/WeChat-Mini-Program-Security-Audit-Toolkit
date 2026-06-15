#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Test: directly add steps via DiceThrowing for UserId=477320"""
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
p(f"  Step Manipulation Test: UserId={TARGET}")
p("=" * 60)

# 1. Get current state
p("\n[1] Current state (GetMapConfig):")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
if isinstance(b, dict) and b.get("Data"):
    d = b["Data"]
    p(f"  UserId: {d.get('UserId')}")
    p(f"  JoinId: {d.get('JoinId')}")
    p(f"  Point (current pos): {d.get('Point')}")
    p(f"  CurrPoint: {d.get('CurrPoint')}")
    p(f"  TotalStep: {d.get('TotalStep')}")
    p(f"  RemainTimes (dice rolls left): {d.get('RemainTimes')}")
    p(f"  HelpTotalTimes: {d.get('HelpTotalTimes')}")
    p(f"  FinalPoint: {d.get('FinalPoint')}")
    p(f"  Points: {d.get('Points')}")
    rank = d.get("Rank", {})
    if rank:
        p(f"  Rank info: Rank={rank.get('Rank')} Steps={rank.get('TotalSteps')} BeHelp={rank.get('BeHelpCount')}")

# 2. Get rank before
p("\n[2] Rank before (GetMapRank):")
st, b = get("ActApi/ActivityApi/GetMapRank", {"ActId":ACT,"CusId":CUS})
steps_before = 0
if isinstance(b, dict) and b.get("Data"):
    for mod in b["Data"].get("ModuleList", []):
        kv = mod.get("KeyValues", "")
        if isinstance(kv, str) and kv.startswith("["):
            try:
                for item in json.loads(kv):
                    if item.get("UserId") == TARGET:
                        steps_before = item.get("TotalSteps", 0)
                        p(f"  UserId={TARGET}: Rank={item.get('Rank')} Steps={steps_before} BeHelp={item.get('BeHelpCount')}")
            except: pass

# 3. Try DiceThrowing
p(f"\n[3] DiceThrowing test (single roll):")
st, b = post("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
if isinstance(b, dict):
    p(f"  HTTP {st} OK={b.get('IsSuccess')} Code={b.get('Code','')} Msg={b.get('Message','')}")
    d = b.get("Data")
    if d:
        p(f"  Data: {json.dumps(d, ensure_ascii=False)[:800]}")

# 4. Try multiple dice rolls
p(f"\n[4] Multiple DiceThrowing (try 10 rolls):")
total_steps_added = 0
for i in range(10):
    st, b = post("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
    if isinstance(b, dict):
        ok = b.get("IsSuccess", False)
        msg = b.get("Message", "") or ""
        code = b.get("Code", "") or ""
        d = b.get("Data")
        dice_val = ""
        step_info = ""
        if d and isinstance(d, dict):
            dice_val = f" dice={d.get('DiceNum','?')}"
            step_info = f" step={d.get('Step','?')} point={d.get('Point','?')} remain={d.get('RemainTimes','?')}"
            s = d.get("Step") or d.get("DiceNum") or 0
            if isinstance(s, (int, float)):
                total_steps_added += int(s)
        p(f"  [{i+1:02d}/10] OK={ok}{dice_val}{step_info} | {msg[:50]}")
    time.sleep(0.3)

# 5. Try alternative endpoints for step manipulation
p(f"\n[5] Try alternative step APIs:")

# Try SubmitDataSignV2 (from PlayPageApi)
alt_endpoints = [
    ("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS,"DiceNum":6,"Step":6}),
    ("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS,"step":500}),
    ("ActApi/ActivityApi/DiceThrowing", {"ActId":ACT,"UserId":TARGET,"CusId":CUS,"Steps":500,"TotalSteps":2700}),
    ("api/PlayPageApi/SubmitDataSignV2", {"ActId":ACT,"UserId":TARGET,"CusId":CUS,"Data":500}),
    ("api/PlayPageApi/SubmitAnswer", {"ActId":ACT,"UserId":TARGET,"CusId":CUS,"Score":500}),
]

for path, params in alt_endpoints:
    st, b = post(path, params)
    if isinstance(b, dict):
        ok = b.get("IsSuccess")
        code = b.get("Code","")
        msg = b.get("Message","") or ""
        d = b.get("Data")
        d_str = json.dumps(d, ensure_ascii=False)[:300] if d else "null"
        p(f"  {path}:")
        p(f"    params={json.dumps({k:v for k,v in params.items() if k not in ['version','client']})}")
        p(f"    OK={ok} Code={code} Msg={msg}")
        p(f"    Data={d_str}")
    else:
        p(f"  {path}: HTTP {st} {b}")

# 6. Check state after
p(f"\n[6] State after:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
if isinstance(b, dict) and b.get("Data"):
    d = b["Data"]
    p(f"  TotalStep: {d.get('TotalStep')}")
    p(f"  RemainTimes: {d.get('RemainTimes')}")
    p(f"  Point: {d.get('Point')}")

# Rank after
st, b = get("ActApi/ActivityApi/GetMapRank", {"ActId":ACT,"CusId":CUS})
if isinstance(b, dict) and b.get("Data"):
    for mod in b["Data"].get("ModuleList", []):
        kv = mod.get("KeyValues", "")
        if isinstance(kv, str) and kv.startswith("["):
            try:
                for item in json.loads(kv):
                    if item.get("UserId") == TARGET:
                        steps_after = item.get("TotalSteps", 0)
                        p(f"  Rank: Rank={item.get('Rank')} Steps={steps_after} (was {steps_before}, delta={steps_after-steps_before:+d})")
            except: pass

p(f"\n{'='*60}")
p(f"Steps: {steps_before} -> ? (dice rolls attempted)")
p(f"{'='*60}")
