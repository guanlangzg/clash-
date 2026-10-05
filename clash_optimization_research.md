# Clash 与 Subconverter 配置优化及分流知识全网调研报告

## 一、Clash / Mihomo (Clash.Meta) 核心机制与分流原理

### 1. 规则匹配流程与优先级
Clash 按照配置中的 `rules` **自顶向下** 逐条匹配，命中即停止（First-Match-Win）：
1. **本地白名单与回环直连**：私有局域网 IP/域名、局域网直连（`LocalAreaNetwork`、`DIRECT`）。
2. **广告与追踪拦截**：`REJECT` 拦截广告、追踪器、恶意软件（减少无用流量与 DNS 解析开销）。
3. **特定敏感/高要求分流**：
   - **AI 服务**（OpenAI, Claude, Gemini, Copilot 等）：需要住宅/纯净/特定地区 IP（美/日/欧等），避免串流或封号。
   - **流媒体**（Netflix, Disney+, YouTube, Spotify, TikTok, 巴哈姆特等）：对解锁和原生 IP 有专门要求。
   - **特殊应用与社交**（Telegram, Discord, 游戏平台, 微软/苹果服务）。
4. **海外代理兜底 / GFWList**：国外常用网站走代理节点。
5. **国内直连规则**：`ChinaDomain`、`ChinaMedia`、`ChinaIP`、`GEOIP,CN,no-resolve`（直连国内流量以降低延迟、节省代理流量）。
6. **最终兜底 (`MATCH` / `FINAL`)**：处理所有未匹配到的流量（通常交给 `🚀 节点选择` 或 `🐟 漏网之鱼` 策略组）。

---

## 二、DNS 防泄露与防污染最佳实践

### 1. Fake-IP 模式核心优势
- 在 `enhanced-mode: fake-ip` 下，本地发起的 DNS 请求由 Clash 立即返回 `198.18.0.0/16` 的虚拟 IP，无需等待真实 DNS 解析完成。
- 当流量到达代理节点后，由远端服务器在出站时进行真实 DNS 解析，**彻底防止本地 DNS 污染并消除客户端 DNS 泄露**。

### 2. `no-resolve` 关键机制
- **问题**：如果在规则集中出现 `IP-CIDR` 或 `GEOIP` 但未加 `no-resolve`，Clash 遇到域名请求时**必须在本地强制向 DNS 服务器发起解析获取 IP**，然后才能匹配 IP 规则。这不仅增加了几百毫秒延迟，还会导致未加密的 DNS 请求在本地泄露，甚至被运营商 DNS 劫持污染。
- **最佳实践**：所有国内 IP 规则和 GEOIP 规则末尾必须添加 `no-resolve`（如 `GEOIP,CN,DIRECT,no-resolve`）。

---

## 三、Subconverter 自定义配置文件 (`proxy.ini`) 规范与技巧

### 1. 规则集 (`ruleset`) 格式
- **内联规则**：`ruleset=策略组名,[]规则类型,参数`
  - 示例：`ruleset=🎯 全球直连,[]GEOIP,CN,no-resolve`
  - 示例：`ruleset=🐟 漏网之鱼,[]FINAL`
- **在线规则集引用**：`ruleset=策略组名,[type:]URL[,interval]`
  - 默认类型为 `surge`（兼容 Clash），也可指定 `clash-classic` 等。
  - `interval` 控制远程规则集更新周期（秒），如 `86400`（24小时）。

### 2. 策略组 (`custom_proxy_group`) 语法与类型
- **`select`（手动选择）**：
  `custom_proxy_group=组名`select`节点1`[]引用策略组2`正则匹配...`
  - 前缀带 `[]` 表示引用已有的策略组名字或保留关键字（`[]DIRECT`、`[]REJECT`）。
  - 不带 `[]` 的字符串会被当作**正则表达式**匹配订阅中的节点名称。
- **`url-test`（自动优选/测速）**：
  `custom_proxy_group=组名`url-test`节点正则`测速URL`测速间隔秒,超时毫秒,容差毫秒`
- **`fallback`（故障转移）**：
  `custom_proxy_group=组名`fallback`节点正则`测速URL`测速间隔秒,超时毫秒,容差毫秒`
- **`load-balance`（负载均衡）**：
  `custom_proxy_group=组名`load-balance`节点正则`测速URL`测速间隔秒`策略(consistent-hashing|round-robin)`

---

## 四、常见避坑指南

1. **正则误匹配**：
   - 典型错误：匹配 AI 节点使用 `AI`，会导致 `TAIWAN`（台湾）、`MAINLAND`、`EMAIL` 等名字被误当做 AI 节点。
   - 正确做法：使用边界断字或区分大小写，或指定完整关键词 `(ChatGPT|OpenAI|Claude|Gemini|GPT|Anthropic)`。
2. **策略组过度嵌套与冗余**：
   - 每个子业务策略组（如 Apple, Microsoft, Telegram）都重复塞入十几个地区组，不仅导致配置膨胀几十 KB，更会严重拖慢客户端渲染与切换。
   - 建议分层设计：业务组 -> 常用优选/主选择组 -> 具体地区/节点。
3. **上游规则源维护度**：
   - 优先选用大型社区高频维护的规则仓库：
     - `blackmatrix7/ios_rule_script`（更新频繁，分流最细）
     - `ACL4SSR/ACL4SSR`（国内经典规则集，覆盖全面）
     - `MetaCubeX/meta-rules-dat`（现代 Mihomo GeoSite 规则）
   - 避免引用长期未更新的个人小仓库，防止 404 导致转换失败。
