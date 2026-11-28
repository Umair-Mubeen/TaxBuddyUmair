"""
Law search for TaxBuddy Umair AI — Phase 3 (section-level retrieval).

Reads the statute books kept as plain text in TaxBuddyApp/law_texts/ (FBR PDFs
converted with pdftotext, one page per form-feed) and offers:

  search_law(query, book=None, k=3)   -> best passages, each tagged with its section
  get_section(book, number)           -> current text of one section / rule
  sections_in(book)                   -> every section number found in a book

How the text is cleaned, page by page:
  * the running header / page number of each page is dropped;
  * the footnote block at the foot of each page (amendment history, often quoting
    the OLD repealed text) is dropped, including old text that carries over to
    the next page;
  * inline footnote markers such as "2[" become "[";
  * the arrangement (table of contents) is dropped, but its section numbers are
    kept as the list of real sections, so table rows numbered "1.", "2." inside a
    section are never mistaken for section headings.

Questions in Roman Urdu or Urdu are expanded with English legal terms before
searching (see _GLOSSARY), so "late return jurmana" also finds s.182.

The index is built in memory on first use (a second or two per worker).
"""
import math
import os
import re
from collections import Counter, defaultdict

LAW_DIR = os.path.join(os.path.dirname(__file__), "law_texts")

# key -> (file name, display name, edition note shown to the agent, unit name)
BOOKS = {
    "ito": ("ito_2001.txt", "Income Tax Ordinance, 2001",
            "amended up to 30 June 2026 (Finance Act 2026)", "Section"),
    "sta": ("sta_1990.txt", "Sales Tax Act, 1990",
            "amended up to Finance Act 2026", "Section"),
    "st_rules": ("st_rules_2006.txt", "Sales Tax Rules, 2006",
                 "updated up to 31 July 2026", "Rule"),
    "it_rules": ("it_rules_2002.txt", "Income Tax Rules, 2002",
                 "amended up to 15 September 2026, plus Rule 38B (SRO 2098(I)/2026)", "Rule"),
}

CHUNK_LINES = 40          # non-empty lines per passage
OVERLAP = 8
MAX_PASSAGE_CHARS = 1800
MAX_SECTION_CHARS = 9000

OPEN, CLOSE = "“", "”"
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = set("""a an the of to in on for by and or is are be with as at from that this
which any such shall may under it its into than other per cent not no""".split())

# ── footnotes ────────────────────────────────────────────────────────────────
# A footnote starts with its number (alone on a line, or before the text) and its
# text starts with amendment wording and names the amending instrument.
_FN_WORDS = re.compile(
    r"^[\[\.\s]*(?:Substituted|Inserted|Added|Omitted|Deleted|Renumbered|Re-numbered|Amended|Modified|Replaced|"
    r"Restored|Came into force|For the words?|For Statements|In (?:section|rule|sub-section|clause|the)|"
    r"(?:The\s+)?(?:words?|expressions?|figures?|brackets?|full[- ]?stops?|commas?|colons?|semi[- ]?colons?|provisos?|"
    r"clauses?|sub-clauses?|sub-sections?|sections?|explanations?|tables?|entry|entries|paragraphs?|"
    r"rules?|sub-rules?|schedules?|serial|chapters?|parts?|divisions?|items?|S\.\s?Nos?|columns?|"
    r"heading|definition|letter|numerals?|paras?|sub-paras?|paragraphs?|sub-paragraphs?|Sr\.?\s?Nos?\.?|follows)\b|Earlier|Vide|Through|Corrigendum|Notification|"
    r"(?:First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth|Ninth|Tenth|New)\b)", re.I)
_FN_SOURCE = re.compile(
    r"Finance|Ordinance|Act,?\s*\d{4}|Act\s+\d{4}|S\.\s?R\.\s?O|\bSRO\b|Notification|Presidential|"
    r"Gazette|w\.e\.f|Order No|Tax Laws|Amendment|dated", re.I)
_FN_NUM = re.compile(r"^(\d{1,3})(?:\s*([A-Z].*))?$")
_TERMINAL = re.compile(r"(?:[”\]\.;:]\s*){1,4}$")


