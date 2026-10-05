# Clash / Mihomo / Subconverter 配置知识库

> **维护版本**：2026-08-27
> **适用范围**：Mihomo（Clash.Meta）、兼容 Clash 的桌面/移动客户端、Subconverter `proxy.ini`
> **研究原则**：把官方事实、实现细节、工程经验和待实测假设分开记录。版本敏感字段以目标内核实际版本的文档、配置校验和运行结果为准。

## 0. 先回答：配置设计应调研哪些维度

后续任何 Clash 配置优化，至少检查以下 10 个维度：

1. **内核与客户端版本**：Mihomo、旧 Clash、客户端打包内核是否一致；字段是否可解析。
2. **策略组拓扑**：手动选择、自动测速、故障转移、负载均衡、业务组与地区组的层级关系。
3. **规则引擎**：规则顺序、规则类型、规则集格式、目标策略以及域名/IP 解析副作用。
4. **DNS 架构**：`fake-ip`/`redir-host`、上游 DNS、策略 DNS、节点域名解析、过滤器和泄漏边界。
5. **TUN、透明代理与嗅探**：系统接管范围、DNS 劫持、IPv4/IPv6、应用旁路和平台限制。
6. **代理协议与链路能力**：TCP/UDP/QUIC、VLESS Reality、Hysteria2、TUIC、WireGuard、前置代理和多跳。
7. **订阅转换与规则源**：Subconverter 语法、正则筛选、远程规则格式、更新周期和来源可用性。
8. **业务分流**：AI、流媒体、社交、开发者服务、游戏平台、国内服务的出口和会话要求。
9. **性能与稳定性**：测速开销、规则规模、连接竞速、复用、MTU、失败恢复和客户端渲染。
10. **安全与验证**：监听面、API、密钥、日志、DNS/IP/WebRTC 泄漏、配置校验和可重复 A/B 测试。

任何结论都应标注为：

- **官方事实**：可在目标版本官方文档或源码中确认。
- **实现细节**：来自当前 Mihomo 实现，升级后需复核。
- **工程经验**：合理的起点，不是普遍保证。
- **待实测假设**：必须在实际节点、网络、设备和客户端上验证。

---

## 1. 内核、客户端与配置边界

### 1.1 生态判断

- **Mihomo（Clash.Meta）**是当前 Clash 配置生态中功能最完整、维护活跃的内核之一，支持较多现代协议、规则扩展、TUN、嗅探和 MRS 规则集。
- **Clash Premium / OpenSource Clash**属于旧生态，字段和协议能力不能与 Mihomo 等同。
- **sing-box**是不同配置体系，不能把 JSON 配置直接当作 Mihomo YAML。
- 客户端名称不等于内核版本；排障时必须记录客户端版本、实际内核名称和内核版本。

### 1.2 标准边界

- Mihomo 原生配置通常是 YAML，核心入口包括全局参数、DNS、代理/代理提供者、`proxy-groups`、`rules` 和 `rule-providers`。
- Subconverter `proxy.ini` 是**转换器外部配置**，不是 Clash/Mihomo 原生配置。直接把 `.ini` 当作 Mihomo 配置不会生效。
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
| `select` | 保存并使用人工选择的代理或策略组 | 主控出口、业务手动切换 | 不会按延迟自动选择 |
| `url-test` | 对候选代理做 HTTP 健康检查，优先选择健康且延迟较低者 | 地区自动优选 | 受 `tolerance`、`lazy`、失败状态影响 |
| `fallback` | 按 `proxies` 顺序选择第一个健康候选 | 主备容灾 | 全部不可用时实现可能仍回退到首项，不能当成绝对可用保证 |
| `load-balance` | 在连接级别分配到多个候选代理 | 同质节点分摊连接 | 不会把一个会话拆到多个出口；需考虑会话粘性 |

当前 Mihomo 实现支持的负载策略包括 `consistent-hashing`、`round-robin`，以及实现版本中提供的会话粘性策略。`round-robin` 不是必然导致登录失败，但可能让连续连接使用不同出口 IP；依赖出口稳定性的业务应优先选择手动、自动优选、一致性哈希或粘性策略。

> **重要版本边界**：当前 Mihomo 已移除 `relay` 策略组。需要前置中转时，应在具体代理节点上研究 `dialer-proxy`；多跳会增加延迟、故障点和排障成本。

