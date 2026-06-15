# WeChat Mini-Program Security Audit Toolkit

微信小程序安全审计工具集 —— 涵盖 wxapkg 提取、漏洞挖掘、API 渗透测试、排行榜异常检测与后端基础设施发现的完整工作流。

## 项目概述

本项目是一个针对微信小程序的安全审计框架，包含从源码提取到漏洞验证的全链路工具。在一次经授权的渗透测试中，成功对目标小程序（爱迪云课堂）完成了反编译、签名算法逆向、API 未授权访问利用、排行榜数据操纵，并发现了后端管理后台和公开的 Swagger API 文档。

## 漏洞发现摘要

| 编号 | 严重等级 | 漏洞描述 |
|------|----------|----------|
| V-01 | Critical | 前端源码硬编码 API 签名密钥，可被完整逆向 |
| V-02 | Critical | 服务端全接口零鉴权（无 JWT / Session / OpenID 校验） |
| V-03 | High | 投票/助力接口未验证用户身份，可伪造任意用户助力 |
| V-04 | Medium | 机构信息遍历接口泄露 500+ 合作单位详情 |
| V-05 | Medium | 排行榜接口无鉴权暴露所有参赛用户隐私数据 |
| V-06 | Medium | 后端管理后台暴露公网，Swagger 文档完全公开（50 个端点） |
| V-07 | Low | 设备指纹算法纯客户端计算，可轻易伪造 |
| V-08 | Low | 前端泄露生产/开发/UAT 环境地址及内部密钥 |

## 项目结构

```
├── config.py                       # 集中化配置（从 .env 或环境变量加载密钥）
├── .env.example                    # 环境变量模板
├── .gitignore
├── requirements.txt
├── README.md
│
├── poc/                            # 漏洞利用 PoC 脚本
│   ├── poc_exploit.py              # 全自动利用工具（发现用户→伪造投票→验证）
│   ├── poc_help_vote.py            # 分步验证工具（支持 --verify-only 只读模式）
│   ├── test_477320.py              # 定向投票测试（50 票注入）
│   ├── test_dice.py                # 骰子操纵测试（GET/POST 对比）
│   ├── dice_1500.py                # 批量掷骰子（最多 600 次）
│   ├── add_dice_500.py             # 刷票获取骰子（1200 票→500 骰子）
│   ├── add_dice_476977.py          # 指定用户骰子注入
│   ├── test_steps.py               # 步数验证脚本
│   └── add_800steps.py             # 定向加 800 步（扣除骰子）
│
├── audit/                          # 数据审计与异常检测
│   ├── audit_rank.py               # 全量排行榜审计（含 IDOR 测试）
│   ├── audit_2users.py             # 用户对比统计分析（骰子数学验证）
│   ├── audit_477320.py             # 单账号取证分析（时间聚集/ID聚类）
│   ├── disguise_477320.py          # 数据伪装测试（归一化尝试）
│   ├── ranking_query.py            # 只读排行榜查询（GetMapConfig 遍历）
│   ├── ranking_scan.py             # 并发 UID 扫描（恢复下线排行榜）
│   └── analyze_top.py              # Top 玩家深度分析（作弊指纹检测）
│
├── recon/                          # 后端侦察与基础设施发现
│   ├── find_admin.py               # 管理面板发现（子域名枚举+路径扫描）
│   ├── fetch_admin.py              # 管理后台内容抓取
│   ├── fetch_admin2.py             # 登录端点分析+路径探测
│   └── fetch_swagger.py            # Swagger API 规范抓取（50 端点）
│
├── tools/                          # 通用工具
│   └── wxapkg_extractor.py         # wxapkg 解密解包工具（独立运行）
│
└── reports/                        # 审计报告
    ├── security_report.md          # 漏洞清单（8 项）
    ├── exploit_analysis.md         # 7 章技术分析报告
    └── attack_flow.txt             # 攻击流程图
```

## 核心工具说明

### wxapkg 提取器

独立 Python 工具，支持自动扫描微信本地缓存、解密加密包（AES-256-CBC + XOR）、解包二进制归档、提取 API 端点和检测敏感信息泄露。

```bash
pip install pycryptodome
python tools/wxapkg_extractor.py --output ./extracted
```

### PoC 利用工具

