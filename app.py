from datetime import datetime
from zoneinfo import ZoneInfo

import gspread
import streamlit as st
from google.oauth2.service_account import Credentials

from dashboard_logic import LINK_MAP, attach_links, parse, render

# ====== PENGATURAN ======
SHEET_ID = "1qMNpvZnB_0TP8tpt8UYkTpRyKQSsjpF529x8FNQbqkw"      # SUMMARY DASHBOARD TOWER
SRC_ID = "1-mvPESb3Q69Mkvyrle4pVwtFL0SSZ4vWTdkXTVR8sXk"        # MONITORING CME (data asli)
WORKSHEET = "Power & CME"   # nama tab yang dibaca (harus sama persis dengan nama tab di Google Sheet)
REFRESH_SECONDS = 60          # interval auto-update
TIMEZONE = "Asia/Jakarta"
# Warna (ubah sesuai selera)
BG, OK, BAD, NA_BG = "#ffffff", "#16a34a", "#ef4444", "#d1d5db"
TITLE = "Monitoring Issue Power & CME"
HIGHLIGHT = "#fde047"  # warna highlight judul
# ========================

# Semua (spreadsheet, tab/gid) yang perlu dibaca untuk membuat link
SOURCE_TABS = list({(c.get("sid", SRC_ID), c["tab"]) for c in LINK_MAP.values()})

st.set_page_config(page_title=TITLE, layout="wide", initial_sidebar_state="collapsed")

st.markdown(f"""<style>
:root{{--f:clamp(11px,.62vw,18px)}}
.stApp{{background:{BG}}}
header[data-testid="stHeader"],footer,#MainMenu,[data-testid="stToolbar"]{{display:none}}
.block-container{{padding:12px 16px 0 16px;max-width:100%;font-size:var(--f)}}
.ttl{{display:inline-block;margin:0;font-size:calc(var(--f)*1.8);font-weight:700;line-height:1.2;background:{HIGHLIGHT};color:#1f2937;padding:.15em .7em;border-radius:.3em}}
.top{{display:flex;justify-content:flex-end;gap:.5em;flex-wrap:wrap}}
.bd{{color:#fff;font-weight:600;font-size:var(--f);padding:.45em .9em;border-radius:.3em}}
.gr{{display:grid;grid-template-columns:repeat(auto-fit,minmax(calc(50*var(--f)),1fr));gap:20px;align-items:start;overflow-x:auto}}
table.ms{{border-collapse:collapse;width:100%;font-size:var(--f);margin:0}}
table.ms th{{color:#1f2937;font-size:.92em;text-align:center;padding:.2em .1em;white-space:nowrap;border:0;background:transparent}}
table.ms td{{color:#1f2937;padding:.2em .1em;text-align:center;white-space:nowrap;border:0;border-bottom:1px solid #e5e7eb;vertical-align:middle}}
table.ms th:nth-child(-n+2),table.ms td:nth-child(-n+2){{text-align:left}}
table.ms td:nth-child(1){{color:#6b7280;padding-right:.4em}}
.p{{display:inline-block;min-width:3em;padding:.08em .45em;border-radius:1em;color:#fff;font-weight:600;font-size:.92em;background:{OK}}}
.p.y{{background:#eab308;color:#1f2937}}.p.o{{background:#f97316}}.p.r{{background:{BAD};animation:blink 1.2s ease-in-out infinite}}
@keyframes blink{{0%,100%{{opacity:1;box-shadow:0 0 .2em rgba(239,68,68,.5)}}50%{{opacity:.7;box-shadow:0 0 .9em .25em rgba(239,68,68,.95)}}}}.p.n{{background:{NA_BG};color:#6b7280}}
a.p{{text-decoration:none!important;color:#fff!important;cursor:pointer}}
a.p.y{{color:#1f2937!important}}a.p.n{{color:#6b7280!important}}
a.p:hover{{filter:brightness(.88);box-shadow:0 0 0 .15em rgba(0,0,0,.15)}}
.lg{{display:flex;gap:1.2em;color:#6b7280;font-size:.92em;align-items:center;flex-wrap:wrap;margin-top:.5em}}
.lg i{{display:inline-block;width:.8em;height:.8em;margin-right:.3em}}
</style>""", unsafe_allow_html=True)


