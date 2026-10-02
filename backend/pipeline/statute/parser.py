"""
Structure layer of the statute parser: classified lines → statute AST.

    Act
    ├── Part / Chapter           (containers; headings recorded)
    │   └── Section 80C          (number, heading from the margin or inline)
    │       ├── (1) sub-section
    │       │   ├── (a) clause
    │       │   │   └── (i) sub-clause → (A) item → (I) sub-item
    │       │   ├── Provided that …   (proviso; `qualifies` = node it follows)
    │       │   └── text              (tail words after a list)
    │       └── Explanation.— …
    └── Schedule                 (paragraphs, table rows)

Finance Acts insert whole provisions in quotation marks (‘115BAC. (1) …’).
Quoted text becomes a `quoted` subtree under the amending section, so the
inserted provision keeps its own internal structure.

Canonical text = one line per paragraph. Every node carries exact offsets
into it (`text[start:end]` is the node's full text including descendants;
`own_end` ends its own paragraph) and the page boxes it was printed in.
Node IDs are content-addressed: sha256(statute | path | text)[:16].
"""
import hashlib
import re
from dataclasses import dataclass, field
from statistics import median
from typing import Optional

from pipeline.statute.layout import Line, read_lines

# ─── zones ──────────────────────────────────────────────────────────────────

_BODY_START_RE = re.compile(r"\bThis\s+(?:Act|Code)\s+may\s+be\s+called\b", re.I)
_TOC_RE = re.compile(r"^\s*ARRANGEMENT\s+OF\s+(?:SECTIONS|CLAUSES)\b", re.I)
# End matter: a Bill's explanatory memoranda, or a Gazette Act's signature
# block ("DR. RAJIV MANI, Secretary to the Govt. of India."). The signature
# pattern only counts on a short line, because provisions themselves mention
# "Joint Secretary to the Government of India".
_END_RE = re.compile(
    r"^\s*(?:STATEMENT\s+OF\s+OBJECTS\s+AND\s+REASONS|NOTES\s+ON\s+CLAUSES|"
    r"MEMORANDUM\s+(?:REGARDING|EXPLAINING)|FINANCIAL\s+MEMORANDUM)\b",
)
_SIGNATURE_RE = re.compile(
    r"^[A-Z][A-Z .]{3,60},\s*(?:Secretary|Additional\s+Secretary|Joint\s+Secretary)\s+to\s+the\s+Govt?\.?",
)

# ─── labels ─────────────────────────────────────────────────────────────────

_QUOTE_OPEN = "‘“'\""
_SECTION_RE = re.compile(r"^(\d{1,4}[A-Z]{0,5})\.\s+(?=\S)")
_PAREN_RE = re.compile(r"^\(\s*([0-9]{1,3}[A-Z]{0,3}|[a-z]{1,3}|[A-Z]{1,3})\s*\)\s*")
_CHAPTER_RE = re.compile(r"^CHAPTER\s+([IVXLC]+(?:-?[A-Z]{1,2})?)\b\.?\s*(.*)$")
_PART_RE = re.compile(r"^PART\s+([IVXLC]+|[A-Z])\b\.?\s*(.*)$")
_SCHEDULE_RE = re.compile(
    r"^(?:THE\s+)?((?:FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|"
    r"ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH|SIXTEENTH)\s+)?SCHEDULE(?:\s+([IVXLC]+|[A-Z]))?\b\.?\s*$"
)
_PROVISO_RE = re.compile(r"^Provided\b")
_EXPLANATION_RE = re.compile(r"^Explanation(?:\s+\d+|\s+[IVX]+)?\s*\.?\s*[—–-]")
_ILLUSTRATION_RE = re.compile(r"^Illustrations?\b")
_INLINE_HEADING_RE = re.compile(r"^([A-Z][^.—–]{2,150}?)\.\s*[—–-]{1,2}\s*")
_ROMAN_RE = re.compile(r"^[ivxlcdm]+$")
_UROMAN_RE = re.compile(r"^[IVXLCDM]+$")
_TERMINAL_RE = re.compile(r"(?:[.;:,]|[—–-]{1,2}|\bor|\band)\s*[’”'\"]?\s*$")
_QUOTE_CLOSE_RE = re.compile(r"[’”'\"]\s*\.?\s*[;,.]?\s*$")

