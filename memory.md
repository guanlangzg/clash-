# 项目长期记忆

## Clash / Mihomo 调研与验证约束（2026-08-27）

- 本项目同时维护 Subconverter 外部配置 `proxy.ini` 与 Mihomo/Clash 配置知识库；`.ini` 不能直接当作 Mihomo YAML 导入。
- 调研时必须区分四类结论：官方事实、当前 Mihomo 实现细节、工程经验、待实测假设。尤其不要把 Fake-IP、TUN、`no-resolve`、`tcp-concurrent`、测速周期或 `round-robin` 的经验写成绝对保证。
- 当前 Mihomo 重点版本边界：`relay` 策略组已移除；链式前置使用节点级 `dialer-proxy`；主配置兜底优先写 `MATCH`，不能把 Subconverter 的 `FINAL` 等同为原生规则；`[]` 是 Subconverter 语法。
- 规则验证必须同时检查规则顺序、UDP 不支持时的后续尝试、`behavior`/`format` 与远程文件内容，以及 `no-resolve` 是否符合具体 DNS/连接上下文。
- DNS/TUN 验证不能只看 `fake-ip`：要检查 `fake-ip-filter`、DNS 劫持 UDP/TCP 覆盖、应用自带 DoH/DoT、Android Private DNS、IPv6、WebRTC、虚拟网卡和防火墙。
- 策略组验证重点：`url-test` 的延迟只是健康检查 URL 的结果并受 `tolerance` 影响；`fallback` 有顺序语义；`load-balance` 是连接级分配，需考虑会话粘性；测速周期按节点数、URL、设备与故障恢复要求实测。
- `proxy.ini` 的静态审计（2026-08-27 记「36 个策略组、40 条 ruleset」）已过期；2026-10-05 实测改动前为 28 个 `custom_proxy_group`、36 条 `ruleset`，同日节点换代后为 51 个策略组、36 条 ruleset（规则行未动）。引用无明显未定义或循环；URL 可达不等于格式正确或业务可用。后续若改配置，必须先确认生成器与目标 Mihomo 版本，再做生成 YAML 校验和业务 A/B 测试。
- 主要官方来源：
  - https://wiki.metacubex.one/config/
  - https://github.com/MetaCubeX/mihomo
  - https://github.com/MetaCubeX/Meta-Docs
  - https://github.com/tindy2013/subconverter
  - https://github.com/ACL4SSR/ACL4SSR
  - https://github.com/blackmatrix7/ios_rule_script

**Why:** 该项目的核心风险不是缺少配置片段，而是版本、语法边界和“经验被误写成保证”。

**How to apply:** 后续修改 `proxy.ini` 或生成 Mihomo 配置前，先读取本文件与 `clash_knowledge_base.md`，再用目标内核校验生成结果；涉及 DNS、TUN、协议和会话问题时，报告必须说明已验证项与未验证项。

## 规则源链接验证经验（2026-08-27）

- jsDelivr 镜像对 ACL4SSR 与 blackmatrix7 规则源可返回 200；本次 `REIJI007/AdBlock_Rule_For_Clash` 的 jsDelivr 地址返回 403，GitHub Raw 地址返回 200，因此该规则保留 Raw 链接。
- `custom_proxy_group` 的反引号数量不能用“必须偶数”判断；`select` 常见为 2 个分隔符，`url-test`/`fallback`/`load-balance` 常见为 4 个，需按字段结构验证。

**Why:** 规则源的 CDN 可达性受仓库、缓存和网络策略影响；语法验证必须依据 Subconverter 字段格式，而不是简单字符计数。

**How to apply:** 更新远程规则链接后逐条请求并记录状态码；对策略组检查组名、类型、候选/正则、测速 URL 和参数字段是否完整。

## 当前节点优化的约束与验证方法（2026-09-21）