### 2.2 健康检查语义

- `url` 是健康检查地址，不是目标业务的完整可用性测试，也不是下载速度测试。
- `interval` 单位为秒，`timeout` 单位为毫秒。
- 未配置统一“最佳间隔”。300–600 秒可作为低频经验起点，但不是官方规范；节点数量、测速地址、故障恢复要求和服务商限制都要纳入评估。
- `tolerance` 单位为毫秒。`url-test` 通常只有在当前节点延迟高于最快节点加上容差，或当前节点不健康时才切换；容差越大，越不容易因抖动切换。
- `lazy` 默认行为和触发时机属于实现细节；未使用的组可能延迟测速，但首次使用、拨号失败或健康检查流程仍可触发检测。
- `expected-status` 可以限制健康检查接受的 HTTP 状态码，默认通常不限制；状态码不符合时节点可能被判定为不健康。
- 测速结果只代表“该代理访问测试 URL 的连通延迟”。它不能证明 OpenAI、Netflix、游戏或下载业务一定可用。

### 2.3 推荐拓扑

```text
业务规则组（AI / 视频 / 社交 / 游戏）
        ↓
主控组（select）
        ↓
自动优选 / 故障转移 / 一致性负载组
        ↓
地区组或实际节点
```

建议优先保持层级清晰：业务组引用少量稳定的主控/地区组，避免每个业务组重复堆入全部节点和全部地区组。是否造成性能问题应通过启动时间、内存、API 响应和切换体验实测，不宜写成绝对阈值。

来源：

- 策略组文档：https://wiki.metacubex.one/config/proxy-groups/
- Mihomo 策略组实现：https://github.com/MetaCubeX/mihomo/tree/Meta/adapter/outboundgroup

---

## 3. 规则引擎与规则集

### 3.1 匹配顺序

Mihomo 通常按 `rules` 从上到下匹配，越靠前优先级越高；一般命中后停止继续匹配。但 UDP 请求遇到当前目标出站不支持 UDP 时，可能继续尝试后续规则。因此，“First-Match-Win”是一般原则，不是无条件的绝对描述。

“局域网 → 广告 → AI → 流媒体 → 海外 → 国内 → 兜底”是常见配置设计建议，不是内核规定的固定优先级。实际优先级只由最终生成的规则列表决定；重叠规则必须按业务意图排序。

### 3.2 常用规则类型

| 类型 | 作用 |
|---|---|
| `DOMAIN` | 完整域名匹配 |
| `DOMAIN-SUFFIX` | 匹配域名自身及后缀域名，但不匹配仅包含该字符串的其他域名 |
| `DOMAIN-KEYWORD` | 域名包含关键字 |
| `DOMAIN-WILDCARD` | Mihomo 支持的 `*`/`?` 通配匹配 |
| `DOMAIN-REGEX` | 域名正则匹配 |
| `IP-CIDR` / `IP-CIDR6` | 目标 IPv4/IPv6 网段 |
| `IP-SUFFIX` | IP 后缀范围 |
| `IP-ASN` | 目标 IP 所属 ASN |
| `GEOIP` | 按目标 IP 国家/地区代码 |
| `GEOSITE` | 按 Geosite 数据库的域名分类 |
| `PROCESS-NAME` | 按进程名（受平台支持影响） |
| `DST-PORT` / `SRC-PORT` | 目标/源端口 |
| `AND` / `OR` / `NOT` | Mihomo 复合逻辑规则 |
| `RULE-SET` | 引用 `rule-providers` |
| `MATCH` | 通用兜底规则 |

`GeoData` 是底层数据概念，不是名为 `GEODATA` 的通用路由规则类型。`geosite.dat`、`geoip.dat`、MMDB 等数据文件也不能仅凭扩展名直接当作规则提供者。

### 3.3 `no-resolve`

`no-resolve` 只适用于目标 IP 类规则，作用是跳过该规则为判断域名目标而触发的额外解析。例如：

```yaml
- IP-CIDR,192.168.0.0/16,DIRECT,no-resolve
- GEOIP,CN,DIRECT,no-resolve
- IP-ASN,13335,PROXY,no-resolve
```

