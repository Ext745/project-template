#!/usr/bin/env python3
"""Redact personal / secret data from logs and raw output before publishing.

Best-effort pattern matching, not a guarantee. It catches the common leaks in
hardware/network projects: modem identifiers (IMEI/IMSI/ICCID), phone numbers,
WireGuard/base64 keys, PEM private keys, credentials in key=value or AT
commands, MAC addresses, public IPv4/IPv6 addresses and emails. Private
address ranges (RFC1918, loopback, link-local, CGNAT 100.64/10) are kept.

Usage:
  scrub.py FILE...                 print scrubbed text to stdout
  scrub.py --in-place FILE...      rewrite files
  scrub.py --check FILE...         list findings, exit 1 if any (pre-commit/CI)
  git log -p | scrub.py --check -  check text from stdin
  scrub.py --git-history [REPO]    check every added line in all commits; reports commit/file/kind
  cmd | scrub.py -                 filter stdin
  scrub.py --self-test

Lines containing the marker  scrub:allow  are left untouched.
"""
import argparse
import ipaddress
import re
import subprocess
import sys

ALLOW_MARKER = "scrub:allow"

_PEM = re.compile(
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?-----END [A-Z ]*PRIVATE KEY-----", re.S
)

# (kind, regex, replacement). Order matters: specific before generic.
_RULES = [
    ("at-credentials", re.compile(r'(AT\+(?:CGAUTH|QICSGP|CSTT)=[^"\r\n]*)"[^"\r\n]*"\s*,\s*"[^"\r\n]*"', re.I),
     r'\1"<REDACTED>","<REDACTED>"'),
    ("credential", re.compile(
        r"(?i)\b(password|passwd|pwd|secret|token|api[_-]?key|private[_-]?key|presharedkey|psk)(\s*[=:]\s*)(\"[^\"]*\"|'[^']*'|\S+)"),
     r"\1\2<REDACTED>"),
    ("wireguard-key", re.compile(r"(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{42}[AEIMQUYcgkosw048]=(?![A-Za-z0-9+/=])"),
     "<KEY>"),
    ("email", re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"), "<EMAIL>"),
    ("mac", re.compile(r"\b(?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2}\b"), "<MAC>"),
    ("iccid", re.compile(r"\b89\d{16,18}[0-9Ff]?\b"), "<ICCID>"),
    ("imei-imsi", re.compile(r"(?<![\d.])\d{15}(?![\d.])"), "<ID15>"),
    ("phone", re.compile(r"(?<![\w+])\+\d{7,15}\b"), "<PHONE>"),
]

_IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")
# Full-form IPv6 with >= 4 groups (avoids matching hh:mm:ss times), or compressed with '::'.
_IPV6 = re.compile(
    r"(?<![0-9A-Fa-f:])(?:(?:[0-9A-Fa-f]{1,4}:){3,7}[0-9A-Fa-f]{1,4}"
    r"|(?:[0-9A-Fa-f]{1,4}:){1,6}:(?:[0-9A-Fa-f]{1,4}:){0,5}[0-9A-Fa-f]{1,4})(?![0-9A-Fa-f:])"
)
_CGNAT = ipaddress.ip_network("100.64.0.0/10")


def _ip_public(text):
    try:
        ip = ipaddress.ip_address(text)
    except ValueError:
        return False
    if ip.version == 4 and ip in _CGNAT:
        return False
    return ip.is_global


def _scrub_line(line, findings=None):
    if ALLOW_MARKER in line:
        return line

    def note(kind):
        if findings is not None:
            findings.append(kind)

    for kind, rx, repl in _RULES:
        line, n = rx.subn(repl, line)
        if n:
            note(kind)

    def ip_repl(tag):
        def _r(m):
            if _ip_public(m.group(0)):
                note("public-ip")
                return tag
            return m.group(0)
        return _r

    line = _IPV4.sub(ip_repl("<IPV4>"), line)
    line = _IPV6.sub(ip_repl("<IPV6>"), line)
    return line


def scrub_text(text, findings=None):
    """Return text with sensitive data redacted. Appends finding kinds to `findings`."""
    def pem_repl(m):
        if findings is not None:
            findings.append("pem-private-key")
        return "<PRIVATE-KEY>"
    text = _PEM.sub(pem_repl, text)
    return "".join(_scrub_line(l, findings) for l in text.splitlines(keepends=True))


def check_files(paths):
    total = 0
    for path in paths:
        try:
            if path == "-":
                content = sys.stdin.read()
            else:
                with open(path, encoding="utf-8", errors="replace") as f:
                    content = f.read()
        except (OSError, IsADirectoryError):
            continue
        pem = []
        scrub_text(content, pem)  # catches multi-line PEM blocks
        if "pem-private-key" in pem:
            print(f"{path}: pem-private-key")
            total += 1
        for no, line in enumerate(content.splitlines(), 1):
            found = []
            _scrub_line(line, found)
            for kind in sorted(set(found)):
                print(f"{path}:{no}: {kind}")
                total += 1
    if total:
        print(f"\n{total} finding(s). Scrub with: python3 tools/scrub.py --in-place <file>"
              f"\nFalse positive? add '{ALLOW_MARKER}' to that line.", file=sys.stderr)
    return 1 if total else 0


DEFAULT_HISTORY_EXCLUDES = ("tools/scrub.py", "*lock.json", "*.lock")
_PEM_START = re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")


def scan_git_history(repo=".", excludes=DEFAULT_HISTORY_EXCLUDES):
    """Scan lines added in every commit on every ref. Works on bare/mirror repos.
    Returns a list of dicts: {commit, file, kind}, one per unique (commit, file, kind)."""
    cmd = ["git", "-C", repo, "log", "-p", "--all", "--no-color", "--no-ext-diff",
           "--format=COMMIT %H", "--", "."] + [f":!{e}" for e in excludes]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
                            text=True, errors="replace")
    commit = path = None
    seen, findings = set(), []
    for line in proc.stdout:
        if line.startswith("COMMIT "):
            commit = line[7:].strip()[:10]
        elif line.startswith("+++ "):
            path = line[6:].rstrip("\n") if line.startswith("+++ b/") else None
        elif line.startswith("+") and path:
            text = line[1:]
            found = ["pem-private-key"] if _PEM_START.search(text) else []
            _scrub_line(text, found)
            for kind in found:
                key = (commit, path, kind)
                if key not in seen:
                    seen.add(key)
                    findings.append({"commit": commit, "file": path, "kind": kind})
    proc.wait()
    if proc.returncode not in (0, None):
        raise RuntimeError(f"git log failed in {repo} (exit {proc.returncode})")
    return findings