- 用户确认只针对当前订阅的节点优化，不建设适配任意订阅的通用模板；节点数已从 8 条换代至 13 条具名（+1 条待命名）见文末「节点换代后的家族前缀与手动孪生约定」。后续改名或添加其他节点家族时，先检查筛选覆盖，再决定是否扩展范围。
- 分组引用存在不代表其中有节点。官方 Subconverter 默认区分名称大小写，无 provider 的空 Clash 分组会补 `DIRECT`；需测试实际名称的匹配结果与默认路径。来源固定在 https://github.com/tindy2013/subconverter/blob/a0d4eab28cb8b6c782d4ce5c3a918de4829b4a72/src/generator/config/subexport.cpp#L643-L654 。
- 基础回归命令：`py -3 -B scripts/test/test_proxy_ini.py`，仅使用名称 fixture，无凭据、无网络。Python Launcher 不可用时改为 `python -B scripts/test/test_proxy_ini.py`。
- 可选内核校验：在 PowerShell 设置 `$env:MIHOMO_BIN = 'D:\Program Files\Clash Verge\verge-mihomo.exe'` 后运行上述测试；该路径来自本机进程检查，迁移设备后必须重新确认。未设置时明确跳过内核校验。
- 内核测试用 `-t -config` 和独立临时目录，传入无凭据、回环地址占位节点的分组投影，只检查分组结构；不启动代理、不加载真实客户端配置。它不能代替实际 Subconverter 输出、完整规则源、VMess 参数、业务连通性或出口地区验证。
- 用 JSON 作为 YAML 兼容输入时，非 BMP 字符应直接输出为 UTF-8（Python `json.dumps(..., ensure_ascii=False)`），避免将组名中的字符输出为 YAML 不支持的 UTF-16 代理对转义。
- CDN 与非 CDN 入口是否共用出口、节点名中的地区与“解锁”是否真实，必须另行实测。手动选择仅避免由测速触发的换节点，不保证服务器出口 IP 不变。

**Why:** 少量自定义节点更容易暴露模板的名称假设；只检查引用或只让内核解析占位配置，都会漏掉实际转换与选路问题。

**How to apply:** 修改时先用脱敏名称测试覆盖、空组、默认路径、候选顺序和循环引用；要求保留规则时，对 `ruleset=` 行按原顺序计算指纹。报告明确哪些验证没有运行，不把占位节点校验表述为真实节点可用。

## 分流规则源审计经验（2026-09-21）

- 规则行没有精确重复，不代表没有语义重复；必须同时比较远程文件正文、规则类型、域名后缀包含关系和最终生成顺序。
- ACL4SSR `Ruleset/AI.list` 与 blackmatrix7 OpenAI/Claude 规则存在明显交集；ACL4SSR AI 自身还有 `DOMAIN` 与 `DOMAIN-SUFFIX` 的同域重复。多个源指向同一策略组通常只增加维护和匹配开销，不能提升出口可用性。
- 大型广告源必须先确认格式与规模。REIJI `adblock_reject.txt` 当前为带 `payload:` 的 YAML 规则文件，规模约 595k 条；Subconverter `ruleset=` 默认按 `surge` 规则解释，官方文档未确认任意 `payload:` YAML 可被默认格式正确导入，必须在实际转换器上验证，不能仅凭 HTTP 200 认为生效。
- 广告源与 AI 源的交集要区分核心服务域名和辅助/追踪域名：广告规则可能命中 `statsig`、`featuregates`、`segment` 等辅助域名，但本次样本未覆盖 `openai.com`、`chatgpt.com`、`anthropic.com`、`claude.ai` 等核心主域；辅助域被 REJECT 仍可能破坏登录、挑战或遥测流程。
- 规则顺序审计应记录白名单/局域网、广告、AI、媒体、海外、国内、兜底的先后，并对重叠域名做首命中模拟；Subconverter 的最终输出和目标内核行为仍需另行验证。

**Why:** 规则源常以不同 URL 提供相同条目，且格式包装、辅助域名和首命中顺序会比单纯的行重复更容易造成隐蔽故障。

