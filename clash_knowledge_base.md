# Clash / Mihomo / Subconverter 配置与分流知识库

> **维护版本**：2026-10-25（已合并全网分流调研报告与项目实证调研结论）
> **适用范围**：Mihomo（Clash.Meta）、兼容 Clash 的桌面/移动客户端、Subconverter 外部配置 `proxy.ini`
> **研究原则**：严格区分官方事实、实现细节、工程经验和待实测假设。版本敏感字段以目标内核实际版本的文档、配置校验和运行结果为准。

## 0. 配置设计十维检查清单

任何 Clash / Mihomo 配置优化与排障，至少检查以下 10 个维度：

1. **内核与客户端版本**：Mihomo、旧 Clash、客户端打包内核是否一致；字段是否可解析。
2. **策略组拓扑**：手动选择、自动测速、故障转移、负载均衡、业务组与自动组的层级关系及候选覆盖。
3. **规则引擎**：规则顺序、规则类型、父子域遮蔽、规则集格式、目标策略以及域名/IP 解析副作用。
4. **DNS 架构**：`fake-ip`/`redir-host`、上游 DNS、策略 DNS、节点域名解析、过滤器和泄漏边界。
5. **TUN、透明代理与嗅探**：系统接管范围、DNS 劫持、IPv4/IPv6、应用旁路和平台限制。
6. **代理协议与链路能力**：TCP/UDP/QUIC、VLESS Reality、Hysteria2、TUIC、WireGuard、前置代理和多跳。
7. **订阅转换与规则源**：Subconverter 语法、正则筛选、空组回退、远程规则格式、污染防范和来源可用性。
8. **业务分流与验证机制**：AI、流媒体、社交、开发者服务、游戏平台、国内服务的出口一致性与 Cloudflare 验证要求。
9. **性能与稳定性**：测速开销、规则规模、连接竞速、复用、MTU、失败恢复和客户端渲染。
10. **安全与分层验证**：监听面、API、密钥、日志、DNS/IP/WebRTC 泄漏、离线/内核校验和可重复 A/B 测试。

所有结论按证据强度分为四类：

- **官方事实**：可在目标版本官方文档或源码中确认。
- **实现细节**：来自当前 Mihomo 或 Subconverter 源码实现，升级后需复核。
- **工程经验**：合理的实践起点，不是普遍保证。
- **待实测假设**：必须在实际节点、网络、设备和客户端上验证。

---

## 1. 内核、客户端与配置边界

### 1.1 生态判断

- **Mihomo（Clash.Meta）**是当前 Clash 配置生态中功能最完整、维护活跃的内核之一，支持现代代理协议、复合规则、TUN、域名嗅探和 MRS 规则集。
- **Clash Premium / OpenSource Clash**属于旧生态，字段和协议能力不能与 Mihomo 等同。
- **sing-box**是独立配置体系，不能把 JSON 配置直接当作 Mihomo YAML。
- 客户端名称不等于内核版本；排障时必须记录客户端版本、实际内核名称和内核版本。

### 1.2 标准边界

- Mihomo 原生配置通常是 YAML（兼容 JSON 子集），核心入口包括全局参数、DNS、代理/代理提供者、`proxy-groups`、`rules` 和 `rule-providers`。
- Subconverter `proxy.ini` 是**转换器外部配置**，不是 Clash/Mihomo 原生配置，直接导入 Mihomo 不会生效；Subconverter `.ini` 也不能直接承载 Mihomo 原生的 `dns:`、`tun:` 等顶层 YAML 块。
- Alpha/开发分支可能包含稳定版没有的字段。生产环境优先使用稳定版；使用新协议或新字段时，先做配置校验和回滚准备。

来源：

- Mihomo 配置示例：https://github.com/MetaCubeX/mihomo/blob/Alpha/docs/config.yaml
- Mihomo 发布页：https://github.com/MetaCubeX/mihomo/releases
- Mihomo 配置总览：https://wiki.metacubex.one/config/

---

## 2. 策略组：拓扑、行为与参数

### 2.1 当前常用类型

| 类型 | 真实行为 | 适用场景 | 注意事项 |
|---|---|---|---|
| `select` | 保存并使用人工选择的代理或策略组 | 业务出口手选、主控切换 | 不会按延迟自动切换；手动固定节点仅避免测速换节点，不保证服务端出口 IP 不变 |
| `url-test` | 对候选代理做 HTTP 健康检查，优先选择健康且延迟较低者 | 自动优选出口 | 受 `tolerance`、`lazy`、失败状态影响 |
| `fallback` | 按 `proxies` 顺序选择第一个健康候选 | 主备容灾 | 全部不可用时实现可能仍回退到首项，不能当成绝对可用保证 |
| `load-balance` | 在连接级别分配到多个候选代理 | 同质节点分摊连接 | 不会把单个连接拆到多个出口；需考虑跨连接会话粘性 |