def _footnote_start(page, i):
    """Is page[i] the first line of a footnote?"""
    m = _FN_NUM.match(page[i].strip())
    if not m:
        return False
    rest = m.group(2)
    if rest is None:                              # number alone: text on the next non-empty line
        nxt = [ln.strip() for ln in page[i + 1:i + 6] if ln.strip() and ln.strip() != ".."]
        if not nxt:
            return False
        rest = nxt[0]
        ctx = " ".join(nxt[:3])
    else:
        ctx = " ".join([rest] + [ln.strip() for ln in page[i + 1:i + 4] if ln.strip() != ".."])
    return bool(_FN_WORDS.match(rest)) and bool(_FN_SOURCE.search(ctx))


def _old_text_continues(block):
    """True if the last footnote of a page quotes old text that runs onto the next page."""
    lines = [ln.strip() for ln in block if ln.strip()]
    if not lines:
        return False
    tail = " ".join(lines[-12:])
    last = lines[-1]
    if re.fullmatch(r"\d{1,3}", last):
        return False
    quoting = re.search(r"read\s+as\s+(?:follows|under)|as\s+follows\s*:", tail, re.I)
    unbalanced = sum(ln.count(OPEN) - ln.count(CLOSE) for ln in lines) > 0
    return bool(quoting or unbalanced) and not _TERMINAL.search(last)


_HEADER = re.compile(r"_{4,}|^(?:Income Tax Ordinance|Income Tax Rules|Sales Tax Act|Sales Tax Rules)[^a-z]{0,8}\d{0,4}\s*$"
                     r"|^CHAPTER\s*[-–]", re.I)
_PAGE_NO = re.compile(r"^\(?\d{1,4}\)?$")


def _clean_page(page, carry):
    """Return (body lines, carry_to_next_page)."""
    lines = [re.sub(r"(?:^|\s)\.\.(?=\s|$)", " ", ln).rstrip() for ln in page]   # ".." layout marks
    # running header (first 1-2 non-empty lines) and page number (last non-empty line)
    for _ in range(2):
        idx = next((i for i, ln in enumerate(lines) if ln.strip()), None)
        if idx is not None and _HEADER.search(lines[idx].strip()):
            lines[idx] = ""
    idx = next((i for i in range(len(lines) - 1, -1, -1) if lines[i].strip()), None)
    if idx is not None and _PAGE_NO.match(lines[idx].strip()):
        lines[idx] = ""

    start = next((i for i in range(len(lines)) if _footnote_start(lines, i)), None)
    body = lines if start is None else lines[:start]
    block = [] if start is None else lines[start:]

    if carry and start is not None:
        # old text from the previous page's footnote sits just above this page's
        # footnotes, after a blank line; the body line above that gap is usually
        # mid-sentence (the body runs on to the next page), so cut at the nearest
        # gap below a non-terminal line, else at the nearest double gap
        j, blanks, cut, wide = len(body) - 1, 0, None, None
        while j >= 0 and len(body) - j < 60:
            t = body[j].strip()
            if t:
                if blanks >= 1 and not re.search(r"[.;:\]\u201d]\s*$", t):
                    cut = j + 1
                    break
                if blanks >= 2 and wide is None:
                    wide = j + 1
                blanks = 0
            else:
                blanks += 1
            j -= 1
        cut = cut if cut is not None else wide
        if cut is not None:
            moved = body[cut:]
            body = body[:cut]
            block = moved + block
    return body, _old_text_continues(block)


_MARKER = re.compile(r"(?<![\w.(/,-])\d{1,3}\s*(?=\[)")
_EMPTY = re.compile(r"^[\s\[\]\.\*]*$")


def _clean_lines(raw_lines):
    """Full cleaned text of a book as a list of lines (footnotes, headers removed)."""
    text = "\n".join(raw_lines)
    pages = text.split("\f")
    out, carry = [], False
    for p in pages:
        body, carry = _clean_page(p.split("\n"), carry)
        for ln in body:
            t = _MARKER.sub("", ln.strip())
            t = re.sub(r"[ \t]{2,}", " ", t)
            if not t or _EMPTY.match(t) or t == "..":
                continue
            out.append(t)
    return out


# ── sections ─────────────────────────────────────────────────────────────────
_HEAD = re.compile(r"^\[?\s*[“\"]?\s*0?(\d{1,3}[A-Z]{0,4})\.\s*[-–]?\s*(?:\[\s*\*+\s*\]\s*)?"
                   r"\[?\d{0,3}\s*\[?\s*[“\"]?\s*([A-Z][^\n]{1,160}|$)")
