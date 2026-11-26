"""ATS formatting / parsing checks. Each check returns Good / Needs Improvement / Problem / Skipped."""
import re

GOOD, IMPROVE, PROBLEM, SKIPPED = "Good", "Needs Improvement", "Problem", "Skipped"

MONTHS = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]*\.?"
RE_MONTH_YEAR = re.compile(r"\b" + MONTHS + r"\s+(?:19|20)\d{2}\b", re.I)
RE_NUMERIC = re.compile(r"\b(?:0?[1-9]|1[0-2])\s*[/.\-]\s*(?:19|20)\d{2}\b")
RE_YEAR = re.compile(r"\b(?:19|20)\d{2}\b")
BULLET_START = re.compile(r"^\s*[•●▪■◦‣▸►➢➤✓\-–*·\uf000-\uf8ff\x7f\x01-\x08]")
ICON_CHARS = re.compile("[\ue000-\uf8ff\u2600-\u26ff\u2700-\u27bf\U0001F300-\U0001FAFF]")


def _check(key, category, name, status, detail, fix=""):
    return {"key": key, "category": category, "name": name, "status": status, "detail": detail, "fix": fix}


def _text_extraction(ext):
    text = ext["text"]
    n = max(len(text), 1)
    garbage = text.count("\ufffd") + text.count("(cid:") * 6
    weird = sum(1 for c in text if ord(c) < 32 and c not in "\n\r\t")
    ratio = (garbage + weird) / n
    toks = text.split()
    spaced = (sum(1 for t in toks if len(t) == 1 and t.isalpha()) / max(len(toks), 1))
    avg = sum(ext["chars_per_page"]) / max(ext["pages"], 1)
    if ratio > 0.05:
        return _check("text_extraction", "parsing", "Text extraction quality", PROBLEM,
                      f"About {ratio:.0%} of the extracted text is unreadable symbols.",
                      "Re-export the CV from Word/Google Docs using a standard font (Arial, Calibri) instead of 'print to PDF' from design tools.")
    if ratio > 0.01 or spaced > 0.30:
        why = "letters appear spaced out" if spaced > 0.30 else "some characters could not be read"
        return _check("text_extraction", "parsing", "Text extraction quality", IMPROVE,
                      f"Text was extracted, but {why}.",
                      "Avoid decorative fonts and letter-spacing; use standard fonts and normal spacing.")
    return _check("text_extraction", "parsing", "Text extraction quality", GOOD,
                  f"Clean selectable text was extracted (~{int(avg)} characters per page).")


def _hidden_in_images(ext, det):
    contact_missing = [k for k in ("email", "phone", "name") if not det["contact"].get(k)]
    if ext["images"] == 0:
        return _check("hidden_info", "parsing", "Information inside images", GOOD,
                      "No embedded images were found, so everything is selectable text.")
    if contact_missing:
        return _check("hidden_info", "parsing", "Information inside images", PROBLEM,
                      f"The CV contains {ext['images']} image(s) and the {', '.join(contact_missing)} could not be read as text. "
                      "It may be embedded in an image or icon.",
                      "Type your contact details as plain text in the header; never place them inside images.")
    return _check("hidden_info", "parsing", "Information inside images", GOOD,
                  f"{ext['images']} image(s) found, but your contact details are readable as text.")


def _layout(ext):
    """Detect side-by-side columns / table cells from the x,y position of text fragments."""
    rows = {}
    for pno, x, y, fs, text in ext.get("fragments", []):
        rows.setdefault((pno, round(y / 3)), []).append((x, fs, text))
    if not rows:
        return _check("layout", "format", "Columns / tables", SKIPPED, "Layout analysis was not available for this file.")
    gapped = 0
    for frs in rows.values():
        frs.sort()
        for (x1, fs1, t1), (x2, _, _) in zip(frs, frs[1:]):
            if x2 - (x1 + 0.45 * fs1 * len(t1.strip())) > 60:  # a wide empty gap inside one line
                gapped += 1
                break
    ratio = gapped / len(rows)
    pipes = sum(1 for l in ext["text"].splitlines() if l.count("|") >= 3)
    if ratio > 0.35:
        return _check("layout", "format", "Columns / tables", PROBLEM,
                      f"About {ratio:.0%} of lines are split into side-by-side columns or table cells.",
                      "Use a single-column layout. Many ATS read columns line-by-line and mix up sections.")
    if ratio > 0.15 or pipes > 3:
        return _check("layout", "format", "Columns / tables", IMPROVE,
                      "Some parts of the CV look like columns or a table (e.g. a sidebar or skills grid).",
                      "Prefer a single column; present skills as a simple comma-separated list.")
    return _check("layout", "format", "Columns / tables", GOOD, "The layout reads as a single column.")


