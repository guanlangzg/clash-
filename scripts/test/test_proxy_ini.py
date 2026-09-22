"""Offline checks for this project's Subconverter groups and node names.

Set MIHOMO_BIN to additionally validate a credential-free group projection.
That projection does not replace conversion with the user's Subconverter.
"""

import base64
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
    "ccus-原生解锁-vm-ws",
    "ccus-原生解锁-vm-ws-cdn",
)
US_NODES = (NODES[0], NODES[1], NODES[6], NODES[7])
HK_NODES = (NODES[2], NODES[3], NODES[4], NODES[5])
CDN_NODES = (NODES[1], NODES[3], NODES[5], NODES[7])
BUILTINS = {"DIRECT", "REJECT"}
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
        # These config regexes use the common Python/PCRE2 subset, case-sensitive.
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

    def test_automatic_selection_covers_all_eight_nodes(self):
        group = self.groups["♻️ 自动选择"]
        self.assertEqual(group["type"], "url-test")
        self.assertEqual(candidates(group), list(NODES))

    def test_manual_selection_groups_cover_all_eight_nodes(self):
        names = ("🚀 全部节点", "🚀 手动切换1", "🚀 手动切换2", "🚀 手动切换3")
        for name in names:
            with self.subTest(group=name):
                self.assertEqual(self.groups[name]["type"], "select")
                self.assertEqual(candidates(self.groups[name]), list(NODES))

    def test_main_selection_exposes_manual_groups(self):
        selectors = self.groups["🚀 节点选择"]["selectors"]
        for name in ("🚀 全部节点", "🚀 手动切换1", "🚀 手动切换2", "🚀 手动切换3"):
            self.assertIn(f"[]{name}", selectors)

    def test_fallback_preserves_import_order_for_all_eight_nodes(self):
        group = self.groups["🛡️ 故障转移"]
        self.assertEqual(group["type"], "fallback")
        self.assertEqual(candidates(group), list(NODES))
        self.assertEqual(candidates(group, NODES[::-1]), list(NODES[::-1]))

    def test_regional_and_cdn_groups_cover_the_named_nodes(self):
        expected = {
            "🇺🇲 美国节点": US_NODES,
            "🇭🇰 香港节点": HK_NODES,
            "cdn节点": CDN_NODES,
        }
        for name, nodes in expected.items():
            with self.subTest(group=name):
                self.assertEqual(candidates(self.groups[name]), list(nodes))

    def test_every_group_has_real_candidates(self):
        for name, group in self.groups.items():
            with self.subTest(group=name):
                self.assertTrue(candidates(group), "Empty groups may become DIRECT")

    def test_sensitive_services_select_nodes_independently(self):
        for name in ("🤖 OpenAI", "🎥 奈飞视频", "🎵 TikTok"):
            with self.subTest(group=name):
                group = self.groups[name]
                self.assertEqual(group["type"], "select")
                self.assertEqual(candidates(group), list(US_NODES + HK_NODES))

    def test_filters_do_not_include_unrelated_node_names(self):
        noise = ("other-us-01", "other-hk-cdn", "isusx-test", "notice", "JP-01")
        for name, group in self.groups.items():
            with self.subTest(group=name):
                matched = candidates(group, noise)
                self.assertFalse(set(matched) & set(noise))

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

    def test_default_routes_do_not_send_ai_through_an_empty_group(self):
        def default_route(name):
            visited = set()
            while name in self.groups:
                self.assertNotIn(name, visited)
                visited.add(name)
                group = self.groups[name]
                choices = candidates(group)
                self.assertTrue(choices, f"Empty default route: {name}")
                if group["type"] != "select":
                    return name
                name = choices[0]
            return name

        self.assertIn(default_route("🤖 OpenAI"), NODES)
        self.assertEqual(default_route("🚀 节点选择"), "♻️ 自动选择")
        self.assertEqual(default_route("🐟 漏网之鱼"), "♻️ 自动选择")
        self.assertEqual(default_route("🎯 全球直连"), "DIRECT")
        self.assertEqual(default_route("🌏 国内媒体"), "DIRECT")
        self.assertEqual(default_route("📺 哔哩哔哩"), "DIRECT")

    def test_health_checks_use_https_and_valid_parameters(self):
        for name, group in self.groups.items():
            if group["type"] == "select":
                continue
            with self.subTest(group=name):
                self.assertEqual(len(group["health"]), 2)
                url, settings = group["health"]
                self.assertTrue(url.startswith("https://"))
                params = settings.split(",")
                self.assertGreater(int(params[0]), 0)
                for param in params[1:]:
                    if param:
                        self.assertGreaterEqual(int(param), 0)

    def test_rules_target_defined_groups_and_end_with_final(self):
        for rule in self.rules:
            self.assertIn(rule.split(",", 1)[0], set(self.groups) | BUILTINS)
        final_rules = [rule for rule in self.rules if rule.endswith(",[]FINAL")]
        self.assertEqual(final_rules, [self.rules[-1]])

    def test_rules_have_no_duplicate_entries(self):
        self.assertEqual(len(self.rules), len(set(self.rules)))

    def test_ad_rules_use_one_verified_classical_source(self):
        ad_rules = [rule for rule in self.rules if rule.startswith("🛑 广告拦截,")]
        self.assertEqual(len(ad_rules), 1)
        self.assertIn("ACL4SSR/ACL4SSR@master/Clash/BanProgramAD.list", ad_rules[0])
        self.assertNotIn("REIJI007/AdBlock_Rule_For_Clash", ad_rules[0])
        self.assertFalse(any(rule.startswith("🍃 应用净化,") for rule in self.rules))
        self.assertNotIn("🍃 应用净化", self.groups)

    def test_google_direct_exceptions_precede_general_proxy_rules(self):
        source_order = {
            rule.rsplit("/", 1)[-1]: index
            for index, rule in enumerate(self.rules)
        }
        proxy_ip = source_order["GoogleCNProxyIP.list"]
        direct = source_order["GoogleCN.list"]
        general = source_order["ProxyGFWlist.list"]
        self.assertTrue(self.rules[direct].startswith("🎯 全球直连,"))
        self.assertLess(proxy_ip, direct)
        self.assertLess(direct, general)

    def test_ai_rules_are_deduplicated_and_ordered_before_other_services(self):
        ai_rules = [rule for rule in self.rules if rule.startswith("🤖 OpenAI,")]
        self.assertEqual(
            ai_rules,
            [
                "🤖 OpenAI,https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/OpenAI/OpenAI.list",
                "🤖 OpenAI,https://cdn.jsdelivr.net/gh/blackmatrix7/ios_rule_script@master/rule/Clash/Claude/Claude.list",
            ],
        )
        self.assertNotIn("challenges.cloudflare.com", "\\n".join(ai_rules))
        self.assertNotIn("ACL4SSR/ACL4SSR@master/Clash/Ruleset/AI.list", "\\n".join(ai_rules))
        ai_indices = [index for index, rule in enumerate(self.rules)
                      if rule.startswith("🤖 OpenAI,")]
        self.assertEqual(ai_indices, list(range(ai_indices[0], ai_indices[0] + len(ai_rules))))
        later_targets = [rule.split(",", 1)[0] for rule in self.rules[ai_indices[-1] + 1:]]
        self.assertNotIn("🤖 OpenAI", later_targets)
        self.assertLess(ai_indices[0], next(index for index, rule in enumerate(self.rules)
                                            if rule.startswith("📲 电报消息,")))
        self.assertLess(ai_indices[-1], next(index for index, rule in enumerate(self.rules)
                                             if rule.startswith("🌍 国外媒体,")))

    @unittest.skipUnless(MIHOMO_BIN, "Set MIHOMO_BIN for offline kernel validation")
    def test_mihomo_accepts_credential_free_group_projection(self):
        projected = []
        for name, group in self.groups.items():
            item = {"name": name, "type": group["type"], "proxies": candidates(group)}
            if group["health"]:
                item["url"] = group["health"][0]
                params = group["health"][1].split(",")
                item["interval"] = int(params[0])
                if group["type"] == "url-test" and len(params) > 2 and params[2]:
                    item["tolerance"] = int(params[2])
            projected.append(item)
        config = {
            "mode": "rule",
            "log-level": "warning",
            "proxies": [{"name": name, "type": "http", "server": "127.0.0.1", "port": 9}
                        for name in NODES],
            "proxy-groups": projected,
            "rules": ["MATCH,🐟 漏网之鱼"],
        }
        encoded = base64.b64encode(
            json.dumps(config, ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        # -t only parses; loopback stand-ins never dial the supplied VMess endpoints.
        with tempfile.TemporaryDirectory(prefix="proxy-ini-check-") as directory:
            result = subprocess.run(
                [MIHOMO_BIN, "-t", "-d", directory, "-config", encoded],
                capture_output=True, encoding="utf-8", errors="replace", timeout=30,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main(verbosity=2)
