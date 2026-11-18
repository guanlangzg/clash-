"""Offline contracts and domain regression cases for Subconverter + Mihomo.

NODES are synthetic name fixtures, not a current subscription. Offline tests do
not fetch remote lists. verify_proxy_ini.py checks their actual expanded rules.
"""

from dataclasses import dataclass
import ipaddress
import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
NODES = (
    "isus-原生解锁", "isus-原生解锁-cdn", "hyhk-vm-ws", "hyhk-vm-ws-cdn",
    "xzhk-vm-ws", "xzhk-vm-ws-cdn", "🇳🇱 NL-vm-ws-nl", "🇳🇱 NL-vm-ws-cdn",
    "🇯🇵 cheaphost-日本-流媒体-解锁", "🇸🇬 三网优化SG伪家宽-解锁-vless",
    "🇯🇵 绿云 IIJ-日本-流媒体-解锁-vl-reality-vision-deadbeef-dead-beef-dead-beefdeadbeef",
    "🇯🇵 绿云 IIJ-日本-流媒体-解锁-vm-ws-deadbeef-dead-beef-dead-beefdeadbeef",
    "🇺🇸 racknerd-us-解锁-vless", "🇺🇸 racknerd-us-解锁-cdn",
    "🇯🇵 cheaphost-日本-流媒体-解锁-cdn", "🇸🇬 三网优化SG伪家宽-解锁-cdn",
)
BUSINESS_GROUPS = (
    "🤖 AI服务", "💬 社区论坛", "🪙 加密与支付", "📲 电报消息", "📹 油管视频",
    "🎵 TikTok", "🌍 国外媒体", "🎥 奈飞视频", "Ⓜ️ 微软服务", "🐟 漏网之鱼",
)
AUTO_GROUP = "♻️ 自动选择"
ALL_GROUPS = BUSINESS_GROUPS + (AUTO_GROUP,)
BUILTINS = {"DIRECT", "REJECT"}
TEST_URL = "https://www.gstatic.com/generate_204"
MIHOMO_BIN = os.environ.get("MIHOMO_BIN")
# Subconverter v0.9.0 ruleconvert.cpp: ClashRuleTypes (remote Surge input).
CLASH_REMOTE_TYPES = {
    "DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "SRC-IP-CIDR",
    "GEOIP", "MATCH", "FINAL", "IP-CIDR6", "SRC-PORT", "DST-PORT", "PROCESS-NAME",
}
DOMAIN_TYPES = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "DOMAIN-REGEX"}
JD_DOMAINS = (
    "jd.com", "360buy.com", "360buyimg.com", "jdcloud.com", "jdpay.com", "jcloudcs.com",
)
EPIC_DOWNLOAD_DOMAINS = (
    "cdn.unrealengine.com", "cdn1.epicgames.com", "cdn1.unrealengine.com",
    "cdn2.epicgames.com", "cdn2.unrealengine.com", "cdn3.unrealengine.com",
    "cloudflare.epicgamescdn.com", "download.epicgames.com", "download2.epicgames.com",
    "download3.epicgames.com", "download4.epicgames.com", "egdownload.fastly-edge.com",
    "egs-cloudfront-chunks.epicgamescdn.com", "epicgames-download1.akamaized.net",
    "fastly-download.epicgames.com",
)
SONY_DOWNLOAD_SUFFIXES = (
    "gs2-ww-prod.psn.akadns.net", "gs2.sonycoment.loris-e.llnwd.net",
    "gs2.ww.prod.dl.playstation.net", "gs2.ww.prod.dl.playstation.net.edgesuite.net",
)
SONY_DOWNLOAD_DOMAINS = (
    "gs-sec.ww.np.dl.playstation.net", "gst.prod.dl.playstation.net",
    "playstation4.sony.akadns.net", "psnobj.prod.dl.playstation.net",
    "sgst.prod.dl.playstation.net", "theia.dl.playstation.net", "tmdb.np.dl.playstation.net",
    "uef.np.dl.playstation.net", "vulcan.dl.playstation.net",
)
AI_DOMAINS = (
    # OpenAI / ChatGPT / Codex / Sora
    "chatgpt.com", "chat.com", "ai.com", "chat.openai.com", "api.openai.com",
    "cdn.oaistatic.com", "oaistatsig.com", "files.oaiusercontent.com", "sora.com",
    "chatgpt.livekit.cloud", "chat.openai.com.cdn.cloudflare.net",
    "openai-api.arkoselabs.com", "openaiassets.blob.core.windows.net", "cdn.openaimerge.com",
    # Anthropic / Claude / Claude Code
    "claude.ai", "api.anthropic.com", "claude.com", "claudeusercontent.com",
    "clau.de", "antspace.dev",
    # Google Gemini / AI Studio / DeepMind / Workspace AI
    "gemini.google", "gemini.google.com", "bard.google.com", "gemini.gstatic.com",
    "geminiweb-pa.clients.google.com", "geminiweb-pa.clients6.google.com",
    "geminiweb-pa.googleapis.com", "aistudio.google.com", "makersuite.google.com",
    "ai.studio", "ai.google.dev", "generativeai.google", "deepmind.com", "deepmind.google",
    "generativelanguage.googleapis.com", "geller-pa.googleapis.com",
    "proactivebackend-pa.googleapis.com", "proactivebackend-pa.clients6.google.com",
    "robinfrontend-pa.googleapis.com", "alkalicore-pa.clients6.google.com",
    "alkalimakersuite-pa.clients6.google.com", "alkalimakersuite-pa.googleapis.com",
    "webchannel-alkalimakersuite-pa.clients6.google.com",
    "alkalimakersuiteapplets.pa.googleapis.com", "makersuite-pa.clients6.google.com",
    "appsgenaiserver-pa.clients.google.com", "appsgenaiserver-pa.clients6.google.com",
    "appsgenaiserver-pa.googleapis.com", "aisandbox-pa.googleapis.com",
    "chromemodelexecution-pa.googleapis.com",
    # Google Antigravity / Gemini Code Assist / Cloud Code / Vertex AI
    "antigravity.google", "docs.antigravity.google", "antigravity.google.com",
    "antigravity-unleash.goog", "antigravity.googleapis.com", "antigravity-pa.googleapis.com",
    "cloudcode-pa.googleapis.com", "daily-cloudcode-pa.googleapis.com",
    "daily-cloudcode-pa.sandbox.googleapis.com",
    "preprod-daily-cloudcode-pa.sandbox.googleapis.com",
    "autopush-cloudcode-pa.sandbox.googleapis.com", "cloudaicompanion.googleapis.com",
    "staging-cloudaicompanion.sandbox.googleapis.com", "aicode.googleapis.com",
    "aida.googleapis.com", "autopush-aicode.sandbox.googleapis.com",
    "businessaicode.googleapis.com", "businessaicode.us.rep.googleapis.com",
    "businessaicode.eu.rep.googleapis.com", "businessaicode.mtls.googleapis.com",
    "aiplatform.googleapis.com", "us-central1-aiplatform.googleapis.com",
    "us-east5-aiplatform.googleapis.com", "aiplatform.us.rep.googleapis.com",
    "aiplatform.eu.rep.googleapis.com", "aiplatform.mtls.googleapis.com",
    "discoveryengine.googleapis.com", "us-discoveryengine.googleapis.com",
    "eu-discoveryengine.mtls.googleapis.com",
    "antigravity-auto-updater-974169037036.us-central1.run.app",
    "antigravity-cli-auto-updater-974169037036.us-central1.run.app",
    "antigravity-ide-auto-updater-974169037036.us-central1.run.app",
    "antigravity-hub-auto-updater-974169037036.us-central1.run.app",
    # NotebookLM / Jules / Labs / Flow / Opal / Stitch
    "notebooklm.google", "notebooklm.google.com", "notebook.google", "notebook.google.com",
    "notebooklm.cloud.google.com", "notebooklm.googleapis.com", "notebooklm-pa.googleapis.com",
    "labstailwind.pa.googleapis.com", "jules.google", "jules.google.com",
    "jules.googleapis.com", "labs.google", "labs.google.com", "flow.google", "flow.google.com",
    "opal.google", "opal.google.com", "opal.goog", "opal.withgoogle.com",
    "appcatalyst.pa.googleapis.com", "stitch.withgoogle.com", "aitestkitchen.withgoogle.com",
    # Copilot / Cursor / Windsurf / Perplexity / xAI / Overseas AI Platforms
    "api.githubcopilot.com", "api.individual.githubcopilot.com",
    "api.business.githubcopilot.com", "api.enterprise.githubcopilot.com",
    "copilot-proxy.githubusercontent.com", "copilotprodattachments.blob.core.windows.net",
    "copilot.microsoft.com", "copilot.cloud.microsoft", "copilot.com", "sydney.bing.com",
    "cursor.com", "api2.cursor.sh", "cursor-cdn.com", "cursorapi.com", "cursorvm.com",
    "windsurf.com", "windsurf.build", "codeium.com", "codeiumdata.com",
    "www.perplexity.ai", "perplexity.com", "pplx.ai",
    "api.x.ai", "grok.com", "grok.x.com", "grokipedia.com", "grokusercontent.com",
    "openrouter.ai", "api.groq.com", "mistral.ai", "cohere.com", "cohere.ai",
    "poe.com", "dify.ai", "meta.ai", "api.jetbrains.ai", "cerebras.ai",
)
SHARED_DOMAINS = (
    "tenant.auth0.com", "checkout.stripe.com", "api.stripe.com", "sentry.io",
    "algolia.net", "static.cloudflareinsights.com", "intercom.io", "segment.io",
    "launchdarkly.com", "featuregates.org", "api.statsig.com", "identrust.com",
    "challenges.cloudflare.com", "apis.google.com", "accounts.google.com",
    "oauth2.googleapis.com", "www.googleapis.com", "storage.googleapis.com",
    "play.googleapis.com", "waa-pa.clients6.google.com", "signaler-pa.clients6.google.com",
    "people-pa.clients6.google.com", "translate-pa.googleapis.com", "www.gstatic.com",
    "fonts.gstatic.com", "cloud.google.com", "console.cloud.google.com",
    "us-central1-apt.pkg.dev", "other-service-974169037036.us-central1.run.app",
    "livekit.cloud", "www.bing.com",
)
TELEGRAM_DOMAINS = (
    "t.me", "web.telegram.org", "telegram.me", "tdesktop.com", "telegra.ph",
    "telesco.pe", "cdn-telegram.org", "telegram-cdn.org", "fragment.com",
    "tx.me", "tg.dev", "graph.org", "legra.ph", "comments.app", "quiz.directory",
)
TELEGRAM_OFFICIAL_CIDRS = (
    "91.108.56.0/22", "91.108.4.0/22", "91.108.8.0/22", "91.108.16.0/22",
    "91.108.12.0/22", "149.154.160.0/20", "91.105.192.0/23", "91.108.20.0/22",
    "185.76.151.0/24", "2001:b28:f23d::/48", "2001:b28:f23f::/48",
    "2001:67c:4e8::/48", "2001:b28:f23c::/48", "2a0a:f280::/32",
)
PAYMENT_DOMAINS = (
    "www.okx.com", "oklink.com", "okx-dns.com", "www.bybit.com", "bytick.com",
    "bycsi.com", "api.bybit.kz", "stream.bybit.kz", "api.bybit.eu", "stream.bybit.eu",
    "api.bybit.nl", "api.bybit.tr", "stream.bybit.tr", "api.bybit.ae",
    "api.bybit.id", "api.bybitgeorgia.ge", "api.manepa.jp", "stream.manepa.jp",
    "api.spark-fintech.com", "stream.spark-fintech.com", "api.bybit-tr.com",
    "www.binance.com", "bnbstatic.com", "bitget.com", "htx.com", "gate.io",
    "coinbase.com", "kraken.com", "www.paypal.com", "www.paypalobjects.com",
    "www.wise.com", "api.transferwise.com", "api.sandbox.transferwise.tech",
    "revolut.com", "airwallex.com", "redotpay.com", "dupay.one", "onekey.so",
    "pokepay.cc", "hyperliquid.xyz", "uniswap.org", "debank.com", "etherscan.io",
)
FORUM_DOMAINS = (
    "nodeseek.com", "i.nodeimage.com", "deepflood.com", "nodequality.com",
    "linux.do", "connect.linux.do", "linuxdo-uploads.s3.linux.do", "idcflare.com",
    "www.v2ex.com", "i.v2ex.co", "hostloc.com", "2libra.com", "lowendtalk.com",
    "lowendspirit.com", "lowendbox.com", "1lou.me", "xdaforums.com", "reddit.com",
    "i.redd.it", "redditmedia.com", "redditstatic.com", "discord.com",
    "cdn.discordapp.com", "discordapp.net", "discord.gg", "discord.media",
    "discordcdn.com", "x.com", "twitter.com", "t.co", "pbs.twimg.com",
)
DOMESTIC_DOMAINS = (
    "douyin.com", "douyincdn.com", "douyinpic.com", "douyinvod.com", "iesdouyin.com",
    "snssdk.com", "amemv.com", "pstatp.com", "bytedance.com", "byteimg.com",
    "bytetos.com", "bytegoofy.com", "bdurl.net", "zijieapi.com", "toutiao.com",
    "toutiaoimg.com", "ixigua.com", "feishu.cn", "feishucdn.com", "larksuitecdn.com",
    "doubao.com", "volces.com", "volcengine.com", "volccdn.com", "kuaishou.com",
    "yximgs.com", "gifshow.com", "inkuai.com", "xiaohongshu.com", "xhscdn.com",
    "xhslink.com", "pinduoduo.com", "yangkeduo.com", "pddpic.com", "taobao.com",
    "tmall.com", "alicdn.com", "alipay.com", "alipayobjects.com", "1688.com",
    "goofish.com", "aliyundrive.com", "alipan.com", "quark.cn", "dingtalk.com",
    "ddurl.to", "amap.com", "autonavi.com", "ele.me", "elemecdn.com", "cainiao.com",
    "aliyun.com", "aliyuncs.com", "qq.com", "wechat.com", "qpic.cn", "gtimg.com",
    "myqcloud.com", "tenpay.com", "tencent.com", "tencent-cloud.net",
    "servicewechat.com", "weiyun.com", "wemeet.tencent.com", "meituan.com",
    "meituan.net", "dpfile.com", "dianping.com", "sankuai.com", *JD_DOMAINS,
    "policy.jd.com", "baidu.com", "bdstatic.com", "baidupcs.com", "bcebos.com",
    "deepseek.com", "moonshot.cn", "kimi.com", "zhipuai.cn", "bigmodel.cn",
    "chatglm.cn", "qianwen.com", "tongyi.com", "hunyuan.tencent.com",
    "yuanbao.tencent.com", "siliconflow.cn", "stepfun.com", "minimax.io",
    "hailuoai.com", "minimaxi.com", "52pojie.cn", "right.com.cn", "chiphell.com",
    "nga.cn", "ngabbs.com", "178.com", "smzdm.com", "zdmimg.com", "coolapk.com",
    "coolapkmarket.com", "hupu.com", "zhihu.com", "zhimg.com", "douban.com",
    "doubanio.com", "weibo.com", "weibocdn.com", "sinaimg.cn", "tieba.baidu.com",
    "csdn.net", "juejin.cn", "oschina.net", "gitee.com", "cnblogs.com",
    "segmentfault.com", "didichuxing.com", "udache.com", "12306.cn",
    "sf-express.com", "wps.cn", "wps.com", "kdocs.cn", "115.com", "115cdn.com",
    "123pan.com", "123pan.cn", "mihoyo.com", "miyoushe.com", "bhsr.com",
    "yuanshen.com", "kurogames.com", "hypergryph.com", "hg-cdn.com", "taptap.cn",
    "taptap.com", "tapimg.com", "unionpay.com", "95516.com", "icbc.com.cn",
    "ccb.com", "cmbchina.com", "abchina.com", "boc.cn", "bankcomm.com",
    "10086.cn", "189.cn", "10010.com", "ke.com", "dewu.com", "zto.com",
    "dongqiudi.com", "wanmei.com", "lilith.com", "futunn.com", "www.srcb.com",
    "www.papegames.com", "www.ztgame.com", "www.yostar.com", "www.haodf.com",
    "www.renrenche.com", "www.lingxigames.com", "openxlab.org.cn", "cdn.openxlab.org.cn",
    "openxmlformats.org", "wxsnsdy.wxs.qq.com", "mimg.126.net", "img1.126.net",
)
AD_DOMAINS = (
    "ads.union.jd.com", "jzt.jd.com", "stat.m.jd.com", "jrclick.jd.com",
    "cps.360buy.com", "g.click.taobao.com", "ai.m.taobao.com", "re.m.taobao.com",
    "act.qq.com", "openx.net", "analytics.126.net", "ad.xiaomi.com",
)
OVERSEAS_EXCEPTIONS = (
    "services.googleapis.cn", "xn--ngstr-lra8j.com", "google.ms", "nyti.ms",
    "ddns.ms", "bx.in.th", "challenges.cloudflare.com",
)