当前 Mihomo 实现支持的负载策略包括 `consistent-hashing`、`round-robin`，以及实现版本中提供的会话粘性策略。`round-robin` 可能让连续连接使用不同出口 IP；依赖出口稳定性的业务（如 AI、登录态敏感站点、Cloudflare 验证站点）应优先选择手动固定、自动优选（配较大容差）或一致性哈希。

> **重要版本边界**：当前 Mihomo 已移除 `relay` 策略组。需要前置中转时，应在具体代理节点上配置 `dialer-proxy`；多跳会增加延迟、故障点和排障成本。

### 2.2 健康检查语义

- `url` 是健康检查地址（常用 `https://www.gstatic.com/generate_204`），仅反映代理访问该 URL 的 HTTP 连通延迟，不是目标业务的解锁能力或下载带宽测试。
- `interval` 单位为秒，`timeout` 单位为毫秒，`tolerance` 单位为毫秒。
- 300–600 秒测速间隔、100–150 毫秒容差可作为偏稳定的工程起点（例如 `600,,150`），减少因瞬时抖动频繁切换出口，但不是官方固定规范。
- `lazy` 默认行为和触发时机属于实现细节；未使用的组可能延迟测速，但首次使用、拨号失败或健康检查流程仍可触发检测。
- `expected-status` 可限制健康检查接受的 HTTP 状态码，状态码不符时节点被判定为不健康。

### 2.3 两种典型策略组拓扑与取舍

1. **多级地区/协议分层拓扑**（业务组 → 主控组 → 自动/故障转移组 → 地区/协议筛选组）：
   - 适合节点数量庞大、命名规范高度统一的订阅。
   - **风险**：若每个子业务组都重复塞入十几个地区组或 `-手动` 孪生组，会导致生成配置膨胀、客户端渲染与切换变慢；当供应商更改节点命名前缀或添加国旗 emoji 时，依赖严格前缀白名单的分组极易失配为空。
2. **扁平业务直选 + 唯一自动组拓扑**（本项目当前采用）：
   - 仅保留少量独立业务 `select` 组 + 1 个全局 `url-test` 自动组，均通过 `.*` 纳入全部有效节点；业务组按特性设置默认首项（地区/解锁敏感业务默认手选节点，通用/带宽型业务默认引用自动组，微软等默认 `DIRECT`）。
   - **优势**：结构极简、客户端状态清晰，对供应商新增家族、改名和添加 emoji 具备天然免疫力。

来源：

- 策略组文档：https://wiki.metacubex.one/config/proxy-groups/
- Mihomo 策略组实现：https://github.com/MetaCubeX/mihomo/tree/Meta/adapter/outboundgroup

---

## 3. 规则引擎、排序铁律与规则集防污染

### 3.1 匹配顺序与父子域遮蔽

Mihomo 按最终生成的 `rules` 列表**自顶向下**逐条匹配，通常命中即停止（First-Match-Win）；仅在 UDP 请求遇到当前目标出站不支持 UDP 时，可能继续尝试后续规则。

**关键事实**：
- **精确规则不会自动越级**：排在后面的精确 `DOMAIN` 不会优先于排在前面的 `DOMAIN-SUFFIX` 或 `DOMAIN-KEYWORD`。
- **分节推荐顺序**：
  1. **基础直连与必要白名单**（局域网 `LocalAreaNetwork`、`UnBan`、明确的隐私页面/静态资源；普通电商整域不能前置绕过广告拦截）。
  2. **广告域拦截**（`REJECT`，同域正文与广告不能靠域名规则区分）。
  3. **专属业务分流**（AI 自有域、YouTube / TikTok / Netflix / 巴哈姆特）。
  4. **国内媒体、Apple 与确定性下载例外**，随后微软与游戏平台/推送规则。微软列表的 `akadns.net` 不能抢先捕获 Sony 下载主机。
  5. **电报、支付、论坛与 Google 例外链**（代理例外 → GoogleCN / 国内域名集合与明确补充）。
  6. **通用海外规则**（`Developer.list`、`ProxyMedia.list`、`ProxyGFWlist.list`）。
  7. **下载与国内 IPv4/IPv6 兜底**（Download、ChinaCompanyIp、ChinaIp、ChinaIpV6、`GEOIP,CN`，在此才按需解析未命中域名）。
  8. **最终兜底**（Mihomo 原生 `MATCH` / Subconverter `[]FINAL`）。

**实证遮蔽案例**：
- `GoogleCN.list` 中的 `DOMAIN-SUFFIX,crl.pki.goog`（直连）若置于 `ProxyGFWlist.list` 之后，会被后者的父域 `DOMAIN-SUFFIX,pki.goog`（代理）遮蔽；而 `GoogleCNProxyIP.list`、`services.googleapis.cn`、`xn--ngstr-lra8j.com` 等代理例外又必须置于 `GoogleCN.list` 之前。
- 游戏平台的国内内容与确定性下载 CDN（如 `SteamCN.list`、`steamserver.net`、`steampipe.akamaized.net` 及 Epic/Sony 下载域）必须置于 `Steam.list`、`Epic.list`、`Sony.list` 平台整体规则之前，否则会被整域后缀规则先行捕获走代理。

### 3.2 常用规则类型

| 类型 | 作用 |
|---|---|
| `DOMAIN` | 完整域名精确匹配 |
| `DOMAIN-SUFFIX` | 匹配域名自身及子域名（不匹配仅含该字符串的无关域名） |
| `DOMAIN-KEYWORD` | 域名包含子串即匹配（极易误伤，慎用） |
| `DOMAIN-WILDCARD` | Mihomo 支持的 `*`/`?` 通配匹配 |
| `DOMAIN-REGEX` | 域名正则匹配 |
| `IP-CIDR` / `IP-CIDR6` | 目标 IPv4/IPv6 网段 |
| `IP-SUFFIX` / `IP-ASN` | IP 后缀范围 / 目标 IP 所属自治系统号 |
| `GEOIP` / `GEOSITE` | 按目标 IP 国家代码 / Geosite 域名分类 |
| `PROCESS-NAME` | 按进程名（受平台与权限限制） |
| `DST-PORT` / `SRC-PORT` | 目标/源端口 |
| `AND` / `OR` / `NOT` | Mihomo 复合逻辑规则 |
| `RULE-SET` | 引用 `rule-providers` |
| `MATCH` | Mihomo 原生通用兜底规则 |

`GeoData` 是底层数据概念，不是名为 `GEODATA` 的路由规则类型；`geosite.dat`、`geoip.dat`、MMDB 等数据文件不能仅凭扩展名直接当作 `rule-providers`。

### 3.3 `no-resolve` 的机制与边界

`no-resolve` 仅适用于目标 IP 类规则（`IP-CIDR`、`IP-CIDR6`、`IP-ASN`、`GEOIP`），作用是当连接目标仍为域名时，**跳过为匹配该条 IP 规则而触发的本地 DNS 解析**：

```yaml
- IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
- GEOIP,CN,DIRECT,no-resolve
```

- **为什么常用**：若规则表后段的国内 IP / `GEOIP,CN` 规则未加 `no-resolve`，尚未命中前置域名规则的海外域名请求在匹配到该行时，会触发本地 DNS 解析以获取 IP，既增加首包延迟，也可能产生非预期的本地解析请求。
- **边界说明**：添加 `no-resolve` 后，尚未解析出 IP 的连接跳过该条 IP 规则；前面若已有真实 IP 则仍能匹配。不能仅看末尾 `no-resolve` 就断言请求进入 MATCH。旧版首条 `5.5.5.5/32` 无该参数，会提前解析域名；当前首条改为 no-resolve，并在通用海外规则之后用 `GEOIP,CN` 按需解析长尾请求。正常 fake-ip 映射会恢复 Host 并清空伪 DstIP，不等于无法执行国内 IP 判断。该取舍依赖客户端 DNS 配置，不能据此承诺 DNS 无污染或无泄露。

### 3.4 `MATCH`、`FINAL` 与 `[]`

- Mihomo 原生主配置通用兜底使用 `MATCH,策略组`。
- `FINAL` 是 Subconverter 输入规则或 Surge 兼容语法，经 Subconverter 转换后在 Clash/Mihomo YAML 中生成 `MATCH`。
- `[]DIRECT`、`[]REJECT`、`[]DOMAIN`、`[]GEOIP`、`[]FINAL` 是 Subconverter `proxy.ini` 的内联规则语法，不能直接写入 Mihomo 原生 YAML 的 `rules:`。

### 3.5 Rule Provider（Mihomo 原生）

```yaml
rule-providers:
  apple:
    type: http
    url: https://example.com/apple.list
    path: ./rules/apple.list
    interval: 86400
    behavior: classical
    format: text
    proxy: DIRECT
```

- `type`：`http`、`file`、`inline`。
- `behavior`：`domain`、`ipcidr`、`classical`（描述规则内容类别）。
- `format`：`yaml`、`text`、`mrs`（描述容器编码格式；`mrs` 仅适用于 `domain` 和 `ipcidr`，与 `classical` 不兼容）。

### 3.6 第三方规则源选型与防污染实证

主流开源规则项目各有侧重，引入前必须审查远程文件正文：

