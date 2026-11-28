"""
TaxBuddyApp/cite_check.py — Phase 3 citation validator for TaxBuddy Umair AI.

The model may only cite a section or rule that it actually received in this
answer: text read with get_law_section / search_law / get_law_schedule, a
section listed in a calculator result's "law", a verified answer's section,
or a section already cited (and checked) earlier in the same chat.

After the answer is written, check() finds every "Section 147A", "s.37(1A)",
"Sections 114 and 115", "Rule 81B" in it and compares them with that list.
Unchecked references are removed from the "Reference:" line and listed in a
short note at the end, so the reader knows to confirm them.
"""
import re

from . import law_search

_UNIT = r"(?:Sections?|Secs?\.|Sec|S\.|s\.|ss\.|u/s|Rules?|R\.|r\.)"
_NUM = r"\d{1,3}(?!\d)[A-Z]{0,4}(?:\(\w{1,4}\))*"
_REF = re.compile(
    rf"(?<![\w/]){_UNIT}\s*({_NUM}(?:\s*(?:,|and|&|or|/|to|aur)\s*{_NUM})*)", re.I)
_ONE = re.compile(r"(?<!\d)(\d{1,3}(?!\d)[A-Z]{0,4})", re.I)
_SALES = re.compile(r"sales\s*tax|\bSTA\b|1990|federal excise", re.I)
_RULES_ST = re.compile(r"sales\s*tax\s*rules|ST\s*Rules", re.I)


def _book_for(unit, before, after):
    """Which book a reference points to, from the words right around it."""
    rule = unit.lower().startswith("r")
    near_after = re.match(r"^[\s,]*(?:\(\w+\)\s*)*(?:of\s+the\s+|of\s+|,\s*|\(|-\s*)?"
                          r"(Sales\s*Tax\s*Rules|ST\s*Rules|Sales\s*Tax|STA\b|Federal\s*Excise|Income\s*Tax\s*Rules|IT\s*Rules)",
                          after, re.I)
    near_before = re.search(r"(Sales\s*Tax\s*Rules|Sales\s*Tax\s*Act(?:,?\s*1990)?|STA|Income\s*Tax\s*Rules)\W{0,3}$",
                            before, re.I)
    which = (near_after or near_before)
    which = which.group(1).lower() if which else ""
    if rule:
        return "st_rules" if ("sales" in which or which.startswith("st")) else "it_rules"
    return "sta" if ("sales" in which or which == "sta" or "excise" in which) else "ito"


def extract(text):
    """[(book, number, unit, line_no)] for every section / rule reference in text."""
    out = []
    for no, line in enumerate(str(text or "").splitlines()):
        for m in _REF.finditer(line):
            unit = m.group(0)[: m.start(1) - m.start(0)].strip()
            ctx = line[max(0, m.start() - 40): m.end() + 60]
            book = _book_for(unit, line[max(0, m.start() - 30): m.start()], line[m.end(): m.end() + 45])
            if unit.lower().startswith("r") and re.search(r"schedule", ctx, re.I) and not re.search(r"rules,?\s*20\d\d", ctx, re.I):
                continue                      # "Tenth Schedule, rule 1" is not an Income Tax Rule
            for num in _ONE.findall(re.sub(r"\(\w{1,4}\)", "", m.group(1))):
                num = num.upper()
                if num.isdigit() and int(num) > 400:
                    continue
                out.append((book, num, unit, no))
    return out


def _flat(text):
    """Law text breaks lines mid-sentence ('section\n171'): join before reading references."""
    return re.sub(r"\s*\n\s*", " ", str(text or ""))


class Tracker:
    """Collects what the model was allowed to cite during one answer."""

    def __init__(self, earlier_answers=()):
        self.allowed = set()          # (book, number)
        for t in earlier_answers or ():
            for book, num, _u, _l in extract(t):
                self.allowed.add((book, num))

    def _add(self, book, num):
        num = law_search._norm(num)
        if num:
            self.allowed.add((book or "ito", num))

    def add_tool(self, name, args, result):
        args = args or {}
        if not isinstance(result, dict) or result.get("error"):
            return
        if name == "get_law_section":
            self._add(args.get("book"), result.get("section") or args.get("number"))
            for book, num, _u, _l in extract(_flat(result.get("text", ""))):     # sections it refers to
                self._add(args.get("book") if book == "ito" else book, num)
        elif name == "search_law":
            for r in result.get("results") or []:
                if r.get("section"):
                    self._add(r.get("book_key"), r["section"])
                for book, num, _u, _l in extract(_flat(r.get("text", ""))):     # sections the passage itself names
                    self._add(r.get("book_key") if book == "ito" else book, num)
        elif name == "get_law_schedule":
            for book, num, _u, _l in extract(_flat(result.get("text", ""))):
                self._add(args.get("book") if book == "ito" else book, num)
        elif name == "find_verified_answer":
            for r in result.get("results") or []:
                if r.get("match_score", 0) >= 0.35:
                    for book, num, _u, _l in extract(" ".join(str(r.get(k, "")) for k in ("section", "answer"))):
                        self._add(book, num)
        else:
            # calculators: every section named anywhere in the result (law, working,
            # tax_nature, notes); rate-card rows ("section": "236C")
            import json
            for book, num, _u, _l in extract(json.dumps(result, default=str, ensure_ascii=False).replace("\\n", "\n")):
                self._add(book, num)
            for row in result.get("results") or result.get("rows") or []:
                if isinstance(row, dict) and row.get("section"):
                    for book, num, _u, _l in extract("s." + str(row["section"])):
                        self._add(book, num)
            if result.get("section"):
                for book, num, _u, _l in extract("s." + str(result["section"])):
                    self._add(book, num)

    def is_allowed(self, book, num):
        if (book, num) in self.allowed:
            return True
        # same number read from another book of the same kind (model named the book loosely)
        return any(n == num for _b, n in self.allowed)


def _exists(book, num):
    try:
        return num in set(law_search.sections_in(book))
    except Exception:
        return True


def check(answer, tracker):
    """Return (clean_answer, bad) where bad = [(book, number, exists)]."""
    refs = extract(answer)
    bad, seen = [], set()
    for book, num, _unit, _line in refs:
        if (book, num) in seen or tracker.is_allowed(book, num):
            continue
        seen.add((book, num))
        bad.append((book, num, _exists(book, num)))
    if not bad:
        return answer, []
    bad_nums = {n for _b, n, _e in bad}

    lines = answer.splitlines()
    for i, ln in enumerate(lines):
        if not re.match(r"^\s*\**\s*Reference", ln, re.I):
            continue
        mh = re.match(r"^(\s*\**\s*Reference[^:]*:\**\s*)(.*)$", ln, re.I)
        if not mh:
            continue
        head, body = mh.group(1), mh.group(2)
        parts = re.split(r";\s*", body)
        keep = []
        for p in parts:
            nums = {n for _b, n, _u, _l in extract(p)}
            if nums and nums <= bad_nums:
                continue
            keep.append(p.strip())
        lines[i] = (head + "; ".join(k for k in keep if k)) if any(keep) else ""
    text = "\n".join(lines).rstrip()

    names = ", ".join(("Rule " if b.endswith("rules") else "Section ") + n for b, n, _e in bad)
    text += (f"\n\n_⚠️ Reference check: {names} could not be confirmed against the law text "
             f"for this answer — please verify before relying on it._")
    return text, bad