_BODY_START = re.compile(r"^\s*\[?\s*0?1\.\s*\[?\s*Short title", re.I)
_TOC_NUM = re.compile(r"^\s*\[?\s*0*(\d{1,3}[A-Z]{0,4})\.?(?=\s|$)")
_SCHEDULE = re.compile(
    r"^\s*\[?(?:THE\s+)?(FIRST|SECOND|THIRD|FOURTH|FIFTH|SIXTH|SEVENTH|EIGHTH|NINTH|TENTH|ELEVENTH|"
    r"TWELFTH|THIRTEENTH|FOURTEENTH|FIFTEENTH)\s+SCHEDULE\b[^a-z]{0,30}$")
_PART = re.compile(r"^\s*\[?PART\s*[-–]?\s*([IVXL]+[A-Z]?)\b", re.I)
_DIV = re.compile(r"^\s*\[?Division\s+([IVXL]+[A-Z]{0,2})\b")


def _key(num):
    m = re.match(r"(\d+)([A-Z]*)", num)
    return (int(m.group(1)), m.group(2))


def _norm(num):
    num = str(num).strip().upper().rstrip(".")
    num = re.sub(r"^(?:SECTION|SEC|S|RULE|R)\.?\s*", "", num)
    num = re.sub(r"\(.*$", "", num).strip()                   # "37(1A)" -> "37"
    m = re.match(r"0*(\d{1,3}[A-Z]{0,4})$", num)
    return m.group(1) if m else ""


def _longest_chain(cands):
    """Longest run of headings whose numbers strictly increase down the book.
    Stray numbers (table rows, cross references, a form line '14. Net gain')
    fall out because keeping them would break the longer real sequence."""
    import bisect
    tails, tails_idx, prev = [], [], [None] * len(cands)
    for n, c in enumerate(cands):
        pos = bisect.bisect_left(tails, c[0])
        if pos == len(tails):
            tails.append(c[0]); tails_idx.append(n)
        else:
            tails[pos] = c[0]; tails_idx[pos] = n
        prev[n] = tails_idx[pos - 1] if pos else None
    out, n = [], tails_idx[-1] if tails_idx else None
    while n is not None:
        out.append(cands[n]); n = prev[n]
    return out[::-1]


_BOOKS = {}   # key -> parsed book


def _parse(book):
    if book in _BOOKS:
        return _BOOKS[book]
    path = os.path.join(LAW_DIR, BOOKS[book][0])
    with open(path, encoding="utf-8", errors="ignore") as f:
        raw = f.read().split("\n")
    # table of contents = everything before the body's "1. Short title" heading
    starts = [i for i, ln in enumerate(raw) if _BODY_START.match(ln)]
    body_at = starts[-1] if starts else 0
    toc = set()
    for ln in raw[:body_at]:
        m = _TOC_NUM.match(ln)
        if m and int(re.match(r"\d+", m.group(1)).group()) <= 400:
            toc.add(m.group(1))
    lines = _clean_lines(raw[body_at:])
    first_sched = next((i for i, ln in enumerate(lines) if _SCHEDULE.match(ln)
                        and _SCHEDULE.match(ln).group(1).upper() == "FIRST"), len(lines))
    lines = [ln for i, ln in enumerate(lines) if i >= first_sched or not re.fullmatch(r"\d{1,3}", ln)]

    # schedules start at the first schedule title after the sections
    sched_at = next((i for i, ln in enumerate(lines) if _SCHEDULE.match(ln)
                     and (_SCHEDULE.match(ln).group(1).upper() == "FIRST")), len(lines))

    cands = []
    for i, ln in enumerate(lines[:sched_at]):
        m = _HEAD.match(ln)
        if not m:
            continue
        num = m.group(1)
        title = m.group(2)
        if not title:                 # "60A." alone, title on the next line
            nxt = lines[i + 1] if i + 1 < len(lines) else ""
            if not re.match(r"[\[“\"]?[A-Z]", nxt):
                continue
            title = nxt.lstrip("[“\" ")
        if toc and num not in toc:
            continue
        if "___" in title or ln.lstrip("[ ").startswith(("“", '"')):   # form line / quoted old text
            continue
        cands.append((_key(num), num, i, title.strip()))
    heads = [(num, i, t) for _k, num, i, t in _longest_chain(cands)]

    sections = {}
    for n, (num, i, title) in enumerate(heads):
        end = heads[n + 1][1] if n + 1 < len(heads) else sched_at
        title = re.split(r"\s*[.\-–—―:]\s*[—–\-―]|\.\s*$|\.\s+\(", title)[0].strip(" .-–—―[]")
        sections[num] = {"start": i, "end": end, "title": title[:90]}

    # label every line: section for the body, schedule/part/division after it
    labels = [""] * len(lines)
    order = sorted(sections.items(), key=lambda x: x[1]["start"])
    for num, s in order:
        unit = BOOKS[book][3]
        lab = f"{unit} {num}. {s['title']}"
        for j in range(s["start"], s["end"]):
            labels[j] = lab
    sch = part = div = ""
    for j in range(sched_at, len(lines)):
        ln = lines[j]
        m = _SCHEDULE.match(ln)
        if m:
            sch, part, div = m.group(1).title() + " Schedule", "", ""
        mp = _PART.match(ln)
        if mp and sch:
            part, div = "Part " + mp.group(1).upper(), ""
        md = _DIV.match(ln)
        if md and sch:
            div = "Division " + md.group(1)
        labels[j] = " ".join(x for x in (sch, part, div) if x)
    _BOOKS[book] = {"lines": lines, "sections": sections, "labels": labels, "sched_at": sched_at}
    return _BOOKS[book]


