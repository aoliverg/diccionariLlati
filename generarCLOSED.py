# generarCLOSED.py
# -*- coding: utf-8 -*-
import os
import unicodedata
from collections import defaultdict

OUTPUT_FILE = "lat.closed"

def normalitzar(text: str) -> str:
    nfkd = unicodedata.normalize('NFKD', text.strip())
    net = "".join(c for c in nfkd if not unicodedata.combining(c))
    return net.lower().replace('v', 'u').replace('j', 'i').strip()

def declinar_1a_2a(arrel: str, es_er: bool = False, nom_masc: str = "") -> list:
    """Declina adjectius i participis del tipus bonus, -a, -um (3 terminacions)."""
    nm = nom_masc if es_er else arrel + "us"
    vm = nom_masc if es_er else arrel + "e"
    return [
        (nm, "SG;NOM;MASC"), (vm, "SG;VOC;MASC"), (arrel + "um", "SG;ACC;MASC"),
        (arrel + "i", "SG;GEN;MASC"), (arrel + "o", "SG;DAT;MASC"), (arrel + "o", "SG;ABL;MASC"),
        (arrel + "a", "SG;NOM;FEM"), (arrel + "a", "SG;VOC;FEM"), (arrel + "am", "SG;ACC;FEM"),
        (arrel + "ae", "SG;GEN;FEM"), (arrel + "ae", "SG;DAT;FEM"), (arrel + "a", "SG;ABL;FEM"),
        (arrel + "um", "SG;NOM;NEUT"), (arrel + "um", "SG;VOC;NEUT"), (arrel + "um", "SG;ACC;NEUT"),
        (arrel + "i", "SG;GEN;NEUT"), (arrel + "o", "SG;DAT;NEUT"), (arrel + "o", "SG;ABL;NEUT"),
        (arrel + "i", "PL;NOM;MASC"), (arrel + "i", "PL;VOC;MASC"), (arrel + "os", "PL;ACC;MASC"),
        (arrel + "orum", "PL;GEN;MASC"), (arrel + "is", "PL;DAT;MASC"), (arrel + "is", "PL;ABL;MASC"),
        (arrel + "ae", "PL;NOM;FEM"), (arrel + "ae", "PL;VOC;FEM"), (arrel + "as", "PL;ACC;FEM"),
        (arrel + "arum", "PL;GEN;FEM"), (arrel + "is", "PL;DAT;FEM"), (arrel + "is", "PL;ABL;FEM"),
        (arrel + "a", "PL;NOM;NEUT"), (arrel + "a", "PL;VOC;NEUT"), (arrel + "a", "PL;ACC;NEUT"),
        (arrel + "orum", "PL;GEN;NEUT"), (arrel + "is", "PL;DAT;NEUT"), (arrel + "is", "PL;ABL;NEUT"),
    ]

def declinar_participi_present(nom_sg: str, arrel_nt: str) -> list:
    """Declina participis de present (tipus amans, amantis - 3a declinació tema en -i)."""
    return [
        (nom_sg, "SG;NOM;MASC+FEM+NEUT"), (nom_sg, "SG;VOC;MASC+FEM+NEUT"),
        (arrel_nt + "em", "SG;ACC;MASC+FEM"), (nom_sg, "SG;ACC;NEUT"),
        (arrel_nt + "is", "SG;GEN;MASC+FEM+NEUT"), (arrel_nt + "i", "SG;DAT;MASC+FEM+NEUT"),
        (arrel_nt + "e", "SG;ABL;MASC+FEM+NEUT"), (arrel_nt + "i", "SG;ABL;MASC+FEM+NEUT"),
        (arrel_nt + "es", "PL;NOM;MASC+FEM"), (arrel_nt + "ia", "PL;NOM;NEUT"),
        (arrel_nt + "es", "PL;VOC;MASC+FEM"), (arrel_nt + "ia", "PL;VOC;NEUT"),
        (arrel_nt + "es", "PL;ACC;MASC+FEM"), (arrel_nt + "is", "PL;ACC;MASC+FEM"),
        (arrel_nt + "ia", "PL;ACC;NEUT"), (arrel_nt + "ium", "PL;GEN;MASC+FEM+NEUT"),
        (arrel_nt + "ibus", "PL;DAT;MASC+FEM+NEUT"), (arrel_nt + "ibus", "PL;ABL;MASC+FEM+NEUT"),
    ]

