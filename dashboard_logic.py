"""Logika parsing sheet + render HTML (tanpa dependensi Streamlit, mudah diuji)."""
import html
import re

NA = ("-", 2)  # (teks, status) status: 0 normal, 1 merah, 2 N/A, 3 kuning, 4 oranye
COLS = ["Battery", "MPPT", "HFSM", "Rectifier", "Genset(h)", "Longsor",
        "Ground(Ω)", "Vertical", "Hammer", "Tower", "CCTV", "AC"]
# Kunci kolom sheet untuk tiap bubble, urutannya sama dengan COLS
CELL_KEYS = ["bat", "mppt", "hfsm", "rect", "genset", "longsor",
             "ground", "vert", "hammer", "tower", "cctv", "ac"]

VERT_TOLERANSI = 10  # toleransi absolut di atas limit vertikal: hasil <= limit + 10 masih hijau

# Skala warna (rendah 1-25%, sedang 26-50%, tinggi 51-100%) dari persen terhadap INSTALLED
SKALA_UNMON = (0, 3, 4)    # hijau, kuning, oranye
SKALA_FAULTY = (3, 4, 1)   # kuning, oranye, merah

# Bubble dengan status ini bisa diklik -> buka sel di spreadsheet sumber.
# 1 = merah. Tambah 4 (oranye), 3 (kuning), atau 0 (hijau) kalau mau ikut bisa diklik.
LINK_STATUS = (1,)

# Peta bubble -> data asli di spreadsheet MONITORING CME.
#   tab   : nama tab sumber
#   key   : header kolom nama site di tab itu
#   col   : header kolom nilai yang dituju (cocok persis, atau diawali teks ini)
#   after : (opsional) header jangkar; kolom nilai = kolom tepat setelah jangkar
# Bubble yang tidak ada di sini (Battery, MPPT, HFSM, Rectifier, Genset, CCTV)
# belum punya sumber -> tidak jadi link.
LINK_MAP = {
    "longsor": dict(tab="MONITORING CME", key="DESCRIPTION SITE", col="STATUS LONGSOR"),
    "ground": dict(tab="MONITORING GROUNDING", key="DESCRIPTION SITE", col="RESULT"),
    "vert": dict(tab="MONITORING VERTICALITY", key="DESCRIPTION SITE", col="HASIL VERTICALITY"),
    "hammer": dict(tab="MONITORING HAMMER TEST", key="DESCRIPTION SITE", col="MUTU BETON"),
    "tower": dict(tab="MONITORING CME", key="DESCRIPTION SITE", col="STATUS",
                  after="STATUS INSTALASI"),
    "ac": dict(tab="MONITORING AC", key="SITE NAME", col="STATUS AC"),
}


def nums(s):
    v = re.findall(r"\d+(?:\.\d+)?", s or "")
    return [float(x) for x in v] if v else None


def num(s):
    try:
        return float(str(s).strip().replace(",", "."))
    except ValueError:
        return None


def col_letter(j):
    """Index kolom 0-based -> huruf kolom Excel/Sheets (0 -> A, 26 -> AA)."""
    s, j = "", j + 1
    while j:
        j, r = divmod(j - 1, 26)
        s = chr(65 + r) + s
    return s


def triple(raw):
    """Format terpasang/un-mon/(faulty): merah jika un-mon atau faulty > 0."""
    n = nums(raw)
    if not n:
        return NA
    return (re.sub(r"\s+", "", raw), 1 if any(x > 0 for x in n[1:]) else 0)


