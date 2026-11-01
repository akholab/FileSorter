"""Where a downloaded file came from, read from its Mark of the Web.

On Windows, browsers (Edge, Chrome, Firefox and others) save a small
`Zone.Identifier` stream next to each download, in INI form:

    [ZoneTransfer]
    ZoneId=3
    ReferrerUrl=https://www.mybank.com/statements
    HostUrl=https://files.mybank.com/statement.pdf

Only the host names are kept; the full URLs are never stored or shown.
The mark is lost on FAT32/exFAT drives and when a file is copied off NTFS, so
"no mark" just means "no domain". Sources:
https://en.wikipedia.org/wiki/Mark_of_the_Web,
https://www.digital-detective.net/forensic-analysis-of-zone-identifier-stream/

No GUI code; tested in tests/test_download_source.py.
"""

import os
from urllib.parse import urlsplit


def hosts_from_zone_text(text):
    """The host names in a Zone.Identifier text, HostUrl first then
    ReferrerUrl, lowercased, without repeats. Values that aren't web URLs
    (like "about:internet" or the path of a zip the file came out of) are left out."""
    hosts = {}
    for line in text.splitlines():
        name, sep, value = line.partition("=")
        if not sep or name.strip().lower() not in ("hosturl", "referrerurl"):
            continue
        try:
            parts = urlsplit(value.strip())
        except ValueError:
            continue
        if parts.scheme.lower() in ("http", "https", "ftp") and parts.hostname:
            hosts[name.strip().lower()] = parts.hostname.lower().rstrip(".")
    result = []
    for key in ("hosturl", "referrerurl"):
        if key in hosts and hosts[key] not in result:
            result.append(hosts[key])
    return result


def read_hosts(file_path):
    """The download hosts for `file_path`, or [] when there is no mark
    (not Windows, not downloaded, or the mark was lost)."""
    if os.name != "nt":
        return []
    try:
        with open(str(file_path) + ":Zone.Identifier", "rb") as f:
            data = f.read(64 * 1024)
    except OSError:
        return []
    return hosts_from_zone_text(data.decode("utf-8", errors="replace"))


def host_matches(host, domain):
    """True when `host` is `domain` or one of its subdomains."""
    return host == domain or host.endswith("." + domain)


def matching_rule(hosts, domain_rules):
    """The first domain rule whose domain matches any of `hosts`, else None."""
    for rule in domain_rules:
        if any(host_matches(h, rule["domain"]) for h in hosts):
            return rule
    return None


def learn_domain(hosts):
    """The one domain used to group learned choices: the page the file was
    downloaded from (ReferrerUrl, last in `hosts`) if known, since HostUrl is
    often a CDN.
    shortcut: drops only a leading "www.", so shop.example.com and example.com
    learn separately; use the Public Suffix List if that turns out to matter."""
    if not hosts:
        return None
    host = hosts[-1]
    return host[4:] if host.startswith("www.") else host