@dataclass(frozen=True)
class Rule:
    target: str
    body: str
    source: str
    line: int

    @property
    def kind(self):
        return self.body.partition(",")[0]

    def matches_domain(self, domain):
        kind, _, value = self.body.partition(",")
        value = value.split(",", 1)[0]
        host = domain.rstrip(".").lower()
        value = value.lower()
        if kind == "DOMAIN":
            return host == value
        if kind == "DOMAIN-SUFFIX":
            return host == value or host.endswith("." + value)
        if kind == "DOMAIN-KEYWORD":
            return value in host
        if kind == "DOMAIN-REGEX":
            return re.search(value, host, flags=re.IGNORECASE) is not None
        return False

    def matches_ip(self, address):
        if self.kind not in ("IP-CIDR", "IP-CIDR6"):
            return False
        network = ipaddress.ip_network(self.body.split(",")[1], strict=False)
        return address.version == network.version and address in network


def parse_groups(lines):
    groups = {}
    for line in lines:
        if not line.startswith("custom_proxy_group="):
            continue
        fields = line.partition("=")[2].split("`")
        name, kind = fields[:2]
        if name in groups:
            raise ValueError(f"Duplicate group: {name}")
        url_index = next((i for i, field in enumerate(fields)
                          if field.startswith(("http://", "https://"))), len(fields))
        groups[name] = {"type": kind, "selectors": fields[2:url_index],
                        "health": fields[url_index:]}
    return groups