**How to apply:** 更新广告或 AI 规则源时，先下载正文做格式识别和交集统计，再验证 Subconverter 实际转换结果；优先保留一套职责清晰、可验证的 AI 源，广告源避免无证据叠加超大规则集。

## 规则集优化决策（2026-09-21）

- 当前配置最终只保留 ACL4SSR `BanProgramAD.list` 作为广告规则源；REIJI `adblock_reject.txt` 因体积过大且返回 `payload:` YAML、未确认可被 Subconverter 默认格式正确导入而移除。
- 当前 AI 分流只保留 blackmatrix7 的 OpenAI 与 Claude 专用规则，移除 ACL4SSR 通用 AI 源和 `challenges.cloudflare.com` 内联规则；后者是通用 Cloudflare 挑战域，不应默认归入 OpenAI。
- 广告规则统一挂到 `🛑 广告拦截`，删除重复的 `🍃 应用净化` 规则组；AI 仍使用原 `🤖 OpenAI` 策略组名以保留客户端选择状态。
- 离线回归新增规则源目标、去重和顺序契约；网络可达性、Subconverter 实际转换、Mihomo 完整生成配置和真实 AI/广告业务效果仍需分层验证。

**Why:** 这套取舍优先保证格式可解释、规则职责单一和首命中顺序稳定，而不是盲目堆叠更大的远程规则集。

**How to apply:** 后续若需要扩大 AI 覆盖，先新增独立业务组或明确白名单，不要把通用 Cloudflare、认证和遥测域名直接并入 OpenAI；替换广告源前先验证正文格式与 Subconverter 转换结果。

## 手动节点分组约定（2026-09-21）

- 当前主组 `🚀 节点选择` 提供手动入口；四组（`🚀 全部节点`、`🚀 手动切换1`–`3`）都使用统一家族正则，覆盖当前全部具名节点。2026-10-05 起另有每个自动组的 `-手动` 孪生组，见下节。
- 手动组使用 `select`，与 `♻️ 自动选择` 和 `🛡️ 故障转移` 分开；用户可为不同用途保存不同节点，不改变业务组的地区筛选。
- 若节点命名家族变化，必须同步检查手动组、每个自动组的 `-手动` 孪生组和主组入口，避免出现空组后被 Subconverter 补成 `DIRECT`。

**Why:** 一个手动组只能保存一个选择，多个独立 `select` 组可以保留不同节点预设，同时不把手动选择与自动测速或故障转移混在一起。

**How to apply:** 新增手动组时优先复用当前节点家族正则，并在 `scripts/test/test_proxy_ini.py` 中验证每组的完整节点覆盖和主组入口。

## Google 国内白名单的顺序约束（2026-09-22）

- `GoogleCN.list` 的直连例外必须位于 `ProxyGFWlist.list` 前，同时保留显式代理例外及 `GoogleCNProxyIP.list` 在前；不能机械地把所有国内规则移到海外通用规则之后。
- 已核实的重叠示例：GoogleCN 的 `DOMAIN-SUFFIX,crl.pki.goog` 会被 GFW 的 `DOMAIN-SUFFIX,pki.goog` 覆盖；UnBan 的 `DOMAIN,dl.google.com` 仅是精确放行，不能替代整份 GoogleCN 白名单。
- 规则源正文会变化；离线顺序契约只防止已知配置回归，不等同于完整远程规则首命中、实际转换或业务验证。

**Why:** 通用代理规则中的关键字和父域后缀可能遮蔽更具体的直连例外，规则分节的可读性不能代替实际匹配优先级。

**How to apply:** 调整规则顺序时，核对上游正文中的父子域和关键字交集，保持代理例外、直连白名单、通用代理的优先级，并先用会失败的顺序回归测试复现问题。

## 节点换代后的家族前缀与手动孪生约定（2026-10-05）

