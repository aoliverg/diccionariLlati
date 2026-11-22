# Diccionari Llatí (`diccionariLlati`)

Aplicació d'escriptori multilingüe (`Català`, `Español`, `English`, `Français`, `Latina`) desenvolupada en **Python** i **PyQt6** per a l'estudi filològic, morfològic i sintàctic del llatí clàssic, arcaic i medieval, amb integració opcional de processament del llenguatge natural (**LatinCy / spaCy**) i intel·ligència artificial generativa en local o remot (**Ollama**).

## Índex

1. [Funcionalitats principals](#1-funcionalitats-principals)
2. [Fonts lèxiques, formaris i models de dades](#2-fonts-lèxiques-formaris-i-models-de-dades)
3. [Instal·lació mitjançant executables (Releases)](#3-installació-mitjançant-executables-releases)
4. [Instal·lació i execució des del codi font](#4-installació-i-execució-des-del-codi-font)
5. [Com instal·lar i configurar Ollama (Opcional)](#5-com-installar-i-configurar-ollama-opcional)
6. [Guia de models d'IA per mides i maquinari](#6-guia-de-models-dia-per-mides-i-maquinari)
7. [Configuració avançada (`config.yaml`)](#7-configuració-avançada-configyaml)
8. [Estructura del projecte i generació de la base de dades](#8-estructura-del-projecte-i-generació-de-la-base-de-dades)

## 1. Funcionalitats principals

* **Informació Morfològica (Pestanya 1):** Identificació instantània de lemes a partir de qualsevol forma flexionada, reconeixement automàtic de grafia ramista o clàssica (`u`/`v`, `i`/`j`), enunciats canònics, declinacions, conjugacions, règim preposicional, significat en anglès i traducció automàtica de glosses amb memòria cau persistent a SQLite.
* **Mode filològic / avançat:** Cerca de variants arcaiques, epigràfiques, vulgars i medievals, així com famílies lèxiques i mots derivats.
* **Flexió Canònica (Pestanya 2):** Generació dinàmica de paradigmes complets de declinació (substantius, adjectius de 1, 2 i 3 terminacions, pronoms i numerals) i conjugació verbal completa (formes personals, infinitius, participis, supí i gerundi, incloent-hi el verb irregular *sum*).
* **Diccionari *Lewis & Short* (Pestanya 3):** Consulta íntegra dels articles lèxics i cites textuals d'autors clàssics en local.
* **Anàlisi d'Oracions amb LatinCy (Pestanya 4):** Etiquetatge morfosintàctic complet (*Universal Dependencies*: lema, categoria gramatical UPOS, trets morfològics, funció sintàctica i dependències) amb enllaços interactius per inspeccionar cada mot al diccionari. Si no es té instal·lat `spacy`, realitza una anàlisi de correspondències sobre la base de dades local.
* **Traducció i Comentari amb Ollama (Pestanya 5):** Traducció al català (o a la llengua configurada) i anàlisi gramatical assistida per LLM en local o servidor remot, amb opció d'injectar l'anàlisi prèvia de LatinCy al *prompt* i un botó per inspeccionar la instrucció exacta enviada al model.
* **Exportació immediata:** Botons per copiar els resultats de qualsevol pestanya en **Text pla** o en codi **LaTeX** llest per a documents acadèmics.
* **Interfície multilingüe:** Canvi d'idioma en temps real des de la barra superior (`Català`, `Español`, `English`, `Français`, `Latina`) mitjançant el fitxer `i18n.properties`.

## 2. Fonts lèxiques, formaris i models de dades

L'aplicació combina diversos recursos acadèmics oberts de filologia clàssica i processament del llenguatge natural (PLN), emmagatzemats a la base de dades local `diccionari.db` i als models neuronals:

| Component / Taula | Font Acadèmica / Projecte | Descripció i Ús a l'Aplicació | Llicència / Atribució |
| :--- | :--- | :--- | :--- |
| **Diccionari principal** (`diccionari_ls`) | *A Latin Dictionary*, Charlton T. Lewis & Charles Short (Oxford, 1879) — Perseus Digital Library (Tufts University) | Entrades lexicogràfiques completes amb definicions, etimologies i cites d'autors clàssics (Pestanya 3). | CC BY-SA 3.0 |
| **Formari base** (`formes`) | UniMorph Latin (`unimorph/lat`) | Paradigmes flexionals anotats amb trets morfològics estàndard (`NOM;SG`, `IND;PRS;ACT;1;SG`, `PTCP;PASS;PST;PFV`, etc.). | CC BY-SA 3.0 |
| **Formari tancat i derivats nominals** (`lat.closed` -> `formes`) | Generació morfològica pròpia (`generarCLOSED.py`) | Expansió sistemàtica de tots els pronoms (personals, reflexius, possessius, demostratius, relatius, interrogatius, indefinits i compostos), numerals declinables, participis declinats en tots els casos/gèneres, gerundis, gerundius i infinitius analítics. | Lliure / Projecte |
| **Glosses lèxiques** (`glosses`) | Whitaker's Words (William Whitaker) | Equivalents lèxics concisos en anglès per lema i categoria gramatical (`N`, `V`, `ADJ`, `PREP`, etc.), utilitzats com a referència ràpida i com a base per a la traducció amb memòria cau (`glosses_llm_cache`). | Domini públic / Lliure |
| **Variants històriques i famílies** (`variants_hist`, `families`) | Wiktionary / Kaikki.org i taules de normalització filològica | Registre de formes arcaiques, epigràfiques, tardanes o medievals, variants ortogràfiques (`u`/`v`, `i`/`j`) i agrupacions de mots derivats per al *Mode filològic / avançat*. | CC BY-SA 3.0 / 4.0 |
| **Anàlisi d'oracions** (Pestanya 4) | LatinCy (`la_core_web_sm/md/lg/trf`), Patrick J. Burns (`latincy` / spaCy) | Models neuronals entrenats sobre els *treebanks* llatins d'Universal Dependencies (*Perseus*, *PROIEL*, *ITTB*, *LLCT*, *UDante*) per a lematització, morfologia i sintaxi de dependències. | MIT / CC BY-SA 4.0 |

## 3. Instal·lació mitjançant executables (Releases)

A l'apartat **Releases** del repositori hi ha disponibles els executables precompilats per a **Windows**, **Linux** i **macOS**, juntament amb la base de dades ja generada `diccionari.db` (allotjada a *Releases* i no al codi font per la seva mida elevada):

1. Descarrega des de la secció **Releases** del repositori l'executable corresponent al teu sistema operatiu (`diccionariLlati` o `diccionariLlati.exe`).
2. **Important:** Descarrega també des del mateix apartat **Releases** l'arxiu `diccionari.db` i desa'l **dins el mateix directori** on hagis posat l'executable. D'aquesta manera l'aplicació tindrà totes les dades llestes a l'instant i no hauràs de generar la base de dades tu mateix.
3. Comprova que al mateix directori hi siguin també els fitxers `config.yaml` i `i18n.properties` (inclosos al paquet de la *Release*).
4. Executa `diccionariLlati` (o `diccionariLlati.exe` a Windows).

Notes segons el sistema operatiu:

* **macOS:** Si el sistema mostra un avís de seguretat en obrir l'aplicació per primera vegada, fes clic amb el botó dret sobre `diccionariLlati` i selecciona **Obre**, o bé autoritza'l des de *Configuració del sistema > Privadesa i seguretat*.
* **Linux:** Assegura't que el fitxer té permisos d'execució (`chmod +x diccionariLlati`).
* **Windows:** Si Windows SmartScreen mostra un avís en tractar-se d'un executable nou, prem **Més informació** i **Executa de totes maneres**.

## 4. Instal·lació i execució des del codi font

Si prefereixes executar el programa directament amb Python, es recomana **Python 3.10 o superior** i un entorn virtual (`venv`).

### 4.1. Obtenir la base de dades (`diccionari.db`)

Per la seva mida, el fitxer `diccionari.db` no es distribueix dins l'arbre principal del repositori. Tens dues opcions:

* **Opció recomanada (descàrrega directa):** Descarrega el fitxer `diccionari.db` ja compilat des de l'apartat **Releases** del repositori i desa'l al mateix directori que `diccionariLlati.py`.
* **Opció alternativa (generació local):** Pots construir la base de dades tu mateix des de zero executant `python3 generarCLOSED.py` i tot seguit `python3 generarBD.py` (vegeu la secció 8).

### 4.2. Crear i activar l'entorn virtual

```bash
python3 -m venv .venv

# A macOS / Linux:
source .venv/bin/activate

# A Windows (PowerShell):
.venv\Scripts\Activate.ps1
```

### 4.3. Instal·lar els requeriments

#### Opció A: Instal·lació bàsica (Recomanada per a equips lleugers)

Inclou la interfície gràfica, tot el diccionari, les taules de flexió canònica, el *Lewis & Short*, l'anàlisi lèxica bàsica d'oracions (via SQLite) i la compatibilitat amb Ollama (si es té instal·lat al sistema).

```bash
pip install -r requeriments-basic.txt
```

*(Conté: `PyQt6` i `PyYAML`)*

#### Opció B: Instal·lació completa (Amb anàlisi sintàctica neuronal LatinCy)

Afegeix `spacy` per descarregar i executar automàticament els models neuronals **LatinCy** (`la_core_web_sm`, `md`, `lg` o `trf`) des de Hugging Face la primera vegada que s'obre el programa.

```bash
pip install -r requeriments-all.txt
```

*(Conté: `PyQt6`, `PyYAML` i `spacy`)*

*Nota sobre dependències:* No cal instal·lar els paquets Python `ollama` ni `huggingface_hub`. L'aplicació es comunica directament mitjançant peticions HTTP estàndard amb Ollama i Hugging Face.

### 4.4. Executar l'aplicació

```bash
python3 diccionariLlati.py
```

## 5. Com instal·lar i configurar Ollama (Opcional)

L'aplicació **funciona completament sense Ollama**: si no el tens instal·lat, totes les pestanyes de consulta lèxica, flexió, *Lewis & Short* i anàlisi amb *LatinCy* continuaran operant amb normalitat.

Si vols activar la traducció assistida per intel·ligència artificial en local (sense enviar dades al núvol), segueix aquests passos:

### Instal·lació per sistema operatiu

* **macOS:**
  * Descarrega l'instal·lador oficial des de `https://ollama.com/download/mac` o executa al Terminal:
    ```bash
    brew install --cask ollama
    ```
  * Obre l'aplicació **Ollama** des de la carpeta *Aplicacions* perquè el servei quedi actiu en segon pla.
* **Windows:**
  * Descarrega `OllamaSetup.exe` des de `https://ollama.com/download/windows` o executa al PowerShell:
    ```powershell
    winget install Ollama.Ollama
    ```
* **Linux:**
  * Executa l'script oficial d'instal·lació al terminal:
    ```bash
    curl -fsSL https://ollama.com/install.sh | sh
    ```
  * Comprova que el servei estigui en marxa amb `systemctl status ollama` (o inicia'l manualment amb `ollama serve`).

Un cop instal·lat i iniciat Ollama, prem el botó **Tornar a comprovar** dins la pestanya *Traducció (Ollama)* de l'aplicació.

## 6. Guia de models d'IA per mides i maquinari

Pots configurar el model desitjat editant el camp `model:` dins de `config.yaml`. Si `auto_pull: true` està activat, l'aplicació el descarregarà automàticament la primera vegada que facis una traducció, o bé el pots descarregar prèviament des del terminal amb `ollama pull <nom_del_model>`.

| Perfil d'Equip | RAM / VRAM Mínima | Models Recomanats | Comanda d'Instal·lació | Observacions |
| :--- | :--- | :--- | :--- | :--- |
| **Lleuger / Portàtil bàsic** | 8 GB RAM | `gemma3:4b`, `qwen2.5:7b` | `ollama pull gemma3:4b` | Molt ràpids. Bons per a glosses lèxiques i oracions senzilles; poden cometre errors en sintaxi clàssica complexa. |
| **Equilibrat (Recomanat)** | 16 GB RAM | `gemma3:12b`, `qwen2.5:14b`, `mistral-nemo:12b` | `ollama pull gemma3:12b` | Excel·lent compromís entre velocitat i rigor filològic. Ideal combinat amb la injecció d'anàlisi de LatinCy. |
| **Avançat / Estació de treball** | 24 – 32 GB RAM | `gemma3:27b`, `qwen3:30b-a3b` | `ollama pull gemma3:27b` | Alta precisió en subordinació llatina (ablatius absoluts, estil indirecte, subjuntius) i traducció literària acurada. |
| **Màxima Qualitat (Apple Silicon / GPU)** | 32 – 64+ GB RAM | `qwen3:32b`, `llama3.3:70b` | `ollama pull qwen3:32b` | Rendiment filològic de referència per a textos clàssics extensos i comentaris sintàctics detallats. |

## 7. Configuració avançada (`config.yaml`)

El fitxer `config.yaml` permet personalitzar el comportament dels mòduls d'IA i de PLN:

* `spacy.model`: Model de LatinCy a carregar (`la_core_web_sm`, `la_core_web_md`, `la_core_web_lg` o `la_core_web_trf`).
* `spacy.auto_install`: Si és `true`, descarrega i instal·la automàticament el model de LatinCy la primera vegada.
* `traduccio_llm.url`: Adreça del servidor Ollama. Per defecte `"http://localhost:11434"`. Si s'indica una IP externa de la xarxa local (ex. `"http://192.168.1.50:11434"`), l'aplicació hi connectarà en mode remot.
* `traduccio_llm.thinking`: Posa-ho a `false` per obtenir respostes ràpides i directes, o a `true` per activar el raonament intern pas per pas en models compatibles.
* `traduccio_llm.llengua_desti`: Llengua a la qual es traduiran les glosses lèxiques a la pestanya d'Informació Morfològica (ex. `"català"`, `"castellà"`, `"anglès"`, `"francès"`).

## 8. Estructura del projecte i generació de la base de dades

### Fitxers necessaris per executar l'aplicació

```text
.
├── diccionariLlati(.exe)      # Executable o script principal (diccionariLlati.py)
├── config.yaml                # Configuració de spaCy/LatinCy i Ollama
├── i18n.properties            # Cadenes de text de la interfície en 5 llengües
├── diccionari.db              # Base de dades SQLite (disponible a Releases o generable localment)
├── requeriments-basic.txt     # Dependències mínimes per a execució des de codi font
├── requeriments-all.txt       # Dependències completes (+ spacy)
└── README.md                  # Aquesta documentació
```

### Scripts de construcció de la base de dades (generació local opcional)

Aquests scripts serveixen per reconstruir `diccionari.db` des de zero si l'usuari prefereix generar-la localment en lloc de descarregar-la des de **Releases**:

1. `generarCLOSED.py`: Genera el fitxer `lat.closed` amb les declinacions completes dels pronoms, numerals, participis, gerundis, gerundius i infinitius analítics a partir del corpus base `lat`.
2. `generarBD.py`: Compila els formaris (`lat`, `lat.closed`), les glosses, les variants històriques, les famílies lèxiques i les entrades del *Lewis & Short* dins la base de dades SQLite `diccionari.db`.