是否需要添加取决于 DNS 模式、前置域名规则、缓存、嗅探和实际连接上下文。不能绝对表述为“所有 IP/GEOIP 规则必须加”，也不能绝对推导为“未加就一定产生本地明文 DNS 泄漏”。添加后也可能使尚未获得 IP 的请求无法通过该 IP 规则匹配。

### 3.4 `MATCH`、`FINAL` 与 `[]`

- Mihomo 原生主配置通用兜底使用 `MATCH,策略组`。
- `FINAL` 常见于 Subconverter 的输入语法或其他兼容格式，不能无条件写入 Mihomo `rules`。
- `RULE-SET,名称,策略组` 需要对应 `rule-providers`，Mihomo YAML 不需要给 `RULE-SET` 加 `[]`。
- `[]DIRECT`、`[]REJECT`、`[]策略组名` 和 `[]GEOIP` 是 Subconverter `proxy.ini` 语法，不能直接当作 Mihomo YAML 规则语法。

### 3.5 Rule Provider

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
- `behavior`：`domain`、`ipcidr`、`classical`，描述规则内容类别。
- `format`：`yaml`、`text`、`mrs`，描述文件容器/编码格式。
- `mrs` 主要适用于 `domain` 和 `ipcidr`；`classical + mrs` 不兼容。
- 规则仓库提供的是规则内容，不等于已经完成 `rule-providers` 定义。

来源：

- 规则文档：https://wiki.metacubex.one/config/rules/
- Rule Providers：https://wiki.metacubex.one/config/rule-providers/
- Meta 规则数据：https://github.com/MetaCubeX/meta-rules-dat
- blackmatrix7：https://github.com/blackmatrix7/ios_rule_script
- ACL4SSR：https://github.com/ACL4SSR/ACL4SSR

---

## 4. DNS：能力、边界与防泄漏

### 4.1 `fake-ip` 与 `redir-host`

- `fake-ip`：向客户端返回虚拟 IP，并由 Mihomo 维护域名到虚拟地址的映射。
- `redir-host`：返回真实解析得到的 IP；仍是合法模式，官方默认值为 `redir-host`。
- Fake-IP 可以减少部分应用通过系统 DNS 直接获得真实地址的情况，但不能单独保证“远端解析”或“完全无 DNS 泄漏”。实际还受直连解析、节点域名解析、代理协议、应用自带 DoH/DoT、TUN 覆盖、IPv6 和过滤器影响。

### 4.2 关键 DNS 字段

| 字段 | 主要职责 |
|---|---|
| `default-nameserver` | 解析 DNS 上游服务器自身的域名；通常应使用可直达 IP |
| `nameserver` | 普通域名常规解析 |
| `fallback` | 普通解析的后备上游，配合 `fallback-filter` 使用 |
| `nameserver-policy` | 按域名/通配符/GEOSITE 选择普通 DNS 上游，优先级高于普通配置 |
| `proxy-server-nameserver` | 仅解析代理节点域名 |
| `proxy-server-nameserver-policy` | 为代理节点域名选择专用 DNS 策略 |
| `fake-ip-filter` | 指定哪些域名使用真实 IP 或 Fake-IP；可能让部分域名回到真实解析 |
| `respect-rules` | 让 DNS 连接遵守路由规则；使用时需要规划代理节点解析 |

`nameserver-policy` 选择的是 DNS 上游，不自动等价于“DNS 请求一定经代理”。URL 后的出站标记、`respect-rules` 和版本行为必须实际验证。

### 4.3 DNS 劫持与 TUN

- `any:53` 未写协议时通常按 UDP 处理；要覆盖 TCP DNS，应显式配置 `tcp://any:53`。
- `dns-hijack` 只影响命中的、且已被 TUN/透明代理接管的连接；DoT、DoH、应用自带 DNS、Android Private DNS 等不一定能被拦截。
- Windows/macOS、Android、虚拟网卡和安全软件存在平台限制。
- DNS 监听在 `0.0.0.0` 会扩大暴露面，应配合绑定地址和防火墙。

### 4.4 DNS 验证原则

不能仅凭 `enhanced-mode: fake-ip` 宣称无泄漏。至少分别测试：系统代理/TUN、IPv4/IPv6、浏览器 DoH 开关、随机域名解析、UDP/TCP 53、853、DoH 连接、应用自带 DNS 和 WebRTC。

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
  stack: gvisor
  dns-hijack:
    - any:53
    - tcp://any:53
  auto-route: true
  auto-detect-interface: true
  strict-route: true
