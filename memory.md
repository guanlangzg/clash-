# 项目长期记忆

## 1. 策略组拓扑与全选节点约定

- **10+1 极简拓扑**：保留 10 个业务手动组（`🤖 AI服务`、`💬 社区论坛`、`🪙 加密与支付`、`📲 电报消息`、`📹 油管视频`、`🎵 TikTok`、`🌍 国外媒体`、`🎥 奈飞视频`、`Ⓜ️ 微软服务`、`🐟 漏网之鱼`）与 1 个自动优选组（`♻️ 自动选择`）。不再设立地区、协议、CDN、主控“节点选择/手动切换”或“-手动”孪生副本；国内服务与广告拦截直接指向内置 `DIRECT` / `REJECT`，不创建可被误切到代理的国内组或独立广告组。
- **全选节点（`.*`）**：所有策略组统一使用 `.*` 筛选转换器实际导入的全部具名节点，不维护供应商家族白名单。供应商改名、增删地区家族或前置多字节 UTF-8 国旗 emoji 均不会导致节点落单。
- **已知边界**：Subconverter 的名称正则只匹配含显示名的节点（订阅中缺失名称片段的节点必然落单）；若订阅将到期/流量公告伪装为合法节点也会被 `.*` 包含，仅在实际出现时做针对性排除，不恢复家族白名单。
- **默认候选与测速参数**：
  - `🤖 AI服务`、`💬 社区论坛`、`🪙 加密与支付`、`🎵 TikTok`、`🌍 国外媒体`、`🎥 奈飞视频` 默认首项为首个节点（手选优先，不以测速延迟替代地区合规、解锁或高频 Cloudflare/金融风控会话 IP 固定要求）；
  - `📲 电报消息`、`📹 油管视频`、`🐟 漏网之鱼` 默认首项为 `[]♻️ 自动选择`（`🐟 漏网之鱼` 末尾保留 `[]DIRECT` 兜底）；
  - `Ⓜ️ 微软服务` 默认首项为 `[]DIRECT`，次选 `[]♻️ 自动选择` 与全节点；
  - `♻️ 自动选择` 使用 `url-test`，测试地址 `https://www.gstatic.com/generate_204`，尾字段按 Subconverter `interval[,timeout][,tolerance]` 三段语法写为 `600,,150`（依据官方 `pref.example.ini` 与 v0.9.0 实测确认，不可简写为两段 `600,150`）。

**Why:** 供应商换代频繁改变命名与 emoji 前缀，维护家族前缀白名单极易造成分组匹配为空并被 Subconverter 静默补成 `DIRECT`（`src/generator/config/subexport.cpp#L643-L654`）；用少量业务入口直接表达用户选择比按节点名分类更稳健。

**How to apply:** 修改 `proxy.ini` 策略组时，保持 10 个业务组 + 1 个 `♻️ 自动选择` 的结构与默认首项顺序，对任意新增或改名节点用 `scripts/test/test_proxy_ini.py` 验证全选覆盖、无空组及无循环引用。

## 2. 分流规则顺序与防污染约束

- **严格顺序匹配**：规则仅按最终生成顺序自顶向下匹配（First-Match-Win），精确 `DOMAIN` 不会自动优先于位置更靠前的 `DOMAIN-SUFFIX` 或 `DOMAIN-KEYWORD`。整体顺序固定为：基础直连与防误杀白名单 → 广告拦截 → AI 专属分流 → 细分视频与微软 → 国内应用与 Apple 直连 → 游戏下载直连例外与平台/推送代理 → 电报消息、加密与支付、社区论坛、海外例外与国内域名规则集合 → 通用开发者/国外媒体/GFW 代理 → 国内 IP 与下载兜底（含 `GEOIP,CN,no-resolve`） → `🐟 漏网之鱼,[]FINAL`。
- **AI 规则纯净源与内联契约**：
  - 远程源仅保留 `blackmatrix7` 的 `OpenAI.list` 与 `Claude.list`；
  - Google AI（`aistudio.google.com`、`makersuite.google.com`、`gemini.google.com`、`generativelanguage.googleapis.com`）、Copilot（`api.githubcopilot.com`、`copilot-proxy.githubusercontent.com`、`copilot.microsoft.com`、`sydney.bing.com`）采用精确 `[]DOMAIN` 内联，Perplexity（`perplexity.ai`）、xAI（`x.ai`、`grok.com`）采用 `[]DOMAIN-SUFFIX` 内联，且整段必须位于微软与通用海外规则之前；
  - **严禁引入污染源**：禁止引入 `ACL4SSR/AI.list`、`blackmatrix7/Gemini.list`、`blackmatrix7/Copilot.list` 及宽泛 `DOMAIN-KEYWORD,generativelanguage`（因其混入 `challenges.cloudflare.com`、`auth0.com`、`stripe.com`、`www.bing.com`、`apis.google.com` 等通用身份认证、支付、搜索与 Google 底层通信域名）。