_ROMAN_VALUES = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}


def _roman_to_int(s: str) -> Optional[int]:
    s = s.lower()
    if not s or any(ch not in _ROMAN_VALUES for ch in s):
        return None
    total, prev = 0, 0
    for ch in reversed(s):
        v = _ROMAN_VALUES[ch]
        total = total - v if v < prev else total + v
        prev = max(prev, v)
    return total


def _section_key(num: str) -> tuple[int, str]:
    m = re.match(r"(\d+)([A-Z]*)", num)
    return (int(m.group(1)), m.group(2)) if m else (0, "")


# ─── data model ─────────────────────────────────────────────────────────────

@dataclass
class Paragraph:
    lines: list[Line]
    text: str = ""
    start: int = 0
    end: int = 0
    is_table_row: bool = False
    centred: bool = False

    @property
    def x0(self) -> float:
        return self.lines[0].x0

    @property
    def page(self) -> int:
        return self.lines[0].page


@dataclass
class Node:
    kind: str                      # act chapter part section subsection clause subclause item
    label: str = ""                # subitem proviso explanation illustration text table_row
    number: str = ""               # heading schedule quoted
    heading: str = ""
    parent: Optional["Node"] = None
    children: list["Node"] = field(default_factory=list)
    paragraph: Optional[Paragraph] = None
    indent: float = 0.0
    label_type: str = ""           # NUM LOWER ROMAN UPPER UROMAN SECTION …
    qualifies: Optional["Node"] = None
    quoted: bool = False
    path: str = ""
    node_id: str = ""

    def last_paragraph_end(self) -> int:
        end = self.paragraph.end if self.paragraph else 0
        for ch in self.children:
            end = max(end, ch.last_paragraph_end())
        return end

    def first_paragraph_start(self) -> Optional[int]:
        if self.paragraph:
            return self.paragraph.start
        for ch in self.children:
            s = ch.first_paragraph_start()
            if s is not None:
                return s
        return None


# ─── paragraphs ─────────────────────────────────────────────────────────────

def _starts_structurally(text: str) -> bool:
    t = text.lstrip(_QUOTE_OPEN)
    return bool(
        _SECTION_RE.match(t) or _PAREN_RE.match(t) or _PROVISO_RE.match(t)
        or _EXPLANATION_RE.match(t) or _ILLUSTRATION_RE.match(t)
        or _CHAPTER_RE.match(t) or _PART_RE.match(t) or _SCHEDULE_RE.match(t)
    )


def _join(prev: str, nxt: str, hyphen_vocab: set[str]) -> str:
    if prev.endswith("-") and not prev.endswith("--") and nxt[:1].islower():
        head = re.findall(r"(\w+)-$", prev)
        tail = re.findall(r"^(\w+)", nxt)
        if head and tail and f"{head[0]}-{tail[0]}".lower() in hyphen_vocab:
            return prev + nxt
        return prev[:-1] + nxt
    return prev + " " + nxt