| 规则源仓库 | 特点与适用场景 | 实测风险与避坑要点 |
|---|---|---|
| `ACL4SSR/ACL4SSR` | 经典 Clash 分流片段，适合局域网、国内域名/IP、主流流媒体、基础去广告（`BanProgramAD.list`） | `ProxyMedia.list` 含 `challenges.cloudflare.com`；`AI.list` 与媒体规则高度重叠 |
| `blackmatrix7/ios_rule_script` | 提供细分平台集合，当前按需使用字节、阿里与 PayPal 源 | `OpenAI.list` 实含 auth0/Stripe/共享遥测和 ASN 20473；`China.list` 含 ms/in.th 整后缀；不能将列表名称当作纯净性证据 |
| `MetaCubeX/meta-rules-dat` | Mihomo 官方维护的 GeoSite/GeoIP/MRS 数据，适合原生 `GEOSITE` 或 `mrs` provider | 需目标内核与客户端数据文件同步更新 |
| `uklans/cache-domains` | 社区维护的 LAN 缓存确定性下载 CDN 清单（Steam/Epic/Sony 等，MIT 许可） | 仅代表下载/缓存 CDN 域名用途，不包含商店/登录主域；复用须保留 MIT 版权声明 |

**防污染工程准则**：
1. **拒绝盲目整份引入宽泛 AI 列表**：当前自维护产品自有域与专用主机，使用带起止边界的内联 DOMAIN-REGEX 合并。共享 `auth0.com`、`stripe.com`、`www.bing.com`、`apis.google.com` 不归 AI；Copilot 使用 githubcopilot.com 全子域，并覆盖官方个人/商业/企业接口。
2. **解耦通用验证域名**：在 `ProxyMedia.list` 之前将 `challenges.cloudflare.com` 显式指向默认海外出口（`🐟 漏网之鱼`），防止非媒体站点触发 Cloudflare 验证时跨出口失败。
3. **控制广告源规模与格式**：超大型广告列表（如 REIJI `adblock_reject.txt` 约 595k 条 `payload:` YAML）不仅未获 Subconverter 默认 `surge` 格式解析保证，且常拦截 `statsig`、`featuregates`、`segment` 等功能开关域名导致正常业务异常；优先使用轻量可验证的 `BanProgramAD.list`。

来源：

- 规则文档：https://wiki.metacubex.one/config/rules/
- Rule Providers：https://wiki.metacubex.one/config/rule-providers/
- Meta 规则数据：https://github.com/MetaCubeX/meta-rules-dat
- blackmatrix7：https://github.com/blackmatrix7/ios_rule_script
- ACL4SSR：https://github.com/ACL4SSR/ACL4SSR
- uklans/cache-domains：https://github.com/uklans/cache-domains

---

## 4. DNS：能力、边界与防泄漏

### 4.1 `fake-ip` 与 `redir-host`

- **`fake-ip`**：本地发起 DNS 请求时，Mihomo 立即从虚拟地址池（默认 `198.18.0.0/16`）返回 Fake-IP 并维护映射表；连接经代理出站时将还原后的域名发往远端代理解析，可显著降低本地等待延迟并减少部分系统 DNS 污染。
- **`redir-host`**：等待并返回真实解析得到的 IP，仍是官方合法的默认模式。
- **防泄漏边界**：开启 `fake-ip` 不能单独保证“绝对无本地 DNS 泄漏”。实际行为仍受 `fake-ip-filter`（命中域名会回退真实解析）、节点服务器域名解析、直连规则解析、浏览器/应用自带 DoH/DoT、Android Private DNS、IPv6 及 TUN 劫持范围影响。

### 4.2 关键 DNS 字段

| 字段 | 主要职责 |
|---|---|
| `default-nameserver` | 解析加密 DNS 上游服务器自身域名；必须使用可直达的纯 IP |
| `nameserver` | 普通域名常规解析上游 |
| `fallback` | 后备 DNS 上游，配合 `fallback-filter` 使用 |
| `nameserver-policy` | 按域名/通配符/GEOSITE 指定 DNS 上游，优先级高于 `nameserver` |
| `proxy-server-nameserver` | 专门解析代理节点自身的服务器域名 |
| `proxy-server-nameserver-policy` | 为特定代理节点域名指定专用 DNS 策略 |
| `fake-ip-filter` | 指定跳过 Fake-IP、直接返回真实 IP 的域名（如局域网、NTP、STUN、游戏连通性探测域） |
| `respect-rules` | 让 Mihomo 自身发出的 DNS 请求遵守路由规则（启用时必须配置 `proxy-server-nameserver` 防止死锁） |

### 4.3 DNS 劫持与验证原则

- `dns-hijack` 中写 `any:53` 默认仅按 UDP 处理；如需同时劫持 TCP 53，应显式配置 `tcp://any:53`。
- `dns-hijack` 只对已被 TUN/透明代理接管的传统 53 端口流量生效，无法直接解密拦截应用内建的 DoH/DoT。
- 验证 DNS 时需分别测试：系统代理模式与 TUN 模式、IPv4 与 IPv6、浏览器安全 DNS（DoH）开关、UDP/TCP 53、WebRTC 以及客户端连接面板中的 `dns` 出站记录。