```

`stack` 可选 `system`、`gvisor`、`mixed`；官方默认值和各版本实现应核对，不能把 `system` 写成普遍“性能最高”，也不能把 `mixed/gvisor` 写成普遍“兼容性最佳”。

- `auto-route` 自动设置路由，但不保证应用、虚拟机、容器、IPv6 或自定义路由全部被接管。
- `strict-route` 可减少部分旁路，但可能影响 VirtualBox 等虚拟化网络；它不是绝对无泄漏保证。
- `auto-redirect` 依赖 `auto-route`，且平台支持范围有限。
- TUN 开启后仍需检查系统防火墙、虚拟网卡、IPv6 默认路由和应用过滤。

### 5.2 Sniffer

Mihomo 当前主要支持 HTTP、TLS、QUIC 嗅探，可按协议和端口配置。Sniffer 不是通用“从任意 IP 还原域名”的工具：ECH、应用层加密、非标准协议、未覆盖端口和直接 IP 连接都可能无法识别。识别出域名后是否改写目标还取决于 `override-destination`；该字段的默认行为存在文档/版本差异时，以目标版本实测为准。

---

## 6. 代理协议与链路选择

### 6.1 选型原则

| 需求 | 可优先研究 | 主要代价 |
|---|---|---|
| 通用兼容性 | HTTP、SOCKS、Shadowsocks、VMess、Trojan | UDP/高级链路能力有限 |
| TCP 稳定性 | VLESS TCP、Trojan、Shadowsocks | 弱网吞吐未必最佳 |
| UDP/QUIC 可用且追求吞吐 | Hysteria2、TUIC | 依赖 UDP、MTU、NAT、服务端实现 |
| 全局网段/设备互联 | WireGuard | 属于隧道/路由体系，管理复杂 |
| 前置中转 | 节点级 `dialer-proxy` | 增加延迟和故障点 |

### 6.2 重要边界

- `udp: true` 只表示客户端配置允许 UDP，不能证明服务端、网络、防火墙和 TUN 全链路支持 UDP。
- QUIC 不必然更快；UDP 受限或丢包严重时 TCP 可能更稳定。
- VLESS Reality 的 UUID、公钥、Short ID、SNI、Flow 和证书校验必须与服务端匹配；不要把 `skip-cert-verify` 当长期修复方案。
- Hysteria2/TUIC 的速率、拥塞控制和 MTU 参数应接近实际链路，不能盲目调大。
- TUIC 0-RTT/`reduce-rtt` 有重放风险，敏感、不可重复提交的业务不应仅为降延迟启用。
- WireGuard 的 `allowed_ips`、MTU、DNS、NAT 保活和密钥管理必须一起设计。
- `dialer-proxy` 配在具体代理节点上；多跳不是默认性能优化手段。

来源：

- 代理总览：https://wiki.metacubex.one/config/proxies/
- VLESS：https://wiki.metacubex.one/config/proxies/vless/
- Hysteria2：https://wiki.metacubex.one/config/proxies/hysteria2/
- TUIC：https://wiki.metacubex.one/config/proxies/tuic/
- QUIC RFC：https://www.rfc-editor.org/rfc/rfc9000
- WireGuard：https://www.wireguard.com/

---

## 7. Subconverter `proxy.ini`

### 7.1 语法边界

典型策略组格式：

```ini
custom_proxy_group=🚀 节点选择`select`[]♻️ 自动选择`.*`DIRECT
custom_proxy_group=♻️ 自动选择`url-test`节点正则`http://www.gstatic.com/generate_204`300,,50
custom_proxy_group=⚖️ 负载均衡`load-balance`节点正则`http://www.gstatic.com/generate_204`300`consistent-hashing
```

- `[]策略组名`、`[]DIRECT`、`[]REJECT` 表示引用已有策略组/内置目标。
- 不带 `[]` 的筛选项通常作为节点名正则。
- `ruleset=目标,地址` 引入远程规则；`[]GEOIP`、`[]FINAL` 等是转换器输入语法。
- `enable_rule_generator=true` 启用规则生成；`overwrite_original_rules=true` 覆盖原始规则。两者只在通过 Subconverter 外部配置加载时有意义。
- `300,,50` 表示填写间隔与容差但留下 timeout 空位，语法可被转换器接受，但最终生成配置要再做内核校验。