def build_paragraphs(lines: list[Line], col_left: float, col_right: float) -> list[Paragraph]:
    body = [ln for ln in lines if ln.kind == "body"]
    gaps = [b.y0 - a.y0 for a, b in zip(body, body[1:])
            if a.page == b.page and 0 < b.y0 - a.y0 < 40]
    spacing = median(gaps) if gaps else 13.0
    width = col_right - col_left

    hyphen_vocab = {w.lower() for ln in body for w in re.findall(r"\b\w+-\w+\b", ln.text)}

    paras: list[Paragraph] = []
    for ln in body:
        left_margin, right_margin = ln.x0 - col_left, col_right - ln.x1
        prev_para = paras[-1] if paras else None
        prev = prev_para.lines[-1] if prev_para else None
        # A centred heading is short, balanced, and not the run-on tail of
        # the previous sentence.
        centred = (left_margin > 0.15 * width and right_margin > 0.15 * width
                   and abs(left_margin - right_margin) < 0.07 * width
                   and ln.x1 - ln.x0 < 0.55 * width
                   and (prev is None or prev.page != ln.page or _TERMINAL_RE.search(prev.text)
                        or prev_para.centred or ln.text.isupper()))
        new = prev is None
        if prev is not None:
            same_page = prev.page == ln.page
            vgap = ln.y0 - prev.y0 if same_page else spacing
            structural = _starts_structurally(ln.text)
            if ln.is_table_row or prev.is_table_row or centred or prev_para.centred:
                new = True
            elif structural and (_TERMINAL_RE.search(prev.text) or vgap > 1.25 * spacing
                                 or ln.x0 > prev.x0 + 6):
                new = True
            elif same_page and vgap > 1.6 * spacing:
                new = True
            elif ln.bold and not prev.bold and _SECTION_RE.match(ln.text.lstrip(_QUOTE_OPEN)):
                new = True
        if new:
            paras.append(Paragraph(lines=[ln], is_table_row=ln.is_table_row, centred=centred))
        else:
            prev_para.lines.append(ln)

    for p in paras:
        text = p.lines[0].text
        for ln in p.lines[1:]:
            text = _join(text, ln.text, hyphen_vocab)
        p.text = re.sub(r"\s{2,}", " ", text).strip()
    return [p for p in paras if p.text]


def _zone(paras: list[Paragraph]) -> tuple[list[Paragraph], list[Paragraph], list[Paragraph]]:
    """Split into (front matter incl. TOC, body, end matter)."""
    start = 0
    for i, p in enumerate(paras):
        if _BODY_START_RE.search(p.text):
            start = i
            # Step back to the paragraph carrying "1." if the sentence was its tail.
            while start > 0 and not _SECTION_RE.match(paras[start].text.lstrip(_QUOTE_OPEN)) \
                    and i - start < 3:
                start -= 1
            if not _SECTION_RE.match(paras[start].text.lstrip(_QUOTE_OPEN)):
                start = i
            # Include chapter/part headings printed just above section 1.
            while start > 0 and (_CHAPTER_RE.match(paras[start - 1].text)
                                 or _PART_RE.match(paras[start - 1].text)
                                 or (paras[start - 1].centred and len(paras[start - 1].text) < 80
                                     and not _TOC_RE.match(paras[start - 1].text))):
                start -= 1
            break
    end = len(paras)
    for j in range(start + 1, len(paras)):
        t = paras[j].text
        if _END_RE.match(t) or (len(t) < 140 and _SIGNATURE_RE.match(t)):
            end = j
            break
    return paras[:start], paras[start:end], paras[end:]


def parse_toc(front: list[Paragraph]) -> dict[str, str]:
    """{section number: heading} from an "ARRANGEMENT OF SECTIONS/CLAUSES"."""
    toc: dict[str, str] = {}
    in_toc = False
    for p in front:
        if _TOC_RE.match(p.text):
            in_toc = True
            continue
        if not in_toc:
            continue
        m = re.match(r"^(\d{1,4}[A-Z]{0,5})\.\s+(.+?)\.?$", p.text)
        if m:
            toc.setdefault(m.group(1), m.group(2).strip())
    return toc


# ─── hierarchy ──────────────────────────────────────────────────────────────

_PAREN_TYPE_ORDER = ["NUM", "LOWER", "ROMAN", "UPPER", "UROMAN"]
_KIND_FOR_TYPE = {"NUM": "subsection", "LOWER": "clause", "ROMAN": "subclause",
                  "UPPER": "item", "UROMAN": "subitem"}


def _prev_letter(c: str) -> str:
    return chr(ord(c) - 1) if c and ord(c.lower()) > ord("a") else ""