def battery_pack(raw):
    """Untuk kolom Battery, MPPT, HFSM, Rectifier.
    Format 'INSTALLED/UNMON/FAULTY', contoh '8/1/1' atau '8/0/0'.
    Persen unmon dan faulty dihitung dari INSTALLED, masing-masing punya skala warna sendiri,
    lalu warna sel = yang terparah.
    Kode warna: 0 = hijau; 3 = kuning; 4 = oranye; 1 = merah.
    - UNMON : 1-25% hijau, 26-50% kuning, 51-100% oranye
    - FAULTY: 1-25% kuning, 26-50% oranye, 51-100% merah
    - unmon = 0 dan faulty = 0 -> hijau"""
    n = nums(raw)
    if not n or len(n) < 2:
        return NA
    inst, unmon, faulty = (n + [0])[:3]
    txt = re.sub(r"\s+", "", raw)
    if inst <= 0 and unmon <= 0 and faulty <= 0:
        return NA

    def level(x, skala):
        if x <= 0:
            return 0
        if inst <= 0:                # ada unmon/faulty tapi installed 0 -> level tertinggi
            return skala[2]
        if x * 4 <= inst:            # 1% - 25%
            return skala[0]
        if x * 2 <= inst:            # 26% - 50%
            return skala[1]
        return skala[2]              # 51% - 100%

    urutan = {0: 0, 3: 1, 4: 2, 1: 3}   # hijau < kuning < oranye < merah
    warna = max(level(unmon, SKALA_UNMON), level(faulty, SKALA_FAULTY), key=lambda s: urutan[s])
    return (txt, warna)


def cells(d):
    out = [battery_pack(d["bat"]), battery_pack(d["mppt"]),
           battery_pack(d["hfsm"]), battery_pack(d["rect"])]
    gh = num(d["genset"])
    out.append(NA if gh is None else (f"{gh:g}", 1 if gh > 20 else 0))
    ls = d["longsor"].upper()
    if "SANGAT" in ls:
        out.append(("Sangat", 1))
    elif "TIDAK" in ls:
        out.append(("Aman", 0))
    elif "RAWAN" in ls:
        out.append(("Rawan", 3))
    else:
        out.append(NA)
    gd = num(d["ground"])
    out.append(NA if gd is None else (f"{gd:g}", 1 if gd >= 1 else 0))
    v = nums(d["vert"])
    if v and len(v) >= 2:
        # format limit/result: result <= limit + toleransi -> hijau, selebihnya merah
        limit, hasil = v[0], v[1]
        batas_aman = limit + VERT_TOLERANSI
        out.append((f"{limit:g}/{hasil:g}", 1 if hasil > batas_aman else 0))
    else:
        out.append(NA)
    hm = num(d["hammer"])
    out.append(NA if hm is None else (f"{hm:g}", 0 if hm >= 200 else 3 if hm >= 150 else 4 if hm >= 100 else 1))  # K-200
    tw = d["tower"].upper()
    out.append(("OK", 0) if tw == "OK" else ("Minor", 3) if tw == "MINOR" else ("Major", 1) if tw == "MAJOR" else NA)
    out.append(triple(d["cctv"]))
    out.append(("OK", 0) if d["ac"].upper() == "OK" else NA)
    return out


def parse(values):
    """values = list of baris (list of string) dari sheet pertama."""
    hdr = next((i for i, r in enumerate(values)
                if any(c.strip().upper() == "SITE NAME" for c in r)), None)
    if hdr is None:
        raise ValueError("Header 'SITE NAME' tidak ditemukan di sheet pertama.")
    h = [c.strip().upper() for c in values[hdr]]

    def ix(key, exact=False):
        for i, c in enumerate(h):
            if (c == key) if exact else (key in c):
                return i
        return -1

    col = {"no": ix("NO", True), "site": ix("SITE NAME"), "reg": ix("REGIONAL"),
           "bat": ix("BATTERY"), "mppt": ix("MPPT"), "hfsm": ix("HFSM"),
           "rect": ix("RECTIFIER"), "genset": ix("GENSET"), "longsor": ix("LONGSOR"),
           "ground": ix("GROUNDING"), "vert": ix("VERTICALITY"), "hammer": ix("HAMMER"),
           "tower": ix("KELENGKAPAN"), "cctv": ix("CCTV"),
           "ac": next((i for i, c in enumerate(h) if c.endswith("STATUS AC")), -1)}
    sites = []
    for r in values[hdr + 1:]:
        d = {k: (r[i].strip() if 0 <= i < len(r) else "") for k, i in col.items()}
        if not d["site"] or not d["no"].isdigit():
            continue
        c = cells(d)
        live = [x for x in c if x[1] != 2]
        d["cells"] = c
        d["links"] = [None] * len(COLS)   # diisi attach_links()
        # Status site hanya dari warna: ada sel merah (1) -> Warning/Critical.
        # Oranye (4) dan kuning (3) tidak dihitung.
        d["status"] = "off" if not live else "bad" if any(x[1] == 1 for x in live) else "ok"
        sites.append(d)
    return sites


