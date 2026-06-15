#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Targeted test: send 50 forged votes to UserId=477320"""
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
VOTES = 50

p(f"Target: UserId={TARGET} | ActId={ACT} CusId={CUS}")
p(f"Sending {VOTES} forged votes...")
p("")

# Before
st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
before = 0
if isinstance(b, dict) and b.get("Data"):
    before = b["Data"].get("HelpCount", 0)
p(f"HelpCount BEFORE: {before}")
p("")

ok_count = 0
fail_count = 0
for i in range(1, VOTES+1):
    helper = random.randint(100000, 999999)
    st, b = post("BaseApi/BaseApi/UserHelp", {
        "ShareUserId": TARGET, "HelpUserId": helper,
        "ActId": ACT, "CusId": CUS
    })
    ok = False
    msg = ""
    if isinstance(b, dict):
        ok = b.get("IsSuccess", False)
        msg = b.get("Message", "")[:50]
    if ok:
        ok_count += 1
    else:
        fail_count += 1
    p(f"  [{i:02d}/{VOTES}] helper={helper} -> {'OK' if ok else 'FAIL'} | {msg}")
    time.sleep(0.2)

p("")

# After
st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId":ACT,"UserId":TARGET,"CusId":CUS})
after = 0
if isinstance(b, dict) and b.get("Data"):
    after = b["Data"].get("HelpCount", 0)

p(f"HelpCount AFTER: {after}")
p(f"Delta: {before} -> {after} ({after - before:+d})")
p(f"Server accepted: {ok_count}/{VOTES}")
p(f"Server rejected: {fail_count}/{VOTES}")