### 7.2 规则源与正则

- 默认规则格式、`surge`/`clash-classic` 等解释属于 Subconverter 语境，不应套用到 Mihomo `rule-providers`。
- 远程 URL 返回 HTTP 200 不等于规则内容格式正确、语义正确或长期可用。
- 正则应避免过宽匹配：单独使用 `AI` 可能误匹配 `TAIWAN`、`EMAIL`；`[^-]日` 也可能匹配大量非日本节点。优先使用边界、完整地区词和排除公告/流量信息的负向条件。
- `select .*` 合法但会把全部节点纳入手动组；节点名、代理组和无效信息混杂时应审查候选范围。

来源：

- Subconverter README：https://github.com/tindy2013/subconverter/blob/master/README-cn.md
- 官方模板：https://raw.githubusercontent.com/tindy2013/subconverter/master/base/config/ACL4SSR_Online.ini
- ACL4SSR：https://github.com/ACL4SSR/ACL4SSR

---

## 8. 业务分流的设计原则

- **AI 服务**：优先固定、稳定、地区符合要求的出口；不要默认使用会改变出口 IP 的轮询。具体服务的可用性和地区限制必须实测。
- **Netflix/流媒体**：解锁能力依赖出口 IP、服务地区和节点侧策略；测速 URL 成功不等于解锁成功。
- **YouTube/下载**：主要关注带宽、晚高峰、连接稳定性；业务分流和测速组要区分。
- **TikTok 等地区敏感业务**：出口地区、DNS、时区/语言和客户端行为都可能影响结果，不应只看节点名称。
- **Telegram/实时通信/游戏**：检查 UDP 能力、NAT、丢包、延迟抖动和会话保持。
- **国内服务**：域名/IP/媒体规则可能重叠，必须用最终规则顺序确认；“国内媒体”不必然全部 DIRECT。
- **游戏平台**：商店、登录、联机和下载 CDN 可能需要不同策略；不要把全平台粗暴指向同一出口。

业务分类是配置设计方法，不是内核保证；规则命中、出口能力和实际服务响应要分别验证。

---

## 9. 性能、稳定性与安全

### 9.1 性能字段不要混淆

- `tcp-concurrent`：对 DNS 返回的多个地址并发拨号，采用先成功连接；主要影响首连等待，不是连接复用。
- TCP Keep Alive：探测/保持空闲连接。
- `smux`/multiplex：在底层连接承载多个 TCP 流，和 `tcp-concurrent` 不同。
- Snell `reuse` 有未确认的连接长期保持报告，不能无条件推荐。
- 官方未给出规则数量、MRS 必然性能优势或策略组数量的统一阈值；用基准测试替代猜测。

### 9.2 控制面和监听面

- `allow-lan: true` 允许其他设备使用代理端口，不等于只允许可信局域网；需结合 `bind-address` 和防火墙。
- `external-controller` 是高权限 REST API 控制面，默认应绑定回环地址；不要直接暴露公网。
- `secret` 主要保护 API HTTP 访问，不是所有 Unix socket、Windows named pipe 或外部 DoH 入口的通用认证。
- `dns.listen: 0.0.0.0:端口` 会扩大 DNS 服务暴露面。
- 调试可提高日志级别，长期运行避免无必要的 `debug`，并注意域名、节点名和内部地址泄露。
- 凭据（订阅链接、UUID、密码、Reality 私钥、WireGuard 私钥、API secret）不得进入公开仓库、截图、日志或报告。

### 9.3 IPv6

官方默认值、客户端行为和 TUN 支持必须按目标版本确认。`ipv6: false` 可以作为特定环境的选择，但不是普遍默认或安全保证。关闭 IPv6 不能替代 DNS、TUN、WebRTC 和应用自带 DNS 检查；开启 IPv6 则必须验证 AAAA 流量是否同样经过预期出口。

来源：

- 全局配置：https://wiki.metacubex.one/config/general/
- API：https://wiki.metacubex.one/api/
- 代理配置：https://wiki.metacubex.one/config/proxies/

---

## 10. 可重复验证与排障清单

### 10.1 配置静态检查