- **电报、加密支付与社区论坛独立分流契约**：
  - **电报（`📲 电报消息`）**：`ACL4SSR/Telegram.list` 仅含 13 条规则，对比 Telegram 官方 `core.telegram.org/resources/cidr.txt` 及 AS62041 路由表漏掉了 `91.105.192.0/23`、`185.76.151.0/24`、`5.28.192.0/18`、`2001:b28:f23c::/48`、`2a0a:f280::/32` 以及 `cdn-telegram.org`、`telegram-cdn.org`、`fragment.com`、`tx.me`、`tg.dev`、`graph.org`、`legra.ph`、`comments.app`、`quiz.directory`，须在 `Telegram.list` 之前显式内联补齐；不直接改用含 `IP-ASN` 与第三方客户端杂项的 `blackmatrix7/Telegram.list`。
  - **加密与支付（`🪙 加密与支付`）**：引用 `ACL4SSR/Ruleset/Crypto.list`（260 条，含 OKX 欧易、Bybit、币安、Gate.io、Coinbase、Kraken、MetaMask、Uniswap、TradingView、DeBank、Etherscan 等）、`ACL4SSR/Ruleset/Binance.list`（9 条）与 `blackmatrix7/PayPal/PayPal.list`（247 条），并内联补齐 `Crypto.list` 漏掉的 Bybit 静态/行情 CDN（`bycsi.com`、`bytick.com`、`byabcde.com`、`bybbi.com`、`byd3c3.com`）、新兴交易所（`bitget.com`、`bitgetapp.com`、`htx.com`、`hyperliquid.xyz`）及跨境支付/U卡（`wise.com`、`revolut.com`、`airwallex.com`、`dupay.one`、`onekey.so`、`pokepay.cc`、`redotpay.com`）。默认手选固定合规节点优先，避免与美国 AI 节点混用或因 `url-test` 频繁切 IP 触发交易所/支付风控。
  - **社区论坛（`💬 社区论坛`）**：NodeSeek（`nodeseek.com` 及官方图床 `nodeimage.com`、姊妹站 `deepflood.com`、评测站 `nodequality.com`）、LINUX DO（`linux.do` 及孵化站 `idcflare.com`）、V2EX（`v2ex.com` 及官方图床 `v2ex.co`）、HostLoc（`hostloc.com`）、2Libra（`2libra.com`）、LowEnd 系列（`lowendtalk.com`、`lowendspirit.com`、`lowendbox.com`）、Reddit、Discord（含 `discordcdn.com`）、X/Twitter 与 `Developer.list` 统一归入 `💬 社区论坛`（默认手选固定节点优先），避免落入 `🐟 漏网之鱼` 因 `url-test` 切换出口 IP 触发 Cloudflare 反复验证或主站与图床跨出口裂图。