def generar_pronoms_i_numerals() -> list:
    """Genera tots els pronoms personals, reflexius, possessius, demostratius, relatius,
    interrogatius, indefinits, compostos (amb -cum, -met, -dem, -que, -cumque) i numerals."""
    entrades = []

    def afegir(lema, pos, llista_formes):
        for forma, morf in llista_formes:
            entrades.append((lema, forma, f"{pos};{morf}"))

    # 1. PRONOMS PERSONALS I REFLEXIU (incloent enclítics -cum, -met i reduplicats)
    afegir("ego", "PRON", [
        ("ego", "SG;NOM"), ("egomet", "SG;NOM"), ("me", "SG;ACC"), ("memet", "SG;ACC"), ("meme", "SG;ACC"),
        ("mei", "SG;GEN"), ("mihi", "SG;DAT"), ("mi", "SG;DAT"), ("me", "SG;ABL"), ("mecum", "SG;ABL"),
        ("nos", "PL;NOM"), ("nosmet", "PL;NOM"), ("nos", "PL;ACC"), ("nostrum", "PL;GEN"), ("nostri", "PL;GEN"),
        ("nobis", "PL;DAT"), ("nobis", "PL;ABL"), ("nobiscum", "PL;ABL")
    ])
    afegir("tu", "PRON", [
        ("tu", "SG;NOM"), ("tute", "SG;NOM"), ("tutemet", "SG;NOM"), ("te", "SG;ACC"), ("temet", "SG;ACC"), ("tete", "SG;ACC"),
        ("tui", "SG;GEN"), ("tibi", "SG;DAT"), ("te", "SG;ABL"), ("tecum", "SG;ABL"),
        ("uos", "PL;NOM"), ("vos", "PL;NOM"), ("uosmet", "PL;NOM"), ("vosmet", "PL;NOM"),
        ("uos", "PL;ACC"), ("vos", "PL;ACC"), ("uestrum", "PL;GEN"), ("vestrum", "PL;GEN"),
        ("uestri", "PL;GEN"), ("vestri", "PL;GEN"), ("uobis", "PL;DAT"), ("vobis", "PL;DAT"),
        ("uobis", "PL;ABL"), ("vobis", "PL;ABL"), ("uobiscum", "PL;ABL"), ("vobiscum", "PL;ABL")
    ])
    afegir("sui", "PRON", [
        ("se", "SG;ACC"), ("sese", "SG;ACC"), ("semet", "SG;ACC"), ("sui", "SG;GEN"), ("sibi", "SG;DAT"),
        ("se", "SG;ABL"), ("sese", "SG;ABL"), ("secum", "SG;ABL"),
        ("se", "PL;ACC"), ("sese", "PL;ACC"), ("sui", "PL;GEN"), ("sibi", "PL;DAT"),
        ("se", "PL;ABL"), ("secum", "PL;ABL")
    ])

    # 2. POSSESSIUS (meus, tuus, suus, noster, uester)
    for lema_p, arrel_p, es_er, nm in [
        ("meus", "me", False, ""), ("tuus", "tu", False, ""), ("suus", "su", False, ""),
        ("noster", "nostr", True, "noster"), ("uester", "uestr", True, "uester"), ("vester", "vestr", True, "vester")
    ]:
        formes_p = declinar_1a_2a(arrel_p, es_er, nm)
        if lema_p == "meus":
            formes_p.append(("mi", "SG;VOC;MASC"))
        afegir(lema_p, "ADJ;PRON", formes_p)

    # 3. DEMOSTRATIUS (hic, iste, ille, is, ipse, idem)
    afegir("hic", "PRON", [
        ("hic", "SG;NOM;MASC"), ("haec", "SG;NOM;FEM"), ("hoc", "SG;NOM;NEUT"),
        ("hunc", "SG;ACC;MASC"), ("hanc", "SG;ACC;FEM"), ("hoc", "SG;ACC;NEUT"),
        ("huius", "SG;GEN;MASC+FEM+NEUT"), ("huic", "SG;DAT;MASC+FEM+NEUT"),
        ("hoc", "SG;ABL;MASC"), ("hac", "SG;ABL;FEM"), ("hoc", "SG;ABL;NEUT"),
        ("hi", "PL;NOM;MASC"), ("hae", "PL;NOM;FEM"), ("haec", "PL;NOM;NEUT"),
        ("hos", "PL;ACC;MASC"), ("has", "PL;ACC;FEM"), ("haec", "PL;ACC;NEUT"),
        ("horum", "PL;GEN;MASC+NEUT"), ("harum", "PL;GEN;FEM"), ("his", "PL;DAT+ABL;MASC+FEM+NEUT")
    ])

    for lema_d, arrel_d, nom_m, nom_n in [
        ("iste", "ist", "iste", "istud"),
        ("ille", "ill", "ille", "illud"),
        ("ipse", "ips", "ipse", "ipsum")
    ]:
        afegir(lema_d, "PRON", [
            (nom_m, "SG;NOM;MASC"), (arrel_d + "a", "SG;NOM;FEM"), (nom_n, "SG;NOM;NEUT"),
            (arrel_d + "um", "SG;ACC;MASC"), (arrel_d + "am", "SG;ACC;FEM"), (nom_n, "SG;ACC;NEUT"),
            (arrel_d + "ius", "SG;GEN;MASC+FEM+NEUT"), (arrel_d + "i", "SG;DAT;MASC+FEM+NEUT"),
            (arrel_d + "o", "SG;ABL;MASC+NEUT"), (arrel_d + "a", "SG;ABL;FEM"),
            (arrel_d + "i", "PL;NOM;MASC"), (arrel_d + "ae", "PL;NOM;FEM"), (arrel_d + "a", "PL;NOM;NEUT"),
            (arrel_d + "os", "PL;ACC;MASC"), (arrel_d + "as", "PL;ACC;FEM"), (arrel_d + "a", "PL;ACC;NEUT"),
            (arrel_d + "orum", "PL;GEN;MASC+NEUT"), (arrel_d + "arum", "PL;GEN;FEM"),
            (arrel_d + "is", "PL;DAT+ABL;MASC+FEM+NEUT")
        ])

    afegir("is", "PRON", [
        ("is", "SG;NOM;MASC"), ("ea", "SG;NOM;FEM"), ("id", "SG;NOM;NEUT"),
        ("eum", "SG;ACC;MASC"), ("eam", "SG;ACC;FEM"), ("id", "SG;ACC;NEUT"),
        ("eius", "SG;GEN;MASC+FEM+NEUT"), ("ei", "SG;DAT;MASC+FEM+NEUT"),
        ("eo", "SG;ABL;MASC+NEUT"), ("ea", "SG;ABL;FEM"),
        ("ei", "PL;NOM;MASC"), ("ii", "PL;NOM;MASC"), ("i", "PL;NOM;MASC"),
        ("eae", "PL;NOM;FEM"), ("ea", "PL;NOM;NEUT"),
        ("eos", "PL;ACC;MASC"), ("eas", "PL;ACC;FEM"), ("ea", "PL;ACC;NEUT"),
        ("eorum", "PL;GEN;MASC+NEUT"), ("earum", "PL;GEN;FEM"),
        ("eis", "PL;DAT+ABL;MASC+FEM+NEUT"), ("iis", "PL;DAT+ABL;MASC+FEM+NEUT"), ("is", "PL;DAT+ABL;MASC+FEM+NEUT")
    ])

    afegir("idem", "PRON", [
        ("idem", "SG;NOM;MASC"), ("eadem", "SG;NOM;FEM"), ("idem", "SG;NOM;NEUT"),
        ("eundem", "SG;ACC;MASC"), ("eandem", "SG;ACC;FEM"), ("idem", "SG;ACC;NEUT"),
        ("eiusdem", "SG;GEN;MASC+FEM+NEUT"), ("eidem", "SG;DAT;MASC+FEM+NEUT"),
        ("eodem", "SG;ABL;MASC+NEUT"), ("eadem", "SG;ABL;FEM"),
        ("eidem", "PL;NOM;MASC"), ("iidem", "PL;NOM;MASC"), ("idem", "PL;NOM;MASC"),
        ("eaedem", "PL;NOM;FEM"), ("eadem", "PL;NOM;NEUT"),
        ("eosdem", "PL;ACC;MASC"), ("easdem", "PL;ACC;FEM"), ("eadem", "PL;ACC;NEUT"),
        ("eorundem", "PL;GEN;MASC+NEUT"), ("earundem", "PL;GEN;FEM"),
        ("eisdem", "PL;DAT+ABL;MASC+FEM+NEUT"), ("iisdem", "PL;DAT+ABL;MASC+FEM+NEUT"), ("isdem", "PL;DAT+ABL;MASC+FEM+NEUT")
    ])

    # 4. RELATIUS, INTERROGATIUS I COMPOSTOS INDEFINITS DE QUI / QUIS
    base_qui = [
        ("qui", "SG;NOM;MASC"), ("quae", "SG;NOM;FEM"), ("quod", "SG;NOM;NEUT"),
        ("quem", "SG;ACC;MASC"), ("quam", "SG;ACC;FEM"), ("quod", "SG;ACC;NEUT"),
        ("cuius", "SG;GEN;MASC+FEM+NEUT"), ("cui", "SG;DAT;MASC+FEM+NEUT"),
        ("quo", "SG;ABL;MASC+NEUT"), ("qua", "SG;ABL;FEM"),
        ("qui", "PL;NOM;MASC"), ("quae", "PL;NOM;FEM"), ("quae", "PL;NOM;NEUT"),
        ("quos", "PL;ACC;MASC"), ("quas", "PL;ACC;FEM"), ("quae", "PL;ACC;NEUT"),
        ("quorum", "PL;GEN;MASC+NEUT"), ("quarum", "PL;GEN;FEM"),
        ("quibus", "PL;DAT+ABL;MASC+FEM+NEUT")
    ]
    afegir("qui", "PRON", base_qui + [("quicum", "SG;ABL;MASC+FEM+NEUT"), ("quibuscum", "PL;DAT+ABL;MASC+FEM+NEUT")])

    # Interrogatiu / indefinit simple quis, quid
    afegir("quis", "PRON", base_qui + [
        ("quis", "SG;NOM;MASC+FEM"), ("qua", "SG;NOM;FEM"), ("quid", "SG;NOM+ACC;NEUT"), ("qua", "PL;NOM+ACC;NEUT")
    ])

    # Compostos amb sufix invariable (-cumque, -que, -piam, -quam, -uis/-vis, -libet, -nam)
    for lema_c, sufix in [
        ("quicumque", "cumque"), ("quisque", "que"), ("quispiam", "piam"),
        ("quisquam", "quam"), ("quiuis", "uis"), ("quivis", "vis"),
        ("quilibet", "libet"), ("quisnam", "nam")
    ]:
        formes_comp = []
        base_estesa = base_qui + [("quis", "SG;NOM;MASC+FEM"), ("quid", "SG;NOM+ACC;NEUT")]
        for f, m in base_estesa:
            if lema_c == "quicumque" and f in ["quis", "quid"]:
                continue
            if lema_c in ["quisque", "quispiam", "quisquam", "quisnam"] and f == "qui" and "SG" in m:
                continue
            f_nova = f + sufix
            if f == "quid" and sufix == "quam":
                formes_comp.append(("quicquam", m))
            formes_comp.append((f_nova, m))
        afegir(lema_c, "PRON", formes_comp)

    # Quidam (amb assimilació m -> n davant -dam)
    afegir("quidam", "PRON", [
        ("quidam", "SG;NOM;MASC"), ("quaedam", "SG;NOM;FEM"), ("quiddam", "SG;NOM+ACC;NEUT"), ("quoddam", "SG;NOM+ACC;NEUT"),
        ("quendam", "SG;ACC;MASC"), ("quandam", "SG;ACC;FEM"),
        ("cuiusdam", "SG;GEN;MASC+FEM+NEUT"), ("cuidam", "SG;DAT;MASC+FEM+NEUT"),
        ("quodam", "SG;ABL;MASC+NEUT"), ("quadam", "SG;ABL;FEM"),
        ("quidam", "PL;NOM;MASC"), ("quaedam", "PL;NOM;FEM"), ("quaedam", "PL;NOM+ACC;NEUT"),
        ("quosdam", "PL;ACC;MASC"), ("quasdam", "PL;ACC;FEM"),
        ("quorundam", "PL;GEN;MASC+NEUT"), ("quarundam", "PL;GEN;FEM"),
        ("quibusdam", "PL;DAT+ABL;MASC+FEM+NEUT")
    ])

    # Aliquis (prefix ali- + quis, amb femení sg. i neutre pl. aliqua)
    formes_aliquis = [
        ("aliquis", "SG;NOM;MASC+FEM"), ("aliqui", "SG;NOM;MASC"), ("aliqua", "SG;NOM;FEM"),
        ("aliquid", "SG;NOM+ACC;NEUT"), ("aliquod", "SG;NOM+ACC;NEUT"),
        ("aliquem", "SG;ACC;MASC"), ("aliquam", "SG;ACC;FEM"),
        ("alicuius", "SG;GEN;MASC+FEM+NEUT"), ("alicui", "SG;DAT;MASC+FEM+NEUT"),
        ("aliquo", "SG;ABL;MASC+NEUT"), ("aliqua", "SG;ABL;FEM"),
        ("aliqui", "PL;NOM;MASC"), ("aliquae", "PL;NOM;FEM"), ("aliqua", "PL;NOM+ACC;NEUT"),
        ("aliquos", "PL;ACC;MASC"), ("aliquas", "PL;ACC;FEM"),
        ("aliquorum", "PL;GEN;MASC+NEUT"), ("aliquarum", "PL;GEN;FEM"),
        ("aliquibus", "PL;DAT+ABL;MASC+FEM+NEUT")
    ]
    afegir("aliquis", "PRON", formes_aliquis)

    # Quisquis (duplicat)
    afegir("quisquis", "PRON", [
        ("quisquis", "SG;NOM;MASC+FEM"), ("quidquid", "SG;NOM+ACC;NEUT"), ("quicquid", "SG;NOM+ACC;NEUT"),
        ("cuiuscuius", "SG;GEN;MASC+FEM+NEUT"), ("cuicui", "SG;DAT;MASC+FEM+NEUT"),
        ("quoquo", "SG;ABL;MASC+NEUT"), ("quaqua", "SG;ABL;FEM"), ("quibusquibus", "PL;DAT+ABL;MASC+FEM+NEUT")
    ])

    # 5. ADJECTIUS PRONOMINALS (genitiu en -ius, datiu en -i: unus, solus, totus, ullus, nullus, alius, alter, uter, uterque, neuter)
    for lema_pr, arrel_pr, nom_m, nom_n, te_pl in [
        ("unus", "un", "unus", "unum", True),
        ("solus", "sol", "solus", "solum", True),
        ("totus", "tot", "totus", "totum", True),
        ("ullus", "ull", "ullus", "ullum", True),
        ("nullus", "null", "nullus", "nullum", True),
        ("alius", "ali", "alius", "aliud", True),
        ("alter", "alter", "alter", "alterum", True),
        ("uter", "utr", "uter", "utrum", True),
        ("neuter", "neutr", "neuter", "neutrum", True)
    ]:
        f_list = [
            (nom_m, "SG;NOM;MASC"), (arrel_pr + "a", "SG;NOM;FEM"), (nom_n, "SG;NOM;NEUT"),
            (arrel_pr + "um", "SG;ACC;MASC"), (arrel_pr + "am", "SG;ACC;FEM"), (nom_n, "SG;ACC;NEUT"),
            (arrel_pr + "ius", "SG;GEN;MASC+FEM+NEUT"), (arrel_pr + "i", "SG;DAT;MASC+FEM+NEUT"),
            (arrel_pr + "o", "SG;ABL;MASC+NEUT"), (arrel_pr + "a", "SG;ABL;FEM")
        ]
        if te_pl:
            f_list.extend([
                (arrel_pr + "i", "PL;NOM;MASC"), (arrel_pr + "ae", "PL;NOM;FEM"), (arrel_pr + "a", "PL;NOM;NEUT"),
                (arrel_pr + "os", "PL;ACC;MASC"), (arrel_pr + "as", "PL;ACC;FEM"), (arrel_pr + "a", "PL;ACC;NEUT"),
                (arrel_pr + "orum", "PL;GEN;MASC+NEUT"), (arrel_pr + "arum", "PL;GEN;FEM"),
                (arrel_pr + "is", "PL;DAT+ABL;MASC+FEM+NEUT")
            ])
        afegir(lema_pr, "PRON", f_list)

    # Uterque
    afegir("uterque", "PRON", [
        ("uterque", "SG;NOM;MASC"), ("utraque", "SG;NOM;FEM"), ("utrumque", "SG;NOM+ACC;NEUT"),
        ("utrumque", "SG;ACC;MASC"), ("utramque", "SG;ACC;FEM"),
        ("utriusque", "SG;GEN;MASC+FEM+NEUT"), ("utrique", "SG;DAT;MASC+FEM+NEUT"),
        ("utroque", "SG;ABL;MASC+NEUT"), ("utraque", "SG;ABL;FEM"),
        ("utrique", "PL;NOM;MASC"), ("utraeque", "PL;NOM;FEM"), ("utraque", "PL;NOM+ACC;NEUT"),
        ("utrosque", "PL;ACC;MASC"), ("utrasque", "PL;ACC;FEM"),
        ("utrorumque", "PL;GEN;MASC+NEUT"), ("utrarumque", "PL;GEN;FEM"),
        ("utrisque", "PL;DAT+ABL;MASC+FEM+NEUT")
    ])

    # Nemo (pronom negatiu defectiu)
    afegir("nemo", "PRON", [
        ("nemo", "SG;NOM;MASC+FEM"), ("neminem", "SG;ACC;MASC+FEM"),
        ("neminis", "SG;GEN;MASC+FEM"), ("nemini", "SG;DAT;MASC+FEM"), ("nemine", "SG;ABL;MASC+FEM")
    ])

    # 6. NUMERALS DECLINABLES (duo, tres, milia)
    afegir("duo", "NUM", [
        ("duo", "PL;NOM;MASC+NEUT"), ("duae", "PL;NOM;FEM"),
        ("duos", "PL;ACC;MASC"), ("duo", "PL;ACC;MASC+NEUT"), ("duas", "PL;ACC;FEM"),
        ("duorum", "PL;GEN;MASC+NEUT"), ("duarum", "PL;GEN;FEM"),
        ("duobus", "PL;DAT+ABL;MASC+NEUT"), ("duabus", "PL;DAT+ABL;FEM")
    ])
    afegir("tres", "NUM", [
        ("tres", "PL;NOM+ACC;MASC+FEM"), ("tria", "PL;NOM+ACC;NEUT"),
        ("trium", "PL;GEN;MASC+FEM+NEUT"), ("tribus", "PL;DAT+ABL;MASC+FEM+NEUT")
    ])
    afegir("mille", "NUM", [
        ("mille", "SG;NOM+ACC+GEN+DAT+ABL;MASC+FEM+NEUT"),
        ("milia", "PL;NOM+VOC+ACC;NEUT"), ("millia", "PL;NOM+VOC+ACC;NEUT"),
        ("milium", "PL;GEN;NEUT"), ("millium", "PL;GEN;NEUT"),
        ("milibus", "PL;DAT+ABL;NEUT"), ("millibus", "PL;DAT+ABL;NEUT")
    ])

    return entrades