def candidates(group, nodes=NODES):
    result = []
    for selector in group["selectors"]:
        matches = ([selector[2:]] if selector.startswith("[]") else
                   [name for name in nodes if re.search(selector, name)])
        for name in matches:
            if name not in result:
                result.append(name)
    return result


def parse_rules(lines):
    return [Rule(*line.partition("=")[2].split(",", 1), "proxy.ini", number)
            for number, line in enumerate(lines, 1) if line.startswith("ruleset=")]


def inline_rules(entries):
    return [Rule(r.target, r.body[2:], r.source, r.line)
            for r in entries if r.body.startswith("[]")]


def expand_rules(entries, snapshots):
    expanded, skipped = [], []
    for entry in entries:
        if entry.body.startswith("[]"):
            expanded.append(Rule(entry.target, entry.body[2:], entry.source, entry.line))
            continue
        text = snapshots[entry.body]
        for number, raw in enumerate(text.splitlines(), 1):
            body = raw.strip()
            if not body or body.startswith(("#", ";", "//")):
                continue
            rule = Rule(entry.target, body, entry.body, number)
            if rule.kind not in CLASH_REMOTE_TYPES:
                skipped.append(rule)
                continue
            expanded.append(rule)
    return expanded, skipped


def first_domain_match(rules, host):
    # IP, ASN, DNS and process metadata are deliberately not simulated here.
    return next((r for r in rules if r.matches_domain(host) or r.kind in ("FINAL", "MATCH")), None)


