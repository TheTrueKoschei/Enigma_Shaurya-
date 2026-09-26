"""Presentation layer: theme, accessibility controls and page chrome.

The interface follows the conventions of an Indian public-sector portal - light
surface, navy primary, a thin tricolour rule under the masthead, flat bordered
blocks and no decorative motion. Everything here is static CSS and session
state; nothing animates and nothing is fetched beyond the typeface.

Accessibility is driven from three pieces of session state - text scale, high
contrast and language - which are read at the top of every run and written into
CSS custom properties before any widget is drawn.
"""

from __future__ import annotations

import pathlib
import subprocess

import streamlit as st

from i18n import LANGUAGES, t

# ----------------------------------------------------------------------
# Palette. Marks were validated against the light surface: every pair clears
# the colourblind-separation and normal-vision floors. Amber sits below 3:1
# against white, so it never carries meaning alone - it is always accompanied
# by the legend and by the ranked table.
# ----------------------------------------------------------------------
NAVY = "#0b4f8a"
SUPPLIER_COLOUR = "#1f5fa9"      # navy blue
RECEIVER_COLOUR = "#eda100"      # amber
LOSS_COLOUR = "#d03b3b"          # status: critical
SAFFRON = "#ff9933"
INDIA_GREEN = "#138808"

# ----------------------------------------------------------------------
# Status colour language. Learned once on the grading screen, then every
# other screen reads itself:
#
#   green  = passes / positive value
#   amber  = marginal / caution
#   red    = fails / negative value
#   navy   = neutral data, no judgement attached
#
# Green and red are 4.1 Delta E apart under deuteranopia, which is well below
# the safe floor - roughly one man in twelve cannot separate them. So NOTHING
# in this interface may carry pass/fail on colour alone: every status mark is
# paired with a glyph and a word. That is a hard rule, not a preference, and
# it is why the components below always take a label.
#
# Amber sits at 1.8:1 against white, so it gets a darker outline wherever it
# is used as a fill, to keep the shape visible without shifting the hue.
# ----------------------------------------------------------------------
STATUS_GOOD = "#0ca30c"
STATUS_WARN = "#fab219"
STATUS_WARN_EDGE = "#8a6100"
STATUS_BAD = "#d03b3b"
ACCENT = "#1f5fa9"
NEUTRAL_GREY = "#b9c0cc"

GLYPH_PASS = "&#10003;"          # check mark
GLYPH_FAIL = "&#10007;"          # ballot X
GLYPH_LOCK = "&#128274;"         # padlock, for a rung not reached


# ----------------------------------------------------------------------
# Build stamp. A hosted instance serves the last build that succeeded, which is
# not necessarily the newest commit on the branch - a failed build, or a deploy
# pinned to a branch that no longer exists, both look exactly like "my changes
# did not appear". Printing the revision the running process was started from
# turns that guess into a one-glance check: compare it against the branch head
# on GitHub. BUILD is bumped by hand and survives even when .git is absent.
# ----------------------------------------------------------------------
BUILD = "2026-09-26.1"


def revision() -> str:
    """Short commit of the checkout this process is running from, or "" if unknown."""
    root = pathlib.Path(__file__).resolve().parent
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=root, capture_output=True, text=True, timeout=5, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    # No git binary in the container, or a tarball deploy. Fall back to reading
    # the ref files directly, which needs nothing but the filesystem.
    try:
        head = (root / ".git" / "HEAD").read_text().strip()
        if head.startswith("ref: "):
            ref = (root / ".git" / head[5:]).read_text().strip()
            return ref[:7]
        return head[:7]
    except OSError:
        return ""


def build_stamp() -> None:
    """Render the build identifier at the foot of the sidebar."""
    rev = revision()
    detail = f"build {BUILD}" + (f" &middot; rev {rev}" if rev else "")
    st.markdown(
        f'<p class="caveat">{detail}</p>'
        '<p class="caveat">If this does not match the latest commit on the '
        'branch, the host is serving an older build.</p>',
        unsafe_allow_html=True,
    )


def status_colour(passes: bool, marginal: bool = False) -> str:
    """The one place a pass/fail becomes a colour."""
    if not passes:
        return STATUS_BAD
    return STATUS_WARN if marginal else STATUS_GOOD