def _images_icons(ext):
    text = ext["text"]
    icons = 0
    for line in text.splitlines():
        body = BULLET_START.sub("", line, count=1)
        icons += len(ICON_CHARS.findall(body))
    problems = []
    if ext["large_images"]:
        problems.append(f"{ext['large_images']} large image(s) (photo/graphic)")
    if ext["images"] - ext["large_images"] > 3:
        problems.append(f"{ext['images'] - ext['large_images']} small images/icons")
    if icons > 3:
        problems.append(f"{icons} icon/symbol characters")
    if not problems:
        return _check("images_icons", "format", "Images, icons and symbols", GOOD, "No problematic images or icons were found.")
    status = PROBLEM if (ext["large_images"] and icons > 6) or ext["images"] > 8 else IMPROVE
    return _check("images_icons", "format", "Images, icons and symbols", status,
                  "Found " + ", ".join(problems) + ".",
                  "Remove the photo, skill-bars and decorative icons; use words instead (e.g. write 'Email:' not an envelope icon).")


def _length(ext, det):
    words = det["metrics"]["word_count"]
    pages = ext["pages"]
    if words < 150:
        return _check("length", "format", "CV length", PROBLEM, f"Only {words} words found, which is too little content.",
                      "Add detail to experience, projects and skills (aim for 300-700 words).")
    if words < 250:
        return _check("length", "format", "CV length", IMPROVE, f"{words} words ({pages} page(s)) is on the short side.",
                      "Expand projects and experience with what you built and the results.")
    if pages > 2 or words > 1100:
        return _check("length", "format", "CV length", IMPROVE, f"{pages} pages / {words} words is long.",
                      "Keep the CV to 1-2 pages; remove old or irrelevant details.")
    return _check("length", "format", "CV length", GOOD, f"{pages} page(s), {words} words: a good length.")


def _headings(det):
    m = det["metrics"]
    core = [k for k in ("education", "experience", "skills", "projects", "summary") if k in det["sections"]]
    n = m["heading_count"]
    names = ", ".join(m["headings"][:8])
    if n >= 4 and len(core) >= 3:
        return _check("headings", "organization", "Standard section headings", GOOD, f"{n} standard headings recognised: {names}.")
    if n >= 2:
        return _check("headings", "organization", "Standard section headings", IMPROVE,
                      f"Only {n} standard heading(s) recognised ({names}).",
                      "Use common headings: Summary, Education, Experience, Skills, Projects, Certifications, Languages.")
    return _check("headings", "organization", "Standard section headings", PROBLEM,
                  "Almost no standard section headings were recognised.",
                  "Use plain, common headings (Education, Experience, Skills...) rather than creative names.")


def _dates(text):
    month = RE_MONTH_YEAR.findall(text)
    numeric = RE_NUMERIC.findall(text)
    rest = RE_NUMERIC.sub(" ", RE_MONTH_YEAR.sub(" ", text))
    years = RE_YEAR.findall(rest)
    styles = [n for n, c in (("Month YYYY", month), ("MM/YYYY", numeric), ("YYYY only", years)) if c]
    if not styles:
        return _check("dates", "organization", "Date consistency", IMPROVE, "No dates were found.",
                      "Add dates to education and experience (e.g. Jan 2024 - Present).")
    # YYYY only next to another style is common (education years), so only flag clearly mixed month styles
    if len([s for s in styles if s != "YYYY only"]) >= 2 or (len(month) >= 2 and len(years) >= 3 and len(month) < len(years)):
        return _check("dates", "organization", "Date consistency", IMPROVE,
                      "Several date formats are mixed: " + ", ".join(styles) + ".",
                      "Choose one format for all dates (for example 'Jan 2024 - Mar 2025').")
    return _check("dates", "organization", "Date consistency", GOOD, "Dates use a consistent format (" + ", ".join(styles) + ").")


def _bullets(ext, det):
    lines = [l for l in ext["text"].splitlines() if l.strip()]
    bullets = sum(1 for l in lines if BULLET_START.match(l))
    exp_words = det["sections"].get("experience", {}).get("words", 0) + det["sections"].get("projects", {}).get("words", 0)
    if exp_words > 40 and bullets < 3:
        return _check("bullets", "organization", "Bullet points", IMPROVE,
                      "Experience/projects are written as long text without bullet points.",
                      "Use short bullet points (2-4 per role/project), each starting with an action verb.")
    return _check("bullets", "organization", "Bullet points", GOOD,
                  f"{bullets} bullet line(s) found." if bullets else "Not much descriptive text, so bullets are not required.")

