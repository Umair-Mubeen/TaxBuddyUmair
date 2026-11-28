"""
Law search for TaxBuddy AI agent.

Reads the statute books kept as plain text in TaxBuddyApp/law_texts/ and gives
two lookups the agent can call:

  search_law(query, book=None, k=3)   -> best-matching passages (BM25)
  get_section(book, number)           -> full text of one section / rule

The index is built in memory the first time it is used (about 1-2 seconds per
worker) and then reused. No database table and no extra package is needed.

To add a book: drop a .txt file in law_texts/ and add it to BOOKS below.
"""
import math
import os
import re
from collections import Counter, defaultdict

LAW_DIR = os.path.join(os.path.dirname(__file__), "law_texts")

# key -> (file name, display name, edition note shown to the agent)
BOOKS = {
    "ito": ("ito_2001.txt", "Income Tax Ordinance, 2001",
            "amended up to 30 June 2026 (Finance Act 2026)"),
    "sta": ("sta_1990.txt", "Sales Tax Act, 1990",
            "amended up to Finance Act 2026"),
    "st_rules": ("st_rules_2006.txt", "Sales Tax Rules, 2006",
                 "updated up to 31 July 2026"),
    "it_rules": ("it_rules_2002.txt", "Income Tax Rules, 2002",
                 "amended up to 15 September 2026, plus Rule 38B (SRO 2098(I)/2026)"),
}

CHUNK_LINES = 40          # non-empty lines per passage
OVERLAP = 8
MAX_PASSAGE_CHARS = 1800
MAX_SECTION_CHARS = 9000

# Amendment footnotes add noise and tokens; the agent answers current law.
_FOOTNOTE = re.compile(
    r"(substituted|inserted|omitted|added|renumbered|re-numbered)\s+(for|by|through|vide)\b"
    r"|reported as PTCL|\(Assented on", re.I)
_HEADING = re.compile(
    r"^\s{0,10}(?:\d{1,2}\s*\[|\[|“|\")?\s*(\d{1,3}[A-Z]{0,4})\.\s+([A-Z][^\n]{2,90})")
_SCHEDULE = re.compile(   # a real schedule title line: upper case and short
    r"^\s*\[?(?:THE\s+)?(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH)\s+SCHEDULE\b[^a-z]{0,30}$")
_PART = re.compile(r"^\s*\[?PART\s+([IVXL]+[A-Z]?)\b", re.I)
_DIV = re.compile(r"^\s*\[?Division\s+([IVXL]+[A-Z]{0,2})\b")
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("""a an the of to in on for by and or is are be with as at from that this
which any such shall may under it its into than other per cent not no""".split())

# a new page starts with "Chapter X – ...____" / "Second Schedule – Part-I ___" or a bare page number
_PAGE_BREAK = re.compile(r"^(?:\d{3,4}|.{0,60}(?:Chapter|Schedule|CHAPTER|SCHEDULE).{0,60}_{4,}.*)$")

# footnote that opens by quoting old words: 'The words and figures “Such person shall …'
_FOOTNOTE_START = re.compile(
    r"^(?:\d{1,2}\s*)?(?:The\s+)?(?:words?|expressions?|figures?|full stop|colon|semi-colon|"
    r"provisos?|clauses?|sub-clauses?|sub-sections?|sections?|explanations?|tables?|entry|entries|"
    r"paragraphs?|rules?|sub-rules?|schedules?|serial)\b[^\u201c]{0,80}\u201c", re.I)

_INDEX = None   # built lazily


def _tokens(text):
    return [t for t in _TOKEN.findall(text.lower()) if t not in _STOP]


def _read(book_key):
    fname = BOOKS[book_key][0]
    path = os.path.join(LAW_DIR, fname)
    with open(path, encoding="utf-8", errors="ignore") as f:
        return f.read().splitlines()


def _clean_lines(lines):
    """Drop amendment footnotes AND the superseded text they quote.

    A footnote looks like:  'Section 182 substituted by the Finance Act, 2019.
    The substituted section read as follows:'  followed by the OLD text in
    curly quotes  \u201c182. Penalty ... \u201d.  Keeping that old text made the
    agent quote repealed law, so after a footnote line any quoted block that
    starts within the next few lines is skipped until its quotes close.
    """
    OPEN, CLOSE = "\u201c", "\u201d"
    out = []
    window = 0      # lines after a footnote in which old quoted text may start
    depth = 0       # quotes still open while skipping old text
    skipped = 0
    prev_num = False   # previous kept/seen line was a bare footnote number ("3")
    for ln in lines:
        t = ln.strip()
        was_num, prev_num = prev_num, False
        if _PAGE_BREAK.match(t):        # new page: footnotes are over, old quoted text too
            depth = window = 0
        if depth > 0:                                   # inside superseded text
            depth += t.count(OPEN) - t.count(CLOSE)
            skipped += 1
            # old text ends with a closing quote at the end of a line
            if depth <= 0 or skipped > 120 or re.search(CLOSE + r"[\]\.;:,\s]*$", t):
                depth = 0
            continue
        if not t:
            prev_num = was_num
            continue
        if re.fullmatch(r"\d{1,2}", t):
            prev_num = True
        if _FOOTNOTE.search(t) or ((was_num or re.match(r"^\d{1,2}[A-Z]", t)) and _FOOTNOTE_START.match(t)):   # footnote line
            window = 4
            opened = t.count(OPEN) - t.count(CLOSE)
            if opened > 0:
                depth, skipped = opened, 0
            continue
        if window:
            window -= 1
            if re.match(r"^\d{0,2}\s*" + OPEN, t):      # old text starts here
                depth, skipped = max(t.count(OPEN) - t.count(CLOSE), 0), 0
                continue
            if re.fullmatch(r"\d{1,2}", t):            # bare footnote number
                continue
        out.append(re.sub(r"[ \t]{2,}", " ", t))
    return out


