# Diccionari Llatí — Morfologia, Flexió, LatinCy, Lewis & Short i Ollama

Aplicació d'escriptori multilingüe (`Català`, `Español`, `English`, `Français`, `Latina`) desenvolupada en **Python** i **PyQt6** per a l'estudi filològic, morfològic i sintàctic del llatí clàssic, arcaic i medieval, amb integració opcional de processament del llenguatge natural (**LatinCy / spaCy**) i intel·ligència artificial generativa en local o remot (**Ollama**).

## Índex

1. [Funcionalitats principals](#1-funcionalitats-principals)
2. [Fonts lèxiques, formaris i models de dades](#2-fonts-lèxiques-formaris-i-models-de-dades)
3. [Requisits del sistema (Obligatoris i Opcionals)](#3-requisits-del-sistema-obligatoris-i-opcionals)
4. [Instal·lació pas a pas](#4-installació-pas-a-pas)
5. [Com instal·lar i configurar Ollama (Opcional)](#5-com-installar-i-configurar-ollama-opcional)
6. [Guia de models d'IA per mides i maquinari](#6-guia-de-models-dia-per-mides-i-maquinari)
7. [Configuració avançada (`config.yaml`)](#7-configuració-avançada-configyaml)
8. [Estructura de fitxers del projecte](#8-estructura-de-fitxers-del-projecte)

## 1. Funcionalitats principals

* **Informació Morfològica (Pestanya 1):** Identificació instantània de lemes a partir de qualsevol forma flexionada, reconeixement automàtic de grafia ramista/clàssica (`u`/`v`, `i`/`j`), enunciats canònics, declinacions, conjugacions, règim preposicional, significat en anglès i traducció automàtica de glosses amb memòria cau persistent a SQLite.
* **Mode filològic / avançat:** Cerca de variants arcaiques, epigràfiques, vulgars i medievals, així com famílies lèxiques i mots derivats.
* **Flexió Canònica (Pestanya 2):** Generació dinàmica de paradigmes complets de declinació (substantius, adjectius de 1, 2 i 3 terminacions, pronoms i numerals) i conjugació verbal completa (formes personals, infinitius, participis, supí i gerundi, incloent-hi el verb irregular *sum*).
* **Diccionari *Lewis & Short* (Pestanya 3):** Consulta íntegra dels articles lèxics i cites textuals d'autors clàssics en local.
* **Anàlisi d'Oracions amb LatinCy (Pestanya 4):** Etiquetatge morfosintàctic complet (*Universal Dependencies*: lema, categoria gramatical UPOS, trets morfològics, funció sintàctica i dependències) amb enllaços interactius per inspeccionar cada mot al diccionari. Si no es té instal·lat `spacy`, realitza una anàlisi de correspondències sobre la base de dades local.
* **Traducció i Comentari amb Ollama (Pestanya 5):** Traducció al català (o a la llengua configurada) i anàlisi gramatical assistida per LLM en local o servidor remot, amb opció d'injectar l'anàlisi prèvia de LatinCy al *prompt* i visor de la instrucció exacta enviada al model.
* **Exportació immediata:** Botons per copiar els resultats de qualsevol pestanya en **Text pla** o en codi **LaTeX** llest per a documents acadèmics.
* **Interfície multilingüe:** Canvi d'idioma en calent des de la barra superior (`Català`, `Español`, `English`, `Français`, `Latina`) mitjançant el fitxer `i18n.properties`.

## 2. Fonts lèxiques, formaris i models de dades

L'aplicació integra diversos recursos acadèmics oberts de filologia clàssica i processament del llenguatge natural (PLN), emmagatzemats a la base de dades local `diccionari.db` i als models neuronals:

| Component / Taula | Font Acadèmica / Projecte | Descripció i Ús a l'Aplicació | Llicència / Atribució |
| :--- | :--- | :--- | :--- |
| **Diccionari principal**<br>(`diccionari_ls`) | ***A Latin Dictionary***<br>Charlton T. Lewis & Charles Short (Oxford, Clarendon Press, 1879) · *Perseus Digital Library* (Tufts University) | Entrades lexicogràfiques completes amb definicions detallades, etimologies i cites textuals d'autors clàssics (Pestanya 3). | CC BY-SA 3.0 |
| **Formari i flexió**<br>(`formes`) | **UniMorph Latin** (`unimorph/lat`) | Paradigmes flexionals complets anotats amb trets morfològics estàndard (`NOM;SG`, `IND;PRS;ACT;1;SG`, `PTCP;PASS;PST;PFV`, etc.) que alimenten els motors de declinació i conjugació (Pestanya 2). | CC BY-SA 3.0 |
| **Glosses lèxiques**<br>(`glosses`) | **Whitaker's Words**<br>(William Whitaker) | Equivalents lèxics concisos en anglès per lema i categoria gramatical (`N`, `V`, `ADJ`, `PREP`, etc.), utilitzats com a referència ràpida i com a base per a la traducció amb memòria cau (`glosses_llm_cache`). | Domini públic / Lliure |
| **Variants històriques i famílies**<br>(`variants_hist`, `families`) | **Wiktionary / Kaikki.org** i taules de normalització filològica | Registre de formes arcaiques, epigràfiques, tardanes o medievals, variants ortogràfiques (`u`/`v`, `i`/`j`) i agrupacions de mots derivats per al *Mode filològic / avançat*. | CC BY-SA 3.0 / 4.0 |
| **Anàlisi d'oracions**<br>(Pestanya 4) | **LatinCy** (`la_core_web_sm/md/lg/trf`)<br>Patrick J. Burns (`latincy` / spaCy) | Models neuronals entrenats sobre els *treebanks* llatins d'**Universal Dependencies** (*Perseus*, *PROIEL*, *ITTB*, *LLCT*, *UDante*) per a lematització, morfologia i sintaxi de dependències. | MIT / CC BY-SA 4.0 |

## 3. Requisits del sistema (Obligatoris i Opcionals)

### Requisits obligatoris

* **Python 3.10 o superior**
* **PyQt6**: Necessari per a tota la interfície gràfica i l'execució de tasques en segon pla.
* **Base de dades SQLite (`diccionari.db`)**: Generada prèviament amb l'script `generarBD.py`.

### Requisits opcionals (per funcionalitats)

* **PyYAML**: Recomanat per llegir la configuració personalitzada de `config.yaml` (si no s'instal·la, l'aplicació arrenca igualment amb els valors per defecte).
* **spaCy + Model LatinCy (`la_core_web_sm` / `md` / `lg` / `trf`)**: Opcional. Activa l'anàlisi sintàctica completa d'oracions a la pestanya 4. El programa descarrega i instal·la automàticament el model de Hugging Face la primera vegada que s'executa.
* **Ollama (Aplicació d'escriptori o servei)**: Opcional. Activa la traducció d'oracions i de glosses lèxiques a la pestanya 5 i la pestanya 1. **No requereix cap paquet Python addicional** (`ollama` ni `huggingface_hub`), ja que la comunicació es fa directament via HTTP estàndard.

## 4. Instal·lació pas a pas

### Pas 1: Crear un entorn virtual (recomanat)

Obre un terminal a la carpeta del projecte i crea un entorn virtual de Python:

```bash
# A macOS / Linux:
python3 -m venv .venv
source .venv/bin/activate

# A Windows (PowerShell):
python -m venv .venv
.venv\Scripts\Activate.ps1
```

### Pas 2: Instal·lar les dependències de Python

Tria una de les dues modalitats segons les teves necessitats:

* **Opció A — Instal·lació bàsica (lleugera i ràpida):**
  Inclou la interfície gràfica, tot el diccionari, la flexió canònica, el *Lewis & Short*, l'anàlisi lèxica bàsica via SQLite i el suport per a Ollama.

  ```bash
  pip install -r requeriments-basic.txt
  ```

* **Opció B — Instal·lació completa (amb anàlisi sintàctica neuronal LatinCy):**
  Afegeix `spacy` per habilitar l'anàlisi morfosintàctica completa d'oracions.

  ```bash
  pip install -r requeriments-all.txt
  ```

### Pas 3: Generar la base de dades (si encara no la tens)

Assegura't de tenir el fitxer `diccionari.db` al mateix directori. Si encara no s'ha creat:

```bash
python3 generarBD.py
```

### Pas 4: Executar l'aplicació

```bash
python3 diccionariLlatiOllama.py
```

> **Nota:** Si has triat la instal·lació completa (`requeriments-all.txt`), la primera vegada que obris el programa es descarregarà i instal·larà en segon pla el model de LatinCy indicat a `config.yaml` (`la_core_web_lg` per defecte). Pots utilitzar el diccionari amb normalitat mentre es completa la descàrrega.

## 5. Com instal·lar i configurar Ollama (Opcional)

L'aplicació funciona al 100 % en les seves funcions de diccionari, morfologia i sintaxi sense tenir Ollama instal·lat. Si vols activar la traducció assistida per IA en local (privada i sense cost per ús), instal·la **Ollama** segons el teu sistema operatiu:

### macOS

1. Descarrega l'instal·lador oficial des de [ollama.com/download/mac](https://ollama.com/download/mac) o instal·la'l via Homebrew:

   ```bash
   brew install --cask ollama
   ```

2. Obre l'aplicació **Ollama** des de la carpeta *Aplicacions* perquè el servei quedi actiu a la barra de menús.

### Windows

1. Descarrega `OllamaSetup.exe` des de [ollama.com/download/windows](https://ollama.com/download/windows) o executa al PowerShell:

   ```powershell
   winget install Ollama.Ollama
   ```

2. Un cop instal·lat, Ollama s'iniciarà automàticament a la safata del sistema.

### Linux

1. Executa l'script oficial d'instal·lació al terminal:

   ```bash
   curl -fsSL https://ollama.com/install.sh | sh
   ```

2. Comprova que el servei estigui en marxa:

   ```bash
   systemctl status ollama
   # O inicia'l manualment si cal:
   ollama serve
   ```

### Descàrrega del model

Amb `auto_pull: true` a `config.yaml`, **el mateix programa descarregarà automàticament el model configurat** la primera vegada que premis *«Traduir amb Ollama»*. També el pots descarregar manualment abans des del terminal:

```bash
ollama pull gemma3:12b
```

## 6. Guia de models d'IA per mides i maquinari

La qualitat de la traducció del llatí al català i de l'explicació sintàctica depèn molt de la capacitat del model lingüístic. Tria el model que millor s'adapti a la memòria RAM o VRAM (targeta gràfica / memòria unificada Apple Silicon) del teu ordinador:

| Categoria | Model recomanat | Ordre d'instal·lació | Mida aproximada | Memòria (RAM / VRAM) | Rendiment en llatí i català |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Ultralleuger** | `gemma3:4b` o `qwen3:4b` | `ollama pull gemma3:4b` | ~3,3 GB | **8 GB** | Molt ràpid. Adequat per a glosses lèxiques i frases senzilles. Pot cometre errors en sintaxi complexa. |
| **Equilibrat** *(Recomanat)* | `gemma3:12b` | `ollama pull gemma3:12b` | ~8,1 GB | **16 GB** | Excel·lent compromís entre velocitat i precisió filològica. Molt bon domini del català normatiu. |
| **Avançat** | `qwen3:14b` | `ollama pull qwen3:14b` | ~9,3 GB | **16 - 24 GB** | Molt sòlid en anàlisi morfosintàctica i construccions subordinades complexes. |
| **Filològic / Alta precisió** | `gemma3:27b` o `qwen3:32b` | `ollama pull gemma3:27b` | ~17 - 20 GB | **32 GB o més** | Qualitat excel·lent en textos literaris (Ciceró, Tàcit, Virgili), amb traduccions molt naturals i comentaris rigorosos. |

### Recomanacions pràctiques

1. **Canviar de model:** Només has d'editar la línia `model:` dins de `config.yaml` (per exemple, `model: "gemma3:12b"`), desar el fitxer i prémer **«↻ Tornar a comprovar»** a la pestanya de Traducció.
2. **Paràmetre `thinking`:** En models recents que suporten raonament intern (com la família `qwen3`), mantenir `thinking: false` a `config.yaml` fa que les traduccions i les glosses es generin entre 3 i 5 vegades més ràpid.
3. **Servidor remot:** Si disposes d'un ordinador potent a la xarxa local amb GPU, pots iniciar-hi Ollama amb `OLLAMA_HOST=0.0.0.0 ollama serve` i posar la seva IP a `config.yaml` (ex: `url: "http://192.168.1.50:11434"`).
4. **Injecció d'anàlisi LatinCy:** Activa la casella *"Injectar anàlisi morfosintàctica prèvia"* abans de traduir per enviar al LLM la taula de casos, temps i dependències generada per spaCy, millorant notablement la precisió dels models mitjans (`12b`–`14b`).

## 7. Configuració avançada (`config.yaml`)

Pots personalitzar el comportament dels motors d'IA editant `config.yaml`:

```yaml
spacy:
  model: "la_core_web_lg"  # Opcions: la_core_web_sm (petit), la_core_web_md (mitjà), la_core_web_lg (gran), la_core_web_trf (transformer)
  auto_install: true       # Descarrega i instal·la automàticament el model de Hugging Face

traduccio_llm:
  actiu: true
  url: "http://localhost:11434"
  model: "gemma3:12b"
  auto_pull: true
  thinking: false
  llengua_desti: "català"  # Llengua per a les glosses lèxiques de la Pestanya 1
  max_tokens: 1500
  temperature: 0.1
```

## 8. Estructura de fitxers del projecte

```text
├── diccionariLlatiOllama.py   # Aplicació principal (interfície PyQt6, motors morfològics i connexió IA)
├── config.yaml                # Configuració de LatinCy, Ollama i plantilles de prompts
├── i18n.properties            # Diccionari de cadenes de la interfície en 5 idiomes (ca, es, en, fr, la)
├── diccionari.db              # Base de dades SQLite amb formes, glosses, variants, Lewis & Short i memòria cau IA
├── generarBD.py               # Script de construcció de la base de dades SQLite
├── requeriments-basic.txt     # Dependències mínimes (PyQt6, PyYAML)
├── requeriments-all.txt       # Dependències completes (PyQt6, PyYAML, spacy)
└── README.md                  # Aquesta documentació
```