def render_rule(rule):
    kind, sep, payload = rule.body.partition(",")
    if kind in ("FINAL", "MATCH"):
        return f"MATCH,{rule.target}"
    value, comma, params = payload.partition(",")
    return f"{kind},{value},{rule.target}" + (f",{params}" if comma else "")


def projection(groups, rules):
    projected = []
    for name, group in groups.items():
        item = {"name": name, "type": group["type"], "proxies": candidates(group)}
        if group["health"]:
            interval, _, tolerance = group["health"][1].split(",")
            item.update(url=group["health"][0], interval=int(interval), tolerance=int(tolerance))
        projected.append(item)
    return {
        "mode": "rule", "log-level": "warning",
        "proxies": [{"name": name, "type": "http", "server": "127.0.0.1", "port": 9}
                    for name in NODES],
        "proxy-groups": projected, "rules": [render_rule(r) for r in rules],
    }


class ProxyIniTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = (ROOT / "proxy.ini").read_text(encoding="utf-8-sig").splitlines()
        cls.groups = parse_groups(cls.lines)
        cls.entries = parse_rules(cls.lines)
        cls.inline = inline_rules(cls.entries)
        cls.sources = {r.body.rsplit("/", 1)[-1]: r for r in cls.entries
                       if r.body.startswith("https://")}

    def test_business_groups_and_single_auto_group(self):
        self.assertEqual(tuple(self.groups), ALL_GROUPS)
        for name in BUSINESS_GROUPS:
            self.assertEqual(self.groups[name]["type"], "select")
        self.assertEqual(self.groups[AUTO_GROUP]["type"], "url-test")

    def test_all_named_nodes_and_default_choices(self):
        for name, group in self.groups.items():
            with self.subTest(group=name):
                self.assertEqual([s for s in group["selectors"] if not s.startswith("[]")], [".*"])
                self.assertEqual([n for n in candidates(group) if n in NODES], list(NODES))
                first = candidates(group)[0]
                expected = "DIRECT" if name == "Ⓜ️ 微软服务" else (
                    AUTO_GROUP if name in ("📲 电报消息", "📹 油管视频", "🐟 漏网之鱼") else NODES[0])
                self.assertEqual(first, expected)
        self.assertEqual(self.groups[AUTO_GROUP]["health"], [TEST_URL, "600,,150"])
        self.assertEqual(candidates(self.groups["🐟 漏网之鱼"])[-1], "DIRECT")

    def test_new_and_renamed_nodes_are_not_dropped(self):
        names = ("🇩🇪 新供应商-德国-01", "Tokyo renamed node", "NL-vm-ws-nl", "custom-node")
        for group in self.groups.values():
            for roster in (names, names[::-1]):
                self.assertEqual([n for n in candidates(group, roster) if n in names], list(roster))

    def test_group_references_are_defined_and_acyclic(self):
        def visit(name, stack):
            if name not in self.groups:
                self.assertIn(name, set(NODES) | BUILTINS)
                return
            self.assertNotIn(name, stack)
            for child in candidates(self.groups[name]):
                visit(child, stack + [name])
        for name in self.groups:
            visit(name, [])

    def test_rules_fit_default_subconverter_ruleset_limit(self):
        self.assertLessEqual(len(self.entries), 64)
        self.assertEqual(len(self.entries), len({(r.target, r.body) for r in self.entries}))
        for rule in self.entries:
            self.assertIn(rule.target, set(self.groups) | BUILTINS)
        self.assertEqual(self.entries[-1].body, "[]FINAL")
        self.assertEqual(sum(r.body == "[]FINAL" for r in self.entries), 1)
        self.assertIn("enable_rule_generator=true", self.lines)
        self.assertIn("overwrite_original_rules=true", self.lines)

    def test_remote_sources_have_expected_business_targets(self):
        targets = {
            "YouTube.list": "📹 油管视频", "TikTok.list": "🎵 TikTok",
            "Netflix.list": "🎥 奈飞视频", "Bahamut.list": "🌍 国外媒体",
            "OneDrive.list": "Ⓜ️ 微软服务", "Microsoft.list": "Ⓜ️ 微软服务",
            "Telegram.list": "📲 电报消息", "Crypto.list": "🪙 加密与支付",
            "Binance.list": "🪙 加密与支付", "PayPal.list": "🪙 加密与支付",
            "Developer.list": "💬 社区论坛", "ProxyMedia.list": "🌍 国外媒体",
            "ProxyGFWlist.list": "🐟 漏网之鱼", "GoogleCNProxyIP.list": "🐟 漏网之鱼",
            "Epic.list": "🐟 漏网之鱼", "Sony.list": "🐟 漏网之鱼",
            "Steam.list": "🐟 漏网之鱼", "GoogleFCM.list": "🐟 漏网之鱼",
        }
        for name, rule in self.sources.items():
            self.assertEqual(rule.target, targets.get(name, "DIRECT") if not name.startswith("Ban") else "REJECT")
        bodies = [r.body for r in self.entries if r.body.startswith("https://")]
        self.assertEqual(len(bodies), len(set(bodies)))

    def test_ai_products_have_domain_coverage_before_microsoft(self):
        for host in AI_DOMAINS:
            with self.subTest(host=host):
                hit = first_domain_match(self.inline, host)
                self.assertEqual(hit.target, "🤖 AI服务")
                self.assertLess(hit.line, self.sources["Microsoft.list"].line)
        for source in ("OpenAI.list", "OpenAi.list", "Claude.list", "China.list"):
            self.assertNotIn(source, self.sources)

    def test_ai_rules_do_not_capture_shared_services_or_lookalikes(self):
        for host in (*SHARED_DOMAINS, "openai.com.example.net", "notchatgpt.com",
                     "api.githubcopilot.com.example.org", "claude.ai.example.net",
                     "antigravity.google.example.org", "notgemini.google.com",
                     "notcloudcode-pa.googleapis.com", "xai.com"):
            with self.subTest(host=host):
                self.assertNotEqual(first_domain_match(self.inline, host).target, "🤖 AI服务")

    def test_merged_regexes_preserve_domain_boundaries(self):
        allowed_chars = set("abcdefghijklmnopqrstuvwxyz0123456789-.()|^$\\")
        for rule in self.inline:
            if rule.kind == "DOMAIN-REGEX":
                pattern = rule.body.split(",", 1)[1]
                re.compile(pattern)
                self.assertTrue(set(pattern).issubset(allowed_chars), pattern)
                self.assertTrue(pattern.endswith("$"))
                self.assertTrue(pattern.startswith(("^", "(^|\\.)")))
        for host in ("notnodeseek.com", "nodeseek.com.example.org", "notbytick.com",
                     "bybit.eu.example.net", "notdeepseek.com", "mimg.126.net.example.org"):
            self.assertEqual(first_domain_match(self.inline, host).kind, "FINAL")

    def test_forums_and_regional_payment_domains_have_explicit_groups(self):
        for host in FORUM_DOMAINS:
            self.assertEqual(first_domain_match(self.inline, host).target, "💬 社区论坛", host)
        for host in ("bytick.com", "bycsi.com", "api.bybit.kz", "stream.bybit.kz",
                     "api.bybit.eu", "stream.bybit.eu", "api.bybit.nl", "api.bybit.tr",
                     "api.bybit.ae", "api.bybit.id", "api.bybitgeorgia.ge", "api.manepa.jp",
                     "stream.manepa.jp", "api.spark-fintech.com", "api.bybit-tr.com",
                     "bitget.com", "htx.com", "www.wise.com", "api.transferwise.com",
                     "api.sandbox.transferwise.tech", "revolut.com", "airwallex.com",
                     "redotpay.com", "dupay.one", "onekey.so", "pokepay.cc", "hyperliquid.xyz"):
            hit = first_domain_match(self.inline, host)
            self.assertEqual(hit.target, "🪙 加密与支付", host)
            self.assertLess(hit.line, self.sources["CN.list"].line)
        for host in ("api.bybit.kz", "stream.bybit.eu", "api.business.githubcopilot.com"):
            self.assertNotEqual(first_domain_match(self.inline, host).target, "🐟 漏网之鱼")

    def test_business_whitelist_is_narrow_and_ad_hosts_are_not_bypassed(self):
        first_ad = min(self.sources[name].line for name in
                       ("BanAD.list", "BanProgramAD.list", "BanEasyListChina.list"))
        early = [r for r in self.inline if r.line < first_ad]
        for host in AD_DOMAINS:
            self.assertFalse(any(r.matches_domain(host) for r in early), host)
        for host in ("policy.jd.com", "mimg.126.net", "wxsnsdy.wxs.qq.com", "openxlab.org.cn"):
            self.assertTrue(any(r.matches_domain(host) and r.target == "DIRECT" for r in early), host)
        for host in ("jd.com", "g.click.taobao.com", "act.qq.com"):
            self.assertFalse(any(r.matches_domain(host) for r in early), host)

    def test_direct_supplement_precedes_general_proxy_lists(self):
        general = min(self.sources[name].line for name in
                      ("Developer.list", "ProxyMedia.list", "ProxyGFWlist.list"))
        for host in ("deepseek.com", "kimi.com", "goofish.com", "pddpic.com", "mihoyo.com",
                     "unionpay.com", "ke.com", "dewu.com", "zto.com", "papegames.com"):
            hit = first_domain_match(self.inline, host)
            self.assertEqual(hit.target, "DIRECT", host)
            self.assertLess(hit.line, general)
        for name in ("CN.list", "ByteDance.list", "Alibaba.list", "ChinaDomain.list"):
            self.assertLess(self.sources[name].line, general)

    def test_overseas_exceptions_precede_direct_sources(self):
        for host in OVERSEAS_EXCEPTIONS:
            hit = first_domain_match(self.inline, host)
            self.assertEqual(hit.target, "🐟 漏网之鱼", host)
            self.assertLess(hit.line, self.sources["CN.list"].line)
        self.assertLess(self.sources["GoogleCNProxyIP.list"].line, self.sources["GoogleCN.list"].line)

    def test_dns_lookup_is_deferred_until_final_china_geoip(self):
        self.assertIn("DIRECT,[]IP-CIDR,5.5.5.5/32,no-resolve",
                      [r.target + ",[]" + r.body for r in self.inline])
        geoip = next(r for r in self.inline if r.kind == "GEOIP")
        self.assertEqual(geoip.body, "GEOIP,CN")
        self.assertGreater(geoip.line, self.sources["ProxyGFWlist.list"].line)
        for r in self.inline:
            if r.kind in ("IP-CIDR", "IP-CIDR6"):
                self.assertTrue(r.body.endswith(",no-resolve"))
        self.assertEqual(self.sources["ChinaIpV6.list"].target, "DIRECT")

    def test_game_downloads_keep_exact_hosts_and_suffix_semantics(self):
        for source in ("SteamCN.list", "GameDownload.list"):
            self.assertLess(self.sources[source].line, self.sources["Steam.list"].line)
        for host in (*EPIC_DOWNLOAD_DOMAINS, *SONY_DOWNLOAD_DOMAINS):
            hit = first_domain_match(self.inline, host)
            self.assertEqual(hit.target, "DIRECT", host)
            self.assertLess(hit.line, self.sources["Epic.list"].line)
            self.assertLess(hit.line, self.sources["Microsoft.list"].line)
            self.assertNotEqual(first_domain_match(self.inline, "other." + host).target, "DIRECT", host)
        for host in ("steamserver.net", *SONY_DOWNLOAD_SUFFIXES):
            self.assertEqual(first_domain_match(self.inline, "cdn." + host).target, "DIRECT")
        for host in ("steamcommunity.com", "epicgames.com", "playstation.net", "unrealengine.com"):
            self.assertNotEqual(first_domain_match(self.inline, host).target, "DIRECT")
        notice = (ROOT / "规则数据许可.txt").read_text(encoding="utf-8")
        self.assertIn("Copyright (c) 2017 UK LAN Techs", notice)

    def test_remote_parser_rejects_missing_snapshots_and_reports_dropped_types(self):
        entry = Rule("🤖 AI服务", "https://example.invalid/rules.list", "proxy.ini", 1)
        with self.assertRaises(KeyError):
            expand_rules([entry], {})
        text = "# synthetic parser fixture\nDOMAIN,api.example.org\nIP-ASN,20473,no-resolve\n"
        rules, dropped = expand_rules([entry], {entry.body: text})
        self.assertEqual([r.kind for r in rules], ["DOMAIN"])
        self.assertEqual([r.kind for r in dropped], ["IP-ASN"])
        self.assertEqual(render_rule(rules[0]), "DOMAIN,api.example.org,🤖 AI服务")

    @unittest.skipUnless(MIHOMO_BIN, "Set MIHOMO_BIN to validate all inline rule syntax")
    def test_mihomo_accepts_groups_and_all_inline_rules(self):
        with tempfile.TemporaryDirectory(prefix="proxy-inline-check-") as directory:
            path = Path(directory) / "config.json"
            path.write_text(json.dumps(projection(self.groups, self.inline), ensure_ascii=False), encoding="utf-8")
            result = subprocess.run([MIHOMO_BIN, "-t", "-d", directory, "-f", str(path)],
                                    capture_output=True, encoding="utf-8", errors="replace", timeout=45)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