def _norm(s):
    return " ".join(str(s).upper().split())


def _canon(name):
    """Samakan penulisan nama site antar-sheet (huruf besar, spasi, ejaan Kobagma/Kobakma)."""
    return _norm(name).replace("KOBAKMA", "KOBAGMA")


def _locate(values, key_hdr, col_hdr, after=None):
    """Cari baris header di tab sumber. Return (index kolom nilai, {nama site: nomor baris})."""
    for r, row in enumerate(values):
        h = [_norm(c) for c in row]
        if key_hdr not in h:
            continue
        kc = h.index(key_hdr)
        if after:
            if after not in h:
                return None
            cc = h.index(after) + 1
            if cc >= len(h) or h[cc] != col_hdr:
                return None
        else:
            cc = next((i for i, c in enumerate(h) if c == col_hdr), None)
            if cc is None:
                cc = next((i for i, c in enumerate(h) if c.startswith(col_hdr)), None)
            if cc is None:
                return None
        rows = {}
        for j in range(r + 1, len(values)):
            v = values[j]
            if kc < len(v) and v[kc].strip():
                rows.setdefault(_canon(v[kc]), j + 1)   # nomor baris sheet = index + 1
        return cc, rows
    return None


def attach_links(sites, src_id, src):
    """Isi s['links'] (URL ke sel di spreadsheet sumber) untuk tiap bubble.
    src = {nama_tab: {"values": [...], "gid": int}} dari spreadsheet MONITORING CME."""
    located = {}
    for k, cfg in LINK_MAP.items():
        t = src.get(cfg["tab"])
        if t:
            located[k] = (_locate(t["values"], cfg["key"], cfg["col"], cfg.get("after")), t["gid"])
    for s in sites:
        links = []
        for k in CELL_KEYS:
            url = None
            loc = located.get(k)
            if loc and loc[0]:
                (cc, rows), gid = loc
                r = rows.get(_canon(s["site"]))
                if r:
                    url = (f"https://docs.google.com/spreadsheets/d/{src_id}/edit"
                           f"?gid={gid}#gid={gid}&range={col_letter(cc)}{r}")
            links.append(url)
        s["links"] = links


def bubble(s, i, t, st):
    """Satu bubble. Jika statusnya ada di LINK_STATUS dan link sumber ada -> jadi link."""
    cls = ('', 'r', 'n', 'y', 'o')[st]
    txt = html.escape(str(t))
    url = s["links"][i] if s.get("links") else None
    if url and st in LINK_STATUS:
        return (f"<a class=\"p {cls}\" href=\"{html.escape(url)}\" "
                f"target=\"_blank\" rel=\"noopener\" "
                f"title=\"{COLS[i]} - klik untuk buka data asal\">{txt}</a>")
    return f"<span class=\"p {cls}\" title=\"{COLS[i]}\">{txt}</span>"


def render(sites, flt="all", per_block=None):
    """Kembalikan HTML tabel 3 blok. flt: all | ok | bad | off."""
    rows = [s for s in sites if flt == "all" or s["status"] == flt]
    n = per_block or max(1, -(-len(rows) // 3))
    blocks = []
    for k in range(3):
        part = rows[k * n:(k + 1) * n]
        if not part:
            break
        head = "<th>No</th><th>Site</th>" + "".join(f"<th>{x}</th>" for x in COLS)
        body = "".join(
            f"<tr><td>{html.escape(s['no'])}</td>"
            f"<td title=\"{html.escape(s['reg'])}\">{html.escape(s['site'])}</td>"
            + "".join(f"<td>{bubble(s, i, t, st)}</td>"
                      for i, (t, st) in enumerate(s["cells"]))
            + "</tr>" for s in part)
        blocks.append(f"<table class=\"ms\"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>")
    return "<div class=\"gr\">" + "".join(blocks) + "</div>"
