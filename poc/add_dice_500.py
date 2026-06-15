#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add ~500 dice (RemainTimes) to UserId=477320 via forged UserHelp votes"""
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
SEND_VOTES = 1200  # send more due to server dedup (~40% pass rate)

p("=" * 60)
p(f"  Add ~500 dice to UserId={TARGET}")
p(f"  Sending {SEND_VOTES} UserHelp votes (expect ~40% pass)")
p("=" * 60)

# 1. Current state
p("\n[1] Current state:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
remain_before = 0
total_before = 0
if isinstance(b, dict) and b.get("Data"):
    d = b["Data"]
    remain_before = d.get("RemainTimes", 0)
    total_before = d.get("TotalStep", 0)
    p(f"  TotalStep: {total_before}")
    p(f"  RemainTimes: {remain_before}")

st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
help_before = 0
if isinstance(b, dict) and b.get("Data"):
    help_before = b["Data"].get("HelpCount", 0)
    p(f"  HelpCount: {help_before}")

# 2. Send votes in batches, check RemainTimes periodically
p(f"\n[2] Sending {SEND_VOTES} forged UserHelp votes:")
ok_count = 0
fail_count = 0

for i in range(1, SEND_VOTES + 1):
    helper = random.randint(100000, 999999)
    st, b = post("BaseApi/BaseApi/UserHelp", {
        "ShareUserId": TARGET, "HelpUserId": helper,
        "ActId": ACT, "CusId": CUS
    })
    ok = False
    if isinstance(b, dict):
        ok = b.get("IsSuccess", False)
    if ok:
        ok_count += 1
    else:
        fail_count += 1

    if i % 50 == 0:
        # Check RemainTimes mid-batch
        st2, b2 = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
        remain_now = 0
        if isinstance(b2, dict) and b2.get("Data"):
            remain_now = b2["Data"].get("RemainTimes", 0)
        delta = remain_now - remain_before
        p(f"  [{i:04d}/{SEND_VOTES}] ok={ok_count} fail={fail_count} | RemainTimes: {remain_before}->{remain_now} (+{delta})")

        if delta >= 500:
            p(f"  >>> RemainTimes increased by {delta}, target reached! Stopping.")
            break

    if i % 10 == 0:
        time.sleep(0.05)  # tiny extra pause every 10
    time.sleep(0.1)

# 3. Final state
p(f"\n[3] Final state:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId":ACT,"CusId":CUS,"UserId":TARGET})
remain_after = 0
if isinstance(b, dict) and b.get("Data"):
    d = b["Data"]
    remain_after = d.get("RemainTimes", 0)
    p(f"  TotalStep: {d.get('TotalStep')}")
    p(f"  RemainTimes: {remain_before} -> {remain_after} (delta={remain_after - remain_before:+d})")
    p(f"  CurrPoint: {d.get('CurrPoint')}")

st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
if isinstance(b, dict) and b.get("Data"):
    help_after = b["Data"].get("HelpCount", 0)
    p(f"  HelpCount: {help_before} -> {help_after} (delta={help_after - help_before:+d})")

p(f"\n{'='*60}")
p(f"SUMMARY: sent {ok_count + fail_count}, accepted={ok_count}, rejected={fail_count}")
p(f"RemainTimes: {remain_before} -> {remain_after} (delta={remain_after - remain_before:+d})")
p(f"{'='*60}")