```bash
# 只读验证模式（不修改任何数据）
python poc/poc_help_vote.py --verify-only

# 完整漏洞利用（需授权）
python poc/poc_exploit.py --act <ActId> --cus <CusId> --votes 10
```

### 排行榜异常检测

GetMapRanking 接口被服务端下线后，通过并发遍历 UserId 范围 + GetMapConfig 恢复排行榜数据，分析助力数据中的作弊指纹：

- **连续 ID 对数**：>5 对提示批量伪造
- **空资料比例**：>50% 提示假用户
- **快速时间间隔**：<2 秒占比 >10% 提示自动化
- **骰子数学验证**：`TotalStep > consumed_dice × 6` 为数学不可能

```bash
python audit/ranking_scan.py   # 扫描 476000-479000 UID 范围
python audit/analyze_top.py    # Top 7 玩家深度对比
```

### 后端侦察

```bash
python recon/find_admin.py     # 子域名枚举 + 常见路径扫描
python recon/fetch_swagger.py  # 抓取 Swagger API 规范
```

## 技术要点

### API 签名算法

目标平台使用 MD5 签名机制，密钥硬编码在前端 JS 中：

```python
import hashlib, time

def sign(params, sign_key="<REDACTED>"):
    ts = str(int(time.time() * 1000))
    keys = sorted(params.keys(), key=lambda k: k.lower())
    vals = "".join(str(params[k]) for k in keys)
    raw = vals + ts + sign_key
    sign2 = hashlib.md5(raw.encode()).hexdigest().upper()
    nonce = hashlib.md5((ts + sign_key).encode()).hexdigest().upper()
    return sign2, nonce, ts

# 请求头: wxminiapisign2 / wxminiapitimespan / wxminiapitimenonce / wxminitype
```

### 发现的后端基础设施

| 地址 | IP | 用途 |
|------|-----|------|
| `wxmini.api.bjadks.com` | 101.201.199.96 | 生产 API + **管理后台登录页** |
| `base2.api.bjadks.com` | 101.201.199.96 | 日志 API + **Swagger 文档**（50 端点） |
| `login.bjadks.com` | 101.201.199.96 | 网上报告厅登录 |
| `test.bjadks.com` | 101.200.227.11 | 测试环境 |
| `demo.bjadks.com` | 123.56.155.150 | 演示站 |
| `mini.bjadks.com` | 43.141.52.49 | 小程序相关 |
| `192.168.1.110:5000` | 内网 | UAT 测试环境 |

### Swagger API 文档

`https://base2.api.bjadks.com/swagger/index.html` 完全公开，规范文件位于 `/swagger/MisApi/swagger.json`（111KB），共 50 个端点，涵盖活动统计、数据导出、机构管理、播放/访问日志、COUNTER5 报告等。认证方式为 Bearer Token。

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

大部分 PoC 和审计脚本仅使用 Python 标准库，无需额外安装。`wxapkg_extractor.py` 需要 `pycryptodome` 进行 AES 解密。

### 2. 配置环境变量

所有敏感配置通过环境变量或 `.env` 文件加载，代码中不包含任何硬编码密钥。

```bash
# 复制模板
cp .env.example .env

# 编辑 .env，填入实际值
# WXMINI_SIGN_KEY=<从前端源码提取的签名密钥>
# WXMINI_API_BASE=<API 基地址>
# WXMINI_ACT_ID=<活动 ID>
# WXMINI_CUS_ID=<机构 ID>
```

也可以通过环境变量设置：

```bash
export WXMINI_SIGN_KEY="your_key"
export WXMINI_API_BASE="https://example.com/"
export WXMINI_ACT_ID=2092
export WXMINI_CUS_ID=3824
```

### 3. 运行工具

```bash
# 只读验证签名漏洞（不修改任何数据）
python poc/poc_help_vote.py --verify-sign

# 全自动漏洞利用（需授权）
python poc/poc_exploit.py --act 2092 --cus 3824 --votes 10

# 并发扫描排行榜（恢复已下线的排名数据）
python audit/ranking_scan.py

# 后端基础设施发现
python recon/find_admin.py
```

## 免责声明

本项目仅供安全研究与授权渗透测试使用。所有 PoC 脚本必须在获得目标系统所有者书面授权后运行。未经授权的测试行为可能违反《计算机信息系统安全保护条例》及相关法律法规。使用者需自行承担法律责任。

## License

MIT License
