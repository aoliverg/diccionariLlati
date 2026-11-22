# Diccionari Llatí — Morfologia, Oracions (LatinCy), Lewis & Short i Ollama

Aplicació d'escriptori en Python (`PyQt6`) per a la consulta morfològica, la flexió canònica, l'anàlisi sintàctica d'oracions en llatí, la consulta del diccionari *Lewis & Short* i la traducció assistida per models de llenguatge locals o remots mitjançant **Ollama**.

---

## ✨ Funcionalitats Principals

1. **Informació Morfològica**: Identificació automàtica de lemes, enunciats canònics, declinacions, conjugacions, gèneres, règims preposicionals, glosses ràpides (en anglès i traduïdes automàticament amb memòria cau persistent a SQLite) i mode filològic/avançat per a variants arcaiques, epigràfiques, medievals i famílies lèxiques.
2. **Flexió Canònica**: Generació completa de taules de declinació (substantius, adjectius de 3, 2 i 1 terminació, pronoms) i de conjugació verbal (formes personals, infinitius, participis, supins i gerundis), amb ressaltat de la forma cercada i adaptació ortogràfica `u`/`v`.
3. **Lewis & Short (Diccionari)**: Consulta íntegra de les entrades clàssiques del diccionari *A Latin Dictionary* de Lewis & Short.
4. **Anàlisi d'Oracions (LatinCy / spaCy)**: Lematització, etiquetatge morfosintàctic (*Universal Dependencies*) i relacions de dependència. Els lemes de la taula són clicables per inspeccionar-ne la morfologia i la flexió a l'instant. Si `spacy` no està instal·lat, l'aplicació fa servir automàticament la base de dades local SQLite.
5. **Traducció i Comentari (Ollama)**: Traducció i anàlisi gramatical assistida per IA (local o en servidor remot), amb opció d'injectar l'anàlisi morfosintàctica prèvia de LatinCy com a guia per evitar errors de concordança o de cas, i visor de la instrucció exacta (*prompt*) enviada al model.
6. **Exportació i Interfície Multilingüe**: Còpia directa al porta-retalls en **Text Pla** o en format **LaTeX** a totes les pestanyes, i selector d'idioma de la interfície en temps real (`Català`, `Español`, `English`, `Français`, `Latina`) mitjançant `i18n.properties`.

---

## 📚 Fonts Lèxiques, Formaris i Models de Dades

L'aplicació combina diversos recursos acadèmics oberts de filologia clàssica i processament del llenguatge natural (PLN), integrats dins la base de dades local `diccionari.db` i els models neuronals:

| Component / Taula | Font Acadèmica / Projecte | Descripció i Ús a l'Aplicació | Llicència / Atribució |
| :--- | :--- | :--- | :--- |
| **Diccionari principal**<br>(`diccionari_ls`) | ***A Latin Dictionary***<br>Charlton T. Lewis & Charles Short (Oxford, 1879) · *Perseus Digital Library* (Tufts University) | Entrades lexicogràfiques completes amb definicions, etimologies i cites d'autors clàssics (Pestanya 3). | CC BY-SA 3.0 |
| **Formari i flexió**<br>(`formes`) | **UniMorph Latin** (`unimorph/lat`) | Paradigmes flexionals complets anotats amb trets morfològics estàndard (`NOM;SG`, `IND;PRS;ACT;1;SG`, `PTCP;PASS;PST;PFV`, etc.) que alimenten els motors de declinació i conjugació (Pestanya 2). | CC BY-SA 3.0 |
| **Glosses lèxiques**<br>(`glosses`) | **Whitaker's Words**<br>(William Whitaker) | Equivalents lèxics concisos en anglès per lema i categoria gramatical (`N`, `V`, `ADJ`, `PREP`, etc.), utilitzats com a referència ràpida i com a base per a la traducció amb memòria cau (`glosses_llm_cache`). | Domini públic / Lliure |
| **Variants històriques i famílies**<br>(`variants_hist`, `families`) | **Wiktionary / Kaikki.org** i taules de normalització filològica | Registre de formes arcaiques, epigràfiques, tardanes o medievals, variants ortogràfiques (`u`/`v`, `i`/`j`) i agrupacions de mots derivats per al *Mode filològic / avançat*. | CC BY-SA 3.0 / 4.0 |
| **Anàlisi d'oracions**<br>(Pestanya 4) | **LatinCy** (`la_core_web_sm/md/lg/trf`)<br>Patrick J. Burns (`latincy` / spaCy) | Models neuronals entrenats sobre els *treebanks* llatins d'**Universal Dependencies** (*Perseus*, *PROIEL*, *ITTB*, *LLCT*, *UDante*) per a lematització, morfologia i sintaxi de dependències. | MIT / CC BY-SA 4.0 |

---

## 📦 Estructura del Projecte

Assegura't de tenir aquests fitxers al mateix directori de treball:

```text
.
├── diccionariLlatiOllama.py   # Aplicació principal
├── config.yaml                # Configuració de spaCy/LatinCy i Ollama
├── i18n.properties            # Cadenes de text de la interfície en 5 llengües
├── diccionari.db              # Base de dades SQLite (generada amb generarBD.py)
├── requeriments-basic.txt     # Dependències mínimes (PyQt6, PyYAML)
├── requeriments-all.txt       # Dependències completes (+ spacy)
└── README.md                  # Aquesta guia