def client():
    creds = Credentials.from_service_account_info(
        dict(st.secrets["gcp_service_account"]),
        scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    return gspread.authorize(creds)


@st.cache_data(ttl=30, show_spinner=False)
def load_values():
    ws = client().open_by_key(SHEET_ID).worksheet(WORKSHEET)
    return ws.get_all_values()


@st.cache_data(ttl=120, show_spinner=False)
def load_sources():
    """Baca semua tab sumber. Return (data, daftar sumber yang gagal dibuka)."""
    gc = client()
    out, books, miss = {}, {}, []
    for sid, ref in SOURCE_TABS:
        try:
            if sid not in books:
                books[sid] = gc.open_by_key(sid)
            if isinstance(ref, int):          # ref = gid tab
                ws = next((w for w in books[sid].worksheets() if w.id == ref), None)
                if ws is None:
                    raise gspread.WorksheetNotFound(str(ref))
            else:                             # ref = nama tab
                ws = books[sid].worksheet(ref)
        except Exception:
            miss.append(f"{sid[:8]}… / {ref}")
            continue
        out[(sid, ref)] = {"values": ws.get_all_values(), "gid": ws.id}
    return out, miss


LABELS = {"Semua": "all", "Normal": "ok", "Warning/Critical": "bad"}


@st.fragment(run_every=REFRESH_SECONDS)
def dashboard():
    err = None
    try:
        sites = parse(load_values())
        try:
            src, miss = load_sources()
            attach_links(sites, SRC_ID, src)
            if miss:
                st.warning("Sumber ini belum bisa dibuka (cek share ke service account, "
                           "atau nama tab/gid): " + "; ".join(miss))
        except Exception as e:  # dashboard tetap tampil, hanya tanpa link
            st.warning(f"Link ke data asal tidak tersedia: {type(e).__name__}: {e}")
        st.session_state["last_sites"] = sites
        st.session_state["last_time"] = datetime.now(ZoneInfo(TIMEZONE))
    except Exception as e:  # tampilkan data terakhir jika ada
        sites, err = st.session_state.get("last_sites"), e
    if err:
        st.error(f"Gagal membaca Google Sheet: {err}")
    if not sites:
        return
    cnt = lambda k: sum(1 for s in sites if s["status"] == k)
    left, right = st.columns([1, 1.6])
    left.markdown(f"<div class='ttl'>{TITLE.replace('&', '&amp;')}</div>", unsafe_allow_html=True)
    right.markdown(
        f"<div class='top'><span class='bd' style='background:#1e3a8a'>Total Monitored: {len(sites)} Site</span>"
        f"<span class='bd' style='background:{OK}'>Normal Sites: {cnt('ok')} Site</span>"
        f"<span class='bd' style='background:{BAD}'>Warning/Critical: {cnt('bad')} Site</span>"
        "</div>",
        unsafe_allow_html=True)
    pick = st.session_state.get("flt", "Semua")
    st.markdown(render(sites, LABELS[pick]), unsafe_allow_html=True)
    t = st.session_state.get("last_time")
    stamp = f"Diperbarui otomatis tiap {REFRESH_SECONDS} detik · terakhir {t:%H:%M:%S}" if t else ""
    st.markdown(
        f"<div class='lg'><span><i style='background:{OK}'></i>Normal</span>"
        f"<span><i style='background:#eab308'></i>Kuning ≤25%</span>"
        f"<span><i style='background:#f97316'></i>Orange ≤50%</span>"
        f"<span><i style='background:{BAD}'></i>Warning/Critical (klik untuk buka data asal)</span>"
        f"<span><i style='background:{NA_BG}'></i>N/A / NY</span>"
        f"<span style='margin-left:auto'>{stamp}</span></div>",
        unsafe_allow_html=True)


# Filter ada di sidebar (panah kecil kiri atas); sidebar tidak boleh dipanggil dari dalam fragment
st.sidebar.radio("Filter site", list(LABELS), key="flt")
dashboard()