来源：

- DNS：https://wiki.metacubex.one/config/dns/
- TUN：https://wiki.metacubex.one/config/inbound/tun/
- Sniffer：https://wiki.metacubex.one/config/sniff/

---

## 5. TUN 与 Sniffer

### 5.1 TUN

```yaml
tun:
  enable: true
  stack: mixed
  dns-hijack:
    - any:53
    - tcp://any:53
  auto-route: true
  auto-detect-interface: true
  strict-route: true
```

- `stack` 可选 `system`、`gvisor`、`mixed`；不同操作系统版本、防火墙与网卡驱动下的吞吐及兼容性需实测确认，不宜绝对化。
- `auto-route` 自动配置系统路由表，但不保证虚拟机、容器、绑定特定物理网卡的程序或自定义路由全部被接管。
- `strict-route` 可减少部分多网卡旁路泄漏，但可能影响 VirtualBox / VMware / WSL 等虚拟网络桥接。

### 5.2 Sniffer（域名嗅探）

Mihomo 支持对 HTTP、TLS（SNI）、QUIC 流量进行域名嗅探。当客户端直接向 IP（或 Fake-IP 映射丢失后的地址）发起连接时，Sniffer 可辅助还原目标域名以匹配域名规则；但对启用 ECH（Encrypted Client Hello）、非标准协议、未覆盖端口或纯 IP 通信无能为力。

---

## 6. 代理协议与链路选择

### 6.1 选型原则

| 需求场景 | 可优先研究 | 主要代价与前提 |
|---|---|---|
| 通用兼容与穿透 | VMess (WS/TLS)、Trojan、VLESS (TCP/WS)、Shadowsocks | 弱网或高丢包下 TCP 队头阻塞明显 |
| 抗特征识别与直连稳定 | VLESS Reality (Vision) | 依赖服务端证书/SNI/ShortID 严格匹配 |
| 高吞吐与弱网 UDP 加速 | Hysteria2、TUIC | 依赖全链路 UDP 畅通；受运营商 QoS/UDP 限速影响大 |
| 异地组网与网段路由 | WireGuard | 属于三层隧道体系，MTU 与路由管理复杂 |
| 链式前置落地 | 节点级 `dialer-proxy` | 增加首包延迟、故障点与排障复杂度 |

### 6.2 重要边界

- 节点配置 `udp: true` 仅代表客户端允许转发 UDP，不代表服务端、中间链路、NAT 和防火墙全链路支持 UDP。
- 严禁将 `skip-cert-verify: true` 作为长期修复手段；TLS/Reality 握手失败应排查服务端配置、系统时间或本地中间人干扰。
- TUIC 0-RTT（`reduce-rtt`）存在重放风险，对交易、认证等非幂等业务不应盲目开启。

来源：

- 代理总览：https://wiki.metacubex.one/config/proxies/
- VLESS：https://wiki.metacubex.one/config/proxies/vless/
- Hysteria2：https://wiki.metacubex.one/config/proxies/hysteria2/
- TUIC：https://wiki.metacubex.one/config/proxies/tuic/

---

## 7. Subconverter `proxy.ini` 规范与源码级边界

### 7.1 核心语法

1. **策略组定义（`custom_proxy_group`）**：
   - `select`（手动选择）：
     `custom_proxy_group=组名`select`[]引用组或内置目标`节点名称正则...`
   - `url-test` / `fallback`（自动测速 / 故障转移）：
     `custom_proxy_group=组名`url-test`节点名称正则`测速URL`interval[,timeout][,tolerance]`
     *注：尾字段为三段式（间隔秒、超时毫秒、容差毫秒）。若仅设 600 秒间隔与 150 毫秒容差，必须保留中间空位写为 `600,,150`（依据官方 `pref.example.ini` 与 v0.9.0 输出核实）。*
   - `load-balance`（负载均衡）：
     `custom_proxy_group=组名`load-balance`节点名称正则`测速URL`interval[,timeout][,tolerance]`策略(consistent-hashing|round-robin)`
   - **反引号分隔符**：`select` 通常有 2 个反引号，`url-test`/`fallback` 通常有 4 个，`load-balance` 通常有 4–5 个；不能用“反引号总数必须为偶数”判断语法合法性。

2. **规则集定义（`ruleset`）**：
   - **内联单条规则**：`ruleset=目标策略组,[]规则类型,参数[,附加参数]`（如 `ruleset=DIRECT,[]GEOIP,CN,no-resolve`、`ruleset=🐟 漏网之鱼,[]FINAL`）。
   - **远程规则列表**：`ruleset=目标策略组,[type:]URL[,interval]`。未指定 `type:` 时默认按 `surge` 规则集格式解析（兼容常见 `DOMAIN`/`DOMAIN-SUFFIX`/`IP-CIDR` 文本行）。
   - **生成控制开关**：`enable_rule_generator=true` 与 `overwrite_original_rules=true` 必须同时开启，转换器才会用当前 `.ini` 的规则覆盖原订阅规则。

