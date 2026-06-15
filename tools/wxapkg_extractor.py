#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
微信小程序 wxapkg 解密解包工具 (Standalone)
基于 Jaysen13/jaysenwxapkg 项目的核心逻辑移植
用法: py wxapkg_extractor.py [packages_dir] [output_dir]
"""

import os
import sys
import re
import struct
import hashlib
import json
import traceback
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import urllib.request
import urllib.error

# ==================== 常量配置 ====================
WXAPKG_FLAG = b"V1MMWX"
WXAPKG_FLAG_LEN = 6
DEFAULT_IV = b"the iv: 16 bytes"
DEFAULT_SALT = b"saltiest"
AES_KEY_SIZE = 32  # 256 bits
PBKDF2_ITERATIONS = 1000

# 默认 API 提取正则
DEFAULT_API_PATTERN = re.compile(
    r'(?:"|\')(((?:[a-zA-Z]{1,10}://|//)[^"\'/]{1,}\.([a-zA-Z]{2,})[^"\']{0,})|'
    r'((?:/|\.\./|\./)[^"\'><,;| *()(%%$^/\\\[\]][^"\'><,;|()]{1,})|'
    r'([a-zA-Z0-9_\-/]{1,}/[a-zA-Z0-9_\-/]{1,}\.(?:[a-zA-Z]{1,4}|action)(?:[\?|/][^"|\']{0,}|))|'
    r'([a-zA-Z0-9_\-]{1,}\.(?:php|asp|aspx|jsp|json|action|html|js|txt|xml)(?:\?[^"|\']{0,}|)))(?:"|\')'
)

# 默认敏感信息正则
DEFAULT_SENSITIVE_PATTERNS = {
    "手机号": re.compile(r'1[3-9]\d{9}'),
    "身份证号": re.compile(r'\b\d{17}([0-9]|X|x)\b'),
    "邮箱地址": re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,4}'),
    "AppSecret泄露": re.compile(r'(?i)\b\w*secret\b'),
    "session_key泄露": re.compile(r'(?i)\bsession_key\b'),
    "IP地址": re.compile(r'^(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])\.(?:25[0-5]|2[0-4][0-9]|1[0-9][0-9]|[1-9]?[0-9])$'),
}

# URL 过滤黑名单
DEFAULT_PREFIX_BLACKLIST = {"/pages/", "/components/", "/static/", "/uni_modules/", "uview-ui/", "uview-plus/", "/package/"}
DEFAULT_SUFFIX_BLACKLIST = {"jpg", "gif", "svg", "wxss", "wxml", "png", "js", "jpeg"}

# ==================== AES-CBC + XOR 解密 ====================
def pbkdf2_hmac_sha1(password: str, salt: bytes, iterations: int, dklen: int) -> bytes:
    """PBKDF2-HMAC-SHA1 密钥派生"""
    return hashlib.pbkdf2_hmac('sha1', password.encode('utf-8'), salt, iterations, dklen=dklen)


def is_encrypted_wxapkg(filepath: str) -> bool:
    """检查文件是否为加密的 wxapkg"""
    try:
        with open(filepath, 'rb') as f:
            header = f.read(WXAPKG_FLAG_LEN)
        return header == WXAPKG_FLAG
    except Exception:
        return False


def decrypt_wxapkg(wxid: str, encrypted_file: str, decrypted_file: str,
                   iv: bytes = DEFAULT_IV, salt: bytes = DEFAULT_SALT):
    """解密 wxapkg 文件 (AES-CBC + XOR)"""
    with open(encrypted_file, 'rb') as f:
        data = f.read()

    # 校验文件头
    flag = data[:WXAPKG_FLAG_LEN]
    if flag != WXAPKG_FLAG:
        raise ValueError(f"文件无需解密，或不是加密的wxapkg包（标识不匹配：{flag}）")

    # PBKDF2 生成 AES 密钥
    aes_key = pbkdf2_hmac_sha1(wxid, salt, PBKDF2_ITERATIONS, AES_KEY_SIZE)

    # AES-CBC 解密前 1024 字节（跳过 FLAG）
    encrypted_head = data[WXAPKG_FLAG_LEN:WXAPKG_FLAG_LEN + 1024]
    cipher = AES.new(aes_key, AES.MODE_CBC, iv=iv)
    origin_head = unpad(cipher.decrypt(encrypted_head), AES.block_size)

    # 计算 XOR 密钥
    xor_key = 0x66
    if wxid and len(wxid) >= 2:
        xor_key = ord(wxid[-2])

    # XOR 解密剩余字节
    af_data = data[WXAPKG_FLAG_LEN + 1024:]
    xor_data = bytes(b ^ xor_key for b in af_data)

    # 拼接: 前 1023 字节 + XOR 数据
    origin_data = origin_head[:1023] + xor_data

    # 写出
    os.makedirs(os.path.dirname(decrypted_file), exist_ok=True)
    with open(decrypted_file, 'wb') as f:
        f.write(origin_data)


# ==================== wxapkg 解包 ====================
def read_unit(b: bytes) -> int:
    """大端字节数组转整数"""
    length = len(b)
    if length == 1:
        return b[0] & 0xFF
    elif length == 2:
        return ((b[0] & 0xFF) << 8) | (b[1] & 0xFF)
    elif length == 4:
        return ((b[0] & 0xFF) << 24) | ((b[1] & 0xFF) << 16) | ((b[2] & 0xFF) << 8) | (b[3] & 0xFF)
    return 0


def unpack_wxapkg(wxapkg_path: str, output_path: str, thread_num: int = 5) -> int:
    """解包 wxapkg 二进制文件，返回提取的文件数量"""
    with open(wxapkg_path, 'rb') as f:
        data = f.read()

    if len(data) < 18:
        return 0

    # 校验文件头标记
    if data[0] != 0xBE or data[13] != 0xED:
        return 0

    # 读取文件数量
    file_count = read_unit(data[14:18])
    if file_count <= 0 or file_count > 100000:
        return 0

    # 解析文件索引表
    file_entries = []
    idx = 18
    for _ in range(file_count):
        if idx + 4 > len(data):
            break
        name_len = read_unit(data[idx:idx + 4])
        idx += 4
        if name_len > 10485760 or idx + name_len > len(data):
            return 0
        name = data[idx:idx + name_len].decode('utf-8', errors='replace')
        idx += name_len
        if idx + 8 > len(data):
            return 0
        offset = read_unit(data[idx:idx + 4])
        idx += 4
        size = read_unit(data[idx:idx + 4])
        idx += 4
        file_entries.append((name, offset, size))

    # 多线程提取文件
    def extract_file(name, offset, size):
        try:
            if offset + size > len(data):
                return False
            file_data = data[offset:offset + size]
            out_file = os.path.join(output_path, name.lstrip('/'))
            os.makedirs(os.path.dirname(out_file), exist_ok=True)
            with open(out_file, 'wb') as f:
                f.write(file_data)
            return True
        except Exception:
            return False

    extracted = 0
    with ThreadPoolExecutor(max_workers=thread_num) as executor:
        futures = {executor.submit(extract_file, n, o, s): n for n, o, s in file_entries}
        for future in as_completed(futures):
            if future.result():
                extracted += 1

    return extracted


# ==================== 提取 AppID ====================
def extract_wx_id(filepath: str) -> str:
    """从文件路径中提取 wx 开头的 AppID"""
    match = re.search(r'\b(wx[a-f0-9]{16})\b', filepath)
    return match.group(1) if match else "unknown_appid"


# ==================== 查询小程序信息 ====================
def query_app_info(appid: str) -> dict:
    """通过外部 API 查询小程序基本信息"""
    result = {"appid": appid, "nickName": "未知", "userName": "", "description": "", "principalName": ""}
    url = "https://kainy.cn/api/weapp/info/"
    payload = json.dumps({"appid": appid}).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST',
                                 headers={
                                     "Content-Type": "application/json;charset=utf-8",
                                     "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
                                 })
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = json.loads(resp.read().decode('utf-8'))
            if body.get("code") == 0 and body.get("data"):
                d = body["data"]
                result["nickName"] = d.get("nickname", "未知")
                result["userName"] = d.get("username", "")
                result["description"] = d.get("description", "")
                result["principalName"] = d.get("principal_name", "")
    except Exception as e:
        result["error"] = str(e)
    return result


# ==================== 信息泄露检测 ====================
def get_url_suffix(url: str) -> str:
    clean = url.split("?")[0].split("#")[0]
    idx = clean.rfind(".")
    if idx == -1 or idx == len(clean) - 1:
        return ""
    return clean[idx + 1:].lower().replace(".", "")


def info_leak_detect(output_path: str):
    """扫描解包后的文件，提取 API 和敏感信息"""
    api_results = []
    sensitive_results = []
    api_index = 1

    for root, dirs, files in os.walk(output_path):
        for fname in files:
            fpath = os.path.join(root, fname)
            rel_path = os.path.relpath(fpath, output_path)
            try:
                with open(fpath, 'r', encoding='utf-8', errors='replace') as f:
                    content = f.read()
            except Exception:
                continue

            # API 提取
            for m in DEFAULT_API_PATTERN.finditer(content):
                url = None
                for i in range(1, 6):
                    try:
                        g = m.group(i)
                        if g and g.strip():
                            url = g.strip()
                            break
                    except IndexError:
                        break
                if not url:
                    continue

                need_filter = False
                for prefix in DEFAULT_PREFIX_BLACKLIST:
                    if prefix in url:
                        need_filter = True
                        break
                if not need_filter and "?" not in url:
                    suffix = get_url_suffix(url)
                    if suffix and suffix in DEFAULT_SUFFIX_BLACKLIST:
                        need_filter = True
                if not need_filter:
                    api_results.append({"index": api_index, "file": rel_path, "api": url})
                    api_index += 1

            # 敏感信息检测
            for stype, pattern in DEFAULT_SENSITIVE_PATTERNS.items():
                for m in pattern.finditer(content):
                    sensitive_results.append({"file": rel_path, "type": stype, "content": m.group()})

    return api_results, sensitive_results


# ==================== 主流程 ====================
def process_wxapkg(wxapkg_path: str, output_base: str) -> dict:
    """处理单个 wxapkg 文件: 解密 → 解包 → 扫描"""
    result = {
        "file": wxapkg_path,
        "appid": "unknown",
        "app_info": {},
        "unpack_count": 0,
        "apis": [],
        "sensitive": [],
        "errors": []
    }

    appid = extract_wx_id(wxapkg_path)
    result["appid"] = appid

    output_dir = os.path.join(output_base, appid)
    os.makedirs(output_dir, exist_ok=True)

    # 尝试直接解包
    unpack_count = unpack_wxapkg(wxapkg_path, output_dir)

    if unpack_count == 0:
        # 可能需要解密
        if is_encrypted_wxapkg(wxapkg_path):
            temp_file = os.path.join(output_dir, "decrypted_tmp.wxapkg")
            try:
                decrypt_wxapkg(appid, wxapkg_path, temp_file)
                result["encrypted"] = True
                unpack_count = unpack_wxapkg(temp_file, output_dir)
                # 清理临时文件
                if os.path.exists(temp_file):
                    os.remove(temp_file)
            except Exception as e:
                result["errors"].append(f"AES解密失败: {e}")
        else:
            result["errors"].append("非加密wxapkg且直接解包失败")

    result["unpack_count"] = unpack_count

    if unpack_count > 0:
        # 查询小程序信息
        result["app_info"] = query_app_info(appid)
        # 信息泄露检测
        apis, sensitive = info_leak_detect(output_dir)
        result["apis"] = apis
        result["sensitive"] = sensitive

    return result


def scan_wxapkg_files(packages_base: str):
    """递归扫描所有 wxapkg 文件"""
    wxapkg_files = []
    for root, dirs, files in os.walk(packages_base):
        for f in files:
            if f.endswith('.wxapkg'):
                wxapkg_files.append(os.path.join(root, f))
    return sorted(wxapkg_files)


def main():
    # 默认路径
    default_base = os.path.join(
        os.environ.get("APPDATA", ""),
        "Tencent", "xwechat", "radium", "users"
    )

    # 输出目录
    output_base = os.path.join(os.path.dirname(os.path.abspath(__file__)), "wxapkg_output")

    if len(sys.argv) >= 2:
        default_base = sys.argv[1]
    if len(sys.argv) >= 3:
        output_base = sys.argv[2]

    print("=" * 70)
    print("  微信小程序 wxapkg 解密解包工具 (基于 jaysenwxapkg)")
    print("=" * 70)
    print(f"\n扫描目录: {default_base}")
    print(f"输出目录: {output_base}\n")

    # 扫描所有用户目录下的 packages
    all_wxapkg = []
    if os.path.isdir(default_base):
        for user_dir in os.listdir(default_base):
            pkg_dir = os.path.join(default_base, user_dir, "applet", "packages")
            if os.path.isdir(pkg_dir):
                wxapkg_files = scan_wxapkg_files(pkg_dir)
                if wxapkg_files:
                    all_wxapkg.extend(wxapkg_files)
                    print(f"  [用户 {user_dir[:8]}...] 发现 {len(wxapkg_files)} 个 wxapkg 文件")
    else:
        # 尝试直接扫描指定目录
        all_wxapkg = scan_wxapkg_files(default_base)

    if not all_wxapkg:
        print("\n未找到任何 wxapkg 文件！")
        print("请确认微信已打开过小程序，或手动指定 packages 目录路径。")
        return

    print(f"\n共发现 {len(all_wxapkg)} 个 wxapkg 文件，开始处理...\n")

    # 按 AppID 分组
    appid_groups = {}
    for f in all_wxapkg:
        appid = extract_wx_id(f)
        if appid not in appid_groups:
            appid_groups[appid] = []
        appid_groups[appid].append(f)

    print(f"共 {len(appid_groups)} 个不同的小程序:\n")

    all_results = []
    for appid, files in appid_groups.items():
        print(f"{'─' * 50}")
        print(f"AppID: {appid}")
        print(f"  文件数: {len(files)}")

        # 先查小程序信息
        app_info = query_app_info(appid)
        name = app_info.get("nickName", "未知")
        desc = app_info.get("description", "")
        principal = app_info.get("principalName", "")
        print(f"  名称: {name}")
        if principal:
            print(f"  主体: {principal}")
        if desc:
            print(f"  描述: {desc[:60]}...")

        total_files = 0
        all_apis = []
        all_sensitive = []
        errors = []

        for fpath in files:
            fname = os.path.basename(fpath)
            fsize = os.path.getsize(fpath) / 1024
            print(f"  处理: {fname} ({fsize:.1f} KB)...", end=" ")

            result = process_wxapkg(fpath, output_base)
            all_results.append(result)

            if result["unpack_count"] > 0:
                print(f"解包成功 ({result['unpack_count']} 个文件)")
                total_files += result["unpack_count"]
                all_apis.extend(result["apis"])
                all_sensitive.extend(result["sensitive"])
            else:
                err_msg = "; ".join(result["errors"]) if result["errors"] else "未知原因"
                print(f"解包失败 - {err_msg}")
                errors.extend(result["errors"])

        print(f"  汇总: 提取 {total_files} 个文件, {len(all_apis)} 个API, {len(all_sensitive)} 个敏感信息")

        if all_apis:
            print(f"\n  --- API 接口 (前20个) ---")
            for api in all_apis[:20]:
                print(f"    [{api['index']}] {api['api']}")
                print(f"         来源: {api['file']}")
            if len(all_apis) > 20:
                print(f"    ... 还有 {len(all_apis) - 20} 个接口")

        if all_sensitive:
            print(f"\n  --- 敏感信息 (前10个) ---")
            for s in all_sensitive[:10]:
                print(f"    [{s['type']}] {s['content'][:50]}")
                print(f"         来源: {s['file']}")
            if len(all_sensitive) > 10:
                print(f"    ... 还有 {len(all_sensitive) - 10} 条")

    # 输出汇总报告
    print(f"\n{'=' * 70}")
    print(f"  处理完成汇总")
    print(f"{'=' * 70}")
    total_apps = len(appid_groups)
    total_extracted = sum(r["unpack_count"] for r in all_results)
    total_apis = sum(len(r["apis"]) for r in all_results)
    total_sensitive = sum(len(r["sensitive"]) for r in all_results)
    print(f"  小程序数量: {total_apps}")
    print(f"  提取文件总数: {total_extracted}")
    print(f"  API 接口数: {total_apis}")
    print(f"  敏感信息数: {total_sensitive}")
    print(f"  输出目录: {output_base}")

    # 保存报告 JSON
    report_path = os.path.join(output_base, "report.json")
    os.makedirs(os.path.dirname(report_path), exist_ok=True)
    report = {
        "total_apps": total_apps,
        "total_files": total_extracted,
        "total_apis": total_apis,
        "total_sensitive": total_sensitive,
        "results": all_results
    }
    with open(report_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"  报告已保存: {report_path}")


if __name__ == "__main__":
    main()