def generar_formes_verbals_derivades() -> list:
    """Llegeix el corpus base 'lat' i expandeix tots els participis (declinats en tots els casos/gèneres),
    gerundis/gerundius i infinitius per als verbs existents."""
    if not os.path.exists("lat"):
        print("Avís: No s'ha trobat el fitxer base 'lat'. Només es generaran pronoms i numerals.")
        return []

    verbs = defaultdict(list)
    with open("lat", "r", encoding="utf-8", errors="ignore") as f:
        for line in f:
            parts = line.strip().split("\t")
            if len(parts) >= 3:
                lema, forma, tag = parts[0].strip(), parts[1].strip(), parts[2].strip()
                if tag.startswith("V;") or "PTCP" in tag or "NFIN" in tag or "V.MSDR" in tag:
                    verbs[lema].append((forma, tag))

    noves_entrades = []

    for lema, formes in verbs.items():
        inf_prs = None
        ptcp_prs = None
        ptcp_pfv = None
        ptcp_fut = None
        gerundiu = None
        pfv_1sg = None

        for forma, tag in formes:
            toks = set(tag.replace("|", ";").split(";"))
            if "NFIN" in toks and "PRS" in toks and "ACT" in toks:
                inf_prs = forma
            elif ("PTCP" in toks or "V.PTCP" in tag) and "PRS" in toks:
                if forma.endswith("ns"):
                    ptcp_prs = forma
            elif ("PTCP" in toks or "V.PTCP" in tag) and ("PFV" in toks or "PST" in toks) and "PASS" in toks:
                if forma.endswith(("us", "a", "um")):
                    ptcp_pfv = forma[:-2] + "us"
            elif ("PTCP" in toks or "V.PTCP" in tag) and "FUT" in toks and "ACT" in toks:
                if forma.endswith(("urus", "ura", "urum")):
                    ptcp_fut = forma[:-2] + "us"
            elif "V.MSDR" in tag or ("FUT" in toks and "PASS" in toks and "PTCP" in toks):
                if forma.endswith(("ndus", "nda", "ndum", "ndi", "ndo")):
                    base_nd = forma[:-2] if forma.endswith(("us", "um")) else forma[:-1]
                    if base_nd.endswith("nd"):
                        gerundiu = base_nd + "us"
            elif {"IND", "PFV", "ACT", "1", "SG"}.issubset(toks):
                pfv_1sg = forma

        # Deducció automàtica si el corpus base no portava el participi o el gerundiu explícit
        if inf_prs and not ptcp_prs:
            inf_net = normalitzar(inf_prs)
            if inf_net.endswith("are"):
                ptcp_prs = inf_prs[:-3] + "ans"
            elif inf_net.endswith("ere") and normalitzar(lema).endswith("eo"):
                ptcp_prs = inf_prs[:-3] + "ens"
            elif inf_net.endswith("ire"):
                ptcp_prs = inf_prs[:-3] + "iens"
            elif inf_net.endswith("ere"):
                tema = inf_prs[:-3]
                ptcp_prs = (tema + "iens") if normalitzar(lema).endswith("io") else (tema + "ens")

        if ptcp_prs and not gerundiu and ptcp_prs.endswith("ns"):
            gerundiu = ptcp_prs[:-2] + "ndus"

        if ptcp_pfv and not ptcp_fut and ptcp_pfv.endswith("us"):
            ptcp_fut = ptcp_pfv[:-2] + "urus"

        # 1. Expandir declinació completa del Participi de Present (-ns, -ntis)
        if ptcp_prs and ptcp_prs.endswith("ns"):
            arrel_nt = ptcp_prs[:-2] + "nt"
            for f_dec, m_dec in declinar_participi_present(ptcp_prs, arrel_nt):
                noves_entrades.append((lema, f_dec, f"V;V.PTCP;PRS;ACT;{m_dec}"))

        # 2. Expandir declinació completa del Participi de Perfet Passiu (-us, -a, -um)
        if ptcp_pfv and ptcp_pfv.endswith("us"):
            arrel_pfv = ptcp_pfv[:-2]
            for f_dec, m_dec in declinar_1a_2a(arrel_pfv):
                noves_entrades.append((lema, f_dec, f"V;V.PTCP;PFV;PASS;{m_dec}"))
            # Infinitius analítics de perfet passiu (amatum esse, amatam esse...)
            noves_entrades.append((lema, arrel_pfv + "um esse", "V;NFIN;PFV;PASS"))
            noves_entrades.append((lema, arrel_pfv + "am esse", "V;NFIN;PFV;PASS"))
            noves_entrades.append((lema, arrel_pfv + "os esse", "V;NFIN;PFV;PASS"))
            noves_entrades.append((lema, arrel_pfv + "as esse", "V;NFIN;PFV;PASS"))
            noves_entrades.append((lema, arrel_pfv + "a esse", "V;NFIN;PFV;PASS"))
            noves_entrades.append((lema, arrel_pfv + "um iri", "V;NFIN;FUT;PASS"))

        # 3. Expandir declinació completa del Participi de Futur Actiu (-urus, -ura, -urum)
        if ptcp_fut and ptcp_fut.endswith("us"):
            arrel_fut = ptcp_fut[:-2]
            for f_dec, m_dec in declinar_1a_2a(arrel_fut):
                noves_entrades.append((lema, f_dec, f"V;V.PTCP;FUT;ACT;{m_dec}"))
            # Infinitius analítics de futur actiu (amaturum esse...)
            noves_entrades.append((lema, arrel_fut + "um esse", "V;NFIN;FUT;ACT"))
            noves_entrades.append((lema, arrel_fut + "am esse", "V;NFIN;FUT;ACT"))
            noves_entrades.append((lema, arrel_fut + "os esse", "V;NFIN;FUT;ACT"))
            noves_entrades.append((lema, arrel_fut + "as esse", "V;NFIN;FUT;ACT"))
            noves_entrades.append((lema, arrel_fut + "a esse", "V;NFIN;FUT;ACT"))

        # 4. Expandir declinació completa del Participi de Futur Passiu / Gerundiu (-ndus, -nda, -ndum) i Gerundi
        if gerundiu and gerundiu.endswith("us"):
            arrel_nd = gerundiu[:-2]
            for f_dec, m_dec in declinar_1a_2a(arrel_nd):
                noves_entrades.append((lema, f_dec, f"V;V.PTCP;FUT;PASS;{m_dec}"))
            noves_entrades.append((lema, arrel_nd + "um esse", "V;NFIN;FUT;PASS"))
            # Casos del gerundi (substantiu verbal neutre singular)
            noves_entrades.append((lema, arrel_nd + "um", "V;V.MSDR;ACC"))
            noves_entrades.append((lema, arrel_nd + "i", "V;V.MSDR;GEN"))
            noves_entrades.append((lema, arrel_nd + "o", "V;V.MSDR;DAT"))
            noves_entrades.append((lema, arrel_nd + "o", "V;V.MSDR;ABL"))

        # 5. Infinitiu de perfet actiu (-isse) si tenim 1a sg. perfet
        if pfv_1sg and pfv_1sg.endswith("i"):
            inf_pfv = pfv_1sg[:-1] + "isse"
            noves_entrades.append((lema, inf_pfv, "V;NFIN;PFV;ACT"))

    return noves_entrades

def main():
    print("Generant formes tancades (pronoms, compostos, numerals)...")
    totes = generar_pronoms_i_numerals()
    print(f"   -> {len(totes):,} formes pronominals i numerals generades.")

    print("Generant declinacions completes de participis, gerundius i infinitius...")
    verbals = generar_formes_verbals_derivades()
    print(f"   -> {len(verbals):,} formes nominals verbals generades.")

    totes.extend(verbals)

    # Deduplicació mantenint l'ordre
    vistos = set()
    linies_uniques = []
    for lema, forma, tag in totes:
        clau = (lema, forma, tag)
        if clau not in vistos:
            vistos.add(clau)
            linies_uniques.append(f"{lema}\t{forma}\t{tag}\n")

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        f.writelines(linies_uniques)

    print(f"\n✓ Fitxer '{OUTPUT_FILE}' generat amb {len(linies_uniques):,} registres.")
    print("Ara executa 'python3 generarBD.py' per actualitzar 'diccionari.db'.")

if __name__ == "__main__":
    main()
