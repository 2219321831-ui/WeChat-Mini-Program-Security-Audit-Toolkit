#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Add ~800 steps to UserId=477320 by consuming dice (DiceThrowing)"""
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

TARGET = 477320
ACT, CUS = 2092, 3824
TARGET_STEPS = 800

p("=" * 60)
p("  DiceThrowing: +%d steps for UserId=%d" % (TARGET_STEPS, TARGET))
p("=" * 60)

# 1. Check current state
p("\n[1] Current state:")
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId": ACT, "CusId": CUS, "UserId": TARGET})
if not (isinstance(b, dict) and b.get("IsSuccess")):
    p("  Failed to get config: %s" % b)
    sys.exit(1)

d = b["Data"]
step_before = d.get("TotalStep", 0)
remain_before = d.get("RemainTimes", 0)
p("  TotalStep: %d" % step_before)
p("  RemainTimes: %d" % remain_before)
p("  Target: +%d steps (need ~%d dice at avg 3.5/die)" % (TARGET_STEPS, int(TARGET_STEPS / 3.5) + 10))

if remain_before < 10:
    p("  Not enough dice! RemainTimes=%d" % remain_before)
    sys.exit(1)

# 2. Roll dice until we've added ~800 steps
p("\n[2] Rolling dice...")
steps_gained = 0
dice_used = 0
errors = 0
step_target = step_before + TARGET_STEPS

while steps_gained < TARGET_STEPS and errors < 5:
    st, b = get("ActApi/ActivityApi/DiceThrowing", {"ActId": ACT, "UserId": TARGET, "CusId": CUS})
    if isinstance(b, dict) and b.get("IsSuccess"):
        data = b.get("Data", {}) or {}
        new_step = data.get("TotalStep", step_before + steps_gained)
        new_remain = data.get("RemainTimes", remain_before - dice_used - 1)
        gained_this = new_step - (step_before + steps_gained)
        if gained_this > 0:
            steps_gained = new_step - step_before
            dice_used += 1
        else:
            # Sometimes returns 0 gain, still consumed a die
            dice_used += 1

        if dice_used % 20 == 0:
            p("  [%3d dice] +%d steps (remain ~%d)" % (dice_used, steps_gained, new_remain))
    else:
        errors += 1
        msg = b.get("Message", b) if isinstance(b, dict) else b
        p("  Error #%d: %s" % (errors, msg))
    
    time.sleep(0.15)

# 3. Verify final state
p("\n[3] Verification:")
time.sleep(0.5)
st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId": ACT, "CusId": CUS, "UserId": TARGET})
if isinstance(b, dict) and b.get("IsSuccess"):
    d = b["Data"]
    step_after = d.get("TotalStep", 0)
    remain_after = d.get("RemainTimes", 0)
    actual_gain = step_after - step_before
    actual_consumed = remain_before - remain_after

    p("  TotalStep: %d -> %d (+%d)" % (step_before, step_after, actual_gain))
    p("  RemainTimes: %d -> %d (-%d dice consumed)" % (remain_before, remain_after, actual_consumed))
    if actual_consumed > 0:
        p("  Avg steps/die: %.2f" % (actual_gain / actual_consumed))
else:
    p("  Verification failed: %s" % b)

p("\n" + "=" * 60)
p("  Done")
p("=" * 60)
