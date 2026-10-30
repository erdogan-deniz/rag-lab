import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from corpus_text import html_to_markdown  # noqa: E402


def convert(body: str) -> str:
    return html_to_markdown(f'<div class="mw-parser-output">{body}</div>', "Page")


def test_wikitable_repeats_rowspan_and_keeps_flag_alt_text():
    md = convert(
        "<table class='wikitable'>"
        "<tr><th>Team</th><th>Nat.</th></tr>"
        "<tr><td rowspan='2'>Barcelona</td><td><img alt='Spain'/></td></tr>"
        "<tr><td>Poland</td></tr>"
        "</table>"
    )
    assert "| Team | Nat. |" in md
    assert "| Barcelona | Spain |" in md
    assert "| Barcelona | Poland |" in md


def test_infobox_becomes_label_value_lines_and_br_separates_values():
    md = convert(
        "<table class='infobox'>"
        "<tr><th>President</th><td>A<br/>B</td></tr>"
        "</table>"
    )
    assert "- **President:** A; B" in md


def test_match_box_becomes_one_line_with_scorers():
    md = convert(
        "<div class='vevent'><table>"
        "<tr><td><span>27 July 2025</span> <small>Friendly</small></td>"
        "<td>Vissel Kobe</td><td>1–3</td><td>Barcelona</td><td>Kobe, Japan</td></tr>"
        "<tr><td>19:00 JST</td>"
        "<td><ul><li>Miyashiro <span>42'</span></li></ul></td><td>Report</td>"
        "<td><ul><li>E. García <span>33'</span></li><li>Dro <span>87'</span></li></ul></td></tr>"
        "</table></div>"
    )
    assert (
        "- 27 July 2025, 19:00 JST, Friendly: Vissel Kobe 1–3 Barcelona (Kobe, Japan). "
        "Goals, Vissel Kobe: Miyashiro 42'. Goals, Barcelona: E. García 33', Dro 87'."
    ) in md


def test_citation_sections_and_reference_marks_are_dropped():
    md = convert(
        "<h2>History</h2><p>Won the title.<sup class='reference'>[1]</sup></p>"
        "<h2>References</h2><p>Some citation.</p>"
        "<h2>Notes</h2><p>Kept.</p>"
    )
    assert "Won the title." in md
    assert "[1]" not in md
    assert "Some citation." not in md
    assert "Kept." in md
