"""Fetch a complete public rule snapshot and check real domain first matches.

Usage: py -3 -B scripts/test/verify_proxy_ini.py [--snapshot <temporary.json>]
       [--mihomo-bin <exe>] [--subconverter-bin <exe>]
Only public rules and synthetic loopback nodes are used. No subscription is read.
"""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import ipaddress
import json
from pathlib import Path
import re
import socket
import subprocess
import tempfile
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from test_proxy_ini import (
    AD_DOMAINS, AI_DOMAINS, DOMESTIC_DOMAINS, EPIC_DOWNLOAD_DOMAINS,
    FORUM_DOMAINS, NODES, OVERSEAS_EXCEPTIONS, PAYMENT_DOMAINS, ROOT, SHARED_DOMAINS,
    SONY_DOWNLOAD_DOMAINS, TELEGRAM_DOMAINS, TELEGRAM_OFFICIAL_CIDRS,
    Rule, candidates, expand_rules, first_domain_match, parse_groups, parse_rules,
    projection, render_rule,
)


def fetch_rules(url):
    fallback = url.replace("https://cdn.jsdelivr.net/gh/", "https://raw.githubusercontent.com/")
    fallback = fallback.replace("@master/", "/master/").replace("@main/", "/main/")
    errors = []
    for address in dict.fromkeys((url, fallback)):
        try:
            request = urllib.request.Request(address, headers={"User-Agent": "proxy-ini-rule-check"})
            with urllib.request.urlopen(request, timeout=20) as response:
                raw = response.read()
            text = raw.decode("utf-8-sig")
            active = [line.strip() for line in text.splitlines()
                      if line.strip() and not line.lstrip().startswith(("#", ";", "//"))]
            allowed = {"DOMAIN", "DOMAIN-SUFFIX", "DOMAIN-KEYWORD", "IP-CIDR", "IP-CIDR6",
                       "SRC-IP-CIDR", "GEOIP", "PROCESS-NAME", "URL-REGEX", "IP-ASN",
                       "DOMAIN-REGEX", "SRC-PORT", "DST-PORT", "FINAL", "MATCH"}
            if not active or any(line.split(",", 1)[0] not in allowed for line in active):
                raise ValueError("Empty or non-classical rule response")
            return {"text": text, "sha256": hashlib.sha256(text.encode()).hexdigest(),
                    "fetched_url": address, "fallback_errors": errors}
        except (OSError, ValueError, urllib.error.URLError) as exc:
            errors.append(f"{address}: {exc}")
    raise RuntimeError("Rule fetch failed; cannot validate partial lists: " + " | ".join(errors))


def check_domains(rules):
    cases = {
        "🤖 AI服务": AI_DOMAINS, "📲 电报消息": TELEGRAM_DOMAINS,
        "🪙 加密与支付": PAYMENT_DOMAINS, "💬 社区论坛": FORUM_DOMAINS,
        "DIRECT": (*DOMESTIC_DOMAINS, *EPIC_DOWNLOAD_DOMAINS, *SONY_DOWNLOAD_DOMAINS),
        "REJECT": AD_DOMAINS,
        "🐟 漏网之鱼": (*OVERSEAS_EXCEPTIONS, "steamcommunity.com", "epicgames.com",
                        "unrealengine.com", "playstation.net", "notnodeseek.com",
                        "nodeseek.com.example.org", "notbytick.com", "bybit.eu.example.net",
                        "notdeepseek.com", "mimg.126.net.example.org", "notchatgpt.com",
                        "api.githubcopilot.com.example.org", "antigravity.google.example.org",
                        "notgemini.google.com", "notcloudcode-pa.googleapis.com", "xai.com"),
    }
    count = 0
    for target, hosts in cases.items():
        for host in hosts:
            hit = first_domain_match(rules, host)
            if hit is None or hit.target != target:
                raise AssertionError(f"{host}: expected {target}, got {hit}")
            count += 1
    for host in (*SHARED_DOMAINS, "openai.com.example.net", "claude.ai.example.net"):
        hit = first_domain_match(rules, host)
        if hit is None or hit.target == "🤖 AI服务":
            raise AssertionError(f"Shared service or unrelated suffix captured by AI rules: {host}: {hit}")
        count += 1
    for rule in rules:
        if rule.target == "DIRECT" and rule.body in (
            "DOMAIN-SUFFIX,ms", "DOMAIN-SUFFIX,in.th", "DOMAIN-KEYWORD,microsoft",
        ):
            raise AssertionError(f"Overbroad direct rule: {rule}")
        if rule.target == "🤖 AI服务" and rule.kind in ("IP-CIDR", "IP-CIDR6", "IP-ASN"):
            raise AssertionError(f"AI must not capture a shared cloud network: {rule}")
    geoip = next(i for i, r in enumerate(rules) if r.body == "GEOIP,CN")
    for rule in rules[:geoip]:
        if rule.kind in ("IP-CIDR", "IP-CIDR6", "GEOIP", "IP-ASN"):
            if not rule.body.endswith(",no-resolve"):
                raise AssertionError(f"Early rule unexpectedly triggers DNS lookup: {rule}")
    for cidr in TELEGRAM_OFFICIAL_CIDRS:
        network = ipaddress.ip_network(cidr)
        for ip in (network.network_address, network.broadcast_address):
            hit = next((r for r in rules if r.matches_ip(ip) or r.kind in ("FINAL", "MATCH")), None)
            if hit is None or hit.target != "📲 电报消息":
                raise AssertionError(f"Telegram address {ip}: {hit}")
    return count


