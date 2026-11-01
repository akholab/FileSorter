"""Tests for download_source.py: reading the download mark and matching
domain rules. Zone.Identifier streams only exist on NTFS, so reading is faked."""
import download_source as ds

CHROME = ("[ZoneTransfer]\r\nZoneId=3\r\n"
          "ReferrerUrl=https://www.MyBank.com/statements?id=42\r\n"
          "HostUrl=https://files.mybank.com/s/statement.pdf\r\n")


def test_hosts_come_from_host_and_referrer_urls():
    assert ds.hosts_from_zone_text(CHROME) == ["files.mybank.com", "www.mybank.com"]


def test_only_host_names_are_kept_never_paths_or_queries():
    assert all("/" not in h and "?" not in h for h in ds.hosts_from_zone_text(CHROME))


def test_non_web_values_are_ignored():
    text = ("[ZoneTransfer]\nZoneId=3\nHostUrl=about:internet\n"
            "ReferrerUrl=C:\\Users\\me\\Downloads\\pack.zip\n")
    assert ds.hosts_from_zone_text(text) == []


def test_same_host_is_listed_once_and_odd_lines_are_skipped():
    text = "[ZoneTransfer]\nnonsense\nHostUrl=https://a.com/x\nReferrerUrl=https://A.com./y\nHostUrl\n"
    assert ds.hosts_from_zone_text(text) == ["a.com"]


def test_no_mark_means_no_hosts(tmp_path, monkeypatch):
    f = tmp_path / "a.pdf"
    f.write_text("x")
    monkeypatch.setattr(ds.os, "name", "nt")
    assert ds.read_hosts(f) == []  # no a.pdf:Zone.Identifier stream to open


def test_reading_is_skipped_off_windows(tmp_path, monkeypatch):
    f = tmp_path / "a.pdf"
    (tmp_path / "a.pdf:Zone.Identifier").write_text(CHROME)  # a plain file on Linux
    monkeypatch.setattr(ds.os, "name", "posix")
    assert ds.read_hosts(f) == []


def test_read_hosts_reads_the_stream(tmp_path, monkeypatch):
    # On Linux, "a.pdf:Zone.Identifier" is just a file name, which stands in for the stream
    f = tmp_path / "a.pdf"
    (tmp_path / "a.pdf:Zone.Identifier").write_bytes(CHROME.encode() + b"\xff")
    monkeypatch.setattr(ds.os, "name", "nt")
    assert ds.read_hosts(f) == ["files.mybank.com", "www.mybank.com"]


def test_domain_matches_itself_and_subdomains_only():
    assert ds.host_matches("mybank.com", "mybank.com")
    assert ds.host_matches("files.eu.mybank.com", "mybank.com")
    assert not ds.host_matches("notmybank.com", "mybank.com")
    assert not ds.host_matches("mybank.com.evil.io", "mybank.com")


def test_first_matching_rule_wins_and_either_host_counts():
    rules = [{"domain": "school.edu", "folder": "S"}, {"domain": "mybank.com", "folder": "B"},
             {"domain": "files.mybank.com", "folder": "F"}]
    assert ds.matching_rule(["cdn.net", "www.mybank.com"], rules)["folder"] == "B"
    assert ds.matching_rule(["cdn.net"], rules) is None
    assert ds.matching_rule([], rules) is None


def test_learn_domain_prefers_the_referring_page():
    assert ds.learn_domain(["files.mybank.com", "www.mybank.com"]) == "mybank.com"
    assert ds.learn_domain(["cdn.example.org"]) == "cdn.example.org"
    assert ds.learn_domain([]) is None
