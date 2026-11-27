"""Streamlit rendering of the ATS report: an Enhancv-style dashboard built on the real analysis results."""
from html import escape

import streamlit as st

from .report import COLORS, build_html_report

# st.fragment lets category clicks re-run only the dashboard (so the results do not disappear).
_fragment = getattr(st, "fragment", None) or getattr(st, "experimental_fragment", None) or (lambda f: f)

# ---------------------------------------------------------------- styling
_CSS = """
<style>
.hp-counters{display:flex;gap:12px;flex-wrap:wrap;margin:6px 0 18px}
.hp-counter{flex:1 1 140px;border:1px solid #e6e8ec;border-radius:14px;padding:12px 16px;background:#fff;border-top-width:4px}
.hp-counter .n{font-size:28px;font-weight:700;line-height:1.1}
.hp-counter .t{font-size:13px;color:#666}
.hp-gauge{text-align:center;border:1px solid #e6e8ec;border-radius:16px;padding:14px 10px 12px;background:#fff;
  box-shadow:0 2px 10px rgba(0,0,0,.04);margin-bottom:12px}
.hp-gauge .t{font-size:20px;font-weight:600}
.hp-gauge .s{font-size:34px;font-weight:700;line-height:1}
.hp-gauge .m{font-size:16px;color:#888}
.hp-gauge .l{font-size:15px;font-weight:600;margin-top:2px}
.hp-head{display:flex;justify-content:space-between;align-items:center;gap:10px;flex-wrap:wrap;
  background:#f3f4f8;border-radius:16px;padding:16px 20px;margin-bottom:14px}
.hp-title{font-size:22px;font-weight:700}
.hp-chip{display:inline-block;border-radius:999px;padding:5px 14px;font-size:13px;font-weight:600;
  background:#fff;border:1px solid #e0e2e8;margin-left:6px}
div[data-testid="stExpander"]{border:1px solid #e6e8ec !important;border-radius:14px !important;
  background:#fff;margin-bottom:10px;box-shadow:0 1px 6px rgba(0,0,0,.03)}
div[data-testid="stExpander"] summary{padding:12px 16px;font-weight:600}
</style>
"""

# ---------------------------------------------------------------- status helpers
_OK = {"Found", "Good"}
_BAD = {"Missing", "Problem"}
_ICON = {"ok": "✅", "warn": "🟠", "bad": "❌", "skip": "⚪"}


def _level(status):
    if status in _OK:
        return "ok"
    if status == "Skipped":
        return "skip"
    if status in _BAD:
        return "bad"
    return "warn"


def _status_text(status):
    return "Passed" if status in _OK else status


def _score_color(score):
    return COLORS["Good"] if score >= 70 else COLORS["Needs Improvement"] if score >= 50 else COLORS["Problem"]


# ---------------------------------------------------------------- "why it matters" (static explanations)
_WHY = {
    "name": "Your name is how recruiters and the ATS create and find your candidate profile.",
    "email": "Recruiters contact you by email, and the ATS uses it to identify you.",
    "phone": "A readable phone number lets recruiters reach you quickly.",
    "location": "Many employers filter candidates by city or country before reading anything else.",
    "summary": "A short summary tells the recruiter who you are in the first few seconds.",
    "education": "Education is a common filter, especially for students and fresh graduates.",
    "experience": "Experience is the first thing most ATS filters and recruiters look at.",
    "skills": "ATS software matches the skills on your CV against the keywords in the job post.",
    "soft_skills": "Soft skills show how you work with others, and many job posts ask for them.",
    "projects": "Projects prove your skills in practice, which matters most when you have little experience.",
    "certifications": "Certifications give extra proof of your skills and show you keep learning.",
    "languages": "Language ability is a requirement or a plus in many roles.",
    "text_extraction": "If the ATS cannot read your text clearly, it cannot match you to any job.",
    "hidden_info": "Information inside images or icons is invisible to the ATS.",
    "layout": "Columns and tables can make the ATS read your sections in the wrong order.",
    "images_icons": "Photos, icons and symbols are ignored by the ATS or turned into unreadable characters.",
    "font_sizes": "Tiny text is hard to read, and too many different sizes make the CV look messy and harder for the ATS to structure.",
    "file_size": "Many job portals reject large files, and heavy PDFs often contain images the ATS cannot read.",
    "links": "Recruiters check your LinkedIn or GitHub to verify your experience, and the ATS can read links only when they are plain text.",
    "design": "Cramped margins, scattered alignment and tight line spacing make a CV tiring to read and harder for the ATS to structure.",
        "quantifying": "Numbers turn a vague duty into proof of impact, and recruiters notice results far faster than responsibilities.",
    "action_verbs": "Bullets that start with strong action verbs read as achievements, not just job descriptions.",
  
    "length": "Too short looks empty and too long gets skimmed; 1-2 pages is the usual sweet spot.",
    "headings": "ATS software finds your sections by standard headings such as Education and Experience.",
    "dates": "Consistent dates let the ATS calculate your experience correctly.",
    "bullets": "Short bullet points are easier for both the ATS and recruiters to scan.",
}