- **通用挑战域解耦**：ACL4SSR `ProxyMedia.list` 含有 `DOMAIN-SUFFIX,challenges.cloudflare.com`，必须在其之前显式单列 `ruleset=🐟 漏网之鱼,[]DOMAIN-SUFFIX,challenges.cloudflare.com`，避免通用 Cloudflare 验证资源被绑死到媒体出口或单一 AI 出口。
- **父子域、国内直连规则集与业务例外顺序**：
  - **京东与广告防误杀白名单**：`jd.com`、`360buy.com`、`360buyimg.com`、`jdcloud.com`、`jdpay.com`、`jcloudcs.com` 以及易被 `BanProgramAD.list` 误伤的微信朋友圈视频（`wxsnsdy.wxs.qq.com`、`wxsnsdythumb.wxs.qq.com`）、腾讯游戏活动中心（`act.qq.com`）、网易邮箱静态图片（`img1.126.net`、`img2.126.net`、`mimg.126.net`）、淘宝优惠跳转（`g.click.taobao.com`、`ai.m.taobao.com`、`re.m.taobao.com`）置于所有代理与广告规则之前直连。
  - **国内直连远程规则集合（防 `no-resolve` 漏入代理）**：第 8 节 `ChinaCompanyIp.list`、`ChinaIp.list` 与 `GEOIP,CN,no-resolve` 均带 `no-resolve`（在系统代理域名连接下不触发 DNS 解析而直接跳过 IP 规则落入 `FINAL`）。由于单一 `ACL4SSR/ChinaDomain.list` 仅 635 条，故在微软、Steam、Sony、GoogleCNProxyIP 之后、宽泛海外规则（`Developer.list`、`ProxyMedia.list`、`ProxyGFWlist.list`）之前，组合引入 `ACL4SSR/Ruleset/CN.list`、`PublicDirectCDN.list`、`AccelerateDirectSites.list`、`blackmatrix7/ByteDance/ByteDance.list`、`blackmatrix7/Alibaba/Alibaba.list`、`blackmatrix7/China/China.list`（3,721 条）与 `ACL4SSR/ChinaDomain.list`，并辅以少量新兴国产大模型与游戏域名内联（`deepseek.com`、`kimi.com`、`qianwen.com`、`tongyi.com`、`stepfun.com`、`minimaxi.com`、`minimax.io`、`hailuoai.com`、`kurogames.com`、`hypergryph.com`、`hg-cdn.com`、`xhslink.com`、`inkuai.com`）。
  - **Google 例外链**：`xn--ngstr-lra8j.com`、`services.googleapis.cn` 与 `GoogleCNProxyIP.list`（代理例外）必须先于 `CN.list` 与 `GoogleCN.list`（直连白名单，含 `crl.pki.goog`），而 `GoogleCN.list` 必须先于 `ProxyGFWlist.list`（含父域后缀 `pki.goog`）。
  - **游戏下载与 FCM 推送**：`SteamCN.list`、`GameDownload.list`、`steamserver.net`、`steampipe.akamaized.net` 及源于 `uklans/cache-domains` 的 Epic / Sony 确定性下载域名必须在 `Steam.list`、`Epic.list`、`Sony.list` 之前直连（须保留根目录 `规则数据许可.txt` 的 MIT 许可声明）；商店、社区、账号主域与 `GoogleFCM.list`（含 IP 段）统一归入 `🐟 漏网之鱼`。
- **广告规则源边界**：采用 ACL4SSR 同源 classical 格式三件套（`BanAD.list` + `BanProgramAD.list` + `BanEasyListChina.list`）并直接指向内置 `REJECT`；不引入未经 Subconverter 默认 `surge` 格式验证的超大 `payload:` YAML（如 REIJI `adblock_reject.txt` 约 595k 条），防止转换异常或误杀 `statsig`、`featuregates` 等业务辅助域名。

**Why:** 第三方规则列表常混入通用基础设施或父域后缀，盲目整份引入或颠倒顺序会造成隐蔽的全局认证/支付劫持、Cloudflare 跨出口验证失败或国内直连失效。

**How to apply:** 新增或调整规则前先核查远程文件正文、格式与父子域交集；核心业务优先使用显式 `[]DOMAIN` / `[]DOMAIN-SUFFIX` 内联，并在 `scripts/test/test_proxy_ini.py` 中同步维护顺序断言与防污染 `assertNotIn` 检查。

## 3. 订阅解码与分层验证方法

