"""Offline checks for this project's Subconverter groups, rules and node names.

NODES retains the last observed 16-node name shapes with synthetic UUIDs.
It checks name selection, not the current subscription or service availability.
Set MIHOMO_BIN to additionally validate a credential-free group projection;
that projection does not replace conversion with the user's Subconverter.
"""

import json
import os
from pathlib import Path
import re
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[2]
NODES = (
    "isus-原生解锁",
    "isus-原生解锁-cdn",
    "hyhk-vm-ws",
    "hyhk-vm-ws-cdn",
    "xzhk-vm-ws",
    "xzhk-vm-ws-cdn",
    "🇳🇱 NL-vm-ws-nl",
    "🇳🇱 NL-vm-ws-cdn",
    "🇯🇵 cheaphost-日本-流媒体-解锁",
    "🇸🇬 三网优化SG伪家宽-解锁-vless",
    "🇯🇵 绿云 IIJ-日本-流媒体-解锁-vl-reality-vision-deadbeef-dead-beef-dead-beefdeadbeef",
    "🇯🇵 绿云 IIJ-日本-流媒体-解锁-vm-ws-deadbeef-dead-beef-dead-beefdeadbeef",
    "🇺🇸 racknerd-us-解锁-vless",
    "🇺🇸 racknerd-us-解锁-cdn",
    "🇯🇵 cheaphost-日本-流媒体-解锁-cdn",
    "🇸🇬 三网优化SG伪家宽-解锁-cdn",
)
BUSINESS_GROUPS = (
    "🤖 AI服务", "📹 油管视频", "🎵 TikTok", "🌍 国外媒体",
    "🎥 奈飞视频", "Ⓜ️ 微软服务", "🐟 漏网之鱼",
)
AUTO_GROUP = "♻️ 自动选择"
ALL_GROUPS = BUSINESS_GROUPS + (AUTO_GROUP,)
ALL_NODES_SELECTOR = ".*"
TEST_URL = "https://www.gstatic.com/generate_204"
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
BUILTINS = {"DIRECT", "REJECT"}
GROUP_SECTION_COMMENT = "; ---------- 全节点选择与自动入口 ----------"
MIHOMO_BIN = os.environ.get("MIHOMO_BIN")


def parse_groups(lines):
    groups = {}
    for line in lines:
        if not line.startswith("custom_proxy_group="):
            continue
        fields = line.partition("=")[2].split("`")
        name, kind = fields[:2]
        if name in groups:
            raise ValueError(f"Duplicate group: {name}")
        url_index = next(
            (i for i, field in enumerate(fields)
             if field.startswith(("http://", "https://"))),
            len(fields),
        )
        groups[name] = {
            "type": kind,
            "selectors": [field for field in fields[2:url_index] if field],
            "health": fields[url_index:],
        }
    return groups


def candidates(group, nodes=NODES):
    result = []
    for selector in group["selectors"]:
        # These selectors use a case-sensitive subset shared with Subconverter.
        matches = ([selector[2:]] if selector.startswith("[]") else
                   [name for name in nodes if re.search(selector, name)])
        for name in matches:
            if name not in result:
                result.append(name)
    return result


class ProxyIniTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lines = (ROOT / "proxy.ini").read_text(encoding="utf-8-sig").splitlines()
        cls.groups = parse_groups(cls.lines)
        cls.rules = [line.partition("=")[2] for line in cls.lines
                     if line.startswith("ruleset=")]
        cls.sources = {rule.rsplit("/", 1)[-1]: (index, rule.split(",", 1)[0])
                       for index, rule in enumerate(cls.rules) if ",https://" in rule}

    def test_only_seven_business_groups_and_one_auto_group_exist(self):
        self.assertEqual(tuple(self.groups), ALL_GROUPS)

    def test_business_groups_are_manual_without_extra_manual_twins(self):
        for name in BUSINESS_GROUPS:
            with self.subTest(group=name):
                self.assertEqual(self.groups[name]["type"], "select")
                self.assertEqual(self.groups[name]["health"], [])
        self.assertFalse(any("手动" in name for name in self.groups))
        self.assertEqual([name for name, group in self.groups.items()
                          if group["type"] != "select"], [AUTO_GROUP])

    def test_business_groups_offer_all_nodes_and_the_single_auto_group(self):
        for name in BUSINESS_GROUPS:
            with self.subTest(group=name):
                expected = [ALL_NODES_SELECTOR, f"[]{AUTO_GROUP}"]
                if name == "Ⓜ️ 微软服务":
                    expected = ["[]DIRECT", f"[]{AUTO_GROUP}", ALL_NODES_SELECTOR]
                elif name in ("📹 油管视频", "🐟 漏网之鱼"):
                    expected = [f"[]{AUTO_GROUP}", ALL_NODES_SELECTOR]
                    if name == "🐟 漏网之鱼":
                        expected.append("[]DIRECT")
                self.assertEqual(self.groups[name]["selectors"], expected)
                self.assertEqual([selector[2:] for selector in expected
                                  if selector.startswith("[]") and selector[2:] in self.groups],
                                 [AUTO_GROUP])

    def test_automatic_selection_uses_all_nodes_and_stability_parameters(self):
        group = self.groups[AUTO_GROUP]
        self.assertEqual(group["type"], "url-test")
        self.assertEqual(group["selectors"], [ALL_NODES_SELECTOR])
        self.assertEqual(group["health"], [TEST_URL, "600,,150"])
        self.assertEqual(candidates(group), list(NODES))

    def test_every_business_group_covers_all_named_nodes(self):
        for name in BUSINESS_GROUPS:
            with self.subTest(group=name):
                matched = candidates(self.groups[name])
                self.assertEqual([node for node in matched if node in NODES], list(NODES))
                self.assertEqual(len([node for node in matched if node in NODES]), len(NODES))

    def test_all_node_selectors_accept_new_families_and_renamed_nodes(self):
        names = ("ccus-returning", "🇩🇪 新供应商-德国-01", "Tokyo renamed node",
                 "NL-vm-ws-nl", "custom-node", "🇭🇰 other-hk-cdn", "JP-01")
        for group_name in ALL_GROUPS:
            with self.subTest(group=group_name):
                group = self.groups[group_name]
                matched = candidates(group, names)
                self.assertEqual([node for node in matched if node in names], list(names))
                self.assertEqual([selector for selector in group["selectors"]
                                  if not selector.startswith("[]")], [ALL_NODES_SELECTOR])
                reversed_names = names[::-1]
                self.assertEqual([node for node in candidates(group, reversed_names)
                                  if node in names], list(reversed_names))

    def test_all_node_selectors_do_not_implicitly_include_strategy_groups(self):
        for name, group in self.groups.items():
            with self.subTest(group=name):
                actual_group_refs = set(candidates(group)) & set(self.groups)
                explicit_group_refs = {selector[2:] for selector in group["selectors"]
                                       if selector.startswith("[]") and selector[2:] in self.groups}
                self.assertEqual(actual_group_refs, explicit_group_refs)
                self.assertNotIn(name, actual_group_refs)

    def test_group_references_are_defined_and_acyclic(self):
        def visit(name, stack):
            if name not in self.groups:
                self.assertIn(name, set(NODES) | BUILTINS)
                return
            self.assertNotIn(name, stack, f"Group cycle: {stack + [name]}")
            for child in candidates(self.groups[name]):
                visit(child, stack + [name])

        for name in self.groups:
            with self.subTest(group=name):
                visit(name, [])

    def test_default_choices_are_explicit_and_nonempty(self):
        for name in BUSINESS_GROUPS:
            with self.subTest(group=name):
                choices = candidates(self.groups[name])
                self.assertTrue(choices, "Empty groups may be converted to DIRECT")
                if name == "Ⓜ️ 微软服务":
                    expected = "DIRECT"
                elif name in ("📹 油管视频", "🐟 漏网之鱼"):
                    expected = AUTO_GROUP
                else:
                    expected = NODES[0]
                self.assertEqual(choices[0], expected)
        self.assertEqual(candidates(self.groups["🐟 漏网之鱼"])[-1], "DIRECT")

    def test_group_section_documents_the_all_nodes_contract(self):
        self.assertIn(GROUP_SECTION_COMMENT, self.lines)
        selectors = [selector for group in self.groups.values() for selector in group["selectors"]
                     if not selector.startswith("[]")]
        self.assertEqual(selectors, [ALL_NODES_SELECTOR] * len(ALL_GROUPS))

    def test_rules_target_defined_groups_and_end_with_final(self):
        for rule in self.rules:
            self.assertIn(rule.split(",", 1)[0], set(self.groups) | BUILTINS)
        final_rules = [rule for rule in self.rules if rule.endswith(",[]FINAL")]
        self.assertEqual(final_rules, ["🐟 漏网之鱼,[]FINAL"])
        self.assertEqual(self.rules[-1], final_rules[0])

    def test_rules_have_no_duplicate_entries(self):
        self.assertEqual(len(self.rules), len(set(self.rules)))

    def test_remote_sources_are_not_reused_with_conflicting_targets(self):
        sources = [rule.split(",", 1)[1] for rule in self.rules if ",https://" in rule]
        self.assertEqual(len(sources), len(set(sources)))

    def test_business_rule_sources_keep_their_targets(self):
        expected = {
            "YouTube.list": "📹 油管视频",
            "TikTok.list": "🎵 TikTok",
            "Netflix.list": "🎥 奈飞视频",
            "Bahamut.list": "🌍 国外媒体",
            "ProxyMedia.list": "🌍 国外媒体",
            "OneDrive.list": "Ⓜ️ 微软服务",
            "Microsoft.list": "Ⓜ️ 微软服务",
            "Telegram.list": "🐟 漏网之鱼",
            "Developer.list": "🐟 漏网之鱼",
            "GoogleCNProxyIP.list": "🐟 漏网之鱼",
            "ProxyGFWlist.list": "🐟 漏网之鱼",
            "Epic.list": "🐟 漏网之鱼",
            "Sony.list": "🐟 漏网之鱼",
            "Steam.list": "🐟 漏网之鱼",
            "GoogleFCM.list": "🐟 漏网之鱼",
        }
        for source, target in expected.items():
            with self.subTest(source=source):
                self.assertEqual(self.sources[source][1], target)

    def test_domestic_and_default_direct_services_cannot_select_a_proxy(self):
        sources = (
            "LocalAreaNetwork.list", "UnBan.list", "BilibiliHMT.list", "Bilibili.list",
            "NetEaseMusic.list", "ChinaMedia.list", "ChinaDomain.list", "ChinaCompanyIp.list",
            "ChinaIp.list", "Download.list", "GoogleCN.list", "Apple.list", "SteamCN.list",
        )
        for source in sources:
            with self.subTest(source=source):
                self.assertEqual(self.sources[source][1], "DIRECT")
        self.assertIn("DIRECT,[]GEOIP,CN,no-resolve", self.rules)
        self.assertIn("DIRECT,[]IP-CIDR,5.5.5.5/32", self.rules)

    def test_game_download_exceptions_precede_platform_proxy_rules(self):
        steam_index = self.sources["Steam.list"][0]
        self.assertLess(self.sources["SteamCN.list"][0], steam_index)
        for rule in ("DIRECT,[]DOMAIN-SUFFIX,steamserver.net",
                     "DIRECT,[]DOMAIN,steampipe.akamaized.net"):
            self.assertIn(rule, self.rules)
            self.assertLess(self.rules.index(rule), steam_index)
        for source, kind, domains in (
            ("Epic.list", "DOMAIN", EPIC_DOWNLOAD_DOMAINS),
            ("Sony.list", "DOMAIN", SONY_DOWNLOAD_DOMAINS),
            ("Sony.list", "DOMAIN-SUFFIX", SONY_DOWNLOAD_SUFFIXES),
        ):
            for domain in domains:
                with self.subTest(source=source, domain=domain):
                    rule = f"DIRECT,[]{kind},{domain}"
                    self.assertIn(rule, self.rules)
                    self.assertLess(self.rules.index(rule), self.sources[source][0])
        for domain in ("steampowered.com", "steamcommunity.com", "epicgames.com",
                       "unrealengine.com", "playstation.com", "playstation.net", "sony.com"):
            with self.subTest(domain=domain):
                self.assertNotIn(f"DIRECT,[]DOMAIN-SUFFIX,{domain}", self.rules)
        first_general = min(self.sources[source][0] for source in
                            ("Developer.list", "ProxyMedia.list", "ProxyGFWlist.list"))
        for source in ("Steam.list", "Epic.list", "Sony.list", "GoogleFCM.list"):
            self.assertLess(self.sources[source][0], first_general)

    def test_reused_download_data_has_its_license_notice(self):
        notice = (ROOT / "规则数据许可.txt").read_text(encoding="utf-8")
        for text in ("MIT License", "Copyright (c) 2017 UK LAN Techs",
                     "uklans/cache-domains/blob/master/epicgames.txt",
                     "uklans/cache-domains/blob/master/sony.txt"):
            self.assertIn(text, notice)

    def test_jd_domains_are_direct_before_proxy_and_ad_rules(self):
        first_non_direct = next(index for index, rule in enumerate(self.rules)
                                if not rule.startswith("DIRECT,"))
        for domain in JD_DOMAINS:
            with self.subTest(domain=domain):
                rule = f"DIRECT,[]DOMAIN-SUFFIX,{domain}"
                self.assertIn(rule, self.rules)
                self.assertLess(self.rules.index(rule), first_non_direct)

    def test_domestic_domain_rules_precede_broad_overseas_rules(self):
        first_broad = min(self.sources[source][0] for source in
                          ("Developer.list", "ProxyMedia.list", "ProxyGFWlist.list"))
        for source in ("BilibiliHMT.list", "Bilibili.list", "NetEaseMusic.list",
                       "ChinaMedia.list", "ChinaDomain.list", "GoogleCN.list"):
            with self.subTest(source=source):
                self.assertLess(self.sources[source][0], first_broad)

    def test_ad_rules_use_one_classical_source_and_builtin_reject(self):
        ad_rules = [rule for rule in self.rules if rule.startswith("REJECT,")]
        self.assertEqual(ad_rules, [
            "REJECT,https://cdn.jsdelivr.net/gh/ACL4SSR/ACL4SSR@master/Clash/BanProgramAD.list",
        ])
        self.assertNotIn("REIJI007/AdBlock_Rule_For_Clash", "\n".join(self.rules))
        self.assertLess(self.rules.index(ad_rules[0]),
                        next(index for index, rule in enumerate(self.rules)
                             if rule.startswith("🤖 AI服务,")))

    def test_google_direct_exceptions_precede_general_proxy_rules(self):
        proxy_ip = self.sources["GoogleCNProxyIP.list"][0]
        direct = self.sources["GoogleCN.list"][0]
        general = self.sources["ProxyGFWlist.list"][0]
        self.assertEqual(self.sources["GoogleCN.list"][1], "DIRECT")
        self.assertLess(proxy_ip, direct)
        self.assertLess(direct, general)
        for domain in ("xn--ngstr-lra8j.com", "services.googleapis.cn"):
            rule = f"🐟 漏网之鱼,[]DOMAIN-SUFFIX,{domain}"
            self.assertIn(rule, self.rules)
            self.assertLess(self.rules.index(rule), direct)

    def test_specific_media_rules_precede_general_media_rules(self):
        general = self.sources["ProxyMedia.list"][0]
        for source in ("YouTube.list", "TikTok.list", "Netflix.list", "Bahamut.list"):
            with self.subTest(source=source):
                self.assertLess(self.sources[source][0], general)

    def test_ai_rules_are_deduplicated_contiguous_and_before_other_services(self):
        ai_rules = [rule for rule in self.rules if rule.startswith("🤖 AI服务,")]
        expected = [
            "🤖 AI服务,https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.list",
            "🤖 AI服务,https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Claude/Claude.list",
            "🤖 AI服务,[]DOMAIN,aistudio.google.com",
            "🤖 AI服务,[]DOMAIN,makersuite.google.com",
            "🤖 AI服务,[]DOMAIN,gemini.google.com",
            "🤖 AI服务,[]DOMAIN,generativelanguage.googleapis.com",
            "🤖 AI服务,[]DOMAIN,api.githubcopilot.com",
            "🤖 AI服务,[]DOMAIN,copilot-proxy.githubusercontent.com",
            "🤖 AI服务,[]DOMAIN,copilot.microsoft.com",
            "🤖 AI服务,[]DOMAIN,sydney.bing.com",
            "🤖 AI服务,[]DOMAIN-SUFFIX,perplexity.ai",
            "🤖 AI服务,[]DOMAIN-SUFFIX,x.ai",
            "🤖 AI服务,[]DOMAIN-SUFFIX,grok.com",
        ]
        self.assertEqual(ai_rules, expected)
        ai_indices = [index for index, rule in enumerate(self.rules)
                      if rule.startswith("🤖 AI服务,")]
        self.assertEqual(ai_indices, list(range(ai_indices[0], ai_indices[0] + len(ai_rules))))
        for source in ("YouTube.list", "TikTok.list", "Netflix.list", "ProxyMedia.list",
                       "OneDrive.list", "Microsoft.list", "Telegram.list"):
            with self.subTest(source=source):
                self.assertLess(ai_indices[-1], self.sources[source][0])

    def test_ai_rules_do_not_capture_shared_infrastructure(self):
        ai_rules = "\n".join(rule for rule in self.rules if rule.startswith("🤖 AI服务,"))
        for forbidden in (
            "challenges.cloudflare.com", "ACL4SSR/ACL4SSR@master/Clash/Ruleset/AI.list",
            "rule/Clash/Gemini/Gemini.list", "rule/Clash/Copilot/Copilot.list",
            "[]DOMAIN-SUFFIX,auth0.com", "[]DOMAIN-SUFFIX,stripe.com",
            "[]DOMAIN,www.bing.com", "[]DOMAIN,apis.google.com",
            "[]DOMAIN-KEYWORD,generativelanguage",
        ):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, ai_rules)

    def test_cloudflare_challenge_resources_use_the_default_outbound_before_media(self):
        rule = "🐟 漏网之鱼,[]DOMAIN-SUFFIX,challenges.cloudflare.com"
        challenge_rules = [item for item in self.rules if "challenges.cloudflare.com" in item]
        self.assertEqual(challenge_rules, [rule])
        self.assertLess(self.rules.index(rule), self.sources["ProxyMedia.list"][0])

    def test_ai_core_domains_are_explicitly_covered(self):
        required = {
            "aistudio.google.com": "DOMAIN",
            "makersuite.google.com": "DOMAIN",
            "gemini.google.com": "DOMAIN",
            "generativelanguage.googleapis.com": "DOMAIN",
            "api.githubcopilot.com": "DOMAIN",
            "copilot-proxy.githubusercontent.com": "DOMAIN",
            "copilot.microsoft.com": "DOMAIN",
            "sydney.bing.com": "DOMAIN",
            "perplexity.ai": "DOMAIN-SUFFIX",
            "x.ai": "DOMAIN-SUFFIX",
            "grok.com": "DOMAIN-SUFFIX",
        }
        for domain, rtype in required.items():
            with self.subTest(domain=domain):
                self.assertIn(f"🤖 AI服务,[]{rtype},{domain}", self.rules)

    def test_rule_generation_stays_enabled(self):
        self.assertIn("enable_rule_generator=true", self.lines)
        self.assertIn("overwrite_original_rules=true", self.lines)

    @unittest.skipUnless(MIHOMO_BIN, "Set MIHOMO_BIN for offline kernel validation")
    def test_mihomo_accepts_credential_free_group_projection(self):
        projected = []
        for name, group in self.groups.items():
            item = {"name": name, "type": group["type"], "proxies": candidates(group)}
            if group["health"]:
                interval, _, tolerance = group["health"][1].split(",")
                item.update(url=group["health"][0], interval=int(interval), tolerance=int(tolerance))
            projected.append(item)
        config = {
            "mode": "rule",
            "log-level": "warning",
            "proxies": [{"name": name, "type": "http", "server": "127.0.0.1", "port": 9}
                        for name in NODES],
            "proxy-groups": projected,
            "rules": ["MATCH,🐟 漏网之鱼"],
        }
        # Windows argv caps near 32KB, so pass the projection as a UTF-8 file.
        with tempfile.TemporaryDirectory(prefix="proxy-ini-check-") as directory:
            config_path = os.path.join(directory, "config.json")
            with open(config_path, "w", encoding="utf-8") as handle:
                handle.write(json.dumps(config, ensure_ascii=False))
            result = subprocess.run(
                [MIHOMO_BIN, "-t", "-d", directory, "-f", config_path],
                capture_output=True, encoding="utf-8", errors="replace", timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