### 7.2 源码级转换行为与避坑指南

- **无节点空分组自动补 `DIRECT`（官方源码实现）**：
  Subconverter 在导出 Clash 策略组时，若某个分组既无 provider 且正则未匹配到任何节点，会自动向该组填入 `DIRECT`（见 `src/generator/config/subexport.cpp#L643-L654`）。因此“配置转换不报错、分组引用完整”绝不等于“分组内有可用节点”，必须用真实或代表性节点名校验匹配结果。
- **正则匹配对象与大小写敏感**：
  - 筛选器默认采用 C++ `std::regex`（ECMAScript 语法）且**区分大小写**。
  - 正则直接匹配订阅解码后的**完整节点显示名**（包含前缀国旗 emoji、空格与中文）。若供应商为节点加上国旗 emoji（如 `🇳🇱 NL-...`），紧贴行首的 `^NL-` 会全部落空；若节点在原始订阅中缺失名称片段，任何名称正则都无法选中它。
  - 使用 `.*` 全选可避免供应商改名或换家族造成空组；若需按关键词匹配，应避免裸写 `AI`（会误匹配 `TAIWAN`、`MAINLAND`、`EMAIL`）或 `[^-]日` 等过宽表达式。
- **`exclude_remarks=` 空值陷阱**：
  在本地运行 Subconverter 或构造转换参数时，若保留空的 `exclude_remarks=`，转换器会将其按空正则处理从而匹配并**排除所有节点**；需要禁用排除过滤时，应删除该配置项或填入不会命中正常名称的表达式。
- **远程规则格式兼容性**：
  HTTP 返回 200 不代表内容可被正确导入。例如带 `payload:` 顶层键的 Clash YAML 规则集在未声明类型时，Subconverter 默认按 `surge` 行格式解析可能失效或产生异常规则。v0.9.0 远程输入的 IP-ASN、URL-REGEX、DOMAIN-REGEX 会被目标类型过滤；内联 `[]DOMAIN-REGEX` 则透传，由 Mihomo 解析。