class _Builder:
    def __init__(self, statute_key: str, toc: dict[str, str], kind: str):
        self.statute_key = statute_key
        self.toc = toc
        self.is_finance_act = kind == "finance_act"
        self.root = Node(kind="act")
        self.container = self.root           # current chapter/part/schedule
        self.stack: list[Node] = []          # open provision nodes, outermost first
        self.last_section: Optional[tuple[int, str]] = None
        self.quote: Optional[Node] = None    # open quoted block (Finance Acts)
        self.quote_stack: list[Node] = []
        self.pending_note: Optional[str] = None

    # helpers ---------------------------------------------------------------
    def _active_stack(self) -> list[Node]:
        return self.quote_stack if self.quote is not None else self.stack

    def _attach(self, parent: Node, node: Node) -> Node:
        node.parent = parent
        parent.children.append(node)
        return node

    def _paren_type(self, label: str, stack: list[Node]) -> str:
        if label[0].isdigit():
            return "NUM"
        lower = label.islower()
        if lower:
            if _ROMAN_RE.match(label):
                if len(label) == 1 and label in "cdlm":
                    return "LOWER"
                sib = next((n for n in reversed(stack) if n.label_type in ("LOWER", "ROMAN")), None)
                if len(label) == 1 and sib is not None and sib.label_type == "LOWER" \
                        and sib.label == _prev_letter(label):
                    return "LOWER"
                if len(label) == 1 and sib is not None and sib.label_type == "ROMAN":
                    prev_val = _roman_to_int(sib.label) or 0
                    if (_roman_to_int(label) or 0) == prev_val + 1:
                        return "ROMAN"
                    if sib.parent is not None:
                        # (h) … (i): clause letters continuing under the same parent
                        cousins = [c for c in sib.parent.children if c.label_type == "LOWER"]
                        if cousins and cousins[-1].label == _prev_letter(label):
                            return "LOWER"
                return "ROMAN"
            return "LOWER"
        if _UROMAN_RE.match(label):
            sib = next((n for n in reversed(stack) if n.label_type in ("UPPER", "UROMAN")), None)
            if len(label) == 1 and sib is not None and sib.label_type == "UPPER" \
                    and sib.label == _prev_letter(label):
                return "UPPER"
            if len(label) == 1 and label in "CDLM":
                return "UPPER"
            return "UROMAN"
        return "UPPER"

    def _place_labelled(self, node: Node, stack: list[Node], base: Node) -> None:
        """Type-stack placement: a label type already open in the stack closes
        everything below it and the new node becomes its sibling; otherwise
        the new node nests under the innermost open node."""
        for i in range(len(stack) - 1, -1, -1):
            if stack[i].label_type == node.label_type:
                parent = stack[i].parent or base
                del stack[i:]
                self._attach(parent, node)
                stack.append(node)
                return
        parent = stack[-1] if stack else base
        self._attach(parent, node)
        stack.append(node)

    def _place_by_indent(self, node: Node, stack: list[Node], base: Node) -> Node:
        """Unlabelled text / provisos / explanations attach to the innermost
        open node printed at or left of their own indent."""
        target_idx = None
        for i in range(len(stack) - 1, -1, -1):
            if stack[i].indent <= node.indent + 3:
                target_idx = i
                break
        if target_idx is None:
            parent = stack[0] if stack else base
            del stack[1:]
        else:
            parent = stack[target_idx]
            del stack[target_idx + 1:]
        if node.kind in ("proviso", "explanation") and parent.children:
            node.qualifies = parent.children[-1]
        return self._attach(parent, node)

    def _close_quote(self) -> None:
        self.quote = None
        self.quote_stack = []

    # main ------------------------------------------------------------------
    def add(self, p: Paragraph) -> None:
        raw = p.text
        if p.lines[0].kind == "marginal_note":
            return
        text = raw.lstrip(_QUOTE_OPEN)
        # A leading quote marks inserted text only when a structural label
        # follows it (‘115BAC. (1) …’, ‘(1A) …’, ‘Explanation.—…’). A quoted
        # defined term (“accountant” means …) is ordinary text.
        opens_quote = len(text) < len(raw) and _starts_structurally(text)
        if not opens_quote:
            text = raw

        m = _CHAPTER_RE.match(raw)
        if m and (p.centred or p.lines[0].bold or len(raw) < 120) and self.quote is None:
            node = Node(kind="chapter", number=m.group(1), heading=m.group(2).strip(),
                        paragraph=p, indent=p.x0, label_type="CHAPTER")
            parent = self.root if self.container.kind in ("act", "chapter", "schedule") \
                else (self.container if self.container.kind == "part" else self.root)
            self._attach(parent, node)
            self.container, self.stack = node, []
            return
        m = _PART_RE.match(raw)
        if m and p.centred and self.quote is None:
            node = Node(kind="part", number=m.group(1), heading=m.group(2).strip(),
                        paragraph=p, indent=p.x0, label_type="PART")
            parent = self.container if self.container.kind == "schedule" else self.root
            self._attach(parent, node)
            self.container, self.stack = node, []
            return
        m = _SCHEDULE_RE.match(raw)
        if m and p.centred and self.quote is None:
            ordinal = (m.group(1) or "").strip()
            node = Node(kind="schedule", number=(ordinal or m.group(2) or "").strip(),
                        heading=raw, paragraph=p, indent=p.x0, label_type="SCHEDULE")
            self._attach(self.root, node)
            self.container, self.stack = node, []
            return

        # A chapter's title on the centred line after "CHAPTER IV".
        if (p.centred and self.container.kind == "chapter" and not self.container.heading
                and not self.stack and not _starts_structurally(raw)):
            self.container.heading = raw
            return

        sec = _SECTION_RE.match(text)
        if sec and self.quote is not None and not opens_quote and p.lines[0].bold \
                and self.last_section is not None:
            # A bold, unquoted number continuing the Act's own numbering ends
            # any quoted insertion that failed to close cleanly.
            key = _section_key(sec.group(1))
            if self.last_section < key and key[0] <= self.last_section[0] + 5:
                self._close_quote()
        if sec and self._accept_section(sec.group(1), p, opens_quote):
            self._add_section(sec, p, text, opens_quote)
            return

        stack = self._active_stack()
        base = self.quote if self.quote is not None else self.container

        if opens_quote and self.quote is None and self.stack:
            # ‘(1A) …’ / ‘Explanation.—…’ inserted by an amending section.
            self.quote = Node(kind="quoted", paragraph=None, indent=p.x0, quoted=True)
            self._attach(self.stack[-1], self.quote)
            self.quote_stack = []
            stack, base = self.quote_stack, self.quote

        node = self._make_node(p, text, stack)
        if node.label_type in _PAREN_TYPE_ORDER:
            self._place_labelled(node, stack, base)
            inner = getattr(node, "_inline_child", None)
            if inner is not None:
                node._inline_child = None  # type: ignore[attr-defined]
                self._attach(node, inner)
                stack.append(inner)
        elif p.centred and not stack:
            self._attach(base, node)
        else:
            self._place_by_indent(node, stack, base)

        if self.quote is not None and _QUOTE_CLOSE_RE.search(raw) and not opens_quote:
            self._close_quote()
        elif self.quote is not None and opens_quote and _QUOTE_CLOSE_RE.search(raw) \
                and raw.count("’") + raw.count("”") >= 1 and len(raw) < 400:
            self._close_quote()

    def _accept_section(self, num: str, p: Paragraph, opens_quote: bool) -> bool:
        if p.is_table_row:
            return False  # "1. | Up to Rs. 2,50,000 | Nil" is a table row
        if opens_quote or self.quote is not None:
            return True  # inserted provisions carry their own numbering
        key = _section_key(num)
        if key[0] > 1500 and not key[1]:
            return False  # a year ("2025.") at a line start, not a section
        if self.toc:
            if num not in self.toc:
                return False
        elif not p.lines[0].bold and self.last_section is not None:
            # Without a table of contents, a section must be bold or at least
            # continue the numbering (Gazette PDFs set section numbers bold).
            if not (key > self.last_section and key[0] <= self.last_section[0] + 3):
                return False
        if self.last_section is not None and key <= self.last_section:
            return False
        return True

    def _add_section(self, sec: re.Match, p: Paragraph, text: str, opens_quote: bool) -> None:
        num = sec.group(1)
        rest = text[sec.end():]
        heading = self.toc.get(num, "") if not opens_quote else ""
        hm = _INLINE_HEADING_RE.match(rest)
        if hm and not heading and len(hm.group(1)) < 120:
            heading = hm.group(1).strip()
        if not heading and self.pending_note:
            heading = self.pending_note
        self.pending_note = None
        node = Node(kind="section", number=num, label=num, heading=heading, paragraph=p,
                    indent=p.x0, label_type="SECTION", quoted=opens_quote or self.quote is not None)

        if opens_quote or self.quote is not None:
            if self.quote is None:
                anchor = self.stack[-1] if self.stack else self.container
                self.quote = Node(kind="quoted", indent=p.x0, quoted=True)
                self._attach(anchor, self.quote)
                self.quote_stack = []
            self.quote_stack = []
            self._attach(self.quote, node)
            self.quote_stack.append(node)
            self._descend_inline_labels(node, rest, self.quote_stack)
            if _QUOTE_CLOSE_RE.search(p.text) and len(p.text) < 600:
                self._close_quote()
            return

        self._close_quote()
        self.last_section = _section_key(num)
        parent = self.container if self.container.kind in ("chapter", "part", "act") else self.root
        if self.container.kind == "schedule":
            parent = self.root
            self.container = self.root
        self._attach(parent, node)
        self.stack = [node]
        self._descend_inline_labels(node, rest, self.stack)

    def _descend_inline_labels(self, section: Node, rest: str, stack: list[Node]) -> None:
        """'2. (1) Subject to …' or '(9)(a) For …': the first paragraph opens
        nested units. They share the section's paragraph text, so only their
        labels are recorded (as zero-length markers) and the stack is primed so
        the next sibling, e.g. '(2)', lands at the right level."""
        m = _PAREN_RE.match(rest)
        parent = section
        while m:
            lbl = m.group(1)
            ltype = self._paren_type(lbl, stack)
            child = Node(kind=_KIND_FOR_TYPE[ltype], label=lbl, number=lbl, paragraph=None,
                         indent=section.indent + 24, label_type=ltype, quoted=section.quoted)
            self._attach(parent, child)
            stack.append(child)
            parent = child
            rest = rest[m.end():]
            m = _PAREN_RE.match(rest)

    def _make_node(self, p: Paragraph, text: str, stack: list[Node]) -> Node:
        if p.is_table_row:
            return Node(kind="table_row", paragraph=p, indent=p.x0, label_type="ROW")
        m = _PAREN_RE.match(text)
        if m:
            lbl = m.group(1)
            ltype = self._paren_type(lbl, stack)
            node = Node(kind=_KIND_FOR_TYPE[ltype], label=lbl, number=lbl, paragraph=p,
                        indent=p.x0, label_type=ltype)
            # "(9)(a) For the purposes …" → (a) nested inside (9)
            rest = text[m.end():]
            m2 = _PAREN_RE.match(rest)
            if m2:
                lbl2 = m2.group(1)
                inner_type = self._paren_type(lbl2, stack + [node])
                inner = Node(kind=_KIND_FOR_TYPE[inner_type], label=lbl2, number=lbl2,
                             paragraph=None, indent=p.x0 + 24, label_type=inner_type)
                node._inline_child = inner  # type: ignore[attr-defined]
            return node
        if _PROVISO_RE.match(text):
            return Node(kind="proviso", paragraph=p, indent=p.x0, label_type="PROVISO")
        if _EXPLANATION_RE.match(text):
            return Node(kind="explanation", paragraph=p, indent=p.x0, label_type="EXPLANATION")
        if _ILLUSTRATION_RE.match(text):
            return Node(kind="illustration", paragraph=p, indent=p.x0, label_type="ILLUSTRATION")
        if p.centred:
            return Node(kind="heading", heading=p.text, paragraph=p, indent=p.x0, label_type="HEADING")
        return Node(kind="text", paragraph=p, indent=p.x0, label_type="TEXT")

    def finish_inline_children(self, node: Optional[Node] = None) -> None:
        node = node or self.root
        for ch in list(node.children):
            inner = getattr(ch, "_inline_child", None)
            if inner is not None:
                ch._inline_child = None  # type: ignore[attr-defined]
                self._attach(ch, inner)
                # Later siblings of the inline child were attached to `ch` by
                # the type stack only if they matched its type; nothing to move.
            self.finish_inline_children(ch)


