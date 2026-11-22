# generar_db.py
# -*- coding: utf-8 -*-
import os
import re
import json
import sqlite3
import unicodedata
from collections import defaultdict

DB_FILE = "diccionari.db"


def normalitzar_text(text: str) -> str:
    if not isinstance(text, str):
        return ""
    nfkd = unicodedata.normalize('NFKD', text.strip())
    net = "".join(c for c in nfkd if not unicodedata.combining(c))
    return (
        net.lower()
        .replace('v', 'u')
        .replace('j', 'i')
        .replace('˘', '')
        .replace('̯', '')
        .replace('*', '')
        .strip()
    )


def reconstruir_lema_whitaker(stems, pos_info):
    s1 = stems[0]
    pos = pos_info[:5].strip()
    rest = pos_info[5:].split()
    if pos == 'N':
        decl = rest[0] if len(rest) > 0 else '1'
        var = rest[1] if len(rest) > 1 else '1'
        gen = rest[2] if len(rest) > 2 else 'C'
        if decl == '1': return s1 + 'a'
        elif decl == '2': return s1 + 'um' if (gen == 'N' or var == '2') else (s1 if s1.endswith(('er', 'ir')) else s1 + 'us')
        elif decl in ['3', '9']: return s1
        elif decl == '4': return s1 + ('u' if gen == 'N' else 'us')
        elif decl == '5': return s1 + 'es'
    elif pos == 'V':
        conj = rest[0] if len(rest) > 0 else '1'
        if conj == '1': return s1 + 'o'
        elif conj == '2': return s1 + 'eo'
        elif conj == '4': return s1 + 'io'
        return s1 + 'o'
    elif pos == 'ADJ':
        decl = rest[0] if len(rest) > 0 else '1'
        if decl == '1': return s1 if s1.endswith('er') else s1 + 'us'
        elif decl == '3': return s1 if s1.endswith(('is', 'x', 's')) else s1 + 'is'
    return s1


def format_ls_json_html(entry):
    orth = entry.get("title_orthography") or entry.get("key", "")
    gen = entry.get("title_genitive")
    gender = entry.get("gender")
    pos = entry.get("part_of_speech")
    notes = entry.get("main_notes")
    senses = entry.get("senses", [])

    html = (
        "<div style='font-family: Georgia, serif; font-size: 14.5px; line-height: 1.6; color: #212529; padding: 14px; background: #ffffff; border-radius: 6px; margin-bottom: 20px; border: 1px solid #e9ecef;'>"
        "<div style='border-bottom: 2px solid #0d6efd; padding-bottom: 6px; margin-bottom: 12px;'>"
        f"<span style='font-size: 22px; font-weight: bold; color: #0d6efd;'>{orth}</span>"
    )
    if gen: html += f" <span style='font-size: 15px; font-style: italic; color: #495057;'>({gen})</span>"
    if gender: html += f" <span style='font-size: 13px; font-weight: bold; color: #6c757d;'>[{gender}]</span>"
    if pos: html += f" <span style='background: #e7f1ff; color: #0a58ca; padding: 2px 7px; border-radius: 4px; font-size: 12px; font-weight: 600; margin-left: 6px;'>{pos}</span>"
    html += "</div>"
    if notes: html += f"<p style='color: #495057; font-size: 13.5px; margin: 6px 0 12px 0;'>{notes}</p>"

    def render_s(sl):
        res = "<ul style='list-style-type: none; padding-left: 14px; margin: 4px 0;'>"
        for s in sl:
            if isinstance(s, str):
                s_fmt = re.sub(r'([A-Z]\.|\b[IVXLCDM]+\.|\b\d+\.)', r'<b style="color: #0d6efd;">\1</b>', s)
                res += f"<li style='margin-bottom: 6px; line-height: 1.55;'>• {s_fmt}</li>"
            elif isinstance(s, list):
                res += f"<li>{render_s(s)}</li>"
        res += "</ul>"
        return res

    if senses:
        html += "<div style='margin-left: 6px;'>" + render_s(senses) + "</div>"
    html += "</div>"
    return html