- **数量限制**：v0.9.0 默认 TOML 的 `max_allowed_rulesets=64` 统计每条 ruleset 指令（含内联）。当前通过同策略边界正则合并至 62 条；正则不得包含逗号或 INI 的 `\\n` / `\\r` / `\\t` 字面转义，仅使用 `a-z0-9-.()|^$\` 避免 `yaml-cpp` 引号包裹。展开总规则还受独立 `max_allowed_rules` 限制，必须确认最终 MATCH 保留并比较完整输出，不能只核对 URL 数量。

来源：

- Subconverter 仓库与文档：https://github.com/tindy2013/subconverter/blob/master/README-cn.md
- Subconverter 空分组处理源码：https://github.com/tindy2013/subconverter/blob/a0d4eab28cb8b6c782d4ce5c3a918de4829b4a72/src/generator/config/subexport.cpp#L643-L654

---

## 8. 业务分流与 Cloudflare 验证排查

### 8.1 核心业务分流原则

- **AI 服务（OpenAI / Claude / Gemini / Copilot / Perplexity / Grok）**：对出口地区与会话 IP 稳定性要求极高，默认应由用户手选固定节点，避免因测速波动或轮询频繁切换出口 IP。
- **Netflix / TikTok / 区域流媒体**：解锁取决于出口 IP 归属地、原生/家宽属性及服务端解锁策略，测速延迟低不代表能解锁，默认以手选节点为主。
- **YouTube / 通用海外访问**：重点关注带宽与可用性，可默认引用低频高容差（`600,,150`）的 `♻️ 自动选择` 组。
- **国内服务与 Apple**：固定 `DIRECT` 直连，并置于宽泛海外规则（`Developer.list`、`ProxyMedia.list`、`ProxyGFWlist.list`）之前，避免国内流量绕行代理。
- **游戏平台与消息推送**：
  - 将确定性的国内内容与大文件下载 CDN（`SteamCN.list`、`steamserver.net`、`steampipe.akamaized.net` 及 `uklans/cache-domains` 确证的 Epic/Sony 下载域）置前 `DIRECT` 直连；
  - 将商店、社区、登录与 Google FCM 推送（`Steam.list`、`Epic.list`、`Sony.list`、`GoogleFCM.list`，含 FCM 的 IP 规则）交由 `🐟 漏网之鱼` 代理，避免锁死直连导致商店打不开或推送断连。

### 8.2 Cloudflare 验证（Managed Challenge / Turnstile）机制与排查

验证码故障应结合实际会话、网络与站点响应判断，不能根据策略组名称断言验证必然成功：

1. **核对原始请求与挑战资源的实际出口**：
   当前配置不保证业务组与 `challenges.cloudflare.com` 使用同一节点。排查时可让两者临时使用同一稳定出口做单变量对照，但不能把所有 Turnstile 或跨域挑战请求概括为“不同出口必然失效”。
   - **配置侧处理**：在 `ProxyMedia.list` 前单列通用挑战资源，避免被绑定到媒体组；实际故障须通过客户端连接与浏览器响应核实。
2. **代理入口（“套 CDN”）与真实出口 IP 的区别**：
   节点名称中的“CDN / 家宽 / 原生解锁”通常只描述客户端到代理入口的中转方式或命名标签，不决定目标网站看到的落地出口 IP；即使客户端固定手选同一节点，部分供应商后端仍可能动态轮换出口 IP。
3. **标准单变量排查流程**：
   - 保持同一浏览器、同一站点、同一隐私/扩展设置，每次仅调整一个变量；
   - 先将 `🤖 AI服务`、`🌍 国外媒体`、`🐟 漏网之鱼` 临时选为同一个实测稳定的节点，排除分流规则导致的跨出口问题；
   - 核查出口 IP 是否被多人高频共享触发信誉风控、浏览器是否拦截了挑战脚本或隐私通行证（Privacy Pass）Token。

来源：

- Cloudflare Challenges 工作原理：https://developers.cloudflare.com/cloudflare-challenges/concepts/how-challenges-work/
- Cloudflare 故障排查：https://developers.cloudflare.com/cloudflare-challenges/troubleshooting/
- Challenge Solve Issues：https://developers.cloudflare.com/cloudflare-challenges/troubleshooting/challenge-solve-issues/

---

## 9. 性能、稳定性与安全

### 9.1 性能字段辨析

- `tcp-concurrent`：对 DNS 返回的多个目标 IP 并发发起 TCP 握手，采用最先建立的连接；主要优化首连等待，不属于连接复用。
- TCP Keep Alive：探测并维持空闲 TCP 连接。
- `smux` / multiplex：在单条底层传输连接上多路复用多个流，与 `tcp-concurrent` 机制不同。

### 9.2 控制面与凭据安全

- `allow-lan: true` 允许局域网设备接入代理端口，开启时应配合 `bind-address` 与系统防火墙。
- `external-controller` 为高权限 REST API，应绑定 `127.0.0.1` 回环地址并设置 `secret`，严禁直接暴露公网。
- **脱敏铁律**：订阅链接、节点真实服务器 IP/端口、UUID、密码、Reality 私钥、API secret 严禁写入公开仓库、配置注释、测试夹具或报告。

### 9.3 IPv6 边界

`ipv6: false` 仅控制内核相关解析或入站行为，不能替代系统网卡、路由器 RA、WebRTC 与应用自带 DoH 的 IPv6 检查；开启 IPv6 时则必须验证 AAAA 流量是否同样命中预期分流规则与出口。

---

## 10. 订阅解码与四层可重复验证体系

### 10.1 订阅链接解码规范（内存脱敏）

- `vmess://`：载荷为 **URL-safe Base64** 编码的 JSON，必须使用 `base64.urlsafe_b64decode`（补齐 `=` padding 后解码），节点显示名取 JSON 中的 `ps` 字段。
- `vless://` / `trojan://` / `ss://`：节点显示名通常位于 URL 末尾 `#fragment`，必须使用 `urllib.parse.unquote` 解码，并完整保留其中的 UTF-8 国旗 emoji、空格与中文字符。
- 解码后应先核对节点总条数，防止终端或日志截断长文本导致漏算。

### 10.2 四层验证矩阵

| 验证层级 | 验证工具与方法 | 能证明什么 | 不能证明什么 |
|---|---|---|---|
| **1. 离线静态与集合回归** | 运行 `py -3 -B scripts/test/test_proxy_ini.py` | 策略组定义、无空组、默认首项、无循环引用、规则去重、关键父子域与防污染顺序契约 | 远程 URL 当前可达性、Subconverter 实际导出、目标内核兼容性 |
| **2. 本地转换校验** | 回环地址运行 Subconverter 转换合成节点 | `.ini` 语法、正则在 C++ `std::regex` 下的实际分组结果、远程规则拉取与展开后首命中 | 真实订阅节点连通性与业务解锁 |
| **3. 内核语法校验** | `MIHOMO_BIN` 验证分组及全部内联规则；`verify_proxy_ini.py --mihomo-bin` 可验证完整规则，搭配 `--subconverter-bin` 验证真正转换的 YAML | 目标版本对分组、正则、IP/进程等完整规则语法的接受情况 | DNS/TUN 接管、真实出口、域名归属与业务可用性 |
| **4. 真实客户端与业务 A/B** | 客户端连接面板 + 目标站点同条件单变量对照 | 规则实际命中、DNS/TUN 接管、出口 IP 稳定性、AI/流媒体/Cloudflare 真实可用性 | 未来供应商后端路由变更后的持续可用性 |

