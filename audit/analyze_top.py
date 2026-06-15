#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only: deep analysis of top players - detect anomalies"""
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
    params.setdefault("version", "2.1.0")
    params.setdefault("client", "standard")
    url = API + path + "?" + urllib.parse.urlencode(params)
    s2, nc, ts = sign(params)
    h = {"User-Agent": "Mozilla/5.0", "wxminitype": "adks",
         "wxminiapisign2": s2, "wxminiapitimespan": ts, "wxminiapitimenonce": nc}
    req = urllib.request.Request(url, headers=h, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            b = r.read().decode("utf-8", "replace")
            return r.status, json.loads(b) if b.startswith("{") else b
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8", "replace"))
        except: return e.code, str(e.reason)
    except: return 0, "err"

ACT, CUS = 2092, 3824

# Top players to analyze
TOP_USERS = [477320, 476832, 477319, 476964, 476836, 477693, 477523]

p("=" * 70)
p("  Deep analysis of top 7 players (read-only)")
p("=" * 70)

for uid in TOP_USERS:
    p("\n" + "-" * 70)
    p("  UserId: %d" % uid)
    p("-" * 70)

    # GetMapConfig
    st, b = get("ActApi/ActivityApi/GetMapConfig", {"ActId": ACT, "CusId": CUS, "UserId": uid})
    if isinstance(b, dict) and b.get("IsSuccess"):
        d = b.get("Data", {})
        total_step = d.get("TotalStep", 0)
        help_total = d.get("HelpTotalTimes", 0)
        watch_video = d.get("WatchVideoTotalTimes", 0)
        remain = d.get("RemainTimes", 0)
        curr_point = d.get("CurrPoint", 0)

        p("  TotalStep: %d" % total_step)
        p("  HelpTotalTimes: %d" % help_total)
        p("  WatchVideoTotalTimes: %d" % watch_video)
        p("  RemainTimes (unused dice): %d" % remain)
        p("  CurrPoint (current position): %d" % curr_point)

        # Dice math analysis
        # Each help = 10 dice, each video = 1 dice (from rules)
        # Total dice earned = HelpTotalTimes * 10 + WatchVideoTotalTimes * 1
        total_dice_earned = help_total * 10 + watch_video
        # Dice consumed = total_dice_earned - remain
        consumed = total_dice_earned - remain
        avg_steps_per_die = total_step / consumed if consumed > 0 else 0

        p("  --- Dice Math ---")
        p("  Total dice earned (help*10 + video): %d" % total_dice_earned)
        p("  Dice consumed (earned - remain): %d" % consumed)
        p("  Avg steps per die: %.2f" % avg_steps_per_die)

        # Anomaly checks
        anomalies = []
        if avg_steps_per_die > 6:
            anomalies.append("HIGH avg steps/die (max should be ~6)")
        if avg_steps_per_die < 1 and consumed > 10:
            anomalies.append("SUSPICIOUSLY LOW avg steps/die")
        if remain > total_dice_earned * 0.8 and consumed > 50:
            anomalies.append("Most dice unused (>80%)")
        if help_total > 150 and uid != 477320:
            anomalies.append("Very high HelpTotalTimes (>150)")

        if anomalies:
            p("  !!! ANOMALIES: %s" % "; ".join(anomalies))
        else:
            p("  [OK] No obvious anomalies")

    # GetHelpInfo
    st, b = get("ActApi/ActivityApi/GetHelpInfo", {"ActId": ACT, "CusId": CUS, "UserId": uid})
    if isinstance(b, dict) and b.get("IsSuccess"):
        data = b.get("Data", {})
        hc = data.get("HelpCount", 0)
        helpers = data.get("HelpUsers", [])

        p("  HelpCount (unique helpers): %d" % hc)
        p("  Helper records: %d" % len(helpers))

        if helpers:
            # Time analysis
            times = [h.get("HelpTime", "") for h in helpers]
            times_sorted = sorted(times)

            # Count helpers with nicknames/avatars
            with_nick = sum(1 for h in helpers if h.get("NickName"))
            with_avatar = sum(1 for h in helpers if h.get("CoverImg"))

            # Time gap analysis
            from datetime import datetime
            parsed_times = []
            for t in times:
                try:
                    parsed_times.append(datetime.strptime(t, "%Y-%m-%d %H:%M:%S"))
                except:
                    pass

            if len(parsed_times) >= 2:
                parsed_times.sort()
                gaps = []
                for i in range(1, len(parsed_times)):
                    gap = (parsed_times[i] - parsed_times[i-1]).total_seconds()
                    gaps.append(gap)

                fast_gaps = sum(1 for g in gaps if g < 2)
                p("  --- Helper Analysis ---")
                p("  With nickname: %d/%d (%.0f%%)" % (with_nick, len(helpers), with_nick/len(helpers)*100))
                p("  With avatar: %d/%d (%.0f%%)" % (with_avatar, len(helpers), with_avatar/len(helpers)*100))
                p("  Time range: %s ~ %s" % (times_sorted[0], times_sorted[-1]))
                p("  Fast gaps (<2s): %d/%d (%.0f%%)" % (fast_gaps, len(gaps), fast_gaps/len(gaps)*100))

                # ID clustering analysis
                helper_ids = [h.get("HelpUserId", 0) for h in helpers]
                if helper_ids:
                    prefixes = set(str(h)[:3] for h in helper_ids if h > 0)
                    p("  Unique ID prefixes (3-digit): %d" % len(prefixes))

                    # Check for sequential IDs (sign of bot)
                    sorted_ids = sorted(set(helper_ids))
                    seq_runs = 0
                    for i in range(1, len(sorted_ids)):
                        if sorted_ids[i] == sorted_ids[i-1] + 1:
                            seq_runs += 1
                    if seq_runs > 5:
                        p("  !!! Sequential ID runs: %d pairs (bot indicator)" % seq_runs)

            # Show first 5 and last 5 helpers
            p("  --- First 5 helpers (newest) ---")
            for h in sorted(helpers, key=lambda x: x.get("HelpTime", ""), reverse=True)[:5]:
                p("    ID=%-8s Nick=%-12s Time=%s Avatar=%s" % (
                    h.get("HelpUserId"), (h.get("NickName") or "(none)")[:10],
                    h.get("HelpTime"), "Y" if h.get("CoverImg") else "N"))

    time.sleep(0.1)  # small delay between users

p("\n" + "=" * 70)
p("  Analysis complete (read-only, no data modified)")
p("=" * 70)