_PERSONAL_KEYS = {"name", "email", "phone", "location"}

_FUTURE = [
    "Repetition", "Spelling & Grammar",
    "ATS Parse Rate", "HR Red Flags",
]


# ---------------------------------------------------------------- building the categories from the real result
def _from_item(i):
    return {"key": i["key"], "name": i["label"], "status": i["status"], "detail": i["detail"], "fix": i["fix"]}


def _from_check(c):
    return {"key": c["key"], "name": c["name"], "status": c["status"], "detail": c["detail"], "fix": c["fix"]}


def _pct(breakdown, names):
    rows = [breakdown[n] for n in names if n in breakdown]
    mx = sum(r["max"] for r in rows)
    return round(100 * sum(r["earned"] for r in rows) / mx) if mx else None


def _build_categories(result):
    bd = {b["category"]: b for b in result["score"]["breakdown"]}
    items, checks = result["items"], result["checks"]

    essentials = [_from_item(i) for i in items if i["key"] in _PERSONAL_KEYS] + \
                 [_from_check(c) for c in checks if c["category"] == "parsing"]
    sections = [_from_item(i) for i in items if i["key"] not in _PERSONAL_KEYS]
    formatting = [_from_check(c) for c in checks if c["category"] not in ("parsing", "content")]
    content = [_from_check(c) for c in checks if c["category"] == "content"]

    return [
        {"id": "essentials", "icon": "📋", "title": "ATS Essentials", "entries": essentials,
         "pct": _pct(bd, ["Personal information", "Readability & parsing"])},
        {"id": "sections", "icon": "📚", "title": "Sections", "entries": sections,
         "pct": _pct(bd, ["Important CV sections"])},
        {"id": "formatting", "icon": "🛠️", "title": "Formatting", "entries": formatting,
         "pct": _pct(bd, ["Formatting quality", "Organization & consistency"])},
         {"id": "content", "icon": "✍️", "title": "Content", "entries": content,
         "pct": _pct(bd, ["Content quality"])},             
        {"id": "recs", "icon": "💡", "title": "Recommendations", "entries": [], "pct": None},
        {"id": "future", "icon": "🧪", "title": "Coming soon", "entries": [], "pct": None},
    ]


def _issues(entries):
    return sum(1 for e in entries if _level(e["status"]) in ("warn", "bad"))


# ---------------------------------------------------------------- pieces
def _gauge(score, label):
    color = _score_color(score)
    st.markdown(
        "<div class='hp-gauge'><div class='t'>Your Score</div>"
        "<svg viewBox='0 0 200 115' width='210' style='max-width:100%'>"
        "<path d='M20 100 A80 80 0 0 1 180 100' pathLength='100' fill='none' stroke='#eceef2' stroke-width='16' stroke-linecap='round'/>"
        f"<path d='M20 100 A80 80 0 0 1 180 100' pathLength='100' fill='none' stroke='{color}' stroke-width='16' "
        f"stroke-linecap='round' stroke-dasharray='{max(0, min(100, score))} 100'/></svg>"
        f"<div class='s' style='color:{color}'>{score}<span class='m'>/100</span></div>"
        f"<div class='l' style='color:{color}'>{escape(label)}</div></div>",
        unsafe_allow_html=True,
    )


def _select(cat_id):
    st.session_state["hp_cat"] = cat_id


def _render_entry(e):
    lvl = _level(e["status"])
    with st.expander(f"{_ICON[lvl]} {e['name']}  ·  {_status_text(e['status'])}", expanded=False):
        st.markdown(f"**What we detected:** {escape(e['detail'])}")
        if e["key"] in _WHY:
            st.markdown(f"**Why it matters:** {_WHY[e['key']]}")
        if lvl in ("warn", "bad") and e["fix"]:
            st.markdown(f"**💡 Recommendation:** {escape(e['fix'])}")
        elif lvl == "ok":
            st.markdown("**No action needed** ✅")