- **订阅解码与脱敏**：
  - `vmess://` 采用 URL-safe Base64（须用 `base64.urlsafe_b64decode` 解析 JSON 中的 `ps` 字段，标准 `b64decode` 会因 `-`/`_` 报错）；`vless://` 节点名位于 `#fragment`（须用 `urllib.parse.unquote` 解码并原样保留 emoji、空格与中文）；
  - 解码后先核对节点总条数以防长内容被截断；订阅内容仅在内存中处理，严禁将真实 `IP:端口`、UUID、节点随机后缀或带参订阅链接写入仓库文件。
- **四层验证边界（报告中必须严格区分）**：
  1. **离线规则与分组回归**：运行 `py -3 -B scripts/test/test_proxy_ini.py`（无 `py` 时用 `python -B scripts/test/test_proxy_ini.py`），基于合成名称夹具校验分组覆盖、默认首项、无环引用与规则顺序。
  2. **可选 Mihomo 内核结构校验**：设置环境变量 `MIHOMO_BIN`（如 `D:\Program Files\Clash Verge\verge-mihomo.exe`，迁移设备后需重确认）再次运行测试脚本。必须通过 `-t -d <临时目录> -f <UTF-8临时文件>` 传入无凭据回环占位配置，且 `json.dumps(..., ensure_ascii=False)` 直接输出 UTF-8（规避 Windows 约 32KB 命令行长度限制 `WinError 206` 与 YAML 不支持的 UTF-16 代理对转义）。
  3. **本地 Subconverter 转换校验**：临时本地转换须固定绑定 `127.0.0.1` 回环地址，仅使用合成节点验证最终 YAML 的语法与首命中；测试环境禁用节点排除时应移除 `exclude_remarks=`（若保留空值 `exclude_remarks=` 会被当作空正则排除全部节点）。
  4. **真实客户端与业务可用性**：远程规则 URL 返回 HTTP 200 或内核 `-t` 校验通过，均不等于规则语义正确或节点出口可用；DNS/TUN 接管效果与流媒体/AI 解锁必须由真实客户端连接记录与业务响应确认。

**Why:** 单一层级的检查容易产生假阳性（例如引用合法但分组为空、内联命令行超长报错、空 `exclude_remarks` 过滤全部节点、或把占位校验当成真实业务可用）。

**How to apply:** 每次修改 `proxy.ini` 后必跑离线回归测试；在交付报告中明确列出已执行的验证层与未验证层（如未设置 `MIHOMO_BIN`、未跑真实 Subconverter 或无现场浏览器会话时如实声明）。

## 4. Cloudflare 与真实业务排查边界

- **入口标签不等于出口能力**：节点名称中的“套 CDN / 家宽 / 原生解锁”仅描述代理入口或供应商命名标签，不能证明目标站点看到的出口 IP 固定或信誉良好；手动固定选择节点仅避免由 `url-test` 测速触发切换，不保证服务端出口 IP 不变。
- **Managed Challenge 同出口要求**：Cloudflare 官方文档明确，Managed Challenge 的原始请求与解题验证请求若来自不同出口 IP，解题可能无效。
- **单变量对照排查法**：遇到 Cloudflare 循环验证或 AI/流媒体访问异常时，保持同一浏览器、同一站点、同一操作会话，每次仅改变一个变量；可先临时将 `🤖 AI服务`、`🌍 国外媒体`、`🐟 漏网之鱼` 指向同一个实测稳定的节点以排除分流跨出口影响，不默认清空 Cookie、不频繁切换节点，也不凭空向 Subconverter `.ini` 添加其不支持的 Mihomo 原生 DNS/TUN 字段。

**Why:** 通用挑战资源被分流到不同出口、服务端动态出口漂移、出口 IP 信誉或客户端环境问题都会触发验证异常，按节点名称中的“CDN”字样归因会误导排障方向。

**How to apply:** 排查业务与验证故障时，先核对目标域名与 `challenges.cloudflare.com` 在客户端连接面板中的实际命中规则与出口一致性，再结合同条件 A/B 测试结果定位原因。