> 2026-10-05 晚订阅再次换代（emoji 前缀 + racknerd-us 家族，14 条具名），见「订阅换代晚间场」一节；本节数字为上午状态。

- 2026-10-05 起节点从旧的 4 家族 8 条（`isus`/`hyhk`/`xzhk`/`ccus`）换代为 **13 条具名 + 1 条无名**，分属 7 个家族：`isus-`（美国原生解锁 ×2）、`hyhk-`/`xzhk-`（香港 ×4）、`NL-`（荷兰 ×2）、`cheaphost-日本-`（×1）、`绿云 IIJ-日本-`（×2）、`三网优化SG伪家宽-`（×2，即新加坡家宽）。`ccus` 在 13 条中已不存在，但前缀仍保留在 alternation 里，回来时不会落单。
- **本次修掉的真实缺陷**：改动前所有节点级选择器都是 `^(?:isus|hyhk|xzhk|ccus)-`，`NL`/`cheaphost-日本`/`绿云 IIJ-日本`/`三网优化SG伪家宽` 四个家族一个都匹配不到 —— 14 条里只有 6 条可选。改名换姓不会让旧正则自动跟上，**每次订阅换代都必须重算节点级覆盖**。
- 唯一家族正则收敛为 `^(?:isus|ccus|hyhk|xzhk|NL|cheaphost-日本|绿云 IIJ-日本|三网优化SG伪家宽)-`，由测试 `test_group_section_documents_the_family_prefix_contract` 钉住；不要用裸子串，锚点用于挡住 `isusx-test`、`other-hk-cdn` 这类噪声名。
- 约定：每个自动组（`url-test`/`fallback`）都有选择器逐字相同、类型为 `select` 的同名 `-手动` 孪生组，并在 `🚀 节点选择` 里暴露，由 `test_every_automatic_group_has_an_identical_manual_twin` 校验（该断言已用 `git show HEAD:proxy.ini` 验证过非空转：旧配置上失败 6 次）。
- 第 14 条节点（vless）在订阅里没有名称片段，Subconverter 的节点级选择器全是名称正则，**无名称节点必然落单**；补到显示名后要把前缀并入 alternation 与测试夹具。当前 51 个组的 `🚀 全部节点` 实际只覆盖 13 条。
- 公开仓库提交前必须脱敏：真实 `IP:端口`、节点名里的 UUID／随机域后缀都不要写进 `proxy.ini` 注释、测试夹具或本文件；夹具用合成名（如 `-example`）即可，断言只依赖家族前缀与 body 标记。

**Why:** 家族前缀是唯一稳定的选区键（随机 UUID 后缀会随订阅刷新变化），而换代时“引用没断”不等于“节点还在候选里”——只查分组引用会漏掉整族节点失效。

**How to apply:** 拿到新订阅后先解码名称、按 `^(?:族...)-` 重算每个组的候选集合，再核对每个自动组是否有 `-手动` 孪生、主组是否暴露；改完跑 `py -3 -B scripts/test/test_proxy_ini.py`（该套件输出在 stderr），并确认 `git diff` 里没有任何 `ruleset=` 行。

## 订阅链接解码与校验方法（2026-10-05）

