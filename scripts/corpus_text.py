"""Rendered Wikipedia HTML -> Markdown that keeps tables.

The plain-text export of a page drops tables (squads, transfers, scores), so the corpus is built
from the rendered markup instead:

- `wikitable` becomes a Markdown table; a rowspan is repeated, so each row reads on its own;
- the infobox becomes `- **Label:** value` lines;
- a match box (`div.vevent`) becomes one line with date, teams, score, venue and scorers.
"""

import re

from bs4 import BeautifulSoup
from bs4.element import NavigableString, Tag

# Sections that carry no facts: citations and links.
SKIPPED_SECTIONS = {"References", "External links", "Further reading"}

# Elements removed before rendering: navigation, citations, images, hidden helpers.
NOISE = (
    "style, script, link, figure, .thumb, .gallery, .navbox, .navbox-styles, .hatnote, .shortdescription, "
    ".mw-empty-elt, .reflist, .refbegin, .sistersitebox, .noprint, .metadata, .locmap, .sidebar, "
    ".mw-editsection, .mw-cite-backlink, .navbar, sup.reference, sup.noprint"
)

BLOCK_TAGS = {"div", "p", "ul", "ol", "li", "dl", "dt", "dd", "table", "tr", "br"}


def html_to_markdown(html: str, title: str) -> str:
    soup = BeautifulSoup(html, "lxml")
    root = soup.select_one("div.mw-parser-output") or soup
    for element in root.select(NOISE):
        element.decompose()
    for element in root.find_all(style=re.compile(r"display\s*:\s*none")):
        element.decompose()

    blocks = [f"# {title}"]
    skipping = False
    for block in render_children(root):
        if block.startswith("## "):
            skipping = block[3:].strip() in SKIPPED_SECTIONS
        if not skipping:
            blocks.append(block)
    return "\n\n".join(blocks) + "\n"


def render_children(parent: Tag):
    for child in parent.children:
        if isinstance(child, Tag):
            yield from render(child)


def classes_of(element: Tag) -> list[str]:
    return list(element.get("class") or [])


def render(element: Tag):
    name = element.name
    classes = set(classes_of(element))

    if name in {"h1", "h2", "h3", "h4", "h5", "h6"}:
        text = inline_text(element)
        if text:
            yield f"{'#' * int(name[1])} {text}"
    elif name == "div" and "vevent" in classes:
        yield from match_box(element)
    elif name == "table":
        yield from table(element)
    elif name in {"ul", "ol"}:
        text = list_items(element, 0)
        if text:
            yield text
    elif name == "div" or name == "section":
        yield from render_children(element)
    elif name in {"p", "dl", "blockquote", "center"}:
        text = inline_text(element)
        if text:
            yield text


def inline_text(element: Tag, skip: frozenset[str] = frozenset()) -> str:
    """Text of an element: block boundaries become spaces or `; `, icons become their alt text."""
    parts: list[str] = []

    def walk(node):
        for child in node.children:
            if isinstance(child, NavigableString):
                parts.append(str(child))
            elif not isinstance(child, Tag) or child.name in skip:
                continue
            elif child.name == "img":
                alt = (child.get("alt") or "").strip()
                if alt:
                    parts.append(f" {alt} ")
            elif child.name == "br":
                parts.append(" ; ")
            elif child.name == "li":
                parts.append(" ; ")
                walk(child)
            elif child.name in BLOCK_TAGS:
                parts.append(" ")
                walk(child)
                parts.append(" ")
            else:
                if any(c.startswith("fb-red") for c in classes_of(child)):
                    parts.append(" (red card) ")
                walk(child)

    walk(element)
    return clean(" ".join("".join(parts).split()).strip(" ;"))


def clean(text: str) -> str:
    text = re.sub(r":\s*;", ":", text)
    text = re.sub(r";\s*\(", " (", text)
    text = re.sub(r"\s+([,.;:)\]])", r"\1", text)
    text = re.sub(r"([(\[])\s+", r"\1", text)
    return re.sub(r"\s{2,}", " ", text).strip()


def list_items(element: Tag, depth: int) -> str:
    lines = []
    for item in element.find_all("li", recursive=False):
        text = inline_text(item, skip=frozenset({"ul", "ol"}))
        if text:
            lines.append(f"{'  ' * depth}- {text}")
        for nested in item.find_all(["ul", "ol"], recursive=False):
            sub = list_items(nested, depth + 1)
            if sub:
                lines.append(sub)
    return "\n".join(lines)