**内核校验工程要点**：
- Windows 命令行参数存在约 32KB 长度上限（`WinError 206`），节点较多时不可使用内联参数，必须写入独立临时目录的 UTF-8 文件并通过 `-t -d <目录> -f <文件>` 校验。
- 用 Python `json.dumps` 生成 YAML 兼容配置时，必须指定 `ensure_ascii=False` 直接输出 UTF-8 字符，避免将策略组或节点名中的 emoji（非 BMP 字符）转义为 YAML 解析器不支持的 UTF-16 代理对（如 `\ud83c...`）。

---

## 11. 本项目 `proxy.ini` 当前架构与维护入口（2026-11-18）

### 11.1 策略组

保留 10 个业务手动组与 1 个自动组，全部按 `.*` 选择具名节点。AI、社区论坛、加密与支付、TikTok、国外媒体、奈飞默认首节点；电报、油管、漏网默认自动；微软默认 DIRECT。自动组仍为 gstatic / `600,,150`。手选与测速均不保证地区、IP 信誉或业务解锁。

### 11.2 规则与验证

- 62 条 ruleset 指令（含 41 个远程列表），兼容默认 64 条限制；部分同策略例外合并为 Mihomo DOMAIN-REGEX。只支持 Subconverter + Mihomo，不承诺旧 Clash 内核兼容。
- AI 自有域与专用主机自维护，移除共享 Auth0/Stripe、通用 Google 账号/API、遥测与云 ASN 污染；覆盖 Google Gemini / AI Studio / DeepMind / NotebookLM / Jules / Labs / Opal 的内部 `-pa` 接口，覆盖 Antigravity（自有域、Unleash、更新器、`cloudcode-pa` 含 daily/sandbox、`cloudaicompanion`、`aicode`/`aida` 及企业版 `businessaicode`/`aiplatform`/`discoveryengine` 官方端点），并覆盖 OpenAI、Claude、Copilot、Cursor、Windsurf、Perplexity、xAI（含 `grok.x.com`）等主流 AI 域。
- 电商普通整域在广告之后直连；前置精确业务白名单与 OpenXLab 等关键词误伤例外。广告域指向 REJECT，不能承诺清除同域广告。
- 社区、Bybit 地区 API/WS、Wise 旧域有明确例外；国内域名集合保留可用远程链接，移除含 ms/in.th 整后缀的 China.list，辅以国内应用/游戏/银行明确域名。
- 末段国内 GEOIP 解析兜底与 ChinaIpV6，避免前置特殊 IP 规则触发全局 DNS 解析；效果受客户端 DNS 与接管影响。
- 离线入口：`py -3 -B scripts/test/test_proxy_ini.py`。`MIHOMO_BIN` 可附加验证全部内联规则语法。
- 远程/转换入口：`py -3 -B scripts/test/verify_proxy_ini.py`，可传 `--snapshot <临时JSON>`、`--subconverter-bin <exe>`、`--mihomo-bin <exe>`。公开列表必须全量成功，验证首命中与共享域负例，报告不支持类型；本地转换仅用回环合成节点，比较完整输出并检查最终 MATCH，再用内核校验真实 YAML。
- 真实订阅、客户端 DNS/TUN、节点出口及业务可用性均为独立验证层；无需把大体积列表快照或临时程序提交仓库。

---

## 12. 主要来源索引

- Mihomo 文档总览：https://wiki.metacubex.one/config/
- Mihomo 源码仓库：https://github.com/MetaCubeX/mihomo
- Mihomo 规则文档：https://wiki.metacubex.one/config/rules/
- Mihomo Rule Providers：https://wiki.metacubex.one/config/rule-providers/
- Mihomo 策略组文档：https://wiki.metacubex.one/config/proxy-groups/
- Mihomo DNS 文档：https://wiki.metacubex.one/config/dns/
- Mihomo TUN 文档：https://wiki.metacubex.one/config/inbound/tun/
- Mihomo Sniffer 文档：https://wiki.metacubex.one/config/sniff/
- Mihomo 代理协议文档：https://wiki.metacubex.one/config/proxies/
- Subconverter 仓库：https://github.com/tindy2013/subconverter
- ACL4SSR 规则仓库：https://github.com/ACL4SSR/ACL4SSR
- blackmatrix7 规则仓库：https://github.com/blackmatrix7/ios_rule_script
- uklans/cache-domains 仓库：https://github.com/uklans/cache-domains
- Cloudflare Challenges 文档：https://developers.cloudflare.com/cloudflare-challenges/
- BrowserLeaks DNS 测试：https://browserleaks.com/dns
- IPLeak 测试：https://ipleak.net/