def check_kernel(binary, directory, config_path):
    result = subprocess.run([str(binary), "-t", "-d", str(directory), "-f", str(config_path)],
                            capture_output=True, encoding="utf-8", errors="replace", timeout=90)
    if result.returncode:
        raise RuntimeError(result.stdout + result.stderr)
    print("Mihomo full rule syntax: PASS", flush=True)


def check_converted_groups(yaml, expected):
    # The local converter is explicitly configured to emit block-style groups.
    normalized = "\n".join(yaml.splitlines())
    section_match = re.search(r"(?m)^proxy-groups:\s*\n([\s\S]*?)(?=^[^\s#]|\Z)", normalized)
    if section_match is None:
        raise AssertionError("Missing block-style proxy-groups: " + normalized[:1000])
    section = section_match.group(1)
    actual, current, field = {}, None, None
    for line in section.splitlines():
        if not line.strip():
            continue
        match = re.match(r"^\s*-?\s*(name|type|proxies|url|interval|tolerance):\s*(.*)$", line)
        if match:
            field, value = match.groups()
            value = json.loads(value) if value.startswith('"') else value.strip("'")
            if field == "name":
                if value in actual:
                    raise AssertionError("Duplicate converted group: " + value)
                current = actual[value] = {}
            elif current is not None:
                current[field] = [] if field == "proxies" and not value else value
        elif field == "proxies" and current is not None and line.strip().startswith("- "):
            value = line.strip()[2:]
            value = json.loads(value) if value.startswith('"') else value.strip("'")
            current["proxies"].append(value)
    if tuple(actual) != tuple(expected):
        raise AssertionError("Converted group names/order differ from configuration")
    for name, group in expected.items():
        if actual[name].get("type") != group["type"] or actual[name].get("proxies") != candidates(group):
            raise AssertionError(f"Converted group candidates differ: {name}: {actual[name]}")
    print(f"Converted group candidates and defaults: PASS ({len(actual)} groups, {len(NODES)} synthetic nodes)",
          flush=True)