def check_git_history(repo="."):
    findings = scan_git_history(repo)
    for f in findings:
        print(f"{f['commit']}  {f['file']}: {f['kind']}")
    if findings:
        print(f"\n{len(findings)} finding(s) in history. Find with: git log --all -p -- <file>",
              file=sys.stderr)
    return 1 if findings else 0


def self_test():
    cases = [
        ("IMEI: 356938035643809", "<ID15>"),
        ("+CCID: 8944500102198304826F", "<ICCID>"),
        ("+CNUM: \"\",\"+447700900123\",145", "<PHONE>"),
        ("PrivateKey = yAnz5TF+lXXJte14tji3zlMNq+hd2rYUIgJBgB3fBmk=", "<REDACTED>"),
        ("peer kFNVwRpe0AnBPlUf5c3hsAxpTBtw3zVgK4HyHP0U6Xs= endpoint", "<KEY>"),
        ('AT+CGAUTH=1,1,"myuser","mypass"', '"<REDACTED>","<REDACTED>"'),
        ("wlan0 ether a4:5e:60:c2:11:9f", "<MAC>"),
        ("endpoint 8.8.8.8:51820", "<IPV4>"),
        ("addr 2001:4860:4860::8888", "<IPV6>"),
        ("contact me@example.org", "<EMAIL>"),
    ]
    keep = [
        "lan 192.168.1.20 and netbird 100.92.1.4 and lo 127.0.0.1",
        "time 12:30:45 uptime 3600 s, 1730892000123 ms",
        "freq 14.074 MHz, 28.400 MHz, sample rate 64000000",
        "ok 356938035643809 scrub:allow",
    ]
    ok = True
    for text, expect in cases:
        out = scrub_text(text)
        if expect not in out:
            ok = False
            print(f"FAIL redact: {text!r} -> {out!r}")
    for text in keep:
        out = scrub_text(text)
        if out != text:
            ok = False
            print(f"FAIL keep:   {text!r} -> {out!r}")
    tag = "OPENSSH " + "PRIVATE KEY"  # split so key scanners don't flag this file
    pem = f"-----BEGIN {tag}-----\nabc\n-----END {tag}-----\n"
    if "<PRIVATE-KEY>" not in scrub_text(pem):
        ok = False
        print("FAIL pem")
    print("self-test:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("files", nargs="*")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--in-place", action="store_true")
    g.add_argument("--check", action="store_true")
    g.add_argument("--self-test", action="store_true")
    g.add_argument("--git-history", nargs="?", const=".", metavar="REPO")
    a = ap.parse_args()

    if a.self_test:
        return self_test()
    if a.git_history:
        return check_git_history(a.git_history)
    if a.check:
        return check_files(a.files)
    if not a.files or a.files == ["-"]:
        sys.stdout.write(scrub_text(sys.stdin.read()))
        return 0
    for path in a.files:
        with open(path, encoding="utf-8", errors="replace") as f:
            out = scrub_text(f.read())
        if a.in_place:
            with open(path, "w", encoding="utf-8") as f:
                f.write(out)
        else:
            sys.stdout.write(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