# Sequential blue for magnitude, light to dark. On a white surface the lightest
# step recedes into the page, so a state with no activity reads as empty.
BLUE_SEQUENTIAL = [
    [0.00, "#eef3f9"], [0.20, "#cfe0f1"], [0.40, "#9fc1e3"],
    [0.60, "#5f93cb"], [0.80, "#2f6cae"], [1.00, "#0b3c6b"],
]

TEXT_SCALES = {"A-": 0.92, "A": 1.0, "A+": 1.14}


def init_state() -> None:
    """Defaults for the accessibility controls, read before any CSS is emitted."""
    st.session_state.setdefault("ui_lang", "en")
    st.session_state.setdefault("ui_scale", "A")
    st.session_state.setdefault("ui_contrast", False)


def lang() -> str:
    return st.session_state.get("ui_lang", "en")


def tr(key: str) -> str:
    """Translate a chrome string into the selected language."""
    return t(key, lang())


def inject_styles() -> None:
    """All styling for the portal. Static - there are no animations."""
    scale = TEXT_SCALES.get(st.session_state.get("ui_scale", "A"), 1.0)
    contrast = bool(st.session_state.get("ui_contrast", False))

    ink = "#000000" if contrast else "#1a1f2b"
    muted = "#1a1f2b" if contrast else "#5a6472"
    line = "#000000" if contrast else "#d5d9e0"
    line_w = "2px" if contrast else "1px"
    surface = "#ffffff"
    page = "#ffffff" if contrast else "#f5f6f8"

    st.markdown(
        f"""
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Sans:wght@400;500;600;700&family=Noto+Sans+Devanagari:wght@400;500;600;700&display=swap');

        html {{ font-size: calc(16px * {scale}); }}

        :root {{
          --ink: {ink};
          --muted: {muted};
          --line: {line};
          --line-w: {line_w};
          --surface: {surface};
          --page: {page};
          --navy: {NAVY};
          --navy-dark: #083a66;
          --saffron: {SAFFRON};
          --green: {INDIA_GREEN};
          --sans: 'Noto Sans', 'Noto Sans Devanagari', Arial, Helvetica, sans-serif;
        }}

        html, body, .stApp, [class*="css"] {{ font-family: var(--sans); }}
        .stApp {{ background: var(--page); color: var(--ink); }}
        .block-container {{ padding-top: 0.6rem; padding-bottom: 3rem; max-width: 1560px; }}

        /* ---------- utility bar ---------- */
        .utilbar {{ background: #e9edf2; border-bottom: var(--line-w) solid var(--line);
          padding: .3rem .8rem; font-size: .78rem; color: var(--ink); }}
        .skiplink {{ position: absolute; left: -9999px; }}
        .skiplink:focus {{ position: static; display: inline-block; padding: .3rem .6rem;
          background: var(--navy); color: #fff; font-weight: 700; }}

        /* ---------- masthead ---------- */
        .masthead {{ background: var(--surface); border: var(--line-w) solid var(--line);
          border-bottom: none; padding: .9rem 1.1rem .8rem; }}
        .wordmark {{ display: inline-flex; align-items: center; justify-content: center;
          width: 46px; height: 46px; border: 2px solid var(--navy); color: var(--navy);
          font-weight: 700; font-size: 1.05rem; letter-spacing: .02em; }}
        .masthead h1 {{ font-size: 1.5rem !important; font-weight: 700; color: var(--navy);
          margin: 0; letter-spacing: -.01em; line-height: 1.2; }}
        .masthead .sub {{ font-size: .86rem; color: var(--muted); margin: .12rem 0 0; }}
        .tricolour {{ height: 6px; display: flex; border: 1px solid var(--line);
          border-top: none; margin-bottom: .45rem; }}
        .tricolour i {{ flex: 1; display: block; height: 100%; }}
        .breadcrumb {{ font-size: .8rem; color: var(--muted); padding: .5rem .1rem .7rem;
          border-bottom: var(--line-w) solid var(--line); margin-bottom: 1rem; }}
        .breadcrumb b {{ color: var(--ink); font-weight: 600; }}

        /* ---------- navigation bar ---------- */
        .stTabs [role="tablist"] {{ gap: 0; background: var(--navy);
          border: none; border-radius: 0; padding: 0; margin: 0;
          border-bottom: 3px solid var(--navy-dark); }}
        .stTabs [data-testid="stTab"], .stTabs [data-baseweb="tab"] {{
          height: auto; padding: .6rem 1.05rem; border-radius: 0;
          background: transparent; color: #ffffff;
          border-right: 1px solid rgba(255,255,255,.25); }}
        .stTabs [data-testid="stTab"] p, .stTabs [data-baseweb="tab"] p {{
          color: #ffffff; font-weight: 600; font-size: .86rem; margin: 0; }}
        .stTabs [data-testid="stTab"]:hover, .stTabs [data-baseweb="tab"]:hover {{
          background: var(--navy-dark); }}
        .stTabs [aria-selected="true"] {{ background: #ffffff !important; }}
        .stTabs [aria-selected="true"] p {{ color: var(--navy) !important;
          font-weight: 700 !important; }}
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {{ display: none !important;
          background: transparent !important; height: 0 !important; }}

        /* ---------- flat stat blocks ---------- */
        .stats {{ display: grid; gap: .55rem; margin: .2rem 0 .7rem; }}
        .stat {{ background: var(--surface); border: var(--line-w) solid var(--line);
          padding: .7rem .8rem; }}
        .stat .lab {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .05em;
          color: var(--muted); font-weight: 600; margin-bottom: .3rem; }}
        .stat .val {{ font-size: 1.32rem; font-weight: 700; color: var(--ink);
          line-height: 1.15; }}
        .stat .sub {{ font-size: .74rem; color: var(--muted); margin-top: .22rem; }}
        .stat .sub.bad {{ color: #a32020; font-weight: 600; }}

        /* ---------- blocks and type ---------- */
        .sect {{ font-size: 1.02rem; font-weight: 700; color: var(--navy);
          margin: 1.1rem 0 .5rem; padding-bottom: .3rem;
          border-bottom: var(--line-w) solid var(--line); }}
        .sub {{ color: var(--muted); font-size: .86rem; line-height: 1.6; margin: 0 0 .8rem; }}
        .note {{ background: var(--surface); border: var(--line-w) solid var(--line);
          border-left: 4px solid var(--navy); padding: .7rem .9rem; margin-bottom: .9rem;
          font-size: .9rem; line-height: 1.55; }}
        .note.loss {{ border-left-color: #a32020; }}
        .sec-title {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .06em;
          color: var(--muted); font-weight: 700; margin: .8rem 0 .2rem; }}
        .sec-body {{ font-size: .9rem; line-height: 1.62; margin: 0; }}
        .caveat {{ font-size: .78rem; color: var(--muted); line-height: 1.5; }}

        /* ---------- widgets ---------- */
        .stButton > button {{ border-radius: 2px; font-weight: 600;
          border: var(--line-w) solid var(--line); background: var(--surface);
          color: var(--ink); }}
        .stButton > button[kind="primary"] {{ background: var(--navy); color: #ffffff;
          border-color: var(--navy); }}
        .stDownloadButton > button {{ border-radius: 2px; }}
        [data-testid="stMetricValue"] {{ font-size: 1.22rem; font-weight: 700;
          color: var(--ink); }}
        [data-testid="stMetricLabel"] {{ font-size: .72rem; text-transform: uppercase;
          letter-spacing: .05em; color: var(--muted); }}
        section[data-testid="stSidebar"] {{ background: var(--surface);
          border-right: var(--line-w) solid var(--line); }}
        section[data-testid="stSidebar"] h3 {{ font-size: .78rem; text-transform: uppercase;
          letter-spacing: .06em; color: var(--navy); font-weight: 700; }}
        div[data-testid="stDataFrame"] {{ font-variant-numeric: tabular-nums; }}
        hr {{ border-color: var(--line); }}

        .meter {{ height: 5px; background: #e8ebef; margin: .4rem 0 .25rem; }}
        .meter > i {{ display: block; height: 100%; }}

        /* ---------- chips, badges and card grids ---------- */
        .chips {{ display: flex; flex-wrap: wrap; gap: .35rem; margin: .1rem 0 .7rem; }}
        .chip {{ display: inline-flex; align-items: center; gap: .3rem;
          font-size: .78rem; font-weight: 600; padding: .22rem .55rem;
          border: var(--line-w) solid var(--line); background: #f2f4f7;
          color: var(--ink); border-radius: 2px; white-space: nowrap; }}
        .chip.good {{ border-color: {STATUS_GOOD}; color: #07610a;
          background: rgba(12,163,12,.10); }}
        .chip.warn {{ border-color: {STATUS_WARN_EDGE}; color: #6b4c00;
          background: rgba(250,178,25,.16); }}
        .chip.bad  {{ border-color: {STATUS_BAD}; color: #8f1f1f;
          background: rgba(208,59,59,.10); }}
        .chip.accent {{ border-color: {ACCENT}; color: {ACCENT};
          background: rgba(31,95,169,.08); }}

        .badge {{ display: inline-flex; align-items: center; justify-content: center;
          width: 76px; height: 76px; border-radius: 50%; color: #ffffff;
          font-size: 2.3rem; font-weight: 700; line-height: 1; flex: none; }}
        .badgerow {{ display: flex; align-items: center; gap: 1rem;
          background: var(--surface); border: var(--line-w) solid var(--line);
          padding: .9rem 1.1rem; margin-bottom: .7rem; }}
        .badgerow .t1 {{ font-size: 1.05rem; font-weight: 700; color: var(--ink);
          line-height: 1.3; }}
        .badgerow .t2 {{ font-size: .82rem; color: var(--muted); margin-top: .2rem; }}
        .badgerow .t3 {{ font-size: .82rem; font-weight: 700; margin-top: .3rem; }}

        .cards {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(232px, 1fr));
          gap: .5rem; margin-bottom: .6rem; }}
        .speccard {{ border: var(--line-w) solid var(--line); background: var(--surface);
          padding: .55rem .65rem; border-left-width: 4px; }}
        .speccard .nm {{ font-size: .78rem; font-weight: 600; line-height: 1.3;
          color: var(--ink); height: 2.6em; overflow: hidden; }}
        .speccard .rw {{ display: flex; align-items: baseline; justify-content: space-between;
          margin-top: .35rem; }}
        .speccard .vd {{ font-size: .74rem; font-weight: 700; }}
        .speccard .pr {{ font-size: .86rem; font-weight: 700; color: var(--ink); }}

        /* ---------- sidebar navigation ---------- */
        .navtitle {{ font-size: .72rem; text-transform: uppercase; letter-spacing: .07em;
          color: var(--muted); font-weight: 700; margin: .1rem 0 .3rem; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] {{ gap: 0; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label {{
          width: 100%; padding: .42rem .55rem; margin: 0;
          border-left: 3px solid transparent; border-bottom: 1px solid var(--line); }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:hover {{
          background: #eef2f7; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label p {{
          font-size: .86rem; font-weight: 600; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) {{
          background: rgba(31,95,169,.10); border-left-color: {ACCENT}; }}
        section[data-testid="stSidebar"] div[role="radiogroup"] > label:has(input:checked) p {{
          color: {ACCENT}; }}

        /* ---------- keyboard focus, deliberately loud ---------- */
        a:focus-visible, button:focus-visible, input:focus-visible,
        select:focus-visible, textarea:focus-visible, summary:focus-visible,
        [role="tab"]:focus-visible, [role="radio"]:focus-visible,
        [role="button"]:focus-visible, [data-baseweb="select"]:focus-within,
        div[role="slider"]:focus-visible {{
          outline: 3px solid #b34700 !important; outline-offset: 2px !important;
        }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def utility_bar() -> None:
    """Skip link, text sizing, contrast and language. Rendered above the masthead."""
    st.markdown(
        f'<a class="skiplink" href="#main-content">{tr("skip")}</a>',
        unsafe_allow_html=True,
    )
    label_col, buttons, contrast_col, lang_col = st.columns(
        [0.9, 1.5, 1.5, 2.1], vertical_alignment="center")

    label_col.markdown(f'<span class="caveat"><strong>{tr("text_size")}</strong></span>',
                       unsafe_allow_html=True)
    a1, a2, a3 = buttons.columns(3)
    for column, size in ((a1, "A-"), (a2, "A"), (a3, "A+")):
        if column.button(size, key=f"scale_{size}",
                         help=f'{tr("text_size")}: {size}', width="stretch"):
            st.session_state["ui_scale"] = size
            st.rerun()

    contrast_col.toggle(tr("contrast"), key="ui_contrast")

    codes = list(LANGUAGES)
    lang_col.radio(
        tr("language"), codes,
        index=codes.index(st.session_state.get("ui_lang", "en")),
        format_func=lambda c: LANGUAGES[c],
        horizontal=True, key="ui_lang", label_visibility="collapsed",
    )


def masthead() -> None:
    """Portal name, a neutral wordmark, and the tricolour rule."""
    st.markdown(
        '<div class="masthead">'
        '<table style="border:none;width:100%"><tr style="border:none">'
        '<td style="border:none;width:58px;vertical-align:middle">'
        '<div class="wordmark">IS</div></td>'
        '<td style="border:none;vertical-align:middle">'
        f'<h1>{tr("portal")}</h1>'
        f'<p class="sub">{tr("portal_sub")}</p>'
        '</td></tr></table></div>'
        '<div class="tricolour">'
        f'<i style="background:{SAFFRON}"></i>'
        '<i style="background:#ffffff"></i>'
        f'<i style="background:{INDIA_GREEN}"></i>'
        '</div>',
        unsafe_allow_html=True,
    )


def breadcrumb(section_key: str) -> None:
    """Home > Section, rendered at the top of each tab so it always matches."""
    st.markdown(
        f'<div id="main-content" class="breadcrumb">{tr("home")} &rsaquo; '
        f'<b>{tr(section_key)}</b></div>',
        unsafe_allow_html=True,
    )


def chip(text: str, tone: str = "") -> str:
    """A small labelled tag. `tone` is good / warn / bad / accent, or empty."""
    return f'<span class="chip {tone}">{text}</span>'


def chip_row(chips: list) -> str:
    return '<div class="chips">' + "".join(chips) + '</div>'


def grade_badge(letter: str, title: str, subtitle: str, verdict: str,
                passes: bool, marginal: bool = False) -> str:
    """The hero verdict: one letter, and the words that must accompany it.

    The glyph and the word carry the verdict; the colour only reinforces it.
    """
    colour = status_colour(passes, marginal)
    glyph = GLYPH_PASS if passes else GLYPH_FAIL
    return (
        f'<div class="badgerow"><div class="badge" style="background:{colour}">'
        f'{letter}</div><div><div class="t1">{title}</div>'
        f'<div class="t2">{subtitle}</div>'
        f'<div class="t3" style="color:{colour}">{glyph} {verdict}</div></div></div>'
    )


def spec_card(name: str, passes: bool, letter: str, price: str,
              marginal: bool = False) -> str:
    colour = status_colour(passes, marginal)
    glyph = GLYPH_PASS if passes else GLYPH_FAIL
    word = "PASS" if passes else "FAIL"
    return (
        f'<div class="speccard" style="border-left-color:{colour}">'
        f'<div class="nm">{name}</div><div class="rw">'
        f'<span class="vd" style="color:{colour}">{glyph} {word} &middot; {letter}</span>'
        f'<span class="pr">{price}</span></div></div>'
    )


def card_grid(cards: list) -> str:
    return '<div class="cards">' + "".join(cards) + '</div>'


def stat_block(label: str, value: str, sub: str = "", bad: bool = False,
               meter: float | None = None, meter_label: str = "",
               meter_tone: str = "accent") -> str:
    """A flat stat. `meter` draws a 0-100 mini-bar under the number.

    The mini-bar replaces a sub-caption that merely restated the label: it shows
    the number's share of its own whole, which the label never could.
    """
    parts = [f'<div class="stat"><div class="lab">{label}</div>'
             f'<div class="val">{value}</div>']
    if meter is not None:
        colour = {"good": STATUS_GOOD, "warn": STATUS_WARN,
                  "bad": STATUS_BAD}.get(meter_tone, ACCENT)
        width = max(0.0, min(100.0, float(meter)))
        parts.append(f'<div class="meter"><i style="width:{width:.1f}%;'
                     f'background:{colour}"></i></div>')
        if meter_label:
            parts.append(f'<div class="sub{" bad" if meter_tone == "bad" else ""}">'
                         f'{meter_label}</div>')
    elif sub:
        parts.append(f'<div class="sub{" bad" if bad else ""}">{sub}</div>')
    parts.append("</div>")
    return "".join(parts)


def stat_row(blocks: list, columns: int) -> None:
    st.markdown(
        f'<div class="stats" style="grid-template-columns:repeat({columns},1fr)">'
        + "".join(blocks) + "</div>",
        unsafe_allow_html=True,
    )
