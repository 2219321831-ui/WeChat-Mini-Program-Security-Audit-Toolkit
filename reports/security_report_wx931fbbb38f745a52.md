## 微信小程序安全测试报告

**目标小程序:** 爱迪云课堂 (wx931fbbb38f745a52)  
**所属机构:** 江西旅游商贸职业学院  
**测试时间:** 2026-06-15  
**测试方式:** 授权渗透测试  
**API 基地址:** https://wxmini.api.bjadks.com/

---

## 漏洞概要

本次测试通过逆向分析小程序前端源码，发现 API 签名密钥硬编码、无会话认证机制等多个安全缺陷，攻击者可利用这些漏洞伪造 API 请求、操纵活动投票/助力数据、枚举所有合作机构信息。

---

## V-01: 硬编码 API 签名密钥 (严重)

**漏洞位置:** 前端源码 `common/config.js`

小程序前端硬编码了 API 签名密钥：

```
signKey = "<REDACTED>"
```

攻击者可通过反编译小程序包（wxapkg）直接获取该密钥，完整复现签名算法：

```
1. 将请求参数的 key 按字母排序 (不区分大小写)
2. 按排序后的 key 顺序取 value 拼接
3. 拼接: values + timestamp(毫秒) + signKey
4. MD5 -> 大写 -> wxminiapisign2 请求头
5. MD5(timestamp + signKey) -> 大写 -> wxminiapitimenonce 请求头
```

**验证结果:** 使用复现的签名算法向生产 API 发送请求，服务端返回 HTTP 200 和业务级别响应（非签名错误），证明伪造签名被完全接受。

**影响:** 攻击者可构造任意合法签名的 API 请求，绕过客户端签名保护。

---

## V-02: 无会话认证机制 (严重)

**漏洞位置:** 全部 API 端点

所有 API 请求仅通过 MD5 签名头进行验证，不存在以下认证机制：

- 无 JWT / Bearer Token
- 无 Session Cookie
- 无 OAuth 令牌
- 无 OpenID 校验

用户 ID (`userId`) 仅以明文参数形式传递，服务端不验证请求者身份。

**验证结果:**
- `GetHelpInfo` 接口：无需登录即可查询任意用户的助力数据 (HTTP 200, IsSuccess=true)
- `GetActivityDetailsV2` 接口：可查询任意活动详情
- `GetCompanysByActId` 接口：可枚举所有合作机构
- `GetActivityList` 接口：可列出任意机构的所有活动

**影响:** 攻击者无需任何用户凭证，即可调用所有 API 端点。

---

## V-03: 助力/投票请求可伪造 (高危)

**漏洞位置:** `POST BaseApi/BaseApi/UserHelp`

助力接口接受以下参数：

```json
{
    "ShareUserId": "<被助力者ID>",
    "HelpUserId": "<助力者ID>",
    "ActId": "<活动ID>",
    "CusId": "<机构ID>"
}
```

服务端仅校验签名合法性，不验证 `HelpUserId` 是否对应真实微信用户（无 openid/session_key 校验）。每次请求使用随机生成的数字 UserId 作为 HelpUserId，即可绕过"同一用户只能助力一次"的限制。

**验证结果（已确认）：**
- 活动参数：ActId=2092, CusId=3824（"江西旅游商贸职业学院"，活动时间 2026-06-15 ~ 2026-06-19，状态 ACTIVE）
- 通过 GetMapRank 排行榜接口泄露了 10 个真实用户的 UserId、昵称、头像
- 使用伪造的 HelpUserId（随机 6 位数字）向 4 个真实用户发送助力请求
- 服务端返回 `IsSuccess: true` + "恭喜你获得了10次掷骰子的机会"
- 助力前后 HelpCount 对比：

| 目标用户 | 助力前 | 助力后 | 增加 |
|----------|--------|--------|------|
| 476964 (Rank 1) | 129 | 133 | +4 |
| 476832 (Rank 2) | 77 | 78 | +1 |
| 476836 (Rank 3) | 63 | 67 | +4 |
| 477320 (Rank 4) | 101 | 102 | +1 |

- 排行榜 BeHelpCount 同步更新，证明伪造助力已写入数据库
- 整个攻击过程无需微信登录、无需 Session、无需 OpenID

---

## V-04: 合作机构信息枚举 (中危)

**漏洞位置:** `GET ActApi/ActivityApi/GetCompanysByActId`