1. 用目标 Mihomo 版本校验完整生成 YAML。
2. 检查所有策略组引用是否已定义、是否循环引用、是否有空候选。
3. 检查规则组目标是否存在，规则源的 `behavior`/`format` 是否与实际内容一致。
4. 检查正则是否过宽、转义是否正确、反引号是否成对。
5. 检查 `MATCH` 是否位于预期末尾；不要把 Subconverter `FINAL` 直接当 Mihomo `MATCH`。

### 10.2 功能 A/B 测试

- 单节点直连、单节点代理、自动组、故障转移分别测试。
- 记录测试 URL 延迟与真实业务可用性，不把二者混为一谈。
- 对 UDP 业务测试 TCP 备用节点、UDP 节点、TUN 和非 TUN 路径。
- 对 DNS 测试 Fake-IP 过滤域名、系统代理/TUN、浏览器 DoH、IPv4/IPv6 和抓包。
- 对会话敏感业务测试手动、`consistent-hashing`、`sticky-sessions` 与 `round-robin` 的出口变化。

### 10.3 常见症状定位

- **OpenAI/Cloudflare 访问异常**：先核查出口 IP、会话是否换出口、挑战域名规则、DNS 和证书校验；不要直接归因于某个策略组类型。
- **国内网页变慢**：核查国内规则顺序、DNS 策略、`no-resolve` 使用场景、直连 DNS 和 TUN 路由。
- **视频画质/解锁异常**：分别检查带宽、出口地区、节点解锁、DNS 和业务规则，不要只看测速延迟。
- **配置转换失败**：检查远程 URL 内容、规则格式、正则、特殊字符和转换器版本；HTTP 200 不是格式正确证明。
- **TUN 开启后断网**：检查权限、防火墙、stack、严格路由、虚拟网卡、IPv6 和 DNS 劫持覆盖范围。

---

## 11. 本项目 `proxy.ini` 当前审计摘要（2026-08-27）

静态检查结果：36 个策略组、40 个 ruleset；所有 `[]` 策略组引用均能在文件中找到定义；反引号无明显缺失；远程规则 URL 当前均返回 HTTP 200，测速 URL 返回 HTTP 204。上述只是当前时点的可达性/静态结果，不代表规则格式、节点实际存在或业务解锁成功。

需要后续验证的项目：

1. `300,,50` 的空 timeout 应在目标转换器和 Mihomo 版本上验证最终输出。
2. `consistent-hashing`/`round-robin` 需按目标内核验证，旧 Clash 可能不兼容。
3. 负向前瞻正则和 `[^-]日` 可能造成节点误匹配。
4. `ruleset` 默认按 Subconverter 语境解释，远程文件需确认实际格式与转换结果。
5. `🚀 测速选择` 的 ruleset 与 `select .*` 的组语义可能冗余。
6. `🎯 全球直连` 当前可切换到代理组，并非纯 `DIRECT`；命名可能造成误解。
7. 同一目标的多个 AI/国内/媒体 ruleset 合法，但必须检查重叠与先后顺序。
8. 不修改现有 `proxy.ini` 前，不应把上述风险当作已修复结论。

---

## 12. 主要来源索引

- Mihomo 文档：https://wiki.metacubex.one/config/
- Mihomo 源码：https://github.com/MetaCubeX/mihomo
- Mihomo Meta 文档：https://github.com/MetaCubeX/Meta-Docs
- Mihomo 规则：https://wiki.metacubex.one/config/rules/
- Mihomo Rule Providers：https://wiki.metacubex.one/config/rule-providers/
- Mihomo 策略组：https://wiki.metacubex.one/config/proxy-groups/
- Mihomo DNS：https://wiki.metacubex.one/config/dns/
- Mihomo TUN：https://wiki.metacubex.one/config/inbound/tun/
- Mihomo Sniffer：https://wiki.metacubex.one/config/sniff/
- Mihomo 代理协议：https://wiki.metacubex.one/config/proxies/
- Subconverter：https://github.com/tindy2013/subconverter
- ACL4SSR：https://github.com/ACL4SSR/ACL4SSR
- blackmatrix7：https://github.com/blackmatrix7/ios_rule_script
- Meta 规则数据：https://github.com/MetaCubeX/meta-rules-dat
- BrowserLeaks DNS：https://browserleaks.com/dns
- IPLeak：https://ipleak.net/