- `vmess://` 的 base64 是 **URL-safe**，必须 `base64.urlsafe_b64decode`；用标准 `b64decode` 会因 `_`/`-` 报 `Incorrect padding`。
- `vless://` 的节点名在 fragment，需 `urllib.parse.unquote`；`ps`／fragment 里可能含 emoji、空格与中文（`绿云 IIJ-日本` 有空格），选择器必须逐字保留。
- 应用过滤器会截断长链接（本次 14 条只到了第 14 条的残缺部分），**解码后要核对条数**，缺名称的那条只能列为待确认，不要猜家族。
- 覆盖与冗余审计的实算语义：整行按反引号切分，第一字段组名、第二字段类型，遇 `http(s)://` 即为测速字段起点；`[]` 前缀是组名或 `DIRECT`/`REJECT` 引用（需做传递闭包），其余按正则解释且**大小写敏感**。
- `🌐 非CDN后缀节点` 的无环视负向表达在 55987 个穷举样本上划分正确，仅对 `NL-cdn`、`NL--cdn` 这类“家族后紧跟 `-cdn`”的极端命名分类错误；真实节点名都有中间 body，不受影响。新增此类命名时要重新穷举验证，别用“看起来完整”的写法掩盖。
- 已知冗余（多维度落到同一候选集合，属数据决定而非缺陷）：`🇸🇬 新加坡节点`≡`🏡 家宽节点`（各 2 条）、`🇺🇲 美国节点`≡`🧬 原生解锁节点`（各 2 条，因无 ccus）；`🎬 流媒体解锁节点`(7) ⊃ `🇯🇵 日本节点`(3)，其 `(?:流媒体|解锁)` 键把 `isus-原生解锁` 也拉进来；`🔌 vm-ws 标记节点`(9) ⊃ `🇭🇰 香港节点` 与 `🇳🇱 荷兰节点`（港荷节点全是 vm-ws）。名字声明的“解锁/流媒体/家宽”只表示字符串包含，不代表服务真实可用。

**Why:** 这些坑都会让“看起来校验通过”的结论失真：padding 报错会让人以为链接坏了，截断会让人漏节点，候选集合相同会让多维度的组在改动其一时静默漂移。

**How to apply:** 解码后先核对条数再解析；审计时同时算“覆盖（有无孤儿）”“互斥（划分是否真划分）”“冗余（候选集合是否恒等）”，并把 `MIHOMO_BIN` 内核校验、真实 Subconverter 转换、出口地区与解锁实测分别列为未验证项。

## AI 规则扩展与第三方规则集防污染经验（2026-10-05）

- **外部规则集的严重污染与劫持风险**：不能盲目引入第三方的分流列表文件：
  - `blackmatrix7/Copilot.list` 混入了 `challenges.cloudflare.com`（违反本项目 challenges 不归入 AI 的约束）、`www.bing.com`（劫持 Bing 正常搜索）、`auth0.com`（劫持通用身份认证）、`stripe.com`（劫持全网支付）及 sentry/segment/launchdarkly 等大量非 AI 基础设施，挂入 AI 组会劫持全局流量；
  - `blackmatrix7/Gemini.list` 混入了 `apis.google.com`（Google 基础服务底层通信）、`colab` 关键词及 `generativelanguage` 宽泛关键词，整份引入会破坏 `GoogleCN.list` 直连白名单并导致 Google 基础通信被误代理；
  - `ACL4SSR/AI.list` 混合了大量第三方工具，并与已有的 `ProxyMedia.list` 严重重叠。
- **扩展 AI 覆盖的最佳工程实践**：坚持“纯净专用源（OpenAI/Claude）+ 核心服务显式内联”方案。
  - 核心服务缺失域（如 `aistudio.google.com` 为 Google AI Studio 实际 302 落点但在各分源均缺失；`api.githubcopilot.com`、`copilot-proxy.githubusercontent.com` 在 Copilot.list 中缺失；`perplexity.ai`、`x.ai`、`grok.com` 分源均缺失）统一在 `proxy.ini` 中用 Subconverter `[]` 语法显式内联；
  - Google Gemini API 域必须严格使用精确 `[]DOMAIN,generativelanguage.googleapis.com`，严禁使用 `DOMAIN-KEYWORD`，杜绝关键词扩大化与误伤。
- **离线测试契约与防御性断言**：
  - 测试契约严格限定离线、无网络、无外部 `.list` 文件，不能在离线单测中编写需依赖远程规则正文首命中的模拟；必须基于 ini 文件的静态 AST/规则断言（断言关键内联规则包含、规则段连续性、先于国外媒体与社交）；
  - 测试套件中对已知污染源必须增加防御性 `assertNotIn`（明确禁止 `challenges.cloudflare.com`、`AI.list`、`Gemini.list`、`Copilot.list` 被引入 AI 规则段）。

