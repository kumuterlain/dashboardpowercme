"""Logika parsing sheet + render HTML (tanpa dependensi Streamlit, mudah diuji)."""
import html
import re

NA = ("-", 2)  # (teks, status) status: 0 normal, 1 merah, 2 N/A, 3 kuning, 4 oranye
COLS = ["Battery", "MPPT", "HFSM", "Rectifier", "Genset(h)", "Longsor",
        "Ground(Ω)", "Vertical", "Hammer", "Tower", "CCTV", "AC"]

VERT_TOLERANSI = 10  # toleransi absolut di atas limit vertikal: hasil <= limit + 10 masih hijau


def nums(s):
    v = re.findall(r"\d+(?:\.\d+)?", s or "")
    return [float(x) for x in v] if v else None


def num(s):
    try:
        return float(str(s).strip().replace(",", "."))
    except ValueError:
        return None


def triple(raw):
    """Format terpasang/un-mon/(faulty): merah jika un-mon atau faulty > 0."""
    n = nums(raw)
    if not n:
        return NA
    return (re.sub(r"\s+", "", raw), 1 if any(x > 0 for x in n[1:]) else 0)


def battery_pack(raw):
    """Untuk kolom Battery, MPPT, HFSM, Rectifier.
    Format 'INSTALLED/UNMON/FAULTY', contoh '8/1/1' atau '8/0/0'.
    Persen unmon dan faulty dihitung dari INSTALLED, lalu dipilih yang terparah.
    0 = hijau; 3 = kuning; 4 = oranye; 1 = merah.
    - 1-25%   -> kuning
    - 26-50%  -> oranye
    - 51-100% -> merah
    - unmon = 0 dan faulty = 0 -> hijau"""
    n = nums(raw)
    if not n or len(n) < 2:
        return NA
    inst, unmon, faulty = (n + [0])[:3]
    txt = re.sub(r"\s+", "", raw)
    if inst <= 0 and unmon <= 0 and faulty <= 0:
        return NA

    def level(x):
        if x <= 0:
            return 0
        if inst <= 0:                # ada unmon/faulty tapi installed 0 -> merah
            return 1
        if x * 4 <= inst:            # 1% - 25%
            return 3
        if x * 2 <= inst:            # 26% - 50%
            return 4
        return 1                     # 51% - 100%

    urutan = {0: 0, 3: 1, 4: 2, 1: 3}   # hijau < kuning < oranye < merah
    warna = max(level(unmon), level(faulty), key=lambda s: urutan[s])
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
    out.append(NA if gd is None else (f"{gd:g}", 1 if gd