# ─── paths, ids, offsets ────────────────────────────────────────────────────

_PATH_TOKEN = {
    "chapter": lambda n: f"ch{n.number}", "part": lambda n: f"pt{n.number}",
    "schedule": lambda n: f"sch{n.number or 'X'}".replace(" ", ""),
    "section": lambda n: f"s{n.number}",
    "subsection": lambda n: f"({n.label})", "clause": lambda n: f"({n.label})",
    "subclause": lambda n: f"({n.label})", "item": lambda n: f"({n.label})",
    "subitem": lambda n: f"({n.label})",
}


def _assign_paths(node: Node, prefix: str, counters: dict) -> None:
    for ch in node.children:
        if ch.kind == "section" and not ch.quoted:
            base = f"{prefix.split('/')[0]}/s{ch.number}"
        elif ch.kind in _PATH_TOKEN:
            base = f"{prefix}/{_PATH_TOKEN[ch.kind](ch)}"
        else:
            short = {"proviso": "proviso", "explanation": "expl", "illustration": "illus",
                     "text": "t", "table_row": "row", "heading": "h", "quoted": "q"}[ch.kind]
            counters[(prefix, short)] = counters.get((prefix, short), 0) + 1
            base = f"{prefix}/{short}{counters[(prefix, short)]}"
        path = base
        n = 2
        while path in counters.get("_seen", set()):
            path = f"{base}~{n}"
            n += 1
        counters.setdefault("_seen", set()).add(path)
        ch.path = path
        _assign_paths(ch, path, counters)