**Why:** 第三方规则列表正文常混合通用基础设施和遥测分析，表面上覆盖了新 AI 服务，实际上极易引入隐蔽的全局认证、支付和搜索劫持。

**How to apply:** 后续扩展分流规则时，必须先逐行核查远程正文与关键词，核心服务优先使用显式 `[]DOMAIN` / `[]DOMAIN-SUFFIX` 内联，并在 `test_proxy_ini.py` 中增加对应的防污染断言与显式覆盖检查。

## 订阅换代晚间场：emoji 前缀导致节点识别不到的修复（2026-10-05）

- **现象与根因**：用户报"订阅之后识别不到"（转换短链 `v1.mk/Eh5rHGn`）。该短链 302 到 `api.v1.mk/sub`，是**已套用本项目 proxy.ini 的转换服务**（输出组名与本项目 51 组完全一致，且输出含 `aistudio.google.com` 规则，可据此判定其引用的是 GitHub main 最新配置）。当天晚间供应商 roster 变为 **14 条具名**：地区节点名被加国旗 emoji 前缀（`🇳🇱 NL-vm-ws-nl`、`🇺🇸 racknerd-us-解锁-vless` 等），并新增 `racknerd-us-` 美国家族 ×2、新加坡降为 1 条、cheaphost 名称缩短。锚定正则 `^(?:族...)-` 对带前缀名字全部落空：线上输出中荷兰/日本/新加坡/家宽/vl-reality 五组只剩 `DIRECT`，8/14 节点不进任何组。
- **判定匹配时机的证据**：美国组（isus，无 emoji）有成员而荷兰/日本/新加坡（带 emoji）为空——若 emoji 是匹配之后才加的，这些组不会为空。因此转换器是在**带 emoji 的名字上做正则匹配**，修复必须落在正则上。
- **修复契约**：所有节点级选择器统一为 `^(?:[^\x00-\x7F]+\s*)?家族前缀`——可选非 ASCII 前缀（emoji 旗标为多字节 UTF-8，`[^\x00-\x7F]` 按字节也成立）+ 可选空白 + 家族整体锚定。`std::regex`（ECMAScript）与 Python `re` 对 `\x`、`\s`、`(?:)` 语义一致。HK 家族（hyhk-/xzhk-）当前无前缀，保持严格锚定作为对照；`racknerd-us` 已并入美国与全量 alternation，`ccus` 保留防回潮。
- **诊断方法（订阅内容只在内存，不落盘、不回显查询参数、不发第三方）**：clash UA 拉取转换输出 → 解析 `proxies:`/`proxy-groups:` 的 name 清单（930KB 全量 YAML）→ 复用 `test_proxy_ini.py` 的 `parse_groups`/`candidates` 把真实名字对照本地正则，按组计数并找孤儿。通用 UA 也返回 YAML，原始 base64 节点列表无法通过 UA 观察；修复后验证标准：全部组计数正确且孤儿为 0（实测 全部14/港4/美4/荷2/日3/新1/家宽1/cdn5/非CDN9/vm-ws7/reality1/原生2/流媒体8）。
- **限制**：修复需推送到 GitHub main 后转换服务才会用上新正则；本地验证时线上输出仍显示空组属预期。真实客户端刷新订阅后的分组显示、节点出口与 AI 业务可用性仍需用户实测。

**Why:** 转换短链掩盖了"正则匹配发生在哪个形态的名字上"；只看引用完整性会误判配置没坏，只有对照转换输出中各组实际成员才能定位锚定失效。

**How to apply:** 再遇"识别不到"：先拉转换输出看各组实际成员（空组=正则没跟上），用 `parse_groups`/`candidates` 对照真实名字，按"可选前缀 + 家族锚定"修 `proxy.ini`，同步更新夹具（UUID 用合成标记）并跑全套测试；改动必须推送后让用户刷新订阅确认。