通过遍历 ActId（1~3000+），可枚举该平台所有合作机构的完整信息：

- CusId（机构编号）
- CusName（机构名称，如天津大学、江西省图书馆等）
- CusCode（机构代码，如 tjdx、jxstsg）
- CreateTime / UpdateTime

**验证结果:** 成功扫描到 500+ 个机构的完整信息，包括目标机构"江西旅游商贸职业学院"（CusId=1115 和 CusId=3824）。

---

## V-05: 设备指纹可伪造 (低危)

**漏洞位置:** 前端 `subpackages/game/pages/help.vue`

设备指纹算法为 `MD5("{userId}adks_device{model}")`，完全在客户端计算。攻击者可随机生成不同 userId + model 组合，产生不同的设备指纹，绕过"同一设备只能助力一次"的前端限制。

---

## V-06: 前端敏感信息泄露 (低危)

前端源码中包含以下敏感信息：

- 生产/开发/UAT 环境 API 地址
- API 签名密钥 (`<REDACTED>`)
- 反馈密钥 (`<REDACTED>`)
- 禁用机构列表 (`disablecus.list: [1, 672]`)
- 试用机构 ID (`tryOutId.adks: 672`)

---

## V-07: 排行榜接口泄露用户隐私 (中危)

**漏洞位置:** `GET ActApi/ActivityApi/GetMapRank`

排行榜接口无需认证即可返回所有参与用户的完整信息，包括：

- UserId（用户内部 ID）
- Nickname（微信昵称）
- CoverImg（微信头像 URL，含 OSS 存储地址）
- TotalSteps（步数/积分）
- BeHelpCount（被助力次数）
- ViewTotalTimes（观看时长）

**验证结果:** 通过该接口获取了江西旅游商贸职业学院活动全部 10 名参与用户的真实 UserId、昵称和头像 URL。这些 UserId 随后被用于成功的助力伪造攻击。

---

## 攻击路径（已实测验证）

```
1. 反编译 wxapkg -> 获取 signKey "<REDACTED>"
2. 复现签名算法 -> MD5(sorted_values + timestamp_ms + signKey).toUpperCase()
3. 调用 GetCompanysByActId -> 枚举 ActId 1~3000, 发现目标 CusId=3824
4. 调用 GetActivityList(CusId=3824) -> 确认 ActId=2092 活动进行中
5. 调用 GetMapRank(ActId=2092) -> 获取排行榜中 10 个真实用户 UserId
6. 调用 UserHelp(ShareUserId=真实用户, HelpUserId=随机数字)
7. 服务端返回 IsSuccess=true -> 助力计数增加, 排行榜同步更新
8. 循环步骤 6 -> 无限刷助力, 操纵排行榜排名
```

---

## PoC 工具使用说明

提供的 PoC 工具 (`poc_help_vote.py`) 支持三种模式：

**模式 1: 签名验证（只读，证明签名可伪造）**
```
py -X utf8 poc_help_vote.py --verify-sign
```

**模式 2: 自动探测当前活动**
```
py -X utf8 poc_help_vote.py --discover
```

**模式 3: 完整投票测试（需要已报名用户的 UserId）**
```
py -X utf8 poc_help_vote.py --act 2092 --cus 3824 --target <userId> --count 5
```

**依赖:** Python 3.6+ (仅使用标准库，无需额外安装)

**当前活动参数:**
- ActId: 2092
- CusId: 3824
- 活动名称: 江西旅游商贸职业学院
- 活动时间: 2026-06-15 ~ 2026-06-19
- 状态: 进行中

---

## 修复建议

1. **签名密钥移至服务端:** signKey 不应出现在前端代码中，建议由服务端直接完成签名校验，或使用非对称加密（如 RSA/HMAC-SHA256 + 服务端私钥）。

2. **引入会话认证:** 所有 API 请求应要求有效的微信 openid/session_key 验证，或引入 JWT Token 机制。

3. **助力身份校验:** UserHelp 接口应验证 HelpUserId 对应的微信用户真实性（校验 openid），而非仅依赖客户端传入的数字 ID。

4. **频率限制:** 对助力接口实施 IP + 用户维度的频率限制。

5. **接口权限控制:** GetCompanysByActId、GetHelpInfo 等接口应限制访问权限，防止未授权枚举。

---

## 附件

- `poc_help_vote.py` — PoC 验证工具 (Python)
- `poc_report_*.json` — 自动化测试报告 (JSON)
- 本报告