def _walk(node: Node):
    for ch in node.children:
        yield ch
        yield from _walk(ch)


@dataclass
class StatuteAST:
    statute: str
    version: str
    title: str
    text: str
    nodes: list[dict]
    toc: dict[str, str]
    marginal_notes: list[dict]
    stats: dict

    def to_dict(self) -> dict:
        return {
            "statute": self.statute, "version": self.version, "title": self.title,
            "text_sha256": hashlib.sha256(self.text.encode("utf-8")).hexdigest(),
            "stats": self.stats, "toc": self.toc, "marginal_notes": self.marginal_notes,
            "nodes": self.nodes,
        }


def parse_statute(pdf_path: str, statute: str, version: str, kind: str = "act",
                  title: str = "") -> StatuteAST:
    lines, pages, layout_stats = read_lines(pdf_path)
    paras = build_paragraphs(lines, layout_stats["col_left"], layout_stats["col_right"])
    front, body, end_matter = _zone(paras)
    toc = parse_toc(front)

    # Canonical text: one body paragraph per line.
    offset = 0
    chunks = []
    for p in body:
        p.start = offset
        p.end = offset + len(p.text)
        chunks.append(p.text)
        offset = p.end + 1
    text = "\n".join(chunks)

    # Marginal notes, used as section headings when the TOC lacks one. A note
    # wrapped over several short lines ("Amendment of" / "section 2.") is one.
    notes = _merge_notes([ln for ln in lines if ln.kind == "marginal_note"])
    builder = _Builder(f"{statute}/{version}", toc, kind)
    note_idx = 0
    for p in body:
        first = p.lines[0]
        while note_idx < len(notes) and (notes[note_idx].page, notes[note_idx].y0) < (first.page, first.y0 - 4):
            note_idx += 1
        builder.pending_note = None
        if note_idx < len(notes):
            nt = notes[note_idx]
            if nt.page == first.page and abs(nt.y0 - first.y0) <= 6 and not _MARGIN_CITATION_RE.match(nt.text):
                builder.pending_note = nt.text.rstrip(". ")
        builder.add(p)
    builder.finish_inline_children()
    _assign_paths(builder.root, statute, {})

    nodes: list[dict] = []
    for n in _walk(builder.root):
        start = n.first_paragraph_start()
        if start is None:
            # Inline markers ("(1)" opened inside the section's paragraph).
            par = n.parent
            while par is not None and par.paragraph is None:
                par = par.parent
            start = par.paragraph.start if par is not None and par.paragraph else 0
        end = max(n.last_paragraph_end(), start)
        own_end = n.paragraph.end if n.paragraph else start
        body_text = text[start:end]
        n.node_id = hashlib.sha256(f"{statute}/{version}|{n.path}|{body_text}".encode("utf-8")).hexdigest()[:16]
        spans = []
        if n.paragraph:
            for ln in n.paragraph.lines:
                spans.append([ln.page + 1, round(ln.x0, 1), round(ln.y0, 1), round(ln.x1, 1), round(ln.y1, 1)])
        nodes.append({
            "node_id": n.node_id, "path": n.path, "kind": n.kind, "label": n.label,
            "number": n.number, "heading": n.heading, "quoted": n.quoted,
            "parent": n.parent.node_id if n.parent is not None and n.parent.kind != "act" else None,
            "start": start, "end": end, "own_end": own_end,
            "page": spans[0][0] if spans else None, "boxes": spans,
            "qualifies": None,  # filled below once all ids exist
        })
    by_obj = {id(n): n for n in _walk(builder.root)}
    id_of = {id(n): n.node_id for n in by_obj.values()}
    for rec, n in zip(nodes, _walk(builder.root)):
        if n.qualifies is not None:
            rec["qualifies"] = id_of.get(id(n.qualifies))
        rec["children"] = [c.node_id for c in n.children]

    kinds: dict[str, int] = {}
    for rec in nodes:
        kinds[rec["kind"]] = kinds.get(rec["kind"], 0) + 1
    sections = [r for r in nodes if r["kind"] == "section" and not r["quoted"]]
    stats = {
        "pages": len(pages),
        "layout": layout_stats,
        "paragraphs": {"front": len(front), "body": len(body), "end": len(end_matter)},
        "node_kinds": kinds,
        "sections": len(sections),
        "toc_sections": len(toc),
        "toc_coverage": round(len({r["number"] for r in sections} & set(toc)) / len(toc), 4) if toc else None,
        "chapters": kinds.get("chapter", 0),
        "chars": len(text),
    }
    return StatuteAST(
        statute=statute, version=version, title=title, text=text, nodes=nodes, toc=toc,
        marginal_notes=[{"page": ln.page + 1, "y": round(ln.y0, 1), "text": ln.text} for ln in notes],
        stats=stats,
    )


def _merge_notes(notes: list[Line]) -> list[Line]:
    merged: list[Line] = []
    for ln in sorted(notes, key=lambda n: (n.page, n.y0, n.x0)):
        last = merged[-1] if merged else None
        if (last is not None and last.page == ln.page and abs(last.x0 - ln.x0) < 12
                and -1 <= ln.y0 - last.y1 < 1.4 * ln.size
                and not _MARGIN_CITATION_RE.match(ln.text) and not last.text.rstrip().endswith(".")):
            merged[-1] = Line(page=last.page, x0=min(last.x0, ln.x0), y0=last.y0, x1=max(last.x1, ln.x1),
                              y1=ln.y1, size=last.size, bold=last.bold,
                              text=re.sub(r"-$", "", last.text) + ("" if last.text.endswith("-") else " ") + ln.text,
                              kind="marginal_note")
        else:
            merged.append(ln)
    return merged


# Margin citations like "43 of 1961." are not headings.
_MARGIN_CITATION_RE = re.compile(r"^\s*\d+\s+of\s+\d{4}\.?\s*$")