def _font_sizes(ext):
    """Check body font size and how many different font sizes are used (uses real fragment data)."""
    weights = {}
    for _pno, _x, _y, fs, text in ext.get("fragments", []):
        n = len(text.strip())
        if n and fs > 0:
            size = round(fs * 2) / 2  # group to the nearest 0.5pt
            weights[size] = weights.get(size, 0) + n
    if not weights:
        return _check("font_sizes", "format", "Font size consistency", SKIPPED,
                      "Font size information was not available for this file.")
    body = max(weights, key=weights.get)
    total = sum(weights.values())
    # ignore tiny leftovers (<2% of the text) when counting how many sizes are used
    used = sorted(s for s, w in weights.items() if w / total >= 0.02)
    sizes_text = ", ".join(f"{s:g}pt" for s in used)
    if body < 9:
        return _check("font_sizes", "format", "Font size consistency", PROBLEM,
                      f"Most of the text is {body:g}pt, which is too small to read comfortably.",
                      "Use 10-12pt for the main text and 14-18pt for headings.")
    if body < 9.5 or len(used) > 6:
        why = f"the main text is {body:g}pt" if body < 9.5 else f"{len(used)} different font sizes are used ({sizes_text})"
        return _check("font_sizes", "format", "Font size consistency", IMPROVE,
                      f"Font sizes could be cleaner: {why}.",
                      "Use 10-12pt for the main text and stick to 2-3 sizes (body, subheadings, name/headings).")
    return _check("font_sizes", "format", "Font size consistency", GOOD,
                  f"Main text is {body:g}pt and the CV uses {len(used)} font size(s): {sizes_text}.")

RE_LINKEDIN = re.compile(r"linkedin\.com/[^\s|,;]+", re.I)
RE_GITHUB = re.compile(r"github\.com/[^\s|,;]+", re.I)
RE_ANY_URL = re.compile(r"(?:https?://|www\.)[^\s|,;]+", re.I)


def _file_size(ext):
    """File size check (the file itself, as uploaded)."""
    size = ext.get("file_size")
    if not size:
        return _check("file_size", "parsing", "File format & size", SKIPPED,
                      "File size information was not available.")
    mb = size / (1024 * 1024)
    shown = f"{mb:.2f} MB" if mb >= 0.1 else f"{size / 1024:.0f} KB"
    if mb > 5:
        return _check("file_size", "parsing", "File format & size", PROBLEM,
                      f"The PDF is {shown}, which is too large. Many ATS portals reject files over 5 MB.",
                      "Compress the PDF or remove heavy images. Aim for under 2 MB.")
    if mb > 2:
        return _check("file_size", "parsing", "File format & size", IMPROVE,
                      f"The PDF is {shown}, which is larger than recommended.",
                      "Compress the PDF or remove images. Aim for under 2 MB.")
    return _check("file_size", "parsing", "File format & size", GOOD,
                  f"The file is a text-based PDF of {shown}, a good size for ATS upload.")


def _links(ext):
    """Look for professional profile links in the extracted text."""
    text = ext["text"]
    linkedin = RE_LINKEDIN.search(text)
    github = RE_GITHUB.search(text)
    others = [u for u in RE_ANY_URL.findall(text) if "linkedin.com" not in u.lower() and "github.com" not in u.lower()]
    found = []
    if linkedin:
        found.append("LinkedIn")
    if github:
        found.append("GitHub")
    if others:
        found.append(f"{len(others)} other link(s)")
    if linkedin or github:
        return _check("links", "parsing", "Profile links", GOOD, "Found: " + ", ".join(found) + ".")
    if others:
        return _check("links", "parsing", "Profile links", IMPROVE,
                      "Only other links were found (" + ", ".join(found) + "), but no LinkedIn or GitHub.",
                      "Add your LinkedIn profile URL (and GitHub if you are in tech) as plain text in the header.")
    return _check("links", "parsing", "Profile links", IMPROVE,
                  "No LinkedIn, GitHub or portfolio link was found in the text.",
                  "Add your LinkedIn profile URL (and GitHub if you are in tech) as plain text in the header.")

