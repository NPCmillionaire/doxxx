"""Tests for the link-in-bio pivot extraction added to pivots.py."""

from doxxx.core.pivots import (
    PivotKind,
    Result,
    extract_bio_pages,
    pivots_from_bio_html,
)


def _result(extra: dict, site_name: str = "Patreon", url: str = "") -> Result:
    return Result.taken(
        reason="test",
        username="testuser",
        site_name=site_name,
        url=url,
        extra=extra,
    )


# --- extract_bio_pages ---


def test_extract_bio_pages_finds_linktree_url_in_extra():
    """A Linktree URL in an extra field is returned as a bio page."""
    result = _result(
        extra={
            "link_in_bio": "https://linktr.ee/sarahxoxo",
            "bio": "Check my links",
        }
    )
    pages = extract_bio_pages([result])
    assert len(pages) == 1
    url, source_site = pages[0]
    assert url == "https://linktr.ee/sarahxoxo"
    assert source_site == "Patreon"


def test_extract_bio_pages_finds_beacons_url():
    """Beacons URLs are also detected."""
    result = _result(
        extra={"website": "https://beacons.ai/sarah"}
    )
    pages = extract_bio_pages([result])
    assert len(pages) == 1
    assert "beacons.ai" in pages[0][0]


def test_extract_bio_pages_ignores_non_bio_urls():
    """Regular platform URLs are not treated as bio pages."""
    result = _result(
        extra={"instagram": "https://instagram.com/sarahxoxo"}
    )
    pages = extract_bio_pages([result])
    assert pages == []


def test_extract_bio_pages_deduplicates():
    """The same bio URL appearing twice is only returned once."""
    result = _result(
        extra={
            "link1": "https://linktr.ee/sarahxoxo",
            "link2": "https://linktr.ee/sarahxoxo",
        }
    )
    pages = extract_bio_pages([result])
    assert len(pages) == 1


def test_extract_bio_pages_only_from_found_results():
    """Results that are not found are skipped."""
    result = _result(
        extra={"link": "https://linktr.ee/sarah"},
    )
    result.status = "not_found"
    pages = extract_bio_pages([result])
    assert pages == []


# --- pivots_from_bio_html ---


def test_pivots_from_bio_html_extracts_platform_links():
    """Outbound platform links from a bio page become BIO pivots."""
    html = """
    <html><body>
      <a href="https://www.instagram.com/sarahxoxo">Instagram</a>
      <a href="https://www.patreon.com/sarahxoxo">Patreon</a>
      <a href="https://www.tiktok.com/@sarahxoxo">TikTok</a>
    </body></html>
    """
    pivots = pivots_from_bio_html(html, "Linktree")
    assert len(pivots) == 3
    assert all(p.kind == PivotKind.BIO for p in pivots)
    modules = {p.site for p in pivots}
    assert "instagram" in modules
    assert "patreon" in modules
    assert "tiktok" in modules


def test_pivots_from_bio_html_ignores_bio_page_links():
    """Links to other bio pages are not treated as pivots (no chaining)."""
    html = '<a href="https://linktr.ee/another">Another bio</a>'
    pivots = pivots_from_bio_html(html, "Linktree")
    assert pivots == []


def test_pivots_from_bio_html_handles_personal_domains():
    """Personal domains found on a bio page become siteless pivots (scan everywhere)."""
    html = '<a href="https://sarahxoxo.com">My website</a>'
    pivots = pivots_from_bio_html(html, "Linktree")
    # resolve_url returns (None, domain-handle) for personal domains; that
    # handle is worth scanning across all platforms.
    assert len(pivots) == 1
    assert pivots[0].username == "sarahxoxo"
    assert pivots[0].site is None
    assert pivots[0].kind == PivotKind.BIO


def test_pivots_from_bio_html_deduplicates():
    """The same link appearing twice is only returned once."""
    html = '<a href="https://instagram.com/sarah">1</a><a href="https://instagram.com/sarah">2</a>'
    pivots = pivots_from_bio_html(html, "Linktree")
    assert len(pivots) == 1


def test_pivots_from_bio_html_empty_html():
    """Empty HTML yields no pivots."""
    assert pivots_from_bio_html("", "Linktree") == []


def test_pivots_from_bio_html_source_site_recorded():
    """The source_site parameter is recorded in each pivot."""
    html = '<a href="https://github.com/sarah">GitHub</a>'
    pivots = pivots_from_bio_html(html, "Beacons")
    assert len(pivots) == 1
    assert pivots[0].source_site == "Beacons"


# --- PivotKind.BIO rank ---


def test_bio_pivot_kind_rank_is_highest():
    """BIO pivots rank above all other pivot kinds."""
    assert PivotKind.BIO.rank > PivotKind.HANDLE.rank
    assert PivotKind.BIO.rank > PivotKind.VERIFIED.rank
    assert PivotKind.BIO.rank > PivotKind.LINK.rank