def check_conversion(binary, config_text, snapshots, expected, groups, directory, mihomo):
    # Serve the exact verified snapshot so a CDN update cannot change this run.
    endpoints = {}
    for index, (url, record) in enumerate(snapshots.items()):
        endpoints[f"/rules/{index}.list"] = record["text"].encode("utf-8")
    subscription = {"proxies": [
        {"name": name, "type": "http", "server": "127.0.0.1", "port": 9}
        for name in NODES
    ]}
    endpoints["/nodes.json"] = json.dumps(subscription, ensure_ascii=False).encode("utf-8")

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            path = urllib.parse.urlsplit(self.path).path
            if path not in endpoints:
                self.send_error(404)
                return
            body = endpoints[path]
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *_):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f"http://127.0.0.1:{server.server_port}"
    for index, url in enumerate(snapshots):
        config_text = config_text.replace(url, origin + f"/rules/{index}.list")
    endpoints["/profile.ini"] = config_text.encode("utf-8")
    probe = socket.socket()
    probe.bind(("127.0.0.1", 0))
    port = probe.getsockname()[1]
    probe.close()
    base = directory / "base.yaml"
    base.write_text("mode: rule\nlog-level: warning\nproxies: []\nproxy-groups: []\nrules: []\n",
                    encoding="utf-8")
    pref = directory / "pref.ini"
    pref.write_text(
        "[common]\napi_mode=false\nenable_insert=false\nbase_path=\n"
        "clash_rule_base=" + str(base).replace("\\", "/") + "\n"
        "proxy_config=NONE\nproxy_ruleset=NONE\nproxy_subscription=NONE\n"
        "[node_pref]\nclash_use_new_field_name=true\nsort_flag=false\n"
        "clash_proxy_groups_style=block\n"
        "[emojis]\nadd_emoji=false\nremove_old_emoji=false\n"
        "[rulesets]\nenabled=true\noverwrite_original_rules=true\n"
        "[server]\nlisten=127.0.0.1\nport=" + str(port) + "\n"
        "[advanced]\nmax_allowed_rulesets=64\nmax_allowed_rules=32768\n"
        "enable_cache=false\nasync_fetch_ruleset=false\n", encoding="utf-8")
    log_path = directory / "subconverter.log"
    process = None
    try:
        with log_path.open("w", encoding="utf-8") as log:
            process = subprocess.Popen([str(binary), "-f", str(pref)], cwd=directory,
                                       stdout=log, stderr=log)
            local = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            root = f"http://127.0.0.1:{port}"
            deadline = time.monotonic() + 15
            while True:
                if process.poll() is not None:
                    raise RuntimeError("Subconverter exited: " + log_path.read_text(encoding="utf-8", errors="replace"))
                try:
                    with local.open(root + "/version", timeout=1) as response:
                        print("Converter:", response.read().decode().strip(), flush=True)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise RuntimeError("Subconverter did not become ready")
                    time.sleep(0.1)
            query = urllib.parse.urlencode({"target": "clash", "new_name": "true",
                                           "url": origin + "/nodes.json", "config": origin + "/profile.ini",
                                           "add_emoji": "false", "remove_emoji": "false", "sort": "false"})
            with local.open(root + "/sub?" + query, timeout=90) as response:
                yaml = response.read().decode("utf-8-sig")
            actual = [line.strip()[2:] for line in yaml.splitlines() if line.strip().startswith("- ")]
            wanted = [render_rule(r) for r in expected]
            actual_rules = [line for line in actual if line.split(",", 1)[0] in
                            ({r.kind for r in expected} | {"MATCH"})]
            if actual_rules != wanted:
                index = next((i for i, pair in enumerate(zip(actual_rules, wanted)) if pair[0] != pair[1]),
                             min(len(actual_rules), len(wanted)))
                raise AssertionError(f"Conversion mismatch at {index}; got {len(actual_rules)} rules, "
                                     f"expected {len(wanted)}; actual={actual_rules[index:index+1]}, "
                                     f"expected={wanted[index:index+1]}")
            check_converted_groups(yaml, groups)
            converted = directory / "converted.yaml"
            converted.write_text(yaml, encoding="utf-8")
            print(f"Subconverter exact rule comparison: PASS ({len(actual_rules)} rules, "
                  "max_allowed_rulesets=64, max_allowed_rules=32768)", flush=True)
            if mihomo:
                check_kernel(mihomo, directory, converted)
    finally:
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--snapshot", type=Path, help="Reuse or create a public-rule JSON snapshot")
    parser.add_argument("--mihomo-bin", type=Path)
    parser.add_argument("--subconverter-bin", type=Path)
    args = parser.parse_args()
    text = (ROOT / "proxy.ini").read_text(encoding="utf-8-sig")
    entries = parse_rules(text.splitlines())
    groups = parse_groups(text.splitlines())
    urls = list(dict.fromkeys(r.body for r in entries if r.body.startswith("https://")))
    if args.snapshot and args.snapshot.exists():
        snapshots = json.loads(args.snapshot.read_text(encoding="utf-8"))
        if set(snapshots) != set(urls):
            raise ValueError("Snapshot source URLs do not match the current config")
        for url, record in snapshots.items():
            if hashlib.sha256(record["text"].encode()).hexdigest() != record["sha256"]:
                raise ValueError("Snapshot hash mismatch: " + url)
    else:
        print(f"Fetching {len(urls)} public rule sources...", flush=True)
        with ThreadPoolExecutor(max_workers=6) as pool:
            snapshots = dict(zip(urls, pool.map(fetch_rules, urls)))
        if args.snapshot:
            args.snapshot.write_text(json.dumps(snapshots, ensure_ascii=False), encoding="utf-8")
    for url, record in snapshots.items():
        if record["fetched_url"] != url:
            print("Source fallback:", url, "->", record["fetched_url"], flush=True)
            for error in record.get("fallback_errors", []):
                print("Fetch attempt failed:", error, flush=True)
    rules, skipped = expand_rules(entries, {url: value["text"] for url, value in snapshots.items()})
    if len(entries) > 64 or len(rules) > 32768:
        raise AssertionError(f"Default conversion limit exceeded: {len(entries)} entries / {len(rules)} rules")
    cases = check_domains(rules)
    print(f"PASS: {len(entries)} ruleset entries, {len(urls)} fetched sources, {len(rules)} expanded rules; "
          f"{cases} domain cases and {len(TELEGRAM_OFFICIAL_CIDRS)} Telegram subnet boundaries", flush=True)
    print("Subconverter-unsupported remote rule types:", dict(Counter(r.kind for r in skipped)), flush=True)
    print("Domain checks do not simulate DNS, ASN, process rules or application reachability.", flush=True)
    with tempfile.TemporaryDirectory(prefix="proxy-full-check-") as tmp:
        directory = Path(tmp)
        if args.subconverter_bin:
            check_conversion(args.subconverter_bin.resolve(), text, snapshots, rules, groups,
                             directory, args.mihomo_bin.resolve() if args.mihomo_bin else None)
        elif args.mihomo_bin:
            config = directory / "expanded.json"
            config.write_text(json.dumps(projection(groups, rules), ensure_ascii=False), encoding="utf-8")
            check_kernel(args.mihomo_bin.resolve(), directory, config)


if __name__ == "__main__":
    main()