def sections_in(book):
    return list(_parse(book)["sections"]) if book in BOOKS else []


def _window(text, focus, limit):
    """Part of a long text around the first place the focus words appear."""
    words = [w for w in _tokens(focus) if len(w) > 2]
    if not words:
        return None
    low = text.lower()
    best, best_hits = None, 0
    for m in re.finditer(re.escape(words[0]), low):
        seg = low[max(0, m.start() - 300): m.start() + 1500]
        hits = sum(w in seg for w in words)
        if hits > best_hits:
            best, best_hits = m.start(), hits
    if best is None:
        for w in words[1:]:
            i = low.find(w)
            if i >= 0:
                best = i
                break
    if best is None:
        return None
    start = max(0, best - limit // 4)
    start = text.rfind("\n", 0, start) + 1
    return text[start:start + limit]


def get_section(book, number, focus=None):
    """Current text of section / rule `number` (e.g. '147A', '114', '81B', 's.37(1A)').
    For a long section, `focus` (e.g. 'return not filed', 'salary definition')
    returns the part that mentions those words."""
    if book not in BOOKS:
        return None
    num = _norm(number)
    if not num:
        return None
    try:
        b = _parse(book)
    except FileNotFoundError:
        return None
    s = b["sections"].get(num)
    if not s:
        return None
    text = "\n".join(b["lines"][s["start"]:s["end"]])
    part = None
    if focus and len(text) > MAX_SECTION_CHARS:
        part = _window(text, focus, MAX_SECTION_CHARS)
    out = {"book": BOOKS[book][1], "edition": BOOKS[book][2], "section": num,
           "unit": BOOKS[book][3], "title": s["title"]}
    if part:
        out.update(text=part, truncated=True, note=f"Part of the section around '{focus}'.")
    else:
        out.update(text=text[:MAX_SECTION_CHARS], truncated=len(text) > MAX_SECTION_CHARS)
        if out["truncated"]:
            out["note"] = "Long section: call again with focus=<words> to read another part."
    return out


_ORD = ["FIRST", "SECOND", "THIRD", "FOURTH", "FIFTH", "SIXTH", "SEVENTH", "EIGHTH", "NINTH",
        "TENTH", "ELEVENTH", "TWELFTH", "THIRTEENTH", "FOURTEENTH", "FIFTEENTH"]
_ROMAN = {"1": "I", "2": "II", "3": "III", "4": "IV", "5": "V", "6": "VI", "7": "VII", "8": "VIII",
          "9": "IX", "10": "X", "11": "XI", "12": "XII", "13": "XIII", "14": "XIV", "15": "XV"}


def get_schedule(book, schedule, part=None, division=None, clause=None, focus=None):
    """Text from a Schedule: a Part / Division, or one numbered clause such as
    Second Schedule, Part I, clause (139)."""
    if book not in BOOKS:
        return None
    sch = str(schedule).strip().upper().replace("SCHEDULE", "").strip()
    sch = _ORD[int(sch) - 1] if sch.isdigit() and 0 < int(sch) <= 15 else sch
    if sch not in _ORD:
        return None
    want = sch.title() + " Schedule"
    roman = lambda v: _ROMAN.get(str(v).strip().upper().replace("PART", "").replace("DIVISION", "").strip(),
                                 str(v).strip().upper().replace("PART", "").replace("DIVISION", "").strip())
    if part:
        want += " Part " + roman(part)
    if division:
        want += " Division " + roman(division)
    b = _parse(book)
    idx = [i for i, lab in enumerate(b["labels"]) if lab == want or lab.startswith(want + " ")]
    if not idx:
        return None
    lines = b["lines"][idx[0]: idx[-1] + 1]
    label = want
    if clause:
        c = re.sub(r"[^0-9A-Za-z]", "", str(clause)).upper()
        num = re.compile(r"^\[?\s*\((" + re.escape(c) + r")\)", re.I)
        anyc = re.compile(r"^\[?\s*\((\d{1,3}[A-Z]{0,3})\)")
        st = next((i for i, ln in enumerate(lines) if num.match(ln)), None)
        if st is None:
            return None
        en = st + 1
        while en < len(lines) and not (anyc.match(lines[en]) and anyc.match(lines[en]).group(1).upper() != c
                                        and not re.match(r"^\[?\s*\((?:[ivxl]+|[a-z])\)", lines[en])):
            en += 1
        lines = lines[st:en]
        label += f", clause ({c})"
    text = "\n".join(lines)
    if focus and len(text) > MAX_SECTION_CHARS:
        text = _window(text, focus, MAX_SECTION_CHARS) or text
    return {"book": BOOKS[book][1], "edition": BOOKS[book][2], "schedule": label,
            "text": text[:MAX_SECTION_CHARS], "truncated": len(text) > MAX_SECTION_CHARS}


# ── search ───────────────────────────────────────────────────────────────────
# Roman Urdu / Urdu / everyday words -> English terms used in the statutes
_GLOSSARY = {
    "jurmana": "penalty", "jurmane": "penalty", "jurmanah": "penalty", "saza": "penalty prosecution",
    "late": "default due date", "dair": "default due date", "deir": "default due date",
    "gosh": "return", "goshwara": "return", "gosha": "return", "wapsi": "refund", "refund": "refund",
    "tankhwa": "salary", "tankhwah": "salary", "tankha": "salary", "salary": "salary employer",
    "kiraya": "rent property", "kiraye": "rent property", "makaan": "immovable property",
    "makan": "immovable property", "ghar": "immovable property house", "plot": "immovable property plot",
    "zameen": "immovable property land", "jaidad": "immovable property", "property": "immovable property",
    "gaari": "motor vehicle", "gari": "motor vehicle", "gaadi": "motor vehicle", "car": "motor vehicle",
    "munafa": "profit gain", "nafa": "profit gain", "faida": "profit gain",
    "hissas": "shares securities", "shares": "shares securities", "share": "shares securities",
    "tohfa": "gift", "tohfe": "gift", "gift": "gift", "wirasat": "inheritance", "virasat": "inheritance",
    "bachat": "saving profit on debt", "bank": "bank profit on debt",
    "filer": "active taxpayers list", "nonfiler": "active taxpayers list", "atl": "active taxpayers list",
    "notice": "notice", "audit": "audit", "chhoot": "exemption", "chhut": "exemption",
    "riayat": "exemption concession", "maaf": "exemption", "kharcha": "expenditure deduction",
    "kharche": "expenditure deduction", "karobar": "business", "kaarobar": "business",
    "dukaan": "business", "dukan": "business", "bechna": "sale disposal", "becha": "sale disposal",
    "bechne": "sale disposal", "khareed": "purchase acquisition", "khareedna": "purchase acquisition",
    "kharida": "purchase acquisition", "bahar": "non-resident abroad", "overseas": "non-resident",
    "pension": "pension", "zakat": "zakat", "sood": "profit on debt interest",
    "talaba": "education", "fees": "fee", "fee": "fee", "school": "educational institution tuition",
    "biwi": "spouse", "shohar": "spouse", "bacha": "child", "bachay": "child", "bachon": "child",
    "rishtedar": "relative", "bhai": "relative", "behan": "relative", "walid": "relative",
    "kaise": "", "kitna": "", "kitni": "", "kya": "", "hai": "", "hain": "", "kab": "",
    # Urdu script
    "ٹیکس": "tax", "جرمانہ": "penalty", "گوشوارہ": "return", "تنخواہ": "salary", "کرایہ": "rent",
    "جائیداد": "immovable property", "گاڑی": "motor vehicle", "منافع": "profit", "تحفہ": "gift",
    "فائلر": "active taxpayers list", "ریفنڈ": "refund", "نوٹس": "notice", "کاروبار": "business",
    "استثنیٰ": "exemption", "زکوٰۃ": "zakat", "پنشن": "pension",
}
_URDU_TOKEN = re.compile(r"[؀-ۿ]+")

_INDEX = {}


def expand_query(query):
    """English legal terms added for Roman Urdu / Urdu words in the question."""
    q = str(query or "")
    extra = []
    for w in _TOKEN.findall(q.lower()) + _URDU_TOKEN.findall(q):
        add = _GLOSSARY.get(w)
        if add:
            extra.append(add)
    return (q + " " + " ".join(extra)).strip()


TITLE_WEIGHT = 1.5


def _stem(w):
    """Very small English stemmer so 'refunds' ~ 'refund', 'penalties' ~ 'penalty'."""
    for suf, rep in (("ies", "y"), ("sses", "ss"), ("ings", ""), ("ing", ""), ("s", "")):
        if len(w) > 4 and w.endswith(suf) and not w.endswith("ss"):
            return w[: -len(suf)] + rep
    return w


def _stem_all(text):
    return " ".join(_stem(w) for w in _TOKEN.findall(str(text).lower()))


def _tokens(text):
    return [t for t in _TOKEN.findall(str(text).lower()) if t not in _STOP]


def _build():
    docs = []
    for key in BOOKS:
        try:
            b = _parse(key)
        except FileNotFoundError:
            continue
        lines, labels = b["lines"], b["labels"]
        # passages never cross a section boundary
        bounds = sorted({s["start"] for s in b["sections"].values()} | {0, b["sched_at"], len(lines)})
        for a, z in zip(bounds, bounds[1:]):
            step = CHUNK_LINES - OVERLAP
            for i in range(a, max(z - OVERLAP, a + 1), step):
                block = lines[i:min(i + CHUNK_LINES, z)]
                if not block:
                    continue
                text = "\n".join(block)[:MAX_PASSAGE_CHARS]
                label = labels[i] if i < len(labels) else ""
                toks = _tokens(_stem_all(text)) + _tokens(_stem_all(label)) * 3     # headings weigh more
                sec = next((n for n, s in b["sections"].items() if s["start"] <= i < s["end"]), None)
                title = b["sections"][sec]["title"] if sec else label
                docs.append({"book": key, "label": label, "section": sec, "text": text,
                             "tf": Counter(toks), "len": len(toks),
                             "title": set(_tokens(_stem_all(title)))})
    df = defaultdict(int)
    for d in docs:
        for t in d["tf"]:
            df[t] += 1
    n = len(docs) or 1
    idf = {t: math.log(1 + (n - c + 0.5) / (c + 0.5)) for t, c in df.items()}
    avg = sum(d["len"] for d in docs) / n
    return {"docs": docs, "idf": idf, "avg": avg}


def _index():
    if "i" not in _INDEX:
        _INDEX["i"] = _build()
    return _INDEX["i"]


def search_law(query, book=None, k=3):
    """Return the k best passages for query. book = one key of BOOKS or None for all."""
    idx = _index()
    q = _tokens(_stem_all(expand_query(query)))
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
            hit = [t for t in set(q) if t in d["title"]]
            if hit:      # the section's own title names the topic: strong signal
                s += TITLE_WEIGHT * sum(idx["idf"].get(t, 0) for t in hit) / math.sqrt(len(d["title"]) or 1)
            scored.append((s, d))
    scored.sort(key=lambda x: -x[0])
    out, seen = [], set()
    for s, d in scored:
        key = (d["book"], d["label"])
        if key in seen:          # one passage per section keeps results varied
            continue
        seen.add(key)
        out.append({"book": BOOKS[d["book"]][1], "book_key": d["book"], "edition": BOOKS[d["book"]][2],
                    "section": d["section"], "near": d["label"], "text": d["text"]})
        if len(out) >= k:
            break
    return out