def principal():
    if os.path.exists(DB_FILE):
        print(f"Eliminant base existent '{DB_FILE}' per regenerar-la...")
        os.remove(DB_FILE)

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()

    # Creació de taules
    cur.execute("""
    CREATE TABLE formes (
        forma TEXT NOT NULL,
        forma_clean TEXT NOT NULL,
        lema TEXT NOT NULL,
        tag TEXT NOT NULL,
        origen TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE glosses (
        clau_clean TEXT NOT NULL,
        pos TEXT,
        glossa TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE diccionari_ls (
        lema_clean TEXT NOT NULL,
        html TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE variants_hist (
        forma_clean TEXT NOT NULL,
        forma_raw TEXT NOT NULL,
        lema_canonic TEXT NOT NULL,
        origen TEXT NOT NULL,
        detalls TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE families (
        lema_clean TEXT PRIMARY KEY,
        derivats TEXT NOT NULL
    );
    """)

    # 1. Carrega de formes escolars (lat, lat.segmentations, lat.closed, lat.user)
    print("1/5. Indexant formari escolar (lat, lat.segmentations, lat.closed, lat.user)...")
    fitxers_escolars = [
        ("lat", "unimorph"),
        ("lat.segmentations", "segmentations"),
        ("lat.closed", "closed"),
        ("lat.user", "user")
    ]
    rows_formes = []
    for fn, origen in fitxers_escolars:
        if os.path.exists(fn):
            with open(fn, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    camps = line.strip().split("\t")
                    if len(camps) >= 3:
                        lema, forma, tag = camps[0].strip(), camps[1].strip(), camps[2].strip()
                        rows_formes.append((forma, normalitzar_text(forma), lema, tag, origen))
    cur.executemany("INSERT INTO formes VALUES (?, ?, ?, ?, ?)", rows_formes)
    print(f"   -> {len(rows_formes):,} formes escolars inserides.")

    # 2. Glosses Whitaker
    print("2/5. Indexant glosses breus en anglès (Whitaker)...")
    fn_whit = "DICTLINE_TRADUIT.GEN" if os.path.exists("DICTLINE_TRADUIT.GEN") else (
        "DICTLINE.GEN" if os.path.exists("DICTLINE.GEN") else None
    )
    rows_glosses = []
    if fn_whit:
        with open(fn_whit, "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                camps = line.rstrip("\r\n").split("\t")
                p0 = camps[0]
                en_def = camps[1].strip() if len(camps) >= 2 else (
                    line.split("|", 1)[1].strip() if "|" in line else ""
                )
                if not en_def:
                    continue

                stems = [p0[0:19].strip(), p0[19:38].strip(), p0[38:57].strip(), p0[57:76].strip()]
                pos_info = p0[76:].strip() if len(p0) > 76 else ""
                pos_cat = pos_info[:5].strip()

                lema_rec = reconstruir_lema_whitaker(stems, pos_info)
                clau_rec = normalitzar_text(lema_rec)
                if clau_rec:
                    rows_glosses.append((clau_rec, pos_cat, en_def))
                if stems[0] and stems[0] != "zzz":
                    st1 = normalitzar_text(stems[0])
                    rows_glosses.append((st1, pos_cat, en_def))
        cur.executemany("INSERT INTO glosses VALUES (?, ?, ?)", rows_glosses)
        print(f"   -> {len(rows_glosses):,} glosses inserides.")

    # 3. Lewis & Short (JSON o XML)
    print("3/5. Indexant Lewis & Short...")
    json_files = [f for f in os.listdir(".") if f.startswith("ls_") and f.endswith(".json")]
    count_ls = 0
    if json_files:
        for jf in json_files:
            try:
                with open(jf, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item in data:
                        k_norm = normalitzar_text(re.sub(r'\d+$', '', item.get("key", "")))
                        html_art = format_ls_json_html(item)
                        if k_norm:
                            cur.execute("INSERT INTO diccionari_ls VALUES (?, ?)", (k_norm, html_art))
                            count_ls += 1
            except Exception as e:
                print(f"   Avís llegint {jf}: {e}")
        print(f"   -> {count_ls:,} entrades inserides des dels JSON.")
    elif os.path.exists("lat.ls.perseus-eng2.xml"):
        # Fallback si no hi ha JSONs
        print("   (Parsejant XML de Perseus...)")
        # El diccionari es podrà consultar via XML directament

    # 4. Variants històriques i medievals (analysis.tsv i forms.csv)
    print("4/5. Indexant variants històriques (Lemlat i PrinParLat)...")
    rows_hist = []
    if os.path.exists("analysis.tsv"):
        with open("analysis.tsv", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                p = line.strip().split("\t")
                if len(p) >= 3:
                    f_raw, l_can = p[0], p[2]
                    cat = p[3] if len(p) > 3 else ""
                    rows_hist.append((normalitzar_text(f_raw), f_raw, l_can, "Lemlat medieval", cat))

    if os.path.exists("lexemes.csv") and os.path.exists("forms.csv"):
        lex_map = {}
        with open("lexemes.csv", "r", encoding="utf-8", errors="ignore") as f:
            next(f)
            for line in f:
                c = line.strip().split(",")
                if len(c) >= 2: lex_map[c[0]] = c[1]

        with open("forms.csv", "r", encoding="utf-8", errors="ignore") as f:
            next(f)
            for line in f:
                c = line.strip().split(",")
                if len(c) >= 5:
                    lex_id, cell, orth, analysed = c[1], c[2], c[3], c[4]
                    l_can = lex_map.get(lex_id, "")
                    if l_can and orth:
                        det = f"{cell} | seg: {analysed}" if analysed != "nan" else cell
                        rows_hist.append((normalitzar_text(orth), orth, l_can, "PrinParLat arcaic", det))

    cur.executemany("INSERT INTO variants_hist VALUES (?, ?, ?, ?, ?)", rows_hist)
    print(f"   -> {len(rows_hist):,} variants històriques inserides.")

    # 5. Famílies lèxiques (dGroups.tsv)
    print("5/5. Indexant famílies de derivats (dGroups.tsv)...")
    count_fam = 0
    if os.path.exists("dGroups.tsv"):
        with open("dGroups.tsv", "r", encoding="utf-8", errors="ignore") as f:
            for line in f:
                p = line.strip().split("\t")
                if len(p) >= 6:
                    lema_d = normalitzar_text(p[0].replace('"', '').split('/')[0])
                    derivats = p[5].strip()
                    if lema_d and derivats:
                        cur.execute("INSERT OR REPLACE INTO families VALUES (?, ?)", (lema_d, derivats))
                        count_fam += 1
        print(f"   -> {count_fam:,} famílies de paraules inserides.")

    # 6. Creació dels índexs de cerca ultra-ràpida
    print("Creant índexs B-Tree per a cerca instantània...")
    cur.execute("CREATE INDEX idx_formes_clean ON formes(forma_clean);")
    cur.execute("CREATE INDEX idx_formes_lema ON formes(lema);")
    cur.execute("CREATE INDEX idx_glosses_clau ON glosses(clau_clean);")
    cur.execute("CREATE INDEX idx_ls_clean ON diccionari_ls(lema_clean);")
    cur.execute("CREATE INDEX idx_variants_clean ON variants_hist(forma_clean);")

    conn.commit()
    conn.close()
    mida_mb = os.path.getsize(DB_FILE) / (1024 * 1024)
    print(f"\n✓ Base de dades '{DB_FILE}' generada correctament ({mida_mb:.2f} MB).")


if __name__ == "__main__":
    principal()
