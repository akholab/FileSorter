"""The user's sorting rules, kept in an editable rules.toml file.

On first run the file is written from the built-in categories, with comments.
If it can't be read or has a mistake, the app sorts with the built-in
categories and reports the error (with the line number when TOML gives one),
so a typo never sends files to the wrong place.

No GUI or Windows code; tested in tests/test_rules.py.
"""

import json
import os

try:
    import tomllib  # Python 3.11+
except ImportError:  # pragma: no cover - older Python
    import tomli as tomllib

from categorizer import default_categories

RULES_FILE = "rules.toml"
FIELDS = ("extensions", "keywords", "folders")

HEADER = """\
# FileSorter rules. Edit this file, then restart the app.
#
# Each [categories.<name>] block is one category. Categories are checked from
# top to bottom and the first match wins:
#   extensions  file endings that belong to this category, like ".pdf"
#   keywords    words in the file name (checked when no extension matched)
#   folders     where to suggest moving the file, as folders next to it
#
# Each [[domain_rules]] block sends files downloaded from a website to one
# folder, and wins over everything else. It matches the site and its
# subdomains, using the download mark Windows browsers save with each file:
#   domain  the site, like "mybank.com" (no https:// and no path)
#   folder  a full path like "D:/Finance/Bank", or a folder next to the file
#
# [[domain_rules]]
# domain = "mybank.com"
# folder = "D:/Finance/Bank"
#
# If this file has a mistake, the app tells you the line and uses its
# built-in categories until you fix it. Delete the file to get the defaults back.
"""


def _toml_string(value):
    # A JSON string is a TOML basic string, except that TOML forbids a raw DEL
    # and \u escapes of surrogate halves; ensure_ascii=False avoids the latter.
    return json.dumps(value, ensure_ascii=False).replace("\x7f", "\\u007f")


def _toml_list(values):
    return "[" + ", ".join(_toml_string(v) for v in values) + "]"


def default_text():
    """The rules.toml text for the built-in categories."""
    lines = [HEADER]
    for name, rules in default_categories().items():
        lines.append(f"[categories.{_toml_string(name)}]")
        for field in FIELDS:
            lines.append(f"{field} = {_toml_list(rules[field])}")
        lines.append("")
    return "\n".join(lines)


def parse(text):
    """Turn rules.toml text into (categories dict, domain rules list). Raises
    ValueError with a readable message when the text isn't valid."""
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"not valid TOML: {e}") from e

    unknown = sorted(set(data) - {"categories", "domain_rules"})
    if unknown:
        raise ValueError(f"unknown setting '{unknown[0]}' "
                         "(only [categories.<name>] and [[domain_rules]] blocks are allowed)")
    raw = data.get("categories")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("no [categories.<name>] blocks found")

    categories = {}
    for name, rules in raw.items():
        if not isinstance(rules, dict):
            raise ValueError(f"category '{name}' must be a [categories.{name}] block")
        if name == "misc":
            raise ValueError("'misc' is reserved for files no category matches; pick another name")
        unknown = sorted(set(rules) - set(FIELDS))
        if unknown:
            raise ValueError(f"category '{name}': unknown setting '{unknown[0]}' "
                             f"(allowed: {', '.join(FIELDS)})")
        clean = {}
        for field in FIELDS:
            values = rules.get(field, [])
            if not isinstance(values, list) or not all(isinstance(v, str) for v in values):
                raise ValueError(f"category '{name}': {field} must be a list of text values")
            clean[field] = [v.strip() for v in values if v.strip()]
        clean["extensions"] = [
            e.lower() if e.startswith(".") else "." + e.lower() for e in clean["extensions"]
        ]
        clean["keywords"] = [k.lower() for k in clean["keywords"]]
        if not clean["folders"]:
            raise ValueError(f"category '{name}' needs at least one folder")
        categories[name] = clean
    return categories, _parse_domain_rules(data.get("domain_rules", []))


def _parse_domain_rules(raw):
    if not isinstance(raw, list):
        raise ValueError("domain_rules must be [[domain_rules]] blocks")
    result = []
    for n, rule in enumerate(raw, 1):
        where = f"domain rule {n}"
        if not isinstance(rule, dict):
            raise ValueError(f"{where} must be a [[domain_rules]] block")
        unknown = sorted(set(rule) - {"domain", "folder"})
        if unknown:
            raise ValueError(f"{where}: unknown setting '{unknown[0]}' (allowed: domain, folder)")
        domain, folder = rule.get("domain"), rule.get("folder")
        if not isinstance(domain, str) or not isinstance(folder, str) or not folder.strip():
            raise ValueError(f"{where} needs a domain and a folder, both as text")
        domain = domain.strip().lower().rstrip(".")
        if domain.startswith("*."):
            domain = domain[2:]
        if domain.startswith("www."):
            domain = domain[4:]
        labels = domain.split(".")
        if len(labels) < 2 or not all(l and all(c.isalnum() or c == "-" for c in l) for l in labels):
            raise ValueError(f"{where}: write just the site with its ending, like \"mybank.com\" "
                             f"(got {rule['domain']!r})")
        result.append({"domain": domain, "folder": folder.strip()})
    return result


def load(path=RULES_FILE):
    """Return (categories, domain rules, error). Writes the default file when
    it's missing. `error` is None when the file was used, else why the
    defaults (and no domain rules) were used."""
    if not os.path.exists(path):
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(default_text())
        except OSError as e:
            return default_categories(), [], f"could not create {path}: {e}"
        return default_categories(), [], None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return (*parse(f.read()), None)
    except (OSError, UnicodeDecodeError, ValueError) as e:
        return default_categories(), [], f"{path}: {e}"
