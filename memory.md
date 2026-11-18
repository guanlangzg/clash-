# 项目长期记忆

## 1. 用户偏好与策略组

- 保持 10 个业务手动组（AI、社区论坛、加密与支付、电报、油管、TikTok、国外媒体、奈飞、微软、漏网之鱼）与唯一 `♻️ 自动选择`。国内业务使用内置 `DIRECT`、广告使用 `REJECT`，不建可误切的国内组或广告开关组。
- 所有组用 `.*` 匹配转换器实际导入的具名节点，不维护供应商名称白名单。新增家族、国旗 emoji 或改名不能导致空组；无名称节点及伪装为节点的订阅公告属于单独边界。
- AI、社区、支付与区域媒体默认首个节点；电报、油管、漏网默认自动；微软默认 DIRECT。手选只固定客户端选择，不保证供应商出口 IP 固定、地区适用性或业务解锁。
- 自动组使用 `url-test`、`https://www.gstatic.com/generate_204`、`600,,150`。Subconverter 尾字段为 `interval[,timeout][,tolerance]`，不可误写成 `600,150`。

**Why:** 分组为空时 Subconverter 可能静默补 DIRECT。节点标签与测速延迟都不能证明真实业务能力。

**How to apply:** 新增或更名策略时检查实际节点名称、默认候选、引用无环；未经业务需求不要恢复地区组或手动孪生副本。

## 2. 外部配置数量与正则兼容边界