def _render_right(cat, result):
    chips = ""
    if cat["pct"] is not None:
        chips += f"<span class='hp-chip' style='color:{_score_color(cat['pct'])}'>{cat['pct']}%</span>"
    if cat["entries"]:
        n = _issues(cat["entries"])
        chips += (f"<span class='hp-chip'>{n} issue{'s' if n != 1 else ''} found</span>" if n
                  else f"<span class='hp-chip' style='color:{COLORS['Good']}'>No issues</span>")
    elif cat["id"] == "recs":
        chips += f"<span class='hp-chip'>{len(result['recommendations'])} suggestions</span>"
    st.markdown(f"<div class='hp-head'><div class='hp-title'>{cat['icon']} {escape(cat['title']).upper()}</div>"
                f"<div>{chips}</div></div>", unsafe_allow_html=True)

    if cat["id"] == "recs":
        icons = {"High": "🔴", "Medium": "🟠", "Low": "🟢"}
        order = {"High": 0, "Medium": 1, "Low": 2}
        recs = sorted(result["recommendations"], key=lambda r: order.get(r["priority"], 3))
        if not recs:
            st.success("No recommendations. Great job!")
        for r in recs:
            with st.container(border=True):
                st.markdown(f"{icons.get(r['priority'], '⚪')} **{escape(r['title'])}** *({r['priority']} priority)*  \n"
                            f"{escape(r['detail'])}")
    elif cat["id"] == "future":
        st.info("These checks are not implemented yet. They are planned as future enhancements, "
                "so no results are shown for them.")
        for name in _FUTURE:
            st.markdown(f"- ⏳ **{name}** - not available yet")
    else:
        for e in cat["entries"]:
            _render_entry(e)


@_fragment
def _dashboard(result):
    cats = _build_categories(result)
    valid = {c["id"] for c in cats}
    if st.session_state.get("hp_cat") not in valid:
        st.session_state["hp_cat"] = cats[0]["id"]
    current = st.session_state["hp_cat"]

    left, right = st.columns([1, 2], gap="large")
    with left:
        _gauge(result["score"]["score"], result["score"]["label"])
        for c in cats:
            selected = c["id"] == current
            pct = f" · {c['pct']}%" if c["pct"] is not None else ""
            st.button(f"{c['icon']} {c['title']}{pct}   {'▾' if selected else '▸'}",
                      key=f"hp_cat_{c['id']}", type="primary" if selected else "secondary",
                      use_container_width=True, on_click=_select, args=(c["id"],))
            if selected and c["entries"]:
                st.markdown("\n".join(f"- {_ICON[_level(e['status'])]} {e['name']}" for e in c["entries"]))
    with right:
        _render_right(next(c for c in cats if c["id"] == current), result)


def _counter(n, title, color):
    return (f"<div class='hp-counter' style='border-top-color:{color}'>"
            f"<div class='n' style='color:{color}'>{n}</div><div class='t'>{title}</div></div>")


def _download(result):
    html = build_html_report(result)
    kwargs = dict(label="⬇️ Download ATS report (HTML - open it and print to PDF)", data=html,
                  file_name="hire_path_ats_report.html", mime="text/html")
    try:  # on_click="ignore" keeps the page from re-running (and hiding the results) after download
        st.download_button(on_click="ignore", **kwargs)
    except TypeError:  # older Streamlit versions
        st.download_button(**kwargs)


# ---------------------------------------------------------------- main
def render_ats_report(result):
    if result.get("error"):
        st.error(result["error"])
        if result.get("is_scanned"):
            st.info("Tip: if you can copy text from your CV when you open it in a PDF viewer, it is ATS-readable. "
                    "If you cannot, ATS software will see an empty page.")
        return

    st.markdown(_CSS, unsafe_allow_html=True)
    s = result["score"]
    st.subheader("ATS Analysis Results")

    _it, _ck = result["items"], result["checks"]
    found = sum(1 for i in _it if i["status"] == "Found") + sum(1 for c in _ck if c["status"] == "Good")
    miss = sum(1 for i in _it if i["status"] == "Missing") + sum(1 for c in _ck if c["status"] == "Problem")
    imp = sum(1 for i in _it if i["status"] == "Needs Improvement") + sum(1 for c in _ck if c["status"] == "Needs Improvement")
    st.markdown("<div class='hp-counters'>"
                + _counter(found, "Found", COLORS["Good"])
                + _counter(imp, "Needs Improvement", COLORS["Needs Improvement"])
                + _counter(miss, "Missing", COLORS["Problem"])
                + "</div>", unsafe_allow_html=True)
   
    _dashboard(result)

    with st.expander("📊 Score breakdown", expanded=False):
        for b in s["breakdown"]:
            st.markdown(f"**{escape(b['category'])}** — {b['earned']} / {b['max']}")
            st.progress(b["earned"] / b["max"] if b["max"] else 0)
    st.caption(s["disclaimer"])
    _download(result)