def table(element: Tag):
    if "infobox" in classes_of(element):
        text = infobox(element)
        if text:
            yield text
        return
    rows = grid(element)
    if not rows:
        return
    width = max(len(row) for row in rows)
    rows = [row + [""] * (width - len(row)) for row in rows]
    caption = element.find("caption")
    lines = []
    if caption and inline_text(caption):
        lines.append(f"**{inline_text(caption)}**\n")
    lines.append("| " + " | ".join(rows[0]) + " |")
    lines.append("| " + " | ".join(["---"] * width) + " |")
    lines.extend("| " + " | ".join(row) + " |" for row in rows[1:])
    yield "\n".join(lines)


def own_rows(element: Tag) -> list[Tag]:
    return [tr for tr in element.find_all("tr") if tr.find_parent("table") is element]


def cell_text(cell: Tag) -> str:
    return inline_text(cell).replace("|", "/")


def grid(element: Tag) -> list[list[str]]:
    """Table cells as rows of text; rowspan is repeated, colspan leaves the extra columns empty."""
    rows: list[list[str]] = []
    pending: dict[tuple[int, int], str] = {}
    for r, tr in enumerate(own_rows(element)):
        row: list[str] = []
        col = 0
        for cell in tr.find_all(["td", "th"], recursive=False):
            while (r, col) in pending:
                row.append(pending.pop((r, col)))
                col += 1
            text = cell_text(cell)
            rowspan = int(re.sub(r"\D", "", cell.get("rowspan", "1")) or 1)
            colspan = int(re.sub(r"\D", "", cell.get("colspan", "1")) or 1)
            for c in range(colspan):
                row.append(text if c == 0 else "")
                for extra in range(1, rowspan):
                    pending[(r + extra, col + c)] = text if c == 0 else ""
            col += colspan
        while (r, col) in pending:
            row.append(pending.pop((r, col)))
            col += 1
        if any(row):
            rows.append(row)
    return rows


def infobox(element: Tag) -> str:
    lines = []
    for tr in own_rows(element):
        head, data = tr.find("th"), tr.find("td")
        if head and data:
            lines.append(f"- **{inline_text(head)}:** {inline_text(data)}")
        elif head:
            text = inline_text(head)
            if text:
                lines.append(f"**{text}**")
        elif data:
            text = inline_text(data)
            if text:
                lines.append(f"- {text}")
    return "\n".join(lines)


def goals(cell: Tag | None) -> str:
    if cell is None:
        return ""
    items = [inline_text(li) for li in cell.find_all("li")]
    return ", ".join(item for item in items if item)


def match_box(element: Tag):
    """One match (`div.vevent`): the template spreads it over three table rows."""
    box = element.find("table")
    if box is None:
        text = inline_text(element)
        if text:
            yield text
        return
    rows = [tr.find_all("td", recursive=False) for tr in own_rows(box)]
    rows = [cells for cells in rows if cells]
    if not rows or len(rows[0]) < 4:
        text = inline_text(box)
        if text:
            yield text
        return

    first = rows[0]
    competition = first[0].find("small")
    competition_text = inline_text(competition) if competition else ""
    date = inline_text(first[0]).replace(competition_text, "").strip(" ,")
    home, score, away = (inline_text(first[i]) for i in (1, 2, 3))
    place = inline_text(first[4]) if len(first) > 4 else ""

    when, home_goals, away_goals = "", "", ""
    if len(rows) > 1:
        second = rows[1]
        when = inline_text(second[0])
        home_goals = goals(second[1]) if len(second) > 1 else ""
        away_goals = goals(second[3]) if len(second) > 3 else ""
    extra = [inline_text(cell) for cells in rows[2:] for cell in cells]

    head = f"- {date}" + (f", {when}" if when else "") + (f", {competition_text}" if competition_text else "")
    text = f"{head}: {home} {score} {away}"
    if place:
        text += f" ({place})"
    text += "."
    if home_goals:
        text += f" Goals, {home}: {home_goals}."
    if away_goals:
        text += f" Goals, {away}: {away_goals}."
    for chunk in extra:
        if chunk:
            text += f" {chunk}"
    yield clean(text)