- 本项目目标是 **Subconverter v0.9.0 + Mihomo（Clash.Meta）**，不是旧版 Clash 通用配置。默认 TOML 的 `max_allowed_rulesets=64` 计算每一条 `ruleset=`，含 `[]` 内联；远程 URL 数量不能代替该计数。规则扩展后还受独立 `max_allowed_rules` 限制（编译默认 32768，具体取决于后端配置）。
- 同策略域名例外使用内联 `[]DOMAIN-REGEX` 合并，后缀语义用 `(^|\.)(a\.com|b\.com)$`，精确主机用 `^(a\.com|b\.com)$`。必须保留起止边界与转义点，不用宽泛关键词省事。
- Subconverter 内联路径直接透传正则；远程 Surge 列表中的 DOMAIN-REGEX、IP-ASN、URL-REGEX 会被 v0.9.0 的目标类型过滤。PROCESS-NAME、IP-CIDR6 支持，但进程规则受真实平台与接管方式影响。
- 正则不能含逗号（转换器按逗号切字段），也不要使用会被 INI 解码的字面 `\n` / `\r` / `\t`、换行、注释或尾随空格。仅用 `a-z0-9-.()|^$\` 构造，不使用可能触发 `yaml-cpp` 引号包裹的 `[`、`]`、`*`、`?`。
- 原始列表可能包含重复项或不受支持类型，不能将原文条数当作最终 YAML 条数；转换后应比较完整规则序列和末尾 MATCH，防止静默截断。

**Why:** v0.9.0 `src/handler/settings.cpp:1246-1257` 检查全部外部 ruleset 数量；`ruleconvert.cpp:220-244` 区分内联透传与远程类型过滤；Mihomo `rules/parser.go` 与 `rules/common/domain_regex.go` 支持正则。

**How to apply:** `scripts/test/test_proxy_ini.py` 保持最多 64 条指令约束与相似域名反例。新增规则先复用现有同策略边界正则，确需超过限制时说明后端要求，不能引用尚未发布的远程合并文件冒充可用。

## 3. 业务分流与广告边界

- 规则按最终生成顺序首命中。基础局域网与必要精确白名单 → 广告 → AI → 视频 → 国内媒体/Apple → 游戏下载例外 → 微软与平台/FCM → 电报/支付/论坛及 Google 海外例外 → 国内域名集合 → 开发者/媒体/GFW → 下载与国内 IP → FINAL。微软源的 akadns.net 属共享 CDN，必须晚于 Sony 等确定性下载主机例外。
- **AI 规则自维护专用域**：不再整份引入 BM7 OpenAI/Claude/Gemini 或 ACL4SSR OpenAi/AI。OpenAI 列表实际含 `auth0.com`、`stripe.com`、共享遥测与云服务 ASN 20473；BM7 Gemini 含共享 `apis.google.com` 与宽泛 `colab` / `developerprofiles` 关键词；检查本地 INI URL 字符串无法发现这些污染。
  - **Google AI 与 Antigravity 防漏及边界**：不能仅列前台主域，须同步覆盖真实 RPC/WebChannel/区域检测接口（AI Studio 的 `alkalimakersuite-pa` / `alkalicore-pa` / `webchannel-alkalimakersuite-pa` / `alkalimakersuiteapplets.pa`、Gemini 的 `proactivebackend-pa` / `robinfrontend-pa` / `geller-pa` / `geminiweb-pa` / `appsgenaiserver-pa` / `aisandbox-pa`、NotebookLM 的 `notebooklm-pa` / `labstailwind`、Jules、Labs/Flow、Opal、Stitch），否则命中后段 `ProxyGFWlist.list`（`DOMAIN-KEYWORD,google` → `🐟 漏网之鱼`，默认自动选低延迟香港节点）会触发锁区。Antigravity（App / IDE / CLI `agy` / `language_server`）须覆盖自有域 `antigravity.google(.com)`、`antigravity-unleash.goog`、Cloud Run 更新器 `antigravity(-cli|-ide|-hub|-app)-auto-updater-974169037036.us-central1.run.app`，后端 `antigravity(-pa).googleapis.com`、`cloudcode-pa`（含 `daily-` / `preprod-daily-` / `autopush-` 及 `.sandbox`，发行版与远程模式会直连 `daily-cloudcode-pa`）、`cloudaicompanion`、`aicode`、`aida`，以及企业版官方白名单 `businessaicode`、`aiplatform`、`discoveryengine`（含全局/区域/mTLS/`.rep`）。不将通用 Google 域（`accounts.google.com`、`oauth2.googleapis.com`、`apis.google.com`、`play.googleapis.com`、`waa-pa.clients6.google.com`、`www.gstatic.com`）、共享 `*-apt.pkg.dev` / `open-vsx.org`、宽泛 `.*-pa.googleapis.com` 或 `PROCESS-NAME,Antigravity.exe`（会劫持内置浏览器与包管理流量）并入 AI。桌面端 Go 子进程 `language_server` / `agy` 仍依赖客户端 TUN 或显式 `HTTPS_PROXY` 接管，且机房 IP 送中/风控与 Google 账号归属地独立于域名分流。
  - **其他主流 AI 覆盖与防截留**：Copilot 覆盖 `githubcopilot.com` 全子域、`copilot(.cloud).microsoft(.com)`、`copilot.com` 及专用主机；同步覆盖 Cursor、Windsurf/Codeium、Claude（含 `claudeusercontent.com`、`clau.de`、`antspace.dev`）、OpenAI（含 `chat.com`、`ai.com`、`oaistatsig.com`、`chatgpt.livekit.cloud`）、xAI（含 `grok.x.com`，避免被 `x.com` 社区规则截留）与主流模型平台，防止被 `ProxyMedia.list` 截留至 `🌍 国外媒体` 或落入 `🐟 漏网之鱼`。
- **广告先于普通国内直连**：京东、淘宝等整域放到广告之前会放行其广告/追踪子域。前置仅保留经确认需要的精确业务主机（例如 `policy.jd.com`）和正常静态资源；`openxlab.org.cn`、`openxmlformats.org` 是 `openx` 关键词的反例。正常国内业务 DIRECT、广告子域 REJECT 可以同时实现；同域正文与广告无法仅靠域名规则区分。
- **国内集合不能按名称盲信**：BM7 China.list 含整个 `ms`、`in.th` 后缀，不能当作纯国内列表整份引入。使用已审查的 ACL4SSR 国内域名、公共 CDN 与加速列表，搭配字节/阿里集合及少量明确补充。Google 的 `services.googleapis.cn`、`xn--ngstr-lra8j.com`、GoogleCNProxyIP 代理例外须在 `.cn` / GoogleCN 之前。
- **电报**：ACL4SSR Telegram 列表与 `core.telegram.org/resources/cidr.txt` 比较需覆盖整个 CIDR 边界，不只抽查一个 IP。补充网段与专用域指向电报组；兼容段不冒充官方 cidr.txt 原文。
- **支付**：Crypto/Binance/PayPal 列表搭配 Bybit 官方地区 API/WS 域（Bybit v5 guide、ws/connect、pybit SDK）与 Wise 旧域。全球主站覆盖不等于地区 API、登录或全部子服务都覆盖；规则不判断账号地区。
- **社区**：NodeSeek/NodeImage、LINUX DO/IDCFlare、V2EX 图床及常用海外社区显式使用社区组。通用 `challenges.cloudflare.com` 使用默认海外出口；不要把全局挑战域绑定单一业务。分组本身不保证验证码或所有图床都可用。
- **游戏**：确定性下载 CDN 置于 Steam/Epic/Sony 整体代理规则前。保留精确主机与后缀之间的区别，保留 `规则数据许可.txt` 中 uklans/cache-domains 的 MIT 声明。

**Why:** 第三方规则的父域、关键词、共享基础设施会跨业务匹配；增加集合既增加覆盖也增加冲突，必须用正例和负例核对。

**How to apply:** 修改远程源后运行完整展开验证。保留广告放行、OpenXLab、共享 Auth0/Stripe、Copilot 子域、Bybit 地区接口、海外 `.ms` 例外及相似恶意后缀等反例，不能只检查“预期规则存在”。

## 4. DNS、客户端与验证码验证边界

- `no-resolve` 只禁止该条 IP 规则主动解析，前面已有真实目标 IP 时仍可匹配。旧版首条 `5.5.5.5/32` 未带 no-resolve，会提前触发 DNS；因此此前“尾部 no-resolve 必然使未收录国内域名进入 FINAL”的归因错误。
- 正常 Fake-IP 预处理会根据映射恢复 Host 并清空伪 DstIP（Mihomo `tunnel/tunnel.go:289-299`），不能说 fake-ip 天然不能匹配国内 IP。
- 当前首条特殊 IP 使用 no-resolve，国内 GEOIP,CN 放在通用海外域名规则之后，按需解析尚未命中的域名。这样长尾直连有解析兜底，也意味着未知域名可能在本地 DNS 解析；实际 DNS、防污染与 TUN 接管仍由客户端决定，不往 Subconverter INI 添加原生 DNS/TUN 字段。
- Cloudflare 问题须同浏览器/站点/操作做单变量对照，核查业务与挑战资源的实际出口。跨出口可能影响会话，但不要断言所有 Turnstile/Managed Challenge 必然要求相同 IP，或图床不同出口必然裂图。

**Why:** 文本域名匹配器不执行内核解析、进程识别、ASN、IPv6 与客户端接管逻辑，不能把域名未命中等同于实际 FINAL。

**How to apply:** 按连接面板中的真实规则、解析地址与业务响应判断。`-t` 只证明内核能解析配置，不代表目标站点可用。

## 5. 可复现验证与凭据边界

1. 离线回归：`py -3 -B scripts/test/test_proxy_ini.py`；无 Launcher 时用 `python -B`。只用合成名称与域名夹具，不联网。可设置 `MIHOMO_BIN` 验证所有内联规则及组的语法。
2. 公开规则展开：`py -3 -B scripts/test/verify_proxy_ini.py`。必须全部源成功，空响应、HTML、抓取失败、快照 URL 不一致或哈希错误一律失败，不用空列表假装成功；报告转换器会丢弃的规则类型。
3. 同快照本地转换：验证脚本支持 `--subconverter-bin` 与 `--mihomo-bin`，临时 HTTP 服务及转换器均绑定 127.0.0.1，只传无凭据回环节点，显式使用 64/32768 限额。比较完整生成规则序列后再用 Mihomo `-t` 验证真正转换结果。`--snapshot` 可保存公开规则快照供同一次调试复用，任务结束清理，无需提交大体积列表。
4. 真实订阅与业务：需要真实客户端连接和业务响应；以上任意检查通过都不代表真实节点、业务解锁或会话稳定性通过。上游 @master 更新还需要后端缓存刷新、重新转换和客户端获取新配置，不是原生 provider 自动更新。

- 不保存订阅地址、节点服务器/端口、UUID、密码或随机名称后缀，不把这些内容发送第三方转换服务。vmess 用 URL-safe Base64；vless 名称解码 fragment，先核对总数避免截断。
- 临时 Mihomo 配置使用 UTF-8 文件与 `json.dumps(..., ensure_ascii=False)`，避免 Windows 命令行长度限制和 emoji UTF-16 转义问题。Subconverter 验证须分别设置 `add_emoji=false`、`remove_emoji=false` 才能保留原始国旗；`emoji=false` 会强制移除旧 emoji。块式 YAML 模板用于逐组核对候选，不把 JSON 流式输出误当块式解析。
- FlClashCore.exe 是应用 IPC 服务，不支持独立 mihomo `-t`；应使用官方独立预编译内核做轻量验证，不改动运行中的客户端。

**Why:** 单纯离线结构测试或远程 HTTP 200 容易给出虚假完整性结论，真实转换和业务验证各有独立边界。

**How to apply:** 交付明确实际执行的验证层，临时程序/快照/缓存任务结束清理，保留验证脚本与必要结果说明，不保存普通测试通过日志。