def _design(ext):
    """Margins, left-edge consistency and line spacing, measured from real text positions."""
    frags = [(p, x, y, fs, t) for p, x, y, fs, t in ext.get("fragments", []) if t.strip() and fs > 0]
    if len(frags) < 10:
        return _check("design", "format", "Design: margins & spacing", SKIPPED,
                      "Not enough layout information was available for this file.")
    problems, notes = [], []

    # left margin (use the 5th percentile of x so one stray item does not decide)
    xs = sorted(x for _, x, _, _, _ in frags)
    left = xs[max(0, int(len(xs) * 0.05))]
    if left < 28:
        problems.append(f"the left margin is only about {left / 72:.2f} inch")
    else:
        notes.append(f"left margin about {left / 72:.1f} inch")

    # left-edge consistency: share of lines that start near the most common start position
    starts = {}
    for _, x, _, _, _ in frags:
        key = round(x / 6)
        starts[key] = starts.get(key, 0) + 1
    top_share = max(starts.values()) / len(frags)
    if top_share < 0.25:
        problems.append("text starts at many different horizontal positions")

    # line spacing: median gap between consecutive lines on the same page, relative to font size
    gaps = []
    by_page = {}
    for p, x, y, fs, t in frags:
        by_page.setdefault(p, []).append((round(y), fs))
    for items in by_page.values():
        ys = sorted({y for y, _ in items}, reverse=True)
        sizes = [fs for _, fs in items]
        body = sorted(sizes)[len(sizes) // 2]
        for a, b in zip(ys, ys[1:]):
            gap = a - b
            if 0 < gap < body * 3:
                gaps.append(gap / body)
    if gaps:
        gaps.sort()
        ratio = gaps[len(gaps) // 2]
        if ratio < 1.05:
            problems.append("lines are packed very tightly")
        else:
            notes.append(f"line spacing about {ratio:.1f}x the font size")

    if problems:
        return _check("design", "format", "Design: margins & spacing", IMPROVE,
                      "Layout could be cleaner: " + "; ".join(problems) + ".",
                      "Keep margins between 0.5 and 1 inch, align text to a clear left edge, "
                      "and leave comfortable space between lines and sections.")
    return _check("design", "format", "Design: margins & spacing", GOOD,
                  "Layout looks balanced (" + ", ".join(notes) + ").")

def _quantifying(det):
    """Share of experience/project lines that contain numbers (from the detector's real metrics)."""
    m = det["metrics"]
    total, num = m["bullets"], m["quantified"]
    if total < 3:
        return _check("quantifying", "content", "Quantifying impact", SKIPPED,
                      "Not enough experience or project lines were found to measure this.")
    share = num / total
    if share >= 0.4:
        return _check("quantifying", "content", "Quantifying impact", GOOD,
                      f"{num} of {total} experience/project lines contain numbers ({share:.0%}).")
    if num == 0:
        return _check("quantifying", "content", "Quantifying impact", IMPROVE,
                      f"None of the {total} experience/project lines contain numbers.",
                      "Add measurable results: percentages, counts, time saved, users, or sizes "
                      "(e.g. 'Reduced page load time by 30%').")
    return _check("quantifying", "content", "Quantifying impact", IMPROVE,
                  f"Only {num} of {total} experience/project lines contain numbers ({share:.0%}).",
                  "Add numbers to more lines: percentages, counts, time saved, users or project sizes.")


def _action_verbs(det):
    """Share of experience/project lines that start with a strong action verb (from the detector's metrics)."""
    m = det["metrics"]
    total, verbs = m["bullets"], m["action_verb_lines"]
    if total < 3:
        return _check("action_verbs", "content", "Action verbs in bullets", SKIPPED,
                      "Not enough experience or project lines were found to measure this.")
    share = verbs / total
    if share >= 0.5:
        return _check("action_verbs", "content", "Action verbs in bullets", GOOD,
                      f"{verbs} of {total} lines start with a strong action verb ({share:.0%}).")
    return _check("action_verbs", "content", "Action verbs in bullets", IMPROVE,
                  f"Only {verbs} of {total} lines start with a recognised action verb ({share:.0%}).",
                  "Start each bullet with a strong verb such as Developed, Built, Designed, Implemented, "
                  "Improved or Led.")


def analyze_formatting(ext, det):
    checks = [
        _text_extraction(ext), _hidden_in_images(ext, det), _file_size(ext), _links(ext),
        _layout(ext), _images_icons(ext), _font_sizes(ext), _design(ext), _length(ext, det),
        _headings(det), _dates(ext["text"]), _bullets(ext, det),
        _quantifying(det), _action_verbs(det),
    ]
    return checks