def _build():
    docs = []   # dicts: book, label, text, tokens
    for key in BOOKS:
        try:
            lines = _clean_lines(_read(key))
        except FileNotFoundError:
            continue
        # label each line with the nearest heading above it
        # The contents list at the top also names the schedules, so the real
        # schedules start at the LAST "FIRST SCHEDULE" title line.
        firsts = [i for i, ln in enumerate(lines)
                  if (_SCHEDULE.match(ln) or [None, ""])[1].upper() == "FIRST"]
        sched_start = firsts[-1] if firsts else len(lines)
        labels, cur_sec, cur_sch, cur_part, cur_div = [], "", "", "", ""
        for li, ln in enumerate(lines):
            m_sch = _SCHEDULE.match(ln) if li >= sched_start else None
            if m_sch:
                cur_sch = m_sch.group(1).title() + " Schedule"
                cur_part = cur_div = ""
            if cur_sch:
                m_p = _PART.match(ln)
                if m_p:
                    cur_part, cur_div = "Part " + m_p.group(1).upper(), ""
                m_d = _DIV.match(ln)
                if m_d:
                    cur_div = "Division " + m_d.group(1)
                labels.append(" ".join(x for x in (cur_sch, cur_part, cur_div) if x))
            else:
                m = _HEADING.match(ln)
                if m:
                    cur_sec = f"{m.group(1)}. {m.group(2)[:70]}"
                labels.append(cur_sec)
        step = CHUNK_LINES - OVERLAP
        for i in range(0, max(len(lines) - OVERLAP, 1), step):
            block = lines[i:i + CHUNK_LINES]
            text = "\n".join(block)[:MAX_PASSAGE_CHARS]
            label = labels[i] if i < len(labels) else ""
            toks = _tokens(text) + _tokens(label) * 3   # headings weigh more
            docs.append({"book": key, "label": label, "text": text,
                         "tf": Counter(toks), "len": len(toks)})
    df = defaultdict(int)
    for d in docs:
        for t in d["tf"]:
            df[t] += 1
    n = len(docs) or 1
    idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    avg = sum(d["len"] for d in docs) / n
    return {"docs": docs, "idf": idf, "avg": avg}


def _index():
    global _INDEX
    if _INDEX is None:
        _INDEX = _build()
    return _INDEX


def search_law(query, book=None, k=3):
    """Return the k best passages for query. book = one key of BOOKS or None for all."""
    idx = _index()
    q = _tokens(query)
    if not q:
        return []
    k1, b = 1.5, 0.75
    scored = []
    for d in idx["docs"]:
        if book and d["book"] != book:
            continue
        s = 0.0
        for t in q:
            f = d["tf"].get(t)
            if f:
                s += idx["idf"][t] * f * (k1 + 1) / (f + k1 * (1 - b + b * d["len"] / idx["avg"]))
        if s:
            scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for s, d in scored:
        key = (d["book"], d["label"])
        if key in seen:          # one passage per section keeps results varied
            continue
        seen.add(key)
        out.append({"book": BOOKS[d["book"]][1], "edition": BOOKS[d["book"]][2],
                    "near": d["label"], "text": d["text"]})
        if len(out) >= k:
            break
    return out


def get_section(book, number):
    """Full text of section / rule `number` (e.g. '147A', '114', '42F') from one book."""
    if book not in BOOKS:
        return None
    number = str(number).strip().upper().rstrip(".")
    try:
        lines = _clean_lines(_read(book))
    except FileNotFoundError:
        return None
    pat = re.compile(r"^\s{0,10}(?:\d{1,2}\s*\[|\[)?\s*" + re.escape(number) + r"\.\s+[A-Z(]")
    starts = [i for i, ln in enumerate(lines) if pat.match(ln)]
    if not starts:
        return None
    base = int(re.match(r"\d+", number).group()) if re.match(r"\d+", number) else 0

    def next_section(ln):
        """A heading that starts another section (not a numbered table row inside this one)."""
        m = _HEADING.match(ln)
        if not m:
            return False
        sec = m.group(1)
        if sec == number:
            return False
        n = int(re.match(r"\d+", sec).group())
        return n >= base or base < 10      # table rows (1., 2., …) are numbered below the section

    best = None
    for st in starts:               # the arrangement list at the top is short; real text is long
        end = st + 1
        while end < len(lines) and not next_section(lines[end]) and end - st < 600:
            end += 1
        txt = "\n".join(lines[st:end])
        if best is None or len(txt) > len(best):
            best = txt
    return {"book": BOOKS[book][1], "edition": BOOKS[book][2], "section": number,
            "text": best[:MAX_SECTION_CHARS],
            "truncated": len(best) > MAX_SECTION_CHARS}