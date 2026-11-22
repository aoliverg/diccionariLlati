import sys
import os
import re
import json
import shutil
import sqlite3
import platform
import subprocess
import unicodedata
import urllib.request
import urllib.error
from urllib.parse import urlparse
from collections import defaultdict

from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QCompleter, QLineEdit, QPushButton, QTextBrowser,
    QTabWidget, QStatusBar, QCheckBox, QTextEdit, QDialog, QComboBox
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QUrl

def obtenir_dir_base() -> str:
    """Retorna el directori de l'executable (si és PyInstaller) o de l'script."""
    if getattr(sys, "frozen", False):
        return os.path.dirname(os.path.abspath(sys.executable))
    return os.path.dirname(os.path.abspath(__file__))


def obtenir_dir_recursos() -> str:
    """Retorna el directori de recursos interns (sys._MEIPASS en PyInstaller) o de l'script."""
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        return sys._MEIPASS
    return obtenir_dir_base()


def resoldre_ruta_fitxer(nom_fitxer: str, preferir_extern: bool = True) -> str:
    """Cerca primer al directori de treball / executable (editable per l'usuari) i després als recursos interns."""
    ruta_cwd = os.path.abspath(nom_fitxer)
    if preferir_extern and os.path.exists(ruta_cwd):
        return ruta_cwd
    ruta_base = os.path.join(obtenir_dir_base(), nom_fitxer)
    if preferir_extern and os.path.exists(ruta_base):
        return ruta_base
    ruta_rec = os.path.join(obtenir_dir_recursos(), nom_fitxer)
    if os.path.exists(ruta_rec):
        return ruta_rec
    return ruta_base


DB_FILE = resoldre_ruta_fitxer("diccionari.db", preferir_extern=True)
CONFIG_FILE = resoldre_ruta_fitxer("config.yaml", preferir_extern=True)
I18N_FILE = resoldre_ruta_fitxer("i18n.properties", preferir_extern=True)

# Estat global del model LatinCy / spaCy (es carrega en segon pla segons config.yaml)
nlp_latincy = None
nom_model_carregat = None


# ==============================================================================
# GESTOR D'INTERNACIONALITZACIÓ (i18n.properties)
# ==============================================================================
class GestorIdiomes:
    IDIOMES_SUPORTATS = [
        ("ca", "Català"),
        ("es", "Español"),
        ("en", "English"),
        ("fr", "Français"),
        ("la", "Latina")
    ]

    def __init__(self, fitxer: str = I18N_FILE, idioma_defecte: str = "ca"):
        self.fitxer = fitxer
        self.idioma = idioma_defecte
        self.missatges: dict[str, dict[str, str]] = defaultdict(dict)
        self.carregar()

    def carregar(self):
        self.missatges.clear()
        if not os.path.exists(self.fitxer):
            return
        try:
            with open(self.fitxer, "r", encoding="utf-8") as f:
                for linia in f:
                    linia = linia.strip()
                    if not linia or linia.startswith("#") or linia.startswith("!"):
                        continue
                    sep = "=" if "=" in linia else (":" if ":" in linia else None)
                    if not sep:
                        continue
                    clau_completa, valor = linia.split(sep, 1)
                    clau_completa = clau_completa.strip()
                    valor = valor.lstrip().replace("\\n", "\n")
                    if "." in clau_completa:
                        clau_base, lang = clau_completa.rsplit(".", 1)
                        self.missatges[lang][clau_base] = valor
        except Exception:
            pass

    def set_idioma(self, codi_lang: str):
        self.idioma = codi_lang

    def tr(self, clau: str, *args) -> str:
        text = (
            self.missatges.get(self.idioma, {}).get(clau)
            or self.missatges.get("ca", {}).get(clau)
            or self.missatges.get("en", {}).get(clau)
            or clau
        )
        if args:
            try:
                return text.format(*args)
            except Exception:
                return text
        return text


I18N = GestorIdiomes()


def tr(clau: str, *args) -> str:
    return I18N.tr(clau, *args)


def carregar_config_yaml() -> dict:
    """Llegeix config.yaml de manera segura; si no existeix, retorna dict buit."""
    if not os.path.exists(CONFIG_FILE):
        return {}
    try:
        import yaml
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def normalitzar_text(text: str) -> str:
    """Elimina macrons, breus, converteix v->u, j->i i passa a minúscules."""
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


def extreure_tokens_tag(tag: str) -> set:
    if not tag:
        return set()
    return set(tag.replace('|', ';').split(';'))


def aplicar_grafia(forma: str, prefer_u: bool) -> str:
    if prefer_u and isinstance(forma, str):
        return forma.replace('v', 'u').replace('V', 'U')
    return forma


def detectar_preferencia_u(text_cercat: str, lemes_trobats: list, lemes_formes: dict) -> bool:
    t_low = text_cercat.lower()
    if 'v' in t_low:
        return False
    if 'u' in t_low:
        for l in lemes_trobats:
            if 'v' in l.lower():
                return True
            for f, _ in lemes_formes.get(l, []):
                if 'v' in f.lower():
                    return True
    return False


def escapar_latex(text: str) -> str:
    """Escapa caràcters especials per a codi LaTeX net."""
    if not text:
        return "---"
    reemplacos = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    res = str(text)
    for k, v in reemplacos.items():
        res = res.replace(k, v)
    return res


def html_a_text_pla(html: str) -> str:
    """Converteix un bloc HTML en text pla net i estructurat."""
    txt = re.sub(r'</tr>', '\n', html, flags=re.IGNORECASE)
    txt = re.sub(r'</t[dh]>', '\t', txt, flags=re.IGNORECASE)
    txt = re.sub(r'<br\s*/?>|</p>|</div>|</h[1-6]>|</li>', '\n', txt, flags=re.IGNORECASE)
    txt = re.sub(r'<[^>]+>', '', txt)
    txt = (
        txt.replace('&nbsp;', ' ')
        .replace('&amp;', '&')
        .replace('&lt;', '<')
        .replace('&gt;', '>')
        .replace('&quot;', '"')
        .replace('◄', '')
        .replace(tr("sent.selected.badge"), '')
    )
    linies = [re.sub(r'[ \t]+', ' ', l).strip() for l in txt.splitlines()]
    return "\n".join(l for l in linies if l)


# ==============================================================================
# MEMÒRIA CAU PERSISTENT DE GLOSSES TRADUÏDES A SQLITE
# ==============================================================================
def assegurar_taula_cache_glosses():
    """Crea la taula de memòria cau dins diccionari.db si encara no existeix."""
    if not os.path.exists(DB_FILE):
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS glosses_llm_cache (
                lema_clean TEXT NOT NULL,
                pos TEXT NOT NULL,
                llengua_desti TEXT NOT NULL,
                model_id TEXT NOT NULL,
                traduccio TEXT NOT NULL,
                data_creacio TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (lema_clean, pos, llengua_desti, model_id)
            );
        """)
        conn.commit()
        conn.close()
    except Exception:
        pass


def obtenir_glossa_cache(lema_clean: str, pos: str, llengua_desti: str, model_id: str) -> str | None:
    """Recupera la traducció desada per a aquest lema, categoria, llengua i versió exacta del model."""
    if not os.path.exists(DB_FILE) or not model_id:
        return None
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            SELECT traduccio FROM glosses_llm_cache
            WHERE lema_clean = ? AND pos = ? AND llengua_desti = ? AND model_id = ?
            LIMIT 1;
        """, (lema_clean, pos, llengua_desti.lower(), model_id))
        row = cur.fetchone()
        conn.close()
        return row[0] if row else None
    except Exception:
        return None


def desar_glossa_cache(lema_clean: str, pos: str, llengua_desti: str, model_id: str, traduccio: str):
    """Guarda a la base de dades la traducció generada pel model i versió actual."""
    if not os.path.exists(DB_FILE) or not model_id or not traduccio.strip():
        return
    try:
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            INSERT OR REPLACE INTO glosses_llm_cache (lema_clean, pos, llengua_desti, model_id, traduccio)
            VALUES (?, ?, ?, ?, ?);
        """, (lema_clean, pos, llengua_desti.lower(), model_id, traduccio.strip()))
        conn.commit()
        conn.close()
    except Exception:
        pass


def obtenir_instruccions_install_ollama() -> str:
    """Retorna les instruccions d'instal·lació d'Ollama adaptades al sistema operatiu."""
    sistema = platform.system()
    if sistema == "Darwin":  # macOS
        return (
            "<li>Download / Descarrega: <a href='https://ollama.com/download/mac'>ollama.com/download/mac</a> "
            "or Terminal: <code>brew install --cask ollama</code></li>"
            "<li>Open / Obre l'aplicació <b>Ollama</b> (Applications).</li>"
        )
    elif sistema == "Windows":
        return (
            "<li>Download / Descarrega <code>OllamaSetup.exe</code>: <a href='https://ollama.com/download/windows'>ollama.com/download/windows</a> "
            "or PowerShell: <code>winget install Ollama.Ollama</code></li>"
            "<li>Ollama will start automatically in the system tray.</li>"
        )
    else:  # Linux
        return (
            "<li>Terminal:<br><code>curl -fsSL https://ollama.com/install.sh | sh</code></li>"
            "<li>Ensure service is running: <code>systemctl status ollama</code> (or <code>ollama serve</code>).</li>"
        )


def verificar_estat_ollama(llm_cfg: dict) -> dict:
    """Comprova la disponibilitat d'Ollama de manera segura sense fallar mai si no està instal·lat."""
    if not os.path.exists(CONFIG_FILE) or not llm_cfg.get("actiu", True):
        return {
            "actiu": False,
            "url": llm_cfg.get("url", "http://localhost:11434"),
            "es_local": True,
            "connectat": False,
            "binari_instal_lat": False,
            "models_disponibles": [],
            "models_digests": {},
            "error": tr("llm.disabled.cfg")
        }

    url = llm_cfg.get("url", "http://localhost:11434").rstrip("/")
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    es_local = host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")

    # Comprovació multiplataforma de si el binari/app d'Ollama existeix al sistema
    binari_trobat = shutil.which("ollama") is not None
    if not binari_trobat and es_local:
        sistema = platform.system()
        if sistema == "Darwin" and os.path.exists("/Applications/Ollama.app"):
            binari_trobat = True
        elif sistema == "Windows":
            local_app = os.environ.get("LOCALAPPDATA", "")
            if local_app and os.path.exists(os.path.join(local_app, "Programs", "Ollama", "ollama.exe")):
                binari_trobat = True

    resultat = {
        "actiu": True,
        "url": url,
        "es_local": es_local,
        "connectat": False,
        "binari_instal_lat": binari_trobat if es_local else True,
        "models_disponibles": [],
        "models_digests": {},
        "error": ""
    }

    try:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            dades = json.loads(resp.read().decode("utf-8"))
            resultat["connectat"] = True
            resultat["binari_instal_lat"] = True
            models = dades.get("models", [])
            resultat["models_disponibles"] = [m["name"] for m in models]
            resultat["models_digests"] = {m["name"]: m.get("digest", "")[:16] for m in models}
    except Exception as e:
        resultat["error"] = str(e)

    return resultat


def resoldre_identificador_model(model_nom: str, models_digests: dict) -> str:
    """Retorna 'nom_model@digest' per distingir tant el nom com la versió exacta del model."""
    digest = models_digests.get(model_nom) or models_digests.get(f"{model_nom}:latest") or ""
    return f"{model_nom}@{digest}" if digest else model_nom


def enviar_peticio_chat_ollama(url: str, model: str, missatge: str, thinking: bool, temp: float, max_tokens: int, timeout: int = 300) -> str:
    """Envia una petició a /api/chat d'Ollama amb control de thinking i compatibilitat amb versions anteriors."""
    opcions = {
        "temperature": temp,
        "num_predict": max_tokens
    }
    payload_dict = {
        "model": model,
        "messages": [{"role": "user", "content": missatge}],
        "think": thinking,
        "stream": False,
        "options": opcions
    }

    req = urllib.request.Request(
        f"{url}/api/chat",
        data=json.dumps(payload_dict).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            dades = json.loads(resp.read().decode("utf-8"))
            return dades.get("message", {}).get("content", "")
    except urllib.error.HTTPError as he:
        if he.code == 400:
            payload_dict.pop("think", None)
            req_retry = urllib.request.Request(
                f"{url}/api/chat",
                data=json.dumps(payload_dict).encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            with urllib.request.urlopen(req_retry, timeout=timeout) as resp:
                dades = json.loads(resp.read().decode("utf-8"))
                return dades.get("message", {}).get("content", "")
        raise


def netejar_pensament_llm(text: str) -> str:
    """Elimina possibles etiquetes de pensament intern (<thought>, <think>, etc.)."""
    text_net = re.sub(r"<(?:thought|think)>.*?</(?:thought|think)>", "", text, flags=re.DOTALL | re.IGNORECASE)
    text_net = re.sub(r"<\|channel>thought.*?<channel\|>", "", text_net, flags=re.DOTALL | re.IGNORECASE)
    return text_net.strip()


# ==============================================================================
# FIL DE CÀRREGA I DESCÀRREGA AUTÒNOMA DEL MODEL DE SPACY / LATINCY
# ==============================================================================
class FilCarregaSpacy(QThread):
    progres = pyqtSignal(str)
    acabat = pyqtSignal(object, str)  # (nlp_object, nom_model)

    VERSIO_FALLBACK = "3.9.4"

    def __init__(self, cfg_spacy: dict):
        super().__init__()
        self.model_nom = cfg_spacy.get("model", "la_core_web_lg").strip()
        self.auto_install = cfg_spacy.get("auto_install", True)
        self.dir_models = os.path.join(obtenir_dir_base(), "models")
        self.desti_model = os.path.join(self.dir_models, self.model_nom)

    def _obtenir_url_whl_hf(self, nom_model: str) -> str:
        """Retorna la URL del .whl del model LatinCy des de Hugging Face."""
        api_hf = f"https://huggingface.co/api/models/latincy/{nom_model}"
        try:
            req = urllib.request.Request(api_hf, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=15) as resp:
                dades = json.loads(resp.read().decode("utf-8"))
                whls = sorted(
                    f["rfilename"]
                    for f in dades.get("siblings", [])
                    if f.get("rfilename", "").endswith(".whl")
                )
                if whls:
                    return f"https://huggingface.co/latincy/{nom_model}/resolve/main/{whls[-1]}"
        except Exception:
            pass
        nom_fitxer_whl = f"{nom_model}-{self.VERSIO_FALLBACK}-py3-none-any.whl"
        return f"https://huggingface.co/latincy/{nom_model}/resolve/main/{nom_fitxer_whl}"

    def _descarregar_i_extreure_whl(self, url: str, desti_dir: str, etiqueta_progres: str = ""):
        """Descarrega un .whl amb barra de progrés i l'extreu dins desti_dir."""
        import zipfile
        import tempfile

        fd, tmp_whl = tempfile.mkstemp(suffix=".whl")
        os.close(fd)
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                total_bytes = int(resp.headers.get("Content-Length", 0))
                descarregat = 0
                ultim_pct = -1
                with open(tmp_whl, "wb") as out_f:
                    while True:
                        bloc = resp.read(1024 * 128)
                        if not bloc:
                            break
                        out_f.write(bloc)
                        descarregat += len(bloc)
                        if etiqueta_progres and total_bytes > 0:
                            pct = int((descarregat / total_bytes) * 100)
                            if pct != ultim_pct and pct % 2 == 0:
                                ultim_pct = pct
                                mb_act = descarregat / (1024 * 1024)
                                mb_tot = total_bytes / (1024 * 1024)
                                self.progres.emit(f"⏳ {etiqueta_progres}: {pct}% ({mb_act:.1f}/{mb_tot:.1f} MB)...")

            if etiqueta_progres:
                self.progres.emit(f"⏳ Descomprimint '{self.model_nom}'...")
            with zipfile.ZipFile(tmp_whl, "r") as zf:
                zf.extractall(desti_dir)
        finally:
            if os.path.exists(tmp_whl):
                try:
                    os.remove(tmp_whl)
                except Exception:
                    pass

    def _registrar_uv_normalizer(self):
        """Registra la factory 'uv_normalizer' a spaCy mitjançant @Language.factory."""
        from spacy.language import Language
        if not Language.has_factory("uv_normalizer"):
            @Language.factory("uv_normalizer", default_config={"method": "uv"})
            def _uv_normalizer(nlp, name, method: str = "uv", **kwargs):
                def _proc(doc):
                    for token in doc:
                        val = token.norm_ if token.norm_ else token.text
                        if method == "vu":
                            val = val.replace("u", "v").replace("U", "V").replace("j", "i").replace("J", "I")
                        else:
                            val = val.replace("v", "u").replace("V", "U").replace("j", "i").replace("J", "I")
                        token.norm_ = val
                    return doc
                return _proc

    def run(self):
        import importlib
        try:
            import spacy
        except ImportError:
            self.progres.emit("⚠ Falta 'spacy' (mode SQLite actiu).")
            self.acabat.emit(None, "")
            return

        try:
            os.makedirs(self.desti_model, exist_ok=True)
            if self.desti_model not in sys.path:
                sys.path.insert(0, self.desti_model)

            # 1. Comprovem si el model ja és a models/<nom_model> o al sistema Python
            model_disponible = os.path.exists(os.path.join(self.desti_model, self.model_nom))
            if not model_disponible:
                try:
                    importlib.import_module(self.model_nom)
                    model_disponible = True
                except ModuleNotFoundError:
                    model_disponible = False

            if not model_disponible:
                if not self.auto_install:
                    self.progres.emit(f"ℹ Model '{self.model_nom}' no instal·lat (auto_install desactivat).")
                    self.acabat.emit(None, "")
                    return
                self.progres.emit(f"⏳ Descarregant '{self.model_nom}'...")
                url_whl = self._obtenir_url_whl_hf(self.model_nom)
                self._descarregar_i_extreure_whl(url_whl, self.desti_model, f"Descarregant '{self.model_nom}'")

            # 2. Comprovem i descarreguem 'la-latincy-lookups' si no es pot importar
            importlib.invalidate_caches()
            try:
                importlib.import_module("la_latincy_lookups")
            except ModuleNotFoundError:
                if self.auto_install:
                    self.progres.emit("⏳ Descarregant 'la-latincy-lookups'...")
                    req_pypi = urllib.request.Request(
                        "https://pypi.org/pypi/la-latincy-lookups/json",
                        headers={"User-Agent": "Mozilla/5.0"}
                    )
                    dades_pypi = json.loads(urllib.request.urlopen(req_pypi, timeout=20).read().decode("utf-8"))
                    whls_lk = [u["url"] for u in dades_pypi.get("urls", []) if u.get("filename", "").endswith(".whl")]
                    if whls_lk:
                        self._descarregar_i_extreure_whl(whls_lk[-1], self.desti_model)

            # 3. Registrem uv_normalizer abans de carregar el model
            self._registrar_uv_normalizer()

            # 4. Carreguem el model LatinCy
            self.progres.emit(f"LatinCy ({self.model_nom})...")
            importlib.invalidate_caches()
            mod = importlib.import_module(self.model_nom)
            nlp = mod.load() if hasattr(mod, "load") else spacy.load(self.model_nom)
            self.acabat.emit(nlp, self.model_nom)

        except Exception as e:
            self.progres.emit(f"⚠ Error LatinCy ({self.model_nom}): {e}")
            self.acabat.emit(None, "")


# ==============================================================================
# FIL DE TRADUCCIÓ ASÍNCRONA AMB OLLAMA (Oracions completes)
# ==============================================================================
class FilTraduccioOllama(QThread):
    progres = pyqtSignal(str)
    acabat = pyqtSignal(str, str)  # (text_resposta, error_msg)

    def __init__(self, oracio: str, llm_cfg: dict, text_analisi: str = ""):
        super().__init__()
        self.oracio = oracio
        self.llm_cfg = llm_cfg
        self.text_analisi = text_analisi.strip()
        self.prompt_enviat = ""

    def _model_existeix(self, url: str, model_objectiu: str) -> bool:
        req = urllib.request.Request(f"{url}/api/tags", method="GET")
        with urllib.request.urlopen(req, timeout=5) as resp:
            dades = json.loads(resp.read().decode("utf-8"))
            instal_lats = [m["name"] for m in dades.get("models", [])]
            return (
                model_objectiu in instal_lats
                or f"{model_objectiu}:latest" in instal_lats
            )

    def _descarregar_model(self, url: str, model: str):
        self.progres.emit(f"⏳ Pulling '{model}'...")
        payload = json.dumps({"name": model, "stream": True}).encode("utf-8")
        req = urllib.request.Request(
            f"{url}/api/pull",
            data=payload,
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with urllib.request.urlopen(req, timeout=None) as resp:
            for linia in resp:
                if not linia:
                    continue
                estat = json.loads(linia.decode("utf-8"))
                if "error" in estat:
                    raise RuntimeError(estat["error"])
                status_txt = estat.get("status", "")
                total = estat.get("total", 0)
                completed = estat.get("completed", 0)
                if total > 0:
                    pct = int((completed / total) * 100)
                    self.progres.emit(f"⏳ '{model}': {status_txt} ({pct}%)")
                elif status_txt:
                    self.progres.emit(f"⏳ '{model}': {status_txt}")

    def run(self):
        url = self.llm_cfg.get("url", "http://localhost:11434").rstrip("/")
        model = self.llm_cfg.get("model", "gemma4:12b")
        auto_pull = self.llm_cfg.get("auto_pull", True)
        thinking = bool(self.llm_cfg.get("thinking", False))
        temp = self.llm_cfg.get("temperature", 0.1)
        max_tok = self.llm_cfg.get("max_tokens", 1500)

        host = (urlparse(url).hostname or "").lower()
        es_local = host in ("localhost", "127.0.0.1", "::1", "0.0.0.0")

        try:
            if not self._model_existeix(url, model):
                if es_local and auto_pull:
                    self._descarregar_model(url, model)
                elif es_local:
                    self.acabat.emit("", f"Model '{model}' not found (auto_pull=false). Run: ollama pull {model}")
                    return
                else:
                    self.acabat.emit("", f"Remote server ({url}) does not have model '{model}'.")
                    return

            bloc_analisi = ""
            if self.text_analisi:
                plantilla_an = self.llm_cfg.get("plantilla_analisi", "Preliminary analysis:\n{taula_analisi}")
                bloc_analisi = plantilla_an.format(taula_analisi=self.text_analisi)

            plantilla_prompt = self.llm_cfg.get("prompt", 'Translate: "{text}"')
            prompt_final = plantilla_prompt.format(bloc_analisi=bloc_analisi, text=self.oracio)
            self.prompt_enviat = prompt_final

            self.progres.emit(f"Ollama ({model})...")

            text_sortida = enviar_peticio_chat_ollama(
                url=url,
                model=model,
                missatge=prompt_final,
                thinking=thinking,
                temp=temp,
                max_tokens=max_tok,
                timeout=300
            )
            self.acabat.emit(netejar_pensament_llm(text_sortida), "")

        except urllib.error.URLError as ue:
            self.acabat.emit("", f"Ollama ({url}): {ue.reason}")
        except Exception as e:
            self.acabat.emit("", f"Ollama ({model}): {e}")


# ==============================================================================
# FIL AUXILIAR PER TRADUIR GLOSSES LÈXIQUES AMB MEMÒRIA CAU PERSISTENT A SQLITE
# ==============================================================================
class FilTraduccioGlossaOllama(QThread):
    glossa_traduida = pyqtSignal(int, int, str, bool)

    def __init__(self, id_cerca: int, tasques: list[dict], llm_cfg: dict, model_id: str):
        super().__init__()
        self.id_cerca = id_cerca
        self.tasques = tasques
        self.llm_cfg = llm_cfg
        self.model_id = model_id

    def run(self):
        url = self.llm_cfg.get("url", "http://localhost:11434").rstrip("/")
        model = self.llm_cfg.get("model", "gemma4:12b")
        llengua = self.llm_cfg.get("llengua_desti", "català")
        plantilla = self.llm_cfg.get(
            "prompt_glossa",
            "Translate the following Latin word into {llengua} given its category and English gloss. "
            "Reply ONLY with the direct equivalents in {llengua}:\n"
            "Latin: {lema}\nCategory: {categoria}\nEnglish: {glossa_en}"
        )

        try:
            req_tags = urllib.request.Request(f"{url}/api/tags", method="GET")
            with urllib.request.urlopen(req_tags, timeout=2.0) as resp:
                dades = json.loads(resp.read().decode("utf-8"))
                instal_lats = [m["name"] for m in dades.get("models", [])]
                if model not in instal_lats and f"{model}:latest" not in instal_lats:
                    for t in self.tasques:
                        self.glossa_traduida.emit(self.id_cerca, t["idx"], "", False)
                    return
        except Exception:
            for t in self.tasques:
                self.glossa_traduida.emit(self.id_cerca, t["idx"], "", False)
            return

        for t in self.tasques:
            if self.isInterruptionRequested():
                return
            try:
                prompt_glossa = plantilla.format(
                    llengua=llengua,
                    lema=t["lema"],
                    categoria=t["categoria"],
                    glossa_en=t["glossa_en"] or "(not available in local database)"
                )
                text_brut = enviar_peticio_chat_ollama(
                    url=url,
                    model=model,
                    missatge=prompt_glossa,
                    thinking=False,
                    temp=0.1,
                    max_tokens=180,
                    timeout=60
                )
                res_text = netejar_pensament_llm(text_brut).strip('"').strip("'")
                if res_text:
                    desar_glossa_cache(t["lema_clean"], t["pos_whit"], llengua, self.model_id, res_text)
                self.glossa_traduida.emit(self.id_cerca, t["idx"], res_text, False)
            except Exception:
                self.glossa_traduida.emit(self.id_cerca, t["idx"], "", False)


# ==============================================================================
# MOTORS DE FLEXIÓ CANÒNICA (Substantius, Adjectius, Verbs, Pronoms)
# ==============================================================================
class MotorNomsCanonic:
    ORDRE_CASOS = ["NOM", "VOC", "ACC", "GEN", "DAT", "ABL"]

    @classmethod
    def nom_cas(cls, codi: str) -> str:
        return tr(f"case.{codi}")

    @classmethod
    def extreure_dades_nom(cls, lema, formes, prefer_u=False):
        nom_sg, gen_sg, nom_pl, acc_sg = [], [], [], []
        generes_detectats = set()

        for f, tag in formes:
            toks = extreure_tokens_tag(tag)
            f_adapt = aplicar_grafia(f, prefer_u)
            if "SG" in toks and "NOM" in toks and f_adapt not in nom_sg: nom_sg.append(f_adapt)
            if "SG" in toks and "GEN" in toks and f_adapt not in gen_sg: gen_sg.append(f_adapt)
            if "PL" in toks and "NOM" in toks and f_adapt not in nom_pl: nom_pl.append(f_adapt)
            if "SG" in toks and "ACC" in toks and f_adapt not in acc_sg: acc_sg.append(f_adapt)

            for p in toks:
                if p in ["MASC", "FEM", "NEUT", "MASC+FEM", "NEUT+MASC"]:
                    generes_detectats.add(p)

        lema_adapt = aplicar_grafia(lema, prefer_u)
        text_nom = "/".join(nom_sg) if nom_sg else lema_adapt
        text_gen = "/".join(gen_sg) if gen_sg else "-"
        enunciat = f"{text_nom}, {text_gen}"

        nom_net = normalitzar_text(nom_sg[0]) if nom_sg else normalitzar_text(lema)
        gen_net = normalitzar_text(gen_sg[0]) if gen_sg else ""

        declinacio = tr("decl.unknown")
        genere = tr("gen.unknown")

        if gen_net:
            if gen_net.endswith("ae"):
                declinacio = tr("decl.1")
                genere = tr("gen.FEM")
            elif gen_net.endswith("ei"):
                declinacio = tr("decl.5")
                genere = tr("gen.MF") if nom_net == "dies" else tr("gen.FEM")
            elif gen_net.endswith("i"):
                declinacio = tr("decl.2")
                genere = tr("gen.NEUT") if (nom_net.endswith("um") or (acc_sg and normalitzar_text(acc_sg[0]) == nom_net)) else tr("gen.MASC")
            elif gen_net.endswith("is"):
                declinacio = tr("decl.3")
                es_neutre_3a = False
                if nom_sg and acc_sg and normalitzar_text(nom_sg[0]) == normalitzar_text(acc_sg[0]):
                    es_neutre_3a = True
                elif nom_pl and any(normalitzar_text(p).endswith(("a", "ia")) for p in nom_pl):
                    es_neutre_3a = True
                genere = tr("gen.NEUT") if es_neutre_3a else tr("gen.MF")
            elif gen_net.endswith("us"):
                declinacio = tr("decl.4")
                genere = tr("gen.NEUT") if nom_net.endswith("u") else tr("gen.MASC")

        if generes_detectats:
            map_gen = {
                "MASC": tr("gen.MASC"),
                "FEM": tr("gen.FEM"),
                "NEUT": tr("gen.NEUT"),
                "MASC+FEM": tr("gen.MF"),
                "NEUT+MASC": f"{tr('tbl.masc')}/{tr('tbl.neut')}"
            }
            genere = " / ".join(map_gen.get(g, g) for g in generes_detectats)

        return {"enunciat": enunciat, "categoria": tr("cat.noun"), "declinacio": declinacio, "genere": genere}

    @classmethod
    def _recollir_dades(cls, formes, prefer_u=False):
        sing = {c: [] for c in cls.ORDRE_CASOS}
        plur = {c: [] for c in cls.ORDRE_CASOS}
        for f, tag in formes:
            toks = extreure_tokens_tag(tag)
            cas = next((c for c in cls.ORDRE_CASOS if c in toks), None)
            num = "SG" if "SG" in toks else ("PL" if "PL" in toks else None)
            if cas and num:
                target = sing if num == "SG" else plur
                f_adapt = aplicar_grafia(f, prefer_u)
                if f_adapt not in target[cas]:
                    target[cas].append(f_adapt)
        return sing, plur

    @classmethod
    def generar_taula_html(cls, formes, forma_cercada="", prefer_u=False):
        sing, plur = cls._recollir_dades(formes, prefer_u)
        cercada_net = normalitzar_text(forma_cercada)

        def cel_la(llista):
            if not llista: return "<span style='color: #8c959f;'>—</span>"
            res = []
            for item in llista:
                if cercada_net and normalitzar_text(item) == cercada_net:
                    res.append(f"<span style='background-color: #fff3cd; color: #856404; font-weight: bold; padding: 3px 6px; border-radius: 4px;'>{item} ◄</span>")
                else:
                    res.append(f"<b>{item}</b>")
            return ", ".join(res)

        html = (
            "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: center; font-family: Segoe UI, sans-serif; font-size: 14px; margin-bottom: 25px;'>"
            f"<tr style='background-color: #f1f8ff; color: #0366d6;'><th style='width: 20%;'>{tr('tbl.case')}</th><th style='width: 40%;'>{tr('tbl.sg')}</th><th style='width: 40%;'>{tr('tbl.pl')}</th></tr>"
        )
        for c in cls.ORDRE_CASOS:
            html += f"<tr><td style='background-color: #fafbfc; text-align: left; padding-left: 12px;'><b>{cls.nom_cas(c)}</b></td><td>{cel_la(sing[c])}</td><td>{cel_la(plur[c])}</td></tr>"
        html += "</table>"
        return html

    @classmethod
    def generar_latex(cls, info_nom, formes, prefer_u=False):
        sing, plur = cls._recollir_dades(formes, prefer_u)
        linies = [
            f"\\subsection*{{{escapar_latex(info_nom['enunciat'])} ({escapar_latex(info_nom['genere'])} — {escapar_latex(info_nom['declinacio'])})}}",
            "\\begin{tabular}{|l|c|c|}",
            "\\hline",
            f"\\textbf{{{escapar_latex(tr('tbl.case'))}}} & \\textbf{{{escapar_latex(tr('tbl.sg'))}}} & \\textbf{{{escapar_latex(tr('tbl.pl'))}}} \\\\",
            "\\hline"
        ]
        for c in cls.ORDRE_CASOS:
            s_txt = ", ".join(escapar_latex(x) for x in sing[c]) if sing[c] else "---"
            p_txt = ", ".join(escapar_latex(x) for x in plur[c]) if plur[c] else "---"
            linies.append(f"\\textbf{{{escapar_latex(cls.nom_cas(c))}}} & {s_txt} & {p_txt} \\\\")
        linies.extend(["\\hline", "\\end{tabular}", ""])
        return "\n".join(linies)


class MotorAdjectiusCanonic:
    ORDRE_CASOS = ["NOM", "VOC", "ACC", "GEN", "DAT", "ABL"]

    @classmethod
    def nom_cas(cls, codi: str) -> str:
        return tr(f"case.{codi}")

    @classmethod
    def extreure_dades_adjectiu(cls, lema, totes_formes, prefer_u=False):
        formes_adj = [(f, t) for f, t in totes_formes if "ADJ" in extreure_tokens_tag(t)] or totes_formes
        nom_masc, nom_fem, nom_neut, nom_mf, nom_mfn = [], [], [], [], []
        gen_sg = []

        for f, tag in formes_adj:
            toks = extreure_tokens_tag(tag)
            f_adapt = aplicar_grafia(f, prefer_u)
            if "SG" in toks and "NOM" in toks:
                if "MASC+FEM+NEUT" in toks and f_adapt not in nom_mfn: nom_mfn.append(f_adapt)
                elif "MASC+FEM" in toks and f_adapt not in nom_mf: nom_mf.append(f_adapt)
                elif "MASC" in toks and f_adapt not in nom_masc: nom_masc.append(f_adapt)
                elif "FEM" in toks and f_adapt not in nom_fem: nom_fem.append(f_adapt)
                elif "NEUT" in toks and f_adapt not in nom_neut: nom_neut.append(f_adapt)
            if "SG" in toks and "GEN" in toks and f_adapt not in gen_sg: gen_sg.append(f_adapt)

        if nom_masc and nom_fem and nom_neut:
            tipus = 3
            enunciat = f"{nom_masc[0]}, {nom_fem[0]}, {nom_neut[0]}"
            desc = tr("adj.3.desc")
            paradigma = tr("adj.3.par1") if normalitzar_text(nom_neut[0]).endswith("um") else tr("adj.3.par2")
        elif nom_mf and nom_neut:
            tipus = 2
            enunciat = f"{nom_mf[0]}, {nom_neut[0]}"
            desc = tr("adj.2.desc")
            paradigma = tr("adj.2.par")
        elif nom_mfn:
            tipus = 1
            gen_str = gen_sg[0] if gen_sg else "-"
            enunciat = f"{nom_mfn[0]}, {gen_str}"
            desc = tr("adj.1.desc")
            paradigma = tr("adj.3.par2")
        else:
            tipus = 3
            enunciat = aplicar_grafia(lema, prefer_u)
            desc = tr("cat.adj")
            paradigma = tr("cat.adj")

        return {"tipus": tipus, "enunciat": enunciat, "desc": desc, "paradigma": paradigma, "categoria": tr("cat.adj"), "formes_adj": formes_adj}

    @classmethod
    def _recollir_dades(cls, formes, prefer_u=False):
        dades = {"SG": {"MASC": defaultdict(list), "FEM": defaultdict(list), "NEUT": defaultdict(list), "MF": defaultdict(list)},
                 "PL": {"MASC": defaultdict(list), "FEM": defaultdict(list), "NEUT": defaultdict(list), "MF": defaultdict(list)}}
        for f, tag in formes:
            toks = extreure_tokens_tag(tag)
            cas = next((c for c in cls.ORDRE_CASOS if c in toks), None)
            num = "SG" if "SG" in toks else ("PL" if "PL" in toks else None)
            if not cas or not num: continue
            f_adapt = aplicar_grafia(f, prefer_u)

            if "MASC+FEM+NEUT" in toks:
                for k in ["MASC", "FEM", "NEUT", "MF"]: dades[num][k][cas].append(f_adapt)
            elif "MASC+FEM" in toks:
                for k in ["MASC", "FEM", "MF"]: dades[num][k][cas].append(f_adapt)
            elif "MASC" in toks:
                dades[num]["MASC"][cas].append(f_adapt)
                dades[num]["MF"][cas].append(f_adapt)
            elif "FEM" in toks:
                dades[num]["FEM"][cas].append(f_adapt)
                dades[num]["MF"][cas].append(f_adapt)
            elif "NEUT" in toks:
                dades[num]["NEUT"][cas].append(f_adapt)
        return dades

    @classmethod
    def generar_taula_html(cls, info_adj, forma_cercada="", prefer_u=False):
        tipus = info_adj["tipus"]
        dades = cls._recollir_dades(info_adj["formes_adj"], prefer_u)
        cercada_net = normalitzar_text(forma_cercada)

        def cel_la(llista):
            unics = list(dict.fromkeys(llista))
            if not unics: return "<span style='color: #8c959f;'>—</span>"
            res = []
            for item in unics:
                if cercada_net and normalitzar_text(item) == cercada_net:
                    res.append(f"<span style='background-color: #fff3cd; color: #856404; font-weight: bold; padding: 3px 6px; border-radius: 4px;'>{item} ◄</span>")
                else:
                    res.append(f"<b>{item}</b>")
            return ", ".join(res)

        html = ""
        for num_code, num_titol in [("SG", tr("tbl.sg")), ("PL", tr("tbl.pl"))]:
            html += f"<h4 style='color: #24292e; margin-top: 14px; margin-bottom: 6px;'>{num_titol}</h4>"
            html += "<table border='1' cellpadding='7' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: center; font-family: Segoe UI, sans-serif; font-size: 14px; margin-bottom: 20px;'>"
            if tipus == 3:
                html += f"<tr style='background-color: #f1f8ff; color: #0366d6;'><th style='width: 19%;'>{tr('tbl.case')}</th><th style='width: 27%;'>{tr('tbl.masc')}</th><th style='width: 27%;'>{tr('tbl.fem')}</th><th style='width: 27%;'>{tr('tbl.neut')}</th></tr>"
                for c in cls.ORDRE_CASOS:
                    html += f"<tr><td style='background-color: #fafbfc; text-align: left; padding-left: 10px;'><b>{cls.nom_cas(c)}</b></td><td>{cel_la(dades[num_code]['MASC'][c])}</td><td>{cel_la(dades[num_code]['FEM'][c])}</td><td>{cel_la(dades[num_code]['NEUT'][c])}</td></tr>"
            else:
                html += f"<tr style='background-color: #f1f8ff; color: #0366d6;'><th style='width: 20%;'>{tr('tbl.case')}</th><th style='width: 40%;'>{tr('tbl.mf')}</th><th style='width: 40%;'>{tr('tbl.neut')}</th></tr>"
                for c in cls.ORDRE_CASOS:
                    html += f"<tr><td style='background-color: #fafbfc; text-align: left; padding-left: 10px;'><b>{cls.nom_cas(c)}</b></td><td>{cel_la(dades[num_code]['MF'][c])}</td><td>{cel_la(dades[num_code]['NEUT'][c])}</td></tr>"
            html += "</table>"
        return html

    @classmethod
    def generar_latex(cls, info_adj, prefer_u=False):
        tipus = info_adj["tipus"]
        dades = cls._recollir_dades(info_adj["formes_adj"], prefer_u)

        def fmt(llista):
            unics = list(dict.fromkeys(llista))
            return ", ".join(escapar_latex(x) for x in unics) if unics else "---"

        linies = [f"\\subsection*{{{escapar_latex(info_adj['enunciat'])} ({escapar_latex(info_adj['desc'])})}}"]
        for num_code, num_titol in [("SG", tr("tbl.sg")), ("PL", tr("tbl.pl"))]:
            linies.append(f"\\subsubsection*{{{escapar_latex(num_titol)}}}")
            if tipus == 3:
                linies.extend([
                    "\\begin{tabular}{|l|c|c|c|}",
                    "\\hline",
                    f"\\textbf{{{escapar_latex(tr('tbl.case'))}}} & \\textbf{{{escapar_latex(tr('tbl.masc'))}}} & \\textbf{{{escapar_latex(tr('tbl.fem'))}}} & \\textbf{{{escapar_latex(tr('tbl.neut'))}}} \\\\",
                    "\\hline"
                ])
                for c in cls.ORDRE_CASOS:
                    linies.append(f"\\textbf{{{escapar_latex(cls.nom_cas(c))}}} & {fmt(dades[num_code]['MASC'][c])} & {fmt(dades[num_code]['FEM'][c])} & {fmt(dades[num_code]['NEUT'][c])} \\\\")
            else:
                linies.extend([
                    "\\begin{tabular}{|l|c|c|}",
                    "\\hline",
                    f"\\textbf{{{escapar_latex(tr('tbl.case'))}}} & \\textbf{{{escapar_latex(tr('tbl.mf'))}}} & \\textbf{{{escapar_latex(tr('tbl.neut'))}}} \\\\",
                    "\\hline"
                ])
                for c in cls.ORDRE_CASOS:
                    linies.append(f"\\textbf{{{escapar_latex(cls.nom_cas(c))}}} & {fmt(dades[num_code]['MF'][c])} & {fmt(dades[num_code]['NEUT'][c])} \\\\")
            linies.extend(["\\hline", "\\end{tabular}", ""])
        return "\n".join(linies)


class MotorVerbsCanonic:
    PERSONES = [
        ("1;SG", "1a Sg. (egō)", {"1", "SG"}), ("2;SG", "2a Sg. (tū)", {"2", "SG"}), ("3;SG", "3a Sg. (is/ea)", {"3", "SG"}),
        ("1;PL", "1a Pl. (nōs)", {"1", "PL"}), ("2;PL", "2a Pl. (vōs)", {"2", "PL"}), ("3;PL", "3a Pl. (iī/eae)", {"3", "PL"})
    ]
    TEMPS_CONFIG = [
        ("IND_PRS_ACT", {"IND", "PRS", "ACT"}),
        ("IND_IPFV_ACT", {"IND", "IPFV", "ACT"}),
        ("IND_FUT_ACT", {"IND", "FUT", "ACT"}),
        ("IND_PFV_ACT", {"IND", "PFV", "ACT"}),
        ("IND_PRF_ACT", {"IND", "PRF", "ACT"}),
        ("IND_FUTPRF_ACT", {"IND", "FUT", "PRF", "ACT"}),
        ("IND_PRS_PASS", {"IND", "PRS", "PASS"}),
        ("IND_IPFV_PASS", {"IND", "IPFV", "PASS"}),
        ("IND_FUT_PASS", {"IND", "FUT", "PASS"}),
        ("SBJV_PRS_ACT", {"SBJV", "PRS", "ACT"}),
        ("SBJV_IPFV_ACT", {"SBJV", "IPFV", "ACT"}),
        ("SBJV_PFV_ACT", {"SBJV", "PFV", "ACT"}),
        ("SBJV_PRF_ACT", {"SBJV", "PRF", "ACT"}),
        ("SBJV_PRS_PASS", {"SBJV", "PRS", "PASS"}),
        ("SBJV_IPFV_PASS", {"SBJV", "IPFV", "PASS"}),
        ("IMP_PRS_ACT", {"IMP", "PRS", "ACT"}),
        ("IMP_FUT_ACT", {"IMP", "FUT", "ACT"}),
    ]
    PARADIGMA_SUM = {
        "enunciat": "sum, es, esse, fuī",
        "formes": {
            "IND_PRS_ACT": ["sum", "es", "est", "sumus", "estis", "sunt"],
            "IND_IPFV_ACT": ["eram", "erās", "erat", "erāmus", "erātis", "erant"],
            "IND_FUT_ACT": ["erō", "eris", "erit", "erimus", "eritis", "erunt"],
            "IND_PFV_ACT": ["fuī", "fuistī", "fuit", "fuimus", "fuistis", "fuērunt, fuēre"],
            "IND_PRF_ACT": ["fueram", "fuerās", "fuerat", "fuerāmus", "fuerātis", "fuerant"],
            "IND_FUTPRF_ACT": ["fuerō", "fueris", "fuerit", "fuerimus", "fueritis", "fuerint"],
            "SBJV_PRS_ACT": ["sim", "sīs", "sit", "sīmus", "sītis", "sint"],
            "SBJV_IPFV_ACT": ["essem", "essēs", "esset", "essēmus", "essētis", "essent"],
            "SBJV_PFV_ACT": ["fuerim", "fuerīs", "fuerit", "fuerīmus", "fuerītis", "fuerint"],
            "SBJV_PRF_ACT": ["fuissem", "fuissēs", "fuisset", "fuissēmus", "fuissētis", "fuissent"]
        },
        "infinitius": {"Present (Act.)": "esse", "Perfet (Act.)": "fuisse", "Futur (Act.)": "futūrum esse, fore"},
        "participis": {"Futur (Act.)": "futūrus, -a, -um"}
    }

    @classmethod
    def nom_temps(cls, t_id: str) -> str:
        return tr(f"tense.{t_id}")

    @classmethod
    def extreure_dades_verb(cls, lema, totes_formes, prefer_u=False):
        c_lema = normalitzar_text(lema)
        if c_lema in ["sum", "esse", "fui"]:
            return {"enunciat": cls.PARADIGMA_SUM["enunciat"], "conjugacio": tr("conj.sum"), "categoria": tr("cat.verb"), "es_sum": True}

        formes_verb = [f for f in totes_formes if any(v in extreure_tokens_tag(f[1]) for v in ["V", "IND", "SBJV", "IMP", "NFIN", "PTCP", "V.PTCP", "V.MSDR"])] or totes_formes
        p1_prs, p2_prs, inf_prs, p1_pfv, supi = [], [], [], [], []

        for f, tag in formes_verb:
            toks = extreure_tokens_tag(tag)
            f_adapt = aplicar_grafia(f, prefer_u)
            if {"IND", "PRS", "ACT", "1", "SG"}.issubset(toks) and f_adapt not in p1_prs: p1_prs.append(f_adapt)
            if {"IND", "PRS", "ACT", "2", "SG"}.issubset(toks) and f_adapt not in p2_prs: p2_prs.append(f_adapt)
            if ("NFIN" in toks or "INF" in toks) and "PRS" in toks and ("ACT" in toks or "PASS" not in toks):
                if f_adapt not in inf_prs and f_adapt.endswith(("re", "rī", "ī")): inf_prs.append(f_adapt)
            if {"IND", "PFV", "ACT", "1", "SG"}.issubset(toks) and f_adapt not in p1_pfv: p1_pfv.append(f_adapt)
            if ("LGSPEC1" in toks or "SUPINE" in toks) and ("ACC" in toks or f_adapt.endswith("um")):
                if f_adapt not in supi and f_adapt.endswith("um"): supi.append(f_adapt)

        forma_1 = p1_prs[0] if p1_prs else aplicar_grafia(lema, prefer_u)
        forma_2 = p2_prs[0] if p2_prs else "-"
        forma_inf = inf_prs[0] if inf_prs else "-"
        forma_pfv = p1_pfv[0] if p1_pfv else "-"
        forma_sup = supi[0] if supi else "-"

        inf_net = normalitzar_text(forma_inf)
        f2_net = normalitzar_text(forma_2)
        if inf_net.endswith("are") or f2_net.endswith("as"): conjugacio = tr("conj.1")
        elif inf_net.endswith("ere") and f2_net.endswith("es"): conjugacio = tr("conj.2")
        elif inf_net.endswith("ire") or (f2_net.endswith("is") and inf_net.endswith("ire")): conjugacio = tr("conj.4")
        elif inf_net.endswith(("ere", "i")):
            conjugacio = tr("conj.3m") if (forma_1.endswith("iō") or normalitzar_text(forma_1).endswith("io")) else tr("conj.3")
        else: conjugacio = tr("conj.reg")

        enunciat = f"{forma_1}, {forma_2}, {forma_inf}, {forma_pfv}, {forma_sup}"
        return {"enunciat": enunciat, "conjugacio": conjugacio, "categoria": tr("cat.verb"), "es_sum": False, "formes_verb": formes_verb}

    @classmethod
    def _recollir_dades(cls, info_v, prefer_u=False):
        formes = info_v["formes_verb"]
        matriu_temps = defaultdict(lambda: defaultdict(list))
        infinitius, participis, supins, gerundis = defaultdict(list), defaultdict(list), defaultdict(list), defaultdict(list)

        for f, tag in formes:
            toks = extreure_tokens_tag(tag)
            f_adapt = aplicar_grafia(f, prefer_u)
            p_code = next((p_id for p_id, _, p_req in cls.PERSONES if p_req.issubset(toks)), None)
            if p_code:
                for t_id, t_req in cls.TEMPS_CONFIG:
                    if t_id in ["IND_FUT_ACT", "IND_FUT_PASS"]:
                        if t_req.issubset(toks) and "PRF" not in toks and f_adapt not in matriu_temps[t_id][p_code]:
                            matriu_temps[t_id][p_code].append(f_adapt)
                    elif t_id == "IND_PRF_ACT":
                        if t_req.issubset(toks) and "FUT" not in toks and f_adapt not in matriu_temps[t_id][p_code]:
                            matriu_temps[t_id][p_code].append(f_adapt)
                    else:
                        if t_req.issubset(toks) and f_adapt not in matriu_temps[t_id][p_code]:
                            matriu_temps[t_id][p_code].append(f_adapt)

            if "NFIN" in toks or "INF" in toks:
                veu = "Pass." if "PASS" in toks else "Act."
                temps = "Perf." if ("PFV" in toks or "PST" in toks) else ("Fut." if "FUT" in toks else "Praes.")
                k = f"{temps} ({veu})"
                if f_adapt not in infinitius[k]: infinitius[k].append(f_adapt)

            if "PTCP" in toks or "V.PTCP" in tag:
                if ("NOM" in toks and "SG" in toks and ("MASC" in toks or "MASC+FEM" in toks or "MASC+FEM+NEUT" in toks)) or tag.endswith(("PTCP;PASS;PST;PFV", "PTCP;ACT;FUT")):
                    veu = "Pass. / Ger." if ("PASS" in toks and "FUT" in toks) else ("Pass." if "PASS" in toks else "Act.")
                    temps = "Perf." if ("PFV" in toks or "PST" in toks) else ("Fut." if "FUT" in toks else "Praes.")
                    k = f"{temps} ({veu})"
                    if f_adapt not in participis[k]: participis[k].append(f_adapt)

            if "LGSPEC1" in toks:
                cas = f"{tr('case.ACC')} (-um)" if "ACC" in toks else f"{tr('case.ABL')} (-ū)"
                if f_adapt not in supins[cas]: supins[cas].append(f_adapt)

            if "V.MSDR" in tag and "LGSPEC1" not in toks and "PTCP" not in toks:
                cas = tr("case.GEN") if "GEN" in toks else (f"{tr('case.DAT')}/{tr('case.ABL')}" if ("DAT" in toks or "ABL" in toks) else tr("case.ACC"))
                if f_adapt not in gerundis[cas]: gerundis[cas].append(f_adapt)

        return matriu_temps, infinitius, participis, supins, gerundis

    @classmethod
    def generar_taula_html(cls, info_v, forma_cercada="", prefer_u=False):
        cercada_net = normalitzar_text(forma_cercada)
        if info_v.get("es_sum"):
            def cel_la_sum(item):
                if not item: return "—"
                if cercada_net and normalitzar_text(item) == cercada_net:
                    return f"<span style='background-color: #fff3cd; color: #856404; font-weight: bold; padding: 2px 4px; border-radius: 3px;'>{item} ◄</span>"
                return f"<b>{item}</b>"

            html = (
                f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; padding: 12px; border-radius: 6px; margin-bottom: 15px;'>"
                f"<p style='margin: 0; font-size: 15px;'><b>{tr('verb.enunciat')}</b> <span style='font-size: 18px; color: #0366d6;'><b>{cls.PARADIGMA_SUM['enunciat']}</b></span> — <i>{tr('conj.sum')}</i></p></div>"
                f"<h3>{tr('verb.personal.title')}</h3><div style='display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;'>"
            )
            for t_id, lf in cls.PARADIGMA_SUM["formes"].items():
                html += f"<div style='border: 1px solid #dcdcdc; border-radius: 6px; padding: 8px; background-color: #ffffff;'><h4 style='margin: 4px 0 8px 0; color: #0366d6; font-size: 13px;'>{cls.nom_temps(t_id)}</h4><table border='1' cellpadding='4' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: center; font-size: 12px;'><tr style='background-color: #f6f8fa;'><th>{tr('verb.person')}</th><th>{tr('verb.form')}</th></tr>"
                for (_, p_lbl, _), f in zip(cls.PERSONES, lf):
                    html += f"<tr><td style='text-align: left; padding-left: 6px;'><b>{p_lbl}</b></td><td>{cel_la_sum(f)}</td></tr>"
                html += "</table></div>"
            html += f"</div><h3 style='margin-top: 15px;'>{tr('verb.nominal.title')}</h3><table border='1' cellpadding='6' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: center; font-size: 13px; margin-bottom: 25px;'><tr style='background-color: #f1f8ff; color: #0366d6;'><th>{tr('verb.nom.col1')}</th><th>{tr('verb.nom.col2')}</th><th>{tr('verb.nom.col3')}</th></tr>"
            for k, v in cls.PARADIGMA_SUM["infinitius"].items(): html += f"<tr><td><b>{tr('verb.inf')}</b></td><td>{k}</td><td>{cel_la_sum(v)}</td></tr>"
            for k, v in cls.PARADIGMA_SUM["participis"].items(): html += f"<tr><td><b>{tr('verb.ptcp')}</b></td><td>{k}</td><td>{cel_la_sum(v)}</td></tr>"
            html += "</table>"
            return html

        matriu_temps, infinitius, participis, supins, gerundis = cls._recollir_dades(info_v, prefer_u)

        def cel_la(llista):
            if not llista: return "<span style='color: #8c959f;'>—</span>"
            res = []
            for item in llista:
                item_net = normalitzar_text(item)
                if cercada_net and (item_net == cercada_net or (len(cercada_net) > 2 and cercada_net in item_net.split())):
                    res.append(f"<span style='background-color: #fff3cd; color: #856404; font-weight: bold; padding: 3px 6px; border-radius: 4px;'>{item} ◄</span>")
                else:
                    res.append(f"<b>{item}</b>")
            return ", ".join(res)

        html = (
            f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; padding: 12px; border-radius: 6px; margin-bottom: 15px;'><p style='margin: 0; font-size: 15px;'><b>{tr('verb.enunciat')}</b> <span style='font-size: 18px; color: #0366d6;'><b>{info_v['enunciat']}</b></span> — <i>{info_v['conjugacio']}</i></p></div>"
            f"<h3>{tr('verb.personal.title')}</h3><div style='display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 20px;'>"
        )
        for t_id, _ in cls.TEMPS_CONFIG:
            pers_dict = matriu_temps.get(t_id, {})
            if any(len(pers_dict.get(p_code, [])) > 0 for p_code, _, _ in cls.PERSONES):
                html += f"<div style='border: 1px solid #dcdcdc; border-radius: 6px; padding: 8px; background-color: #ffffff;'><h4 style='margin: 4px 0 8px 0; color: #0366d6; font-size: 13px;'>{cls.nom_temps(t_id)}</h4><table border='1' cellpadding='4' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: center; font-size: 12px;'><tr style='background-color: #f6f8fa;'><th>{tr('verb.person')}</th><th>{tr('verb.form')}</th></tr>"
                for p_code, p_lbl, _ in cls.PERSONES:
                    html += f"<tr><td style='text-align: left; padding-left: 6px;'><b>{p_lbl}</b></td><td>{cel_la(pers_dict.get(p_code, []))}</td></tr>"
                html += "</table></div>"

        html += f"</div><h3 style='margin-top: 15px;'>{tr('verb.nominal.title')}</h3><table border='1' cellpadding='6' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: center; font-size: 13px; margin-bottom: 25px;'><tr style='background-color: #f1f8ff; color: #0366d6;'><th>{tr('verb.nom.col1')}</th><th>{tr('verb.nom.col2')}</th><th>{tr('verb.nom.col3')}</th></tr>"
        for k, v in infinitius.items(): html += f"<tr><td><b>{tr('verb.inf')}</b></td><td>{k}</td><td>{cel_la(v)}</td></tr>"
        for k, v in participis.items(): html += f"<tr><td><b>{tr('verb.ptcp')}</b></td><td>{k}</td><td>{cel_la(v)}</td></tr>"
        for k, v in supins.items(): html += f"<tr><td><b>{tr('verb.sup')}</b></td><td>{k}</td><td>{cel_la(v)}</td></tr>"
        for k, v in gerundis.items(): html += f"<tr><td><b>{tr('verb.ger')}</b></td><td>{k}</td><td>{cel_la(v)}</td></tr>"
        html += "</table>"
        return html

    @classmethod
    def generar_latex(cls, info_v, prefer_u=False):
        if info_v.get("es_sum"):
            linies = [
                f"\\subsection*{{{escapar_latex(info_v['enunciat'])} ({escapar_latex(info_v['conjugacio'])})}}",
            ]
            for t_id, lf in cls.PARADIGMA_SUM["formes"].items():
                linies.extend([
                    f"\\subsubsection*{{{escapar_latex(cls.nom_temps(t_id))}}}",
                    "\\begin{tabular}{|l|c|}",
                    "\\hline",
                    f"\\textbf{{{escapar_latex(tr('verb.person'))}}} & \\textbf{{{escapar_latex(tr('verb.form'))}}} \\\\",
                    "\\hline"
                ])
                for (_, p_lbl, _), f in zip(cls.PERSONES, lf):
                    linies.append(f"\\textbf{{{escapar_latex(p_lbl)}}} & {escapar_latex(f)} \\\\")
                linies.extend(["\\hline", "\\end{tabular}", ""])
            linies.extend([
                f"\\subsubsection*{{{escapar_latex(tr('verb.nominal.title'))}}}",
                "\\begin{tabular}{|l|l|c|}",
                "\\hline",
                f"\\textbf{{{escapar_latex(tr('verb.nom.col1'))}}} & \\textbf{{{escapar_latex(tr('verb.nom.col2'))}}} & \\textbf{{{escapar_latex(tr('verb.nom.col3'))}}} \\\\",
                "\\hline"
            ])
            for k, v in cls.PARADIGMA_SUM["infinitius"].items():
                linies.append(f"\\textbf{{{escapar_latex(tr('verb.inf'))}}} & {escapar_latex(k)} & {escapar_latex(v)} \\\\")
            for k, v in cls.PARADIGMA_SUM["participis"].items():
                linies.append(f"\\textbf{{{escapar_latex(tr('verb.ptcp'))}}} & {escapar_latex(k)} & {escapar_latex(v)} \\\\")
            linies.extend(["\\hline", "\\end{tabular}", ""])
            return "\n".join(linies)

        matriu_temps, infinitius, participis, supins, gerundis = cls._recollir_dades(info_v, prefer_u)
        linies = [f"\\subsection*{{{escapar_latex(info_v['enunciat'])} ({escapar_latex(info_v['conjugacio'])})}}"]

        for t_id, _ in cls.TEMPS_CONFIG:
            pers_dict = matriu_temps.get(t_id, {})
            if any(len(pers_dict.get(p_code, [])) > 0 for p_code, _, _ in cls.PERSONES):
                linies.extend([
                    f"\\subsubsection*{{{escapar_latex(cls.nom_temps(t_id))}}}",
                    "\\begin{tabular}{|l|c|}",
                    "\\hline",
                    f"\\textbf{{{escapar_latex(tr('verb.person'))}}} & \\textbf{{{escapar_latex(tr('verb.form'))}}} \\\\",
                    "\\hline"
                ])
                for p_code, p_lbl, _ in cls.PERSONES:
                    f_list = pers_dict.get(p_code, [])
                    f_txt = ", ".join(escapar_latex(x) for x in f_list) if f_list else "---"
                    linies.append(f"\\textbf{{{escapar_latex(p_lbl)}}} & {f_txt} \\\\")
                linies.extend(["\\hline", "\\end{tabular}", ""])

        if infinitius or participis or supins or gerundis:
            linies.extend([
                f"\\subsubsection*{{{escapar_latex(tr('verb.nominal.title'))}}}",
                "\\begin{tabular}{|l|l|c|}",
                "\\hline",
                f"\\textbf{{{escapar_latex(tr('verb.nom.col1'))}}} & \\textbf{{{escapar_latex(tr('verb.nom.col2'))}}} & \\textbf{{{escapar_latex(tr('verb.nom.col3'))}}} \\\\",
                "\\hline"
            ])
            for k, v in infinitius.items():
                linies.append(f"\\textbf{{{escapar_latex(tr('verb.inf'))}}} & {escapar_latex(k)} & {', '.join(escapar_latex(x) for x in v)} \\\\")
            for k, v in participis.items():
                linies.append(f"\\textbf{{{escapar_latex(tr('verb.ptcp'))}}} & {escapar_latex(k)} & {', '.join(escapar_latex(x) for x in v)} \\\\")
            for k, v in supins.items():
                linies.append(f"\\textbf{{{escapar_latex(tr('verb.sup'))}}} & {escapar_latex(k)} & {', '.join(escapar_latex(x) for x in v)} \\\\")
            for k, v in gerundis.items():
                linies.append(f"\\textbf{{{escapar_latex(tr('verb.ger'))}}} & {escapar_latex(k)} & {', '.join(escapar_latex(x) for x in v)} \\\\")
            linies.extend(["\\hline", "\\end{tabular}", ""])

        return "\n".join(linies)


class MotorPronomsCanonic:
    ORDRE_CASOS = ["NOM", "VOC", "ACC", "GEN", "DAT", "ABL"]

    @classmethod
    def nom_cas(cls, codi: str) -> str:
        return tr(f"case.{codi}")

    @classmethod
    def _recollir_dades(cls, formes, prefer_u=False):
        te_genere = any(any(g in extreure_tokens_tag(t) for g in ["MASC", "FEM", "NEUT"]) for _, t in formes)
        dades = {"SG": {"MASC": defaultdict(list), "FEM": defaultdict(list), "NEUT": defaultdict(list), "COM": defaultdict(list)},
                 "PL": {"MASC": defaultdict(list), "FEM": defaultdict(list), "NEUT": defaultdict(list), "COM": defaultdict(list)}}
        for f, tag in formes:
            toks = extreure_tokens_tag(tag)
            cas = next((c for c in cls.ORDRE_CASOS if c in toks), None)
            num = "SG" if "SG" in toks else ("PL" if "PL" in toks else None)
            if not cas or not num: continue
            f_adapt = aplicar_grafia(f, prefer_u)

            if te_genere:
                if "MASC+FEM+NEUT" in toks or "DAT+ABL" in toks:
                    for k in ["MASC", "FEM", "NEUT"]: dades[num][k][cas].append(f_adapt)
                elif "MASC+FEM" in toks:
                    for k in ["MASC", "FEM"]: dades[num][k][cas].append(f_adapt)
                elif "MASC+NEUT" in toks:
                    for k in ["MASC", "NEUT"]: dades[num][k][cas].append(f_adapt)
                elif "FEM+NEUT" in toks:
                    for k in ["FEM", "NEUT"]: dades[num][k][cas].append(f_adapt)
                elif "MASC" in toks: dades[num]["MASC"][cas].append(f_adapt)
                elif "FEM" in toks: dades[num]["FEM"][cas].append(f_adapt)
                elif "NEUT" in toks: dades[num]["NEUT"][cas].append(f_adapt)
            else:
                dades[num]["COM"][cas].append(f_adapt)
        return te_genere, dades

    @classmethod
    def generar_taula_html(cls, formes, forma_cercada="", prefer_u=False):
        te_genere, dades = cls._recollir_dades(formes, prefer_u)
        cercada_net = normalitzar_text(forma_cercada)

        def cel_la(llista):
            unics = list(dict.fromkeys(llista))
            if not unics: return "<span style='color: #8c959f;'>—</span>"
            res = []
            for item in unics:
                if cercada_net and normalitzar_text(item) == cercada_net:
                    res.append(f"<span style='background-color: #fff3cd; color: #856404; font-weight: bold; padding: 3px 6px; border-radius: 4px;'>{item} ◄</span>")
                else:
                    res.append(f"<b>{item}</b>")
            return ", ".join(res)

        html = ""
        for num_code, num_titol in [("SG", tr("tbl.sg")), ("PL", tr("tbl.pl"))]:
            html += f"<h4 style='color: #24292e; margin-top: 14px; margin-bottom: 6px;'>{num_titol}</h4>"
            html += "<table border='1' cellpadding='7' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: center; font-family: Segoe UI, sans-serif; font-size: 14px; margin-bottom: 20px;'>"
            if te_genere:
                html += f"<tr style='background-color: #f1f8ff; color: #0366d6;'><th style='width: 19%;'>{tr('tbl.case')}</th><th style='width: 27%;'>{tr('tbl.masc')}</th><th style='width: 27%;'>{tr('tbl.fem')}</th><th style='width: 27%;'>{tr('tbl.neut')}</th></tr>"
                for c in cls.ORDRE_CASOS:
                    val_m = cel_la(dades[num_code]["MASC"][c])
                    val_f = cel_la(dades[num_code]["FEM"][c])
                    val_n = cel_la(dades[num_code]["NEUT"][c])
                    if val_m != "<span style='color: #8c959f;'>—</span>" or val_f != "<span style='color: #8c959f;'>—</span>" or val_n != "<span style='color: #8c959f;'>—</span>":
                        html += f"<tr><td style='background-color: #fafbfc; text-align: left; padding-left: 10px;'><b>{cls.nom_cas(c)}</b></td><td>{val_m}</td><td>{val_f}</td><td>{val_n}</td></tr>"
            else:
                html += f"<tr style='background-color: #f1f8ff; color: #0366d6;'><th style='width: 25%;'>{tr('tbl.case')}</th><th style='width: 75%;'>{tr('tbl.pronform')}</th></tr>"
                for c in cls.ORDRE_CASOS:
                    val_com = cel_la(dades[num_code]["COM"][c])
                    if val_com != "<span style='color: #8c959f;'>—</span>":
                        html += f"<tr><td style='background-color: #fafbfc; text-align: left; padding-left: 10px;'><b>{cls.nom_cas(c)}</b></td><td>{val_com}</td></tr>"
            html += "</table>"
        return html

    @classmethod
    def generar_latex(cls, lema_disp, formes, prefer_u=False):
        te_genere, dades = cls._recollir_dades(formes, prefer_u)

        def fmt(llista):
            unics = list(dict.fromkeys(llista))
            return ", ".join(escapar_latex(x) for x in unics) if unics else "---"

        linies = [f"\\subsection*{{{escapar_latex(tr('cat.pron'))}: {escapar_latex(lema_disp)}}}"]
        for num_code, num_titol in [("SG", tr("tbl.sg")), ("PL", tr("tbl.pl"))]:
            files_num = []
            if te_genere:
                for c in cls.ORDRE_CASOS:
                    m, f, n = dades[num_code]["MASC"][c], dades[num_code]["FEM"][c], dades[num_code]["NEUT"][c]
                    if m or f or n:
                        files_num.append(f"\\textbf{{{escapar_latex(cls.nom_cas(c))}}} & {fmt(m)} & {fmt(f)} & {fmt(n)} \\\\")
                if files_num:
                    linies.extend([
                        f"\\subsubsection*{{{escapar_latex(num_titol)}}}",
                        "\\begin{tabular}{|l|c|c|c|}",
                        "\\hline",
                        f"\\textbf{{{escapar_latex(tr('tbl.case'))}}} & \\textbf{{{escapar_latex(tr('tbl.masc'))}}} & \\textbf{{{escapar_latex(tr('tbl.fem'))}}} & \\textbf{{{escapar_latex(tr('tbl.neut'))}}} \\\\",
                        "\\hline",
                        *files_num,
                        "\\hline",
                        "\\end{tabular}",
                        ""
                    ])
            else:
                for c in cls.ORDRE_CASOS:
                    com = dades[num_code]["COM"][c]
                    if com:
                        files_num.append(f"\\textbf{{{escapar_latex(cls.nom_cas(c))}}} & {fmt(com)} \\\\")
                if files_num:
                    linies.extend([
                        f"\\subsubsection*{{{escapar_latex(num_titol)}}}",
                        "\\begin{tabular}{|l|c|}",
                        "\\hline",
                        f"\\textbf{{{escapar_latex(tr('tbl.case'))}}} & \\textbf{{{escapar_latex(tr('tbl.pronform'))}}} \\\\",
                        "\\hline",
                        *files_num,
                        "\\hline",
                        "\\end{tabular}",
                        ""
                    ])
        return "\n".join(linies)


# ==============================================================================
# FIL DE CÀRREGA ASÍNCRONA DES DE SQLITE (Connecta instantàniament)
# ==============================================================================
class FilCarregaSQLite(QThread):
    progres = pyqtSignal(str)
    acabat = pyqtSignal(list)

    def run(self):
        if not os.path.exists(DB_FILE):
            self.progres.emit(tr("status.db.missing", DB_FILE))
            self.acabat.emit([])
            return

        assegurar_taula_cache_glosses()
        self.progres.emit(tr("status.db.indexing"))
        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()
        cur.execute("""
            SELECT DISTINCT lema FROM formes
            UNION
            SELECT DISTINCT lema_clean FROM diccionari_ls
            ORDER BY lema;
        """)
        lemes = [r[0] for r in cur.fetchall()]
        conn.close()

        msg = tr("status.db.ready", f"{len(lemes):,}")
        if nom_model_carregat:
            msg += f" | LatinCy: {nom_model_carregat}"
        self.progres.emit(msg)
        self.acabat.emit(lemes)


# ==============================================================================
# INTERFÍCIE D'USUARI AMB 5 PESTANYES I EXPORTACIÓ
# ==============================================================================
class DiccionariLatinApp(QWidget):
    def __init__(self):
        super().__init__()
        self.lemes_disponibles = []
        self.ultims_tokens_oracio = []
        self.lema_seleccionat = None
        self.fil_llm = None
        self.fil_spacy = None
        self.fil_glossa = None

        self.cerca_id_actual = 0
        self.estat_info_actual = None
        self.ultim_prompt_ollama = ""

        self.export_info = {"plain": "", "latex": ""}
        self.export_flexio = {"plain": "", "latex": ""}
        self.export_perseus = {"plain": "", "latex": ""}
        self.export_oracio = {"plain": "", "latex": ""}
        self.export_llm = {"plain": "", "latex": ""}

        self.botons_export_plain = []
        self.botons_export_latex = []

        self.init_ui()
        self.retradueix_interficie()
        self.iniciar_carrega()

    def _crear_barra_exportacio(self, clau_pestanya: str) -> QHBoxLayout:
        barra = QHBoxLayout()
        barra.addStretch()

        btn_plain = QPushButton(tr("export.plain"))
        btn_plain.setStyleSheet("padding: 4px 10px; font-size: 12px; background-color: #f8f9fa; border: 1px solid #ced4da; border-radius: 4px;")
        btn_plain.clicked.connect(lambda: self.copiar_al_portaretalls(clau_pestanya, "plain"))
        self.botons_export_plain.append(btn_plain)

        btn_latex = QPushButton(tr("export.latex"))
        btn_latex.setStyleSheet("padding: 4px 10px; font-size: 12px; background-color: #eef5ff; color: #0a58ca; font-weight: 600; border: 1px solid #b6d4fe; border-radius: 4px;")
        btn_latex.clicked.connect(lambda: self.copiar_al_portaretalls(clau_pestanya, "latex"))
        self.botons_export_latex.append(btn_latex)

        barra.addWidget(btn_plain)
        barra.addWidget(btn_latex)
        return barra

    def copiar_al_portaretalls(self, clau_pestanya: str, format_tipus: str):
        dades = {
            "info": self.export_info,
            "flexio": self.export_flexio,
            "perseus": self.export_perseus,
            "oracio": self.export_oracio,
            "llm": self.export_llm
        }.get(clau_pestanya, {})

        contingut = dades.get(format_tipus, "").strip()
        if not contingut:
            self.status_bar.showMessage(tr("export.empty"), 4000)
            return

        QApplication.clipboard().setText(contingut)
        etiqueta = "LaTeX" if format_tipus == "latex" else tr("export.fmt.plain")
        self.status_bar.showMessage(tr("export.copied", etiqueta), 4000)

    def init_ui(self):
        self.resize(1240, 880)

        layout_principal = QVBoxLayout()

        # Barra superior: Cerca + Mode avançat + Selector d'idioma
        layout_cerca = QHBoxLayout()
        self.label_paraula = QLabel()
        self.label_paraula.setStyleSheet("font-weight: bold; font-size: 14px;")

        self.input_cerca = QLineEdit()
        self.input_cerca.setStyleSheet("padding: 6px; font-size: 14px;")
        self.input_cerca.setEnabled(False)
        self.input_cerca.returnPressed.connect(self.executar_cerca)

        self.btn_cerca = QPushButton()
        self.btn_cerca.setStyleSheet("padding: 6px 14px; font-weight: bold; font-size: 14px;")
        self.btn_cerca.setEnabled(False)
        self.btn_cerca.clicked.connect(self.executar_cerca)

        self.chk_avancat = QCheckBox()
        self.chk_avancat.setStyleSheet("font-weight: 600; color: #495057; margin-left: 8px;")
        self.chk_avancat.stateChanged.connect(self.actualitzar_autocompletador)

        self.lbl_llengua = QLabel()
        self.lbl_llengua.setStyleSheet("font-weight: 600; color: #495057; margin-left: 12px;")

        self.combo_llengua = QComboBox()
        self.combo_llengua.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToContents)
        self.combo_llengua.setMinimumWidth(115)
        self.combo_llengua.setStyleSheet("padding: 4px 10px; font-size: 13px; font-weight: 600;")
        for codi, nom in GestorIdiomes.IDIOMES_SUPORTATS:
            self.combo_llengua.addItem(nom, codi)
        self.combo_llengua.currentIndexChanged.connect(self.canviar_llengua_ui)

        layout_cerca.addWidget(self.label_paraula)
        layout_cerca.addWidget(self.input_cerca)
        layout_cerca.addWidget(self.btn_cerca)
        layout_cerca.addWidget(self.chk_avancat)
        layout_cerca.addWidget(self.lbl_llengua)
        layout_cerca.addWidget(self.combo_llengua)

        layout_principal.addLayout(layout_cerca)

        # Pestanyes de l'aplicació
        self.tabs = QTabWidget()
        self.tabs.setStyleSheet("QTabBar::tab { font-size: 13px; padding: 7px 14px; font-weight: 600; }")

        # Pestanya 1: Informació Morfològica
        tab1 = QWidget()
        l_tab1 = QVBoxLayout(tab1)
        l_tab1.addLayout(self._crear_barra_exportacio("info"))
        self.browser_info = QTextBrowser()
        self.browser_info.setOpenExternalLinks(False)
        self.browser_info.anchorClicked.connect(self.enllac_clicat)
        l_tab1.addWidget(self.browser_info)
        self.tabs.addTab(tab1, "")

        # Pestanya 2: Flexió Canònica
        tab2 = QWidget()
        l_tab2 = QVBoxLayout(tab2)
        l_tab2.addLayout(self._crear_barra_exportacio("flexio"))
        self.browser_flexio = QTextBrowser()
        self.browser_flexio.setOpenExternalLinks(False)
        self.browser_flexio.anchorClicked.connect(self.enllac_clicat)
        l_tab2.addWidget(self.browser_flexio)
        self.tabs.addTab(tab2, "")

        # Pestanya 3: Lewis & Short
        tab3 = QWidget()
        l_tab3 = QVBoxLayout(tab3)
        l_tab3.addLayout(self._crear_barra_exportacio("perseus"))
        self.browser_perseus = QTextBrowser()
        self.browser_perseus.setOpenExternalLinks(False)
        self.browser_perseus.anchorClicked.connect(self.enllac_clicat)
        l_tab3.addWidget(self.browser_perseus)
        self.tabs.addTab(tab3, "")

        # Pestanya 4: Anàlisi d'oracions (LatinCy)
        self.tab_oracions = QWidget()
        self.configurar_tab_oracions()
        self.tabs.addTab(self.tab_oracions, "")

        # Pestanya 5: Traducció i Comentari (Ollama)
        self.tab_llm = QWidget()
        self.configurar_tab_llm()
        self.tabs.addTab(self.tab_llm, "")

        layout_principal.addWidget(self.tabs)

        self.status_bar = QStatusBar()
        layout_principal.addWidget(self.status_bar)

        self.setLayout(layout_principal)

    def configurar_tab_oracions(self):
        layout = QVBoxLayout()

        layout_in = QHBoxLayout()
        self.input_oracio = QLineEdit()
        self.input_oracio.setStyleSheet("padding: 7px; font-size: 14px;")
        self.input_oracio.returnPressed.connect(self.analitzar_oracio)

        self.btn_analitzar = QPushButton()
        self.btn_analitzar.setStyleSheet("padding: 7px 16px; font-weight: bold; background-color: #0d6efd; color: white;")
        self.btn_analitzar.clicked.connect(self.analitzar_oracio)

        self.btn_exemple = QPushButton()
        self.btn_exemple.setStyleSheet("padding: 7px 12px;")
        self.btn_exemple.clicked.connect(lambda: self.input_oracio.setText("Gallia est omnis divisa in partes tres"))

        layout_in.addWidget(self.input_oracio)
        layout_in.addWidget(self.btn_analitzar)
        layout_in.addWidget(self.btn_exemple)
        layout.addLayout(layout_in)

        layout.addLayout(self._crear_barra_exportacio("oracio"))

        self.browser_oracio = QTextBrowser()
        self.browser_oracio.setOpenExternalLinks(False)
        self.browser_oracio.anchorClicked.connect(self.enllac_clicat)
        layout.addWidget(self.browser_oracio)

        self.tab_oracions.setLayout(layout)

    def configurar_tab_llm(self):
        layout = QVBoxLayout()

        layout_estat = QHBoxLayout()
        self.lbl_estat_llm = QLabel()
        self.lbl_estat_llm.setWordWrap(True)

        self.btn_refrescar_ollama = QPushButton()
        self.btn_refrescar_ollama.setStyleSheet("padding: 6px 10px; font-size: 12px;")
        self.btn_refrescar_ollama.clicked.connect(self.refrescar_estat_ollama_ui)

        layout_estat.addWidget(self.lbl_estat_llm, stretch=1)
        layout_estat.addWidget(self.btn_refrescar_ollama)
        layout.addLayout(layout_estat)

        layout_in = QHBoxLayout()
        self.input_llm = QTextEdit()
        self.input_llm.setMaximumHeight(90)
        self.input_llm.setStyleSheet("padding: 6px; font-size: 14px;")

        layout_btns = QVBoxLayout()
        self.btn_traduir_llm = QPushButton()
        self.btn_traduir_llm.setStyleSheet("padding: 8px 16px; font-weight: bold; background-color: #198754; color: white;")
        self.btn_traduir_llm.clicked.connect(self.executar_traduccio_llm)

        self.btn_copiar_des_doracio = QPushButton()
        self.btn_copiar_des_doracio.setStyleSheet("padding: 6px 12px; font-size: 12px;")
        self.btn_copiar_des_doracio.clicked.connect(lambda: self.input_llm.setPlainText(self.input_oracio.text()))

        layout_btns.addWidget(self.btn_traduir_llm)
        layout_btns.addWidget(self.btn_copiar_des_doracio)

        layout_in.addWidget(self.input_llm)
        layout_in.addLayout(layout_btns)
        layout.addLayout(layout_in)

        # Barra d'opcions: casella d'anàlisi + BOTÓ per veure la instrucció exacta
        layout_opcions = QHBoxLayout()
        self.chk_injectar_analisi = QCheckBox()
        self.chk_injectar_analisi.setStyleSheet("font-weight: 600; color: #0a58ca; padding: 2px 0;")

        self.btn_veure_instruccio = QPushButton()
        self.btn_veure_instruccio.setStyleSheet(
            "padding: 4px 12px; font-size: 12px; font-weight: 600; "
            "background-color: #f8f9fa; color: #212529; border: 1px solid #ced4da; border-radius: 4px; margin-left: 14px;"
        )
        self.btn_veure_instruccio.setEnabled(False)
        self.btn_veure_instruccio.clicked.connect(self.obrir_dialeg_instruccio)

        layout_opcions.addWidget(self.chk_injectar_analisi)
        layout_opcions.addWidget(self.btn_veure_instruccio)
        layout_opcions.addStretch()
        layout.addLayout(layout_opcions)

        layout.addLayout(self._crear_barra_exportacio("llm"))

        self.browser_llm = QTextBrowser()
        self.browser_llm.setOpenExternalLinks(False)
        layout.addWidget(self.browser_llm)

        self.tab_llm.setLayout(layout)

    def canviar_llengua_ui(self, index: int):
        codi = self.combo_llengua.itemData(index)
        if codi:
            I18N.set_idioma(codi)
            self.retradueix_interficie()

    def retradueix_interficie(self):
        """Actualitza tots els textos visibles de la UI i re-renderitza els continguts actius."""
        self.setWindowTitle(tr("app.title"))
        self.label_paraula.setText(tr("search.label"))
        if self.input_cerca.isEnabled():
            self.input_cerca.setPlaceholderText(tr("search.placeholder.ready"))
        else:
            self.input_cerca.setPlaceholderText(tr("search.placeholder.loading"))

        self.btn_cerca.setText(tr("search.btn"))
        self.chk_avancat.setText(tr("search.adv"))
        self.chk_avancat.setToolTip(tr("search.adv.tooltip"))
        self.lbl_llengua.setText(tr("ui.lang.label"))

        self.tabs.setTabText(0, tr("tab.info"))
        self.tabs.setTabText(1, tr("tab.flexio"))
        self.tabs.setTabText(2, tr("tab.perseus"))
        self.tabs.setTabText(3, tr("tab.oracions"))
        self.tabs.setTabText(4, tr("tab.llm"))

        for b in self.botons_export_plain:
            b.setText(tr("export.plain"))
        for b in self.botons_export_latex:
            b.setText(tr("export.latex"))

        self.input_oracio.setPlaceholderText(tr("sent.placeholder"))
        self.btn_analitzar.setText(tr("sent.btn.analyze"))
        self.btn_exemple.setText(tr("sent.btn.example"))

        self.btn_refrescar_ollama.setText(tr("llm.btn.refresh"))
        self.input_llm.setPlaceholderText(tr("llm.placeholder"))
        self.btn_traduir_llm.setText(tr("llm.btn.translate"))
        self.btn_copiar_des_doracio.setText(tr("llm.btn.import"))
        self.chk_injectar_analisi.setText(tr("llm.chk.inject"))
        self.chk_injectar_analisi.setToolTip(tr("llm.chk.inject.tooltip"))
        self.btn_veure_instruccio.setText(tr("llm.btn.prompt"))
        self.btn_veure_instruccio.setToolTip(tr("llm.btn.prompt.tooltip"))

        self.refrescar_estat_ollama_ui()

        if self.ultims_tokens_oracio:
            self.dibuixar_taula_oracio()

        if self.input_cerca.text().strip():
            self.mostrar_informacio(self.input_cerca.text())

    def obrir_dialeg_instruccio(self):
        if not self.ultim_prompt_ollama:
            self.status_bar.showMessage(tr("llm.status.noprompt"), 4000)
            return

        dialeg = QDialog(self)
        dialeg.setWindowTitle(tr("llm.dialog.title"))
        dialeg.resize(780, 540)

        layout_d = QVBoxLayout(dialeg)

        lbl_info = QLabel(tr("llm.dialog.desc"))
        lbl_info.setStyleSheet("font-weight: 600; color: #212529; margin-bottom: 4px;")
        layout_d.addWidget(lbl_info)

        visor_prompt = QTextEdit()
        visor_prompt.setReadOnly(True)
        visor_prompt.setPlainText(self.ultim_prompt_ollama)
        visor_prompt.setStyleSheet("font-family: Menlo, Monaco, Consolas, monospace; font-size: 13px; background-color: #f8f9fa; padding: 8px;")
        layout_d.addWidget(visor_prompt)

        barra_btns = QHBoxLayout()
        barra_btns.addStretch()

        btn_copiar = QPushButton(tr("llm.dialog.copy"))
        btn_copiar.setStyleSheet("padding: 6px 12px; font-weight: 600;")
        btn_copiar.clicked.connect(lambda: QApplication.clipboard().setText(self.ultim_prompt_ollama))

        btn_tancar = QPushButton(tr("llm.dialog.close"))
        btn_tancar.setStyleSheet("padding: 6px 14px;")
        btn_tancar.clicked.connect(dialeg.accept)

        barra_btns.addWidget(btn_copiar)
        barra_btns.addWidget(btn_tancar)
        layout_d.addLayout(barra_btns)

        dialeg.exec()

    def refrescar_estat_ollama_ui(self):
        cfg = carregar_config_yaml()
        llm_cfg = cfg.get("traduccio_llm", {})
        estat = verificar_estat_ollama(llm_cfg)
        model_cfg = llm_cfg.get("model", "gemma4:12b")
        thinking_actiu = bool(llm_cfg.get("thinking", False))
        badge_think = "thinking: ON" if thinking_actiu else "thinking: OFF"

        if estat["connectat"]:
            tipus_srv = tr("llm.connected.local") if estat["es_local"] else tr("llm.connected.remote", estat["url"])
            te_model = model_cfg in estat["models_disponibles"] or f"{model_cfg}:latest" in estat["models_disponibles"]
            nota_model = (
                tr("llm.model.ready", model_cfg, badge_think)
                if te_model
                else tr("llm.model.pending", model_cfg, badge_think)
            )
            self.lbl_estat_llm.setStyleSheet("padding: 8px 12px; border-radius: 4px; font-size: 13px; background-color: #e8f5e9; color: #1b5e20; border-left: 4px solid #2e7d32;")
            self.lbl_estat_llm.setText(tr("llm.connected.banner", tipus_srv, nota_model))
            self.btn_traduir_llm.setEnabled(True)
            self.browser_llm.setOpenExternalLinks(False)
            if not self.ultim_prompt_ollama:
                self.browser_llm.setHtml("")
        else:
            self.btn_traduir_llm.setEnabled(False)
            self.lbl_estat_llm.setStyleSheet("padding: 8px 12px; border-radius: 4px; font-size: 13px; background-color: #fff3cd; color: #856404; border-left: 4px solid #ffc107;")

            if not estat["actiu"]:
                self.lbl_estat_llm.setText(tr("llm.disabled.banner", estat["error"]))
                self.browser_llm.setHtml(f"<div style='padding: 15px; font-family: Segoe UI, sans-serif;'>{estat['error']}</div>")
            elif not estat["es_local"]:
                self.lbl_estat_llm.setText(tr("llm.remote.err.banner", estat["url"]))
                self.browser_llm.setOpenExternalLinks(False)
                self.browser_llm.setHtml(
                    f"<div style='padding: 15px; font-family: Segoe UI, sans-serif; line-height: 1.5;'>"
                    f"{tr('llm.remote.err.body', estat['url'], estat['error'])}</div>"
                )
            elif not estat["binari_instal_lat"]:
                so_nom = {"Darwin": "macOS", "Windows": "Windows"}.get(platform.system(), "Linux")
                instruccions = obtenir_instruccions_install_ollama()
                self.lbl_estat_llm.setText(tr("llm.notinstalled.banner", so_nom))
                self.browser_llm.setOpenExternalLinks(True)
                self.browser_llm.setHtml(
                    f"<div style='padding: 15px; font-family: Segoe UI, sans-serif; line-height: 1.6;'>"
                    f"{tr('llm.notinstalled.body', so_nom, instruccions, model_cfg)}</div>"
                )
            else:
                self.lbl_estat_llm.setText(tr("llm.stopped.banner"))
                self.browser_llm.setOpenExternalLinks(False)
                self.browser_llm.setHtml(
                    f"<div style='padding: 15px; font-family: Segoe UI, sans-serif; line-height: 1.5;'>"
                    f"{tr('llm.stopped.body')}</div>"
                )

    def _obtenir_taula_analisi_per_prompt(self, text_llati: str) -> str:
        global nlp_latincy
        if nlp_latincy is None:
            return ""

        if self.input_oracio.text().strip() == text_llati and self.ultims_tokens_oracio:
            tokens = self.ultims_tokens_oracio
        else:
            doc = nlp_latincy(text_llati)
            tokens = [
                {
                    "forma": t.text,
                    "lema": t.lemma_,
                    "pos": t.pos_,
                    "morph": str(t.morph) if t.morph else "—",
                    "dep": t.dep_,
                    "head": t.head.text
                }
                for t in doc
            ]

        linies = ["Forma | Lema | Categoria | Morfologia | Funció | Cap"]
        for t in tokens:
            linies.append(f"{t['forma']} | {t['lema']} | {t['pos']} | {t['morph']} | {t['dep']} | {t['head']}")
        return "\n".join(linies)

    def executar_traduccio_llm(self):
        text_llati = self.input_llm.toPlainText().strip()
        if not text_llati:
            self.status_bar.showMessage(tr("llm.status.empty"), 4000)
            return

        cfg = carregar_config_yaml()
        llm_cfg = cfg.get("traduccio_llm", {})
        estat = verificar_estat_ollama(llm_cfg)
        if not estat["connectat"]:
            self.refrescar_estat_ollama_ui()
            self.status_bar.showMessage(tr("llm.status.noconn"), 5000)
            return

        text_analisi = ""
        if self.chk_injectar_analisi.isChecked():
            if nlp_latincy is None:
                self.status_bar.showMessage(tr("llm.status.nospacy_warn"), 4000)
            else:
                text_analisi = self._obtenir_taula_analisi_per_prompt(text_llati)

        model_nom = llm_cfg.get("model", "gemma4:12b")
        nota_analisi = tr("llm.with_analysis") if text_analisi else ""

        self.btn_traduir_llm.setEnabled(False)
        self.browser_llm.setOpenExternalLinks(False)
        self.browser_llm.setHtml(
            f"<p style='padding: 15px; font-family: Segoe UI, sans-serif; color: #0d6efd;'>"
            f"<i>{tr('llm.processing', model_nom, nota_analisi)}</i></p>"
        )

        self.fil_llm = FilTraduccioOllama(text_llati, llm_cfg, text_analisi)
        self.fil_llm.progres.connect(self.status_bar.showMessage)
        self.fil_llm.acabat.connect(lambda res, err: self.traduccio_llm_acabada(text_llati, model_nom, bool(text_analisi), res, err))
        self.fil_llm.start()

    def traduccio_llm_acabada(self, text_llati: str, model_nom: str, amb_analisi: bool, resposta: str, error_msg: str):
        self.btn_traduir_llm.setEnabled(True)
        if self.fil_llm and self.fil_llm.prompt_enviat:
            self.ultim_prompt_ollama = self.fil_llm.prompt_enviat
            self.btn_veure_instruccio.setEnabled(True)
        self.refrescar_estat_ollama_ui()

        if error_msg:
            self.status_bar.showMessage(error_msg, 5000)
            self.browser_llm.setHtml(f"<div style='padding: 15px; color: #dc3545; font-family: Segoe UI, sans-serif;'><b>Error:</b> {error_msg}</div>")
            return

        self.status_bar.showMessage(f"✓ Ollama ({model_nom})", 5000)

        resp_segura = (
            resposta.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        resp_segura = re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', resp_segura)
        resp_segura = re.sub(r'\*(.+?)\*', r'<i>\1</i>', resp_segura)
        resp_segura = resp_segura.replace("\n", "<br/>")

        etiqueta_ctx = f"Model: <b>{model_nom}</b>" + (tr("llm.ctx.injected") if amb_analisi else "")

        html = (
            "<div style='font-family: Segoe UI, sans-serif; padding: 14px; line-height: 1.6;'>"
            f"<div style='background-color: #f1f8ff; border-left: 4px solid #0d6efd; padding: 10px 14px; margin-bottom: 14px; border-radius: 4px;'>"
            f"<div style='font-size: 12px; color: #0a58ca; margin-bottom: 4px;'>{etiqueta_ctx}</div>"
            f"<b>{tr('llm.orig.text')}</b> <i>{text_llati}</i></div>"
            f"<div style='font-size: 14.5px; color: #212529;'>{resp_segura}</div>"
            "</div>"
        )
        self.browser_llm.setHtml(html)

        self.export_llm["plain"] = f"{tr('llm.orig.text')}\n{text_llati}\n\n{tr('llm.export.header', model_nom)}\n{resposta}"
        self.export_llm["latex"] = (
            f"\\subsection*{{{escapar_latex(tr('llm.export.latex', model_nom))}}}\n"
            f"\\begin{{quote}}\n\\textit{{{escapar_latex(text_llati)}}}\n\\end{{quote}}\n\n"
            f"{escapar_latex(resposta)}"
        )

    def iniciar_carrega(self):
        self.status_bar.showMessage(tr("status.db.connecting"))
        self.fil = FilCarregaSQLite()
        self.fil.progres.connect(self.status_bar.showMessage)
        self.fil.acabat.connect(self.dades_carregades)
        self.fil.start()

        cfg = carregar_config_yaml()
        self.fil_spacy = FilCarregaSpacy(cfg.get("spacy", {}))
        self.fil_spacy.progres.connect(self.status_bar.showMessage)
        self.fil_spacy.acabat.connect(self.spacy_carregat)
        self.fil_spacy.start()

    def spacy_carregat(self, nlp_obj, nom_model: str):
        global nlp_latincy, nom_model_carregat
        nlp_latincy = nlp_obj
        nom_model_carregat = nom_model if nlp_obj is not None else None
        if nom_model_carregat:
            self.status_bar.showMessage(f"✓ LatinCy '{nom_model_carregat}'", 5000)

    def dades_carregades(self, lemes):
        self.lemes_disponibles = lemes
        self.actualitzar_autocompletador()

        self.input_cerca.setEnabled(True)
        self.btn_cerca.setEnabled(True)
        self.input_cerca.setPlaceholderText(tr("search.placeholder.ready"))
        self.input_cerca.setFocus()

        info_mod = f"LatinCy: {nom_model_carregat}" if nom_model_carregat else "LatinCy..."
        self.status_bar.showMessage(f"{tr('status.db.ready', f'{len(lemes):,}')} ({info_mod})", 6000)

    def actualitzar_autocompletador(self):
        paraules = list(self.lemes_disponibles)
        if self.chk_avancat.isChecked() and os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            cur.execute("SELECT DISTINCT forma_raw FROM variants_hist LIMIT 10000;")
            paraules_ext = [r[0] for r in cur.fetchall()]
            conn.close()
            paraules = sorted(list(set(paraules + paraules_ext)))

        completer = QCompleter(paraules, self)
        completer.setCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        completer.setFilterMode(Qt.MatchFlag.MatchStartsWith)
        completer.activated.connect(self.mostrar_informacio)
        self.input_cerca.setCompleter(completer)

    def executar_cerca(self):
        self.mostrar_informacio(self.input_cerca.text())

    def enllac_clicat(self, url: QUrl):
        val = url.toString()
        if val.startswith("lema:"):
            lema_cercat = val.replace("lema:", "").strip()
            self.lema_seleccionat = lema_cercat
            self.input_cerca.setText(lema_cercat)
            self.mostrar_informacio(lema_cercat)
            if self.tabs.currentIndex() == 3 and self.ultims_tokens_oracio:
                self.dibuixar_taula_oracio()
                self.status_bar.showMessage(tr("status.lemma.selected", lema_cercat), 4000)

    # ==========================================================================
    # ANÀLISI D'ORACIONS (LatinCy / spaCy o fallback basat en SQLite)
    # ==========================================================================
    def analitzar_oracio(self):
        text = self.input_oracio.text().strip()
        if not text:
            return

        self.input_llm.setPlainText(text)

        global nlp_latincy
        self.ultims_tokens_oracio = []
        self.lema_seleccionat = None

        if nlp_latincy is not None:
            doc = nlp_latincy(text)
            for token in doc:
                morph_str = str(token.morph) if token.morph else "—"
                self.ultims_tokens_oracio.append({
                    "forma": token.text,
                    "lema": token.lemma_,
                    "pos": token.pos_,
                    "dep": token.dep_,
                    "head": token.head.text,
                    "morph": morph_str
                })
        elif os.path.exists(DB_FILE):
            conn = sqlite3.connect(DB_FILE)
            cur = conn.cursor()
            paraules = re.findall(r"[\w]+|[^\w\s]", text)
            for w in paraules:
                if re.match(r"^\w+$", w):
                    w_clean = normalitzar_text(w)
                    cur.execute("SELECT DISTINCT lema, tag FROM formes WHERE forma_clean = ? LIMIT 1;", (w_clean,))
                    row = cur.fetchone()
                    if row:
                        self.ultims_tokens_oracio.append({
                            "forma": w, "lema": row[0], "pos": "LEX", "dep": "—", "head": "—", "morph": row[1]
                        })
                    else:
                        self.ultims_tokens_oracio.append({
                            "forma": w, "lema": w, "pos": "X", "dep": "—", "head": "—", "morph": "—"
                        })
                else:
                    self.ultims_tokens_oracio.append({
                        "forma": w, "lema": w, "pos": "PUNCT", "dep": "punct", "head": "—", "morph": "—"
                    })
            conn.close()

        self.dibuixar_taula_oracio()

    def dibuixar_taula_oracio(self):
        text = self.input_oracio.text().strip()
        cfg = carregar_config_yaml()
        model_cfg = cfg.get("spacy", {}).get("model", "la_core_web_lg")

        html = (
            "<div style='font-family: Segoe UI, sans-serif; padding: 12px; line-height: 1.5;'>"
            f"<h3 style='color: #0d6efd; margin-top: 0;'>{tr('sent.title')} <span style='color: #212529;'><i>«{text}»</i></span></h3>"
            f"<p style='color: #6c757d; font-size: 13px; margin-bottom: 12px;'><i>{tr('sent.hint')}</i></p>"
        )

        if nlp_latincy is None:
            html += (
                f"<div style='background: #fff3cd; border-left: 4px solid #ffc107; padding: 8px 12px; border-radius: 4px; font-size: 13px; margin-bottom: 12px;'>"
                f"{tr('sent.nospacy', model_cfg)}</div>"
            )
        else:
            html += (
                f"<div style='background: #e8f5e9; border-left: 4px solid #2e7d32; padding: 6px 12px; border-radius: 4px; font-size: 12.5px; margin-bottom: 12px; color: #1b5e20;'>"
                f"{tr('sent.spacy.active', nom_model_carregat)}</div>"
            )

        html += (
            "<table border='1' cellpadding='8' cellspacing='0' style='border-collapse: collapse; width: 100%; text-align: left; font-size: 13.5px; margin-top: 8px;'>"
            "<tr style='background-color: #f1f8ff; color: #0366d6; font-weight: bold;'>"
            f"<th>#</th><th>{tr('sent.col.form')}</th><th>{tr('sent.col.lemma')}</th><th>UPOS</th>"
            f"<th>{tr('sent.col.morph')}</th><th>{tr('sent.col.dep')}</th><th>{tr('sent.col.head')}</th>"
            "</tr>"
        )

        linies_plain = [f"{tr('sent.title')} {text}", f"#\t{tr('sent.col.form')}\t{tr('sent.col.lemma')}\tUPOS\t{tr('sent.col.morph')}\t{tr('sent.col.dep')}\t{tr('sent.col.head')}"]
        linies_latex = [
            f"\\subsection*{{{escapar_latex(tr('sent.latex.title'))}: \\textit{{{escapar_latex(text)}}}}}",
            "\\begin{tabular}{|c|l|l|l|l|l|l|}",
            "\\hline",
            f"\\textbf{{\\#}} & \\textbf{{{escapar_latex(tr('sent.col.form'))}}} & \\textbf{{{escapar_latex(tr('sent.col.lemma'))}}} & \\textbf{{UPOS}} & \\textbf{{{escapar_latex(tr('sent.col.morph'))}}} & \\textbf{{{escapar_latex(tr('sent.col.dep'))}}} & \\textbf{{{escapar_latex(tr('sent.col.head'))}}} \\\\",
            "\\hline"
        ]

        badge_sel = tr("sent.selected.badge")
        for i, t in enumerate(self.ultims_tokens_oracio, 1):
            es_actiu = (self.lema_seleccionat and (t['lema'] == self.lema_seleccionat or normalitzar_text(t['lema']) == normalitzar_text(self.lema_seleccionat)))

            if es_actiu:
                fons = "#fff3cd"
                lema_link = f"<a href='lema:{t['lema']}' style='color: #856404; font-weight: bold; text-decoration: underline; background: #ffe69c; padding: 2px 6px; border-radius: 3px;'>{t['lema']} {badge_sel}</a>"
            else:
                fons = '#ffffff' if i % 2 == 1 else '#f8f9fa'
                if t['pos'] != 'PUNCT':
                    lema_link = f"<a href='lema:{t['lema']}' style='color: #0d6efd; font-weight: bold; text-decoration: underline;'>{t['lema']}</a>"
                else:
                    lema_link = t['lema']

            html += (
                f"<tr style='background-color: {fons};'>"
                f"<td>{i}</td>"
                f"<td><b>{t['forma']}</b></td>"
                f"<td>{lema_link}</td>"
                f"<td><span style='background: #e7f1ff; color: #0a58ca; padding: 2px 6px; border-radius: 3px; font-weight: bold;'>{t['pos']}</span></td>"
                f"<td><code>{t['morph']}</code></td>"
                f"<td><b>{t['dep']}</b></td>"
                f"<td>{t['head']}</td>"
                "</tr>"
            )

            linies_plain.append(f"{i}\t{t['forma']}\t{t['lema']}\t{t['pos']}\t{t['morph']}\t{t['dep']}\t{t['head']}")
            linies_latex.append(
                f"{i} & \\textbf{{{escapar_latex(t['forma'])}}} & \\textit{{{escapar_latex(t['lema'])}}} & "
                f"{escapar_latex(t['pos'])} & \\texttt{{{escapar_latex(t['morph'])}}} & "
                f"{escapar_latex(t['dep'])} & {escapar_latex(t['head'])} \\\\"
            )

        html += "</table></div>"
        linies_latex.extend(["\\hline", "\\end{tabular}"])

        self.export_oracio["plain"] = "\n".join(linies_plain)
        self.export_oracio["latex"] = "\n".join(linies_latex)
        self.browser_oracio.setHtml(html)

    # ==========================================================================
    # RENDERITZAT PROGRESSIU DE LA PESTANYA 1 (Informació Morfològica + Glossa IA)
    # ==========================================================================
    def _renderitzar_pestanya_info(self):
        estat = self.estat_info_actual
        if not estat:
            return

        text_cercat = estat["text_cercat"]
        llengua_desti = estat["llengua_desti"]
        ollama_actiu = estat["ollama_actiu"]

        html_info = (
            "<div style='font-family: Segoe UI, Arial, sans-serif; padding: 12px; line-height: 1.5;'>"
            f"<h2 style='color: #1f2328; margin-bottom: 12px; border-bottom: 2px solid #0969da; padding-bottom: 6px;'>{tr('res.title')} <span style='color: #0969da;'><i>{text_cercat}</i></span></h2>"
        )
        latex_info_blocs = [f"\\section*{{{escapar_latex(tr('res.latex.title'))}: \\textit{{{escapar_latex(text_cercat)}}}}}"]

        if estat["is_mode_avancat"] and estat["info_avancada_notes"]:
            notes_html = "".join(f"<li style='margin-bottom: 3px;'>{n}</li>" for n in estat["info_avancada_notes"][:6])
            html_info += (
                "<div style='background-color: #fff8c5; border: 1px solid #d4a72c; border-left: 4px solid #bf8700; border-radius: 4px; padding: 10px 14px; margin-bottom: 14px;'>"
                f"<div style='font-size: 12px; font-weight: bold; color: #7d4e00; text-transform: uppercase;'>{tr('res.adv.header')}</div>"
                f"<ul style='margin: 6px 0 0 16px; padding: 0; font-size: 13px; color: #442800;'>{notes_html}</ul>"
                "</div>"
            )

        for entry in estat["entrades"]:
            glossa_en = entry["glossa_en"]
            glossa_llm = entry["glossa_llm"]
            ve_de_cache = entry.get("ve_de_cache", False)

            bloc_glossa = ""
            if glossa_en or (ollama_actiu and glossa_llm != "") or glossa_llm:
                linies_g = []
                if glossa_en:
                    linies_g.append(f"<div><b>{tr('res.gloss.en')}</b> <span style='color: #212529;'>{glossa_en}</span></div>")

                if glossa_llm is None and ollama_actiu:
                    linies_g.append(
                        f"<div style='margin-top: 5px; color: #0a58ca;'>"
                        f"<b>{tr('res.gloss.llm.pending', llengua_desti)}</b> <i>{tr('res.gloss.llm.generating')}</i></div>"
                    )
                elif glossa_llm:
                    etiqueta_origen = tr("res.source.cache") if ve_de_cache else "Ollama"
                    linies_g.append(
                        f"<div style='margin-top: 5px; color: #146c43;'>"
                        f"<b>{tr('res.gloss.llm.done', llengua_desti, etiqueta_origen)}</b> <span style='color: #198754; font-weight: 600;'>{glossa_llm}</span></div>"
                    )

                if linies_g:
                    bloc_glossa = (
                        "<div style='margin-top: 10px; padding: 8px 12px; background-color: #f8f9fa; border-left: 3px solid #0d6efd; border-radius: 4px; font-size: 13.5px;'>"
                        + "".join(linies_g)
                        + "</div>"
                    )

            html_info += (
                "<div style='background-color: #f6f8fa; border: 1px solid #d0d7de; border-radius: 8px; padding: 16px; margin-bottom: 18px;'>"
                "<div style='border-bottom: 1px solid #d0d7de; padding-bottom: 8px; margin-bottom: 10px;'>"
                f"<span style='font-size: 20px; color: #0969da; font-weight: bold;'>{entry['enunciat_cap']}</span>"
                f"&nbsp;&nbsp;&nbsp;<span style='background-color: #eaeef2; color: #24292f; padding: 3px 8px; border-radius: 12px; font-size: 12px; font-weight: bold;'>{entry['categoria_nom']}</span>"
                "</div>"
                f"{entry['detalls_html']}"
                f"{bloc_glossa}"
                f"{entry['bloc_familia']}"
                f"{entry['bloc_formes_html']}"
                "</div>"
            )

            latex_info_blocs.append(f"\\subsection*{{{escapar_latex(entry['enunciat_cap'])} [{escapar_latex(entry['categoria_nom'])}]}}")
            if glossa_en:
                latex_info_blocs.append(f"\\textbf{{{escapar_latex(tr('res.gloss.en'))}}} {escapar_latex(glossa_en)}\\\\")
            if glossa_llm:
                latex_info_blocs.append(f"\\textbf{{{escapar_latex(tr('res.gloss.llm.pending', llengua_desti))}}} {escapar_latex(glossa_llm)}\\\\")
            if entry["tags_latex"]:
                latex_info_blocs.extend(["\\begin{itemize}", *sorted(entry["tags_latex"]), "\\end{itemize}", ""])

        html_info += "</div>"

        barra_scroll = self.browser_info.verticalScrollBar()
        pos_scroll = barra_scroll.value()
        self.browser_info.setHtml(html_info)
        barra_scroll.setValue(pos_scroll)

        self.export_info["plain"] = html_a_text_pla(html_info)
        self.export_info["latex"] = "\n".join(latex_info_blocs)

    def _glossa_traduida_rebuda(self, id_cerca: int, idx_entrada: int, text_traduit: str, ve_de_cache: bool):
        if id_cerca != self.cerca_id_actual or not self.estat_info_actual:
            return
        entrades = self.estat_info_actual["entrades"]
        if 0 <= idx_entrada < len(entrades):
            entrades[idx_entrada]["glossa_llm"] = text_traduit
            entrades[idx_entrada]["ve_de_cache"] = ve_de_cache
            self._renderitzar_pestanya_info()

    # ==========================================================================
    # CONSULTA DE LEMES I FORMES A LA BASE DE DADES
    # ==========================================================================
    def mostrar_informacio(self, text_a_cercar=None):
        if not text_a_cercar or not isinstance(text_a_cercar, str):
            text_a_cercar = self.input_cerca.text()

        text_cercat = text_a_cercar.strip()
        if not text_cercat:
            return

        if not os.path.exists(DB_FILE):
            self.browser_info.setHtml(f"<p style='color:red;'>{tr('status.db.missing', DB_FILE)}</p>")
            return

        assegurar_taula_cache_glosses()

        self.cerca_id_actual += 1
        id_cerca_local = self.cerca_id_actual
        if self.fil_glossa and self.fil_glossa.isRunning():
            self.fil_glossa.requestInterruption()

        conn = sqlite3.connect(DB_FILE)
        cur = conn.cursor()

        clau_q = normalitzar_text(text_cercat)
        is_mode_avancat = self.chk_avancat.isChecked()

        cur.execute("SELECT DISTINCT lema FROM formes WHERE forma_clean = ?;", (clau_q,))
        lemes_trobats = [r[0] for r in cur.fetchall()]

        cur.execute("SELECT DISTINCT lema FROM formes WHERE lema = ?;", (text_cercat,))
        for r in cur.fetchall():
            if r[0] not in lemes_trobats:
                lemes_trobats.append(r[0])

        info_avancada_notes = []
        if is_mode_avancat:
            cur.execute("SELECT forma_raw, lema_canonic, origen, detalls FROM variants_hist WHERE forma_clean = ?;", (clau_q,))
            for f_raw, l_can, orig, det in cur.fetchall():
                if l_can not in lemes_trobats:
                    lemes_trobats.append(l_can)
                info_avancada_notes.append(f"Variant ({orig}): <b>{f_raw}</b> ➔ <b>{l_can}</b> [{det}]")

        if not lemes_trobats:
            if clau_q in ["sum", "es", "est", "sumus", "estis", "sunt", "eram", "ero", "fui", "esse"]:
                lemes_trobats = ["sum"]
            else:
                cur.execute("SELECT DISTINCT lema_clean FROM diccionari_ls WHERE lema_clean = ? LIMIT 1;", (clau_q,))
                row_ls = cur.fetchone()
                if row_ls:
                    lemes_trobats = [row_ls[0]]

        if not lemes_trobats:
            msg = (
                "<div style='padding: 15px; font-family: Segoe UI, sans-serif;'>"
                f"{tr('res.notfound', text_cercat)}</div>"
            )
            self.estat_info_actual = None
            self.browser_info.setHtml(msg)
            self.browser_flexio.setHtml("")
            self.browser_perseus.setHtml("")
            self.export_info = {"plain": "", "latex": ""}
            self.export_flexio = {"plain": "", "latex": ""}
            self.export_perseus = {"plain": "", "latex": ""}
            conn.close()
            return

        lemes_formes = {}
        for l in lemes_trobats:
            cur.execute("SELECT forma, tag FROM formes WHERE lema = ?;", (l,))
            lemes_formes[l] = cur.fetchall()

        prefer_u = detectar_preferencia_u(text_cercat, lemes_trobats, lemes_formes)

        cfg = carregar_config_yaml()
        llm_cfg = cfg.get("traduccio_llm", {})
        llengua_desti = llm_cfg.get("llengua_desti", "català")
        model_cfg = llm_cfg.get("model", "gemma4:12b")
        estat_ollama = verificar_estat_ollama(llm_cfg)
        ollama_actiu = estat_ollama["connectat"]
        model_id = resoldre_identificador_model(model_cfg, estat_ollama.get("models_digests", {}))

        # ----------------------------------------------------------------------
        # PESTANYA 1: Informació Morfològica
        # ----------------------------------------------------------------------
        entrades_info = []
        tasques_ollama = []

        for idx, lema in enumerate(lemes_trobats):
            formes = lemes_formes.get(lema, [])
            toks_tots = set()
            for _, t in formes: toks_tots.update(extreure_tokens_tag(t))

            lema_disp = aplicar_grafia(lema, prefer_u)

            if not formes:
                categoria_nom = tr("cat.dict_entry")
                enunciat_cap = lema_disp
                pos_whit = "X"
                detalls_html = (
                    "<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'>"
                    f"<tr><td><span style='background-color: #fff3cd; color: #856404; padding: 2px 7px; border-radius: 4px; font-weight: bold;'>{tr('res.ls.only')}</span></td></tr>"
                    "</table>"
                )
            else:
                es_verb = lema == "sum" or any(v in toks_tots for v in ["V", "IND", "SBJV", "IMP", "NFIN"])
                es_adj = "ADJ" in toks_tots and "PRON" not in toks_tots
                es_pron = "PRON" in toks_tots
                es_num = "NUM" in toks_tots
                es_prep = "PREP" in toks_tots
                es_conj = "CONJ" in toks_tots
                es_adv = "ADV" in toks_tots
                es_interj = "INTERJ" in toks_tots

                if es_verb:
                    info = MotorVerbsCanonic.extreure_dades_verb(lema, formes, prefer_u)
                    categoria_nom = tr("cat.verb")
                    pos_whit = "V"
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.conjugation')}</b></td><td><span style='background-color: #ddf4ff; color: #0969da; padding: 2px 7px; border-radius: 4px; font-weight: bold;'>{info['conjugacio']}</span></td></tr></table>"
                    enunciat_cap = info['enunciat']
                elif es_adj:
                    info = MotorAdjectiusCanonic.extreure_dades_adjectiu(lema, formes, prefer_u)
                    categoria_nom = tr("cat.adj")
                    pos_whit = "ADJ"
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.classification')}</b></td><td><b>{info['desc']}</b></td></tr><tr><td><b>{tr('lbl.paradigm')}</b></td><td><span style='background-color: #ddf4ff; color: #0969da; padding: 2px 7px; border-radius: 4px; font-weight: bold;'>{info['paradigma']}</span></td></tr></table>"
                    enunciat_cap = info['enunciat']
                elif es_pron:
                    categoria_nom = tr("cat.pron")
                    pos_whit = "PRON"
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.category')}</b></td><td><span style='background-color: #ddf4ff; color: #0969da; padding: 2px 7px; border-radius: 4px; font-weight: bold;'>{tr('val.pronominal')}</span></td></tr></table>"
                    enunciat_cap = lema_disp
                elif es_prep:
                    categoria_nom = tr("cat.prep")
                    pos_whit = "PREP"
                    regim = tr("case.ABL") if "ABL" in toks_tots and "ACC" not in toks_tots else (tr("case.ACC") if "ACC" in toks_tots and "ABL" not in toks_tots else f"{tr('case.ACC')} / {tr('case.ABL')}")
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.regimen')}</b></td><td>{tr('val.prep_gov', regim)}</td></tr></table>"
                    enunciat_cap = lema_disp
                elif es_conj:
                    categoria_nom = tr("cat.conj")
                    pos_whit = "CONJ"
                    tipus = tr("val.coord") if "COORD" in toks_tots else tr("val.subord")
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.type')}</b></td><td>{tr('val.conj_type', tipus)}</td></tr></table>"
                    enunciat_cap = lema_disp
                elif es_adv:
                    categoria_nom = tr("cat.adv")
                    pos_whit = "ADV"
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.type')}</b></td><td>{tr('val.adv_inv')}</td></tr></table>"
                    enunciat_cap = lema_disp
                elif es_num:
                    categoria_nom = tr("cat.num")
                    pos_whit = "NUM"
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.type')}</b></td><td>{tr('cat.num')}</td></tr></table>"
                    enunciat_cap = lema_disp
                elif es_interj:
                    categoria_nom = tr("cat.interj")
                    pos_whit = "INTERJ"
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.type')}</b></td><td>{tr('cat.interj')}</td></tr></table>"
                    enunciat_cap = lema_disp
                else:
                    info = MotorNomsCanonic.extreure_dades_nom(lema, formes, prefer_u)
                    categoria_nom = info['categoria']
                    pos_whit = "N"
                    detalls_html = f"<table border='0' cellpadding='4' cellspacing='0' style='font-size: 14px;'><tr><td width='130'><b>{tr('lbl.gender')}</b></td><td><b>{info['genere']}</b></td></tr><tr><td><b>{tr('lbl.paradigm')}</b></td><td><span style='background-color: #ddf4ff; color: #0969da; padding: 2px 7px; border-radius: 4px; font-weight: bold;'>{info['declinacio']}</span></td></tr></table>"
                    enunciat_cap = info['enunciat']

            c_lem = normalitzar_text(lema)
            cur.execute("SELECT glossa FROM glosses WHERE clau_clean = ? AND pos = ? LIMIT 1;", (c_lem, pos_whit))
            r_glo = cur.fetchone()
            if not r_glo:
                cur.execute("SELECT glossa FROM glosses WHERE clau_clean = ? LIMIT 1;", (c_lem,))
                r_glo = cur.fetchone()

            glossa_en = r_glo[0] if r_glo else ""

            bloc_familia = ""
            if is_mode_avancat:
                cur.execute("SELECT derivats FROM families WHERE lema_clean = ?;", (c_lem,))
                r_fam = cur.fetchone()
                if r_fam:
                    mots = [m.strip() for m in r_fam[0].split(',') if m.strip()]
                    mots_fmt = ", ".join(mots[:12])
                    if len(mots) > 12: mots_fmt += f" <i>{tr('res.more', len(mots)-12)}</i>"
                    bloc_familia = f"<div style='margin-top: 10px; padding: 10px; background-color: #f6f8fa; border: 1px dashed #d0d7de; border-radius: 4px; font-size: 13px;'><b>{tr('res.family')}</b> <span>{mots_fmt}</span></div>"

            bloc_formes_html = ""
            tags_latex = set()
            if formes:
                bloc_formes_html += f"<div style='margin-top: 14px;'><p style='margin-bottom: 4px; font-size: 13px; font-weight: bold; color: #24292f;'>{tr('res.forms.title')}</p><ul style='margin-top: 4px; padding-left: 20px; font-size: 13px;'>"
                tags_trobats = set()
                for f, t in formes:
                    if normalitzar_text(f) == clau_q:
                        f_display = aplicar_grafia(f, prefer_u)
                        tags_trobats.add(f"<li>{tr('res.forms.exact')} <b>{f_display}</b> &nbsp;➔&nbsp; <code style='background-color: #eff1f3; padding: 2px 5px; border-radius: 3px;'>{t}</code></li>")
                        tags_latex.add(f"  \\item \\textbf{{{escapar_latex(f_display)}}}: \\texttt{{{escapar_latex(t)}}}")

                bloc_formes_html += "".join(tags_trobats) if tags_trobats else f"<li><i>{tr('res.forms.canonical')}</i></li>"
                bloc_formes_html += f"</ul><p style='color: #656d76; margin: 6px 0 0 0; font-size: 12px;'>{tr('res.forms.total')} <b>{len(formes)}</b></p></div>"

            glossa_cache = obtenir_glossa_cache(c_lem, pos_whit, llengua_desti, model_id)
            ve_de_cache = glossa_cache is not None

            if ve_de_cache:
                glossa_inicial = glossa_cache
            elif ollama_actiu:
                glossa_inicial = None
                tasques_ollama.append({
                    "idx": idx,
                    "lema_clean": c_lem,
                    "pos_whit": pos_whit,
                    "lema": enunciat_cap,
                    "categoria": categoria_nom,
                    "glossa_en": glossa_en
                })
            else:
                glossa_inicial = ""

            entrades_info.append({
                "enunciat_cap": enunciat_cap,
                "categoria_nom": categoria_nom,
                "detalls_html": detalls_html,
                "glossa_en": glossa_en,
                "glossa_llm": glossa_inicial,
                "ve_de_cache": ve_de_cache,
                "bloc_familia": bloc_familia,
                "bloc_formes_html": bloc_formes_html,
                "tags_latex": tags_latex
            })

        self.estat_info_actual = {
            "text_cercat": text_cercat,
            "is_mode_avancat": is_mode_avancat,
            "info_avancada_notes": info_avancada_notes,
            "llengua_desti": llengua_desti,
            "ollama_actiu": ollama_actiu,
            "entrades": entrades_info
        }

        self._renderitzar_pestanya_info()

        if ollama_actiu and tasques_ollama:
            self.fil_glossa = FilTraduccioGlossaOllama(id_cerca_local, tasques_ollama, llm_cfg, model_id)
            self.fil_glossa.glossa_traduida.connect(self._glossa_traduida_rebuda)
            self.fil_glossa.start()

        # ----------------------------------------------------------------------
        # PESTANYA 2: Flexió Canònica
        # ----------------------------------------------------------------------
        html_flex = (
            "<div style='font-family: Segoe UI, Arial, sans-serif; padding: 12px; line-height: 1.5;'>"
            f"<h2 style='color: #1f2328; margin-bottom: 12px; border-bottom: 2px solid #0969da; padding-bottom: 6px;'>{tr('flex.title')} <span style='color: #0969da;'><i>{text_cercat}</i></span></h2>"
        )
        latex_flex_blocs = [f"\\section*{{{escapar_latex(tr('flex.latex.title'))}: \\textit{{{escapar_latex(text_cercat)}}}}}"]

        for idx, lema_mestre in enumerate(lemes_trobats, 1):
            formes_mestre = lemes_formes.get(lema_mestre, [])
            toks_mestre = set()
            for _, t in formes_mestre: toks_mestre.update(extreure_tokens_tag(t))

            lema_disp_m = aplicar_grafia(lema_mestre, prefer_u)
            html_flex += "<div style='margin-bottom: 30px; border-bottom: 2px dashed #d0d7de; padding-bottom: 25px;'>"

            if not formes_mestre:
                html_flex += (
                    f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; padding: 12px; border-radius: 6px; margin-bottom: 15px;'>"
                    f"<p style='margin: 0; font-size: 15px;'><b>{tr('sent.col.lemma')}:</b> <span style='font-size: 18px; color: #0366d6;'><b>{lema_disp_m}</b></span></p></div>"
                    f"<p style='color: #6c757d; font-size: 14px;'><i>{tr('flex.notables')}</i></p>"
                )
                latex_flex_blocs.append(f"\\subsection*{{{escapar_latex(lema_disp_m)}}}\n{escapar_latex(tr('flex.notables'))}\n")
            else:
                es_verb_mestre = lema_mestre == "sum" or any(v in toks_mestre for v in ["V", "IND", "SBJV", "IMP", "NFIN"])
                es_adj_mestre = "ADJ" in toks_mestre and "PRON" not in toks_mestre
                es_pron_mestre = "PRON" in toks_mestre or ("NUM" in toks_mestre and len(formes_mestre) > 1)

                if es_verb_mestre:
                    info_v = MotorVerbsCanonic.extreure_dades_verb(lema_mestre, formes_mestre, prefer_u)
                    html_flex += MotorVerbsCanonic.generar_taula_html(info_v, text_cercat, prefer_u)
                    latex_flex_blocs.append(MotorVerbsCanonic.generar_latex(info_v, prefer_u))
                elif es_adj_mestre:
                    info_adj = MotorAdjectiusCanonic.extreure_dades_adjectiu(lema_mestre, formes_mestre, prefer_u)
                    html_flex += f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; padding: 12px; border-radius: 6px; margin-bottom: 15px;'><p style='margin: 0; font-size: 15px;'><b>{tr('cat.adj')}:</b> <span style='font-size: 18px; color: #0366d6;'><b>{info_adj['enunciat']}</b></span> — <i>{info_adj['desc']}</i></p></div>"
                    html_flex += MotorAdjectiusCanonic.generar_taula_html(info_adj, text_cercat, prefer_u)
                    latex_flex_blocs.append(MotorAdjectiusCanonic.generar_latex(info_adj, prefer_u))
                elif es_pron_mestre:
                    html_flex += f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; padding: 12px; border-radius: 6px; margin-bottom: 15px;'><p style='margin: 0; font-size: 15px;'><b>{tr('cat.pron')}:</b> <span style='font-size: 18px; color: #0366d6;'><b>{lema_disp_m}</b></span></p></div>"
                    html_flex += MotorPronomsCanonic.generar_taula_html(formes_mestre, text_cercat, prefer_u)
                    latex_flex_blocs.append(MotorPronomsCanonic.generar_latex(lema_disp_m, formes_mestre, prefer_u))
                elif any(inv in toks_mestre for inv in ["PREP", "CONJ", "ADV", "INTERJ", "INVAR"]):
                    html_flex += f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; padding: 12px; border-radius: 6px; margin-bottom: 15px;'><p style='margin: 0; font-size: 15px;'><b>{tr('flex.invar.header')}</b> <span style='font-size: 18px; color: #0366d6;'><b>{lema_disp_m}</b></span></p></div><p style='font-size: 14px;'><i>{tr('flex.invar.desc')}</i></p>"
                    latex_flex_blocs.append(f"\\subsection*{{{escapar_latex(lema_disp_m)}}}\n{escapar_latex(tr('flex.invar.desc'))}\n")
                else:
                    info_nom = MotorNomsCanonic.extreure_dades_nom(lema_mestre, formes_mestre, prefer_u)
                    html_flex += f"<div style='background-color: #f1f8ff; border: 1px solid #c8e1ff; padding: 12px; border-radius: 6px; margin-bottom: 15px;'><p style='margin: 0; font-size: 15px;'><b>{tr('cat.noun')}:</b> <span style='font-size: 18px; color: #0366d6;'><b>{info_nom['enunciat']}</b></span> — <i>{info_nom['genere']}</i> ({info_nom['declinacio']})</p></div>"
                    html_flex += MotorNomsCanonic.generar_taula_html(formes_mestre, text_cercat, prefer_u)
                    latex_flex_blocs.append(MotorNomsCanonic.generar_latex(info_nom, formes_mestre, prefer_u))

            html_flex += "</div>"

        html_flex += "</div>"
        self.export_flexio["plain"] = html_a_text_pla(html_flex)
        self.export_flexio["latex"] = "\n".join(latex_flex_blocs)

        # ----------------------------------------------------------------------
        # PESTANYA 3: Lewis & Short
        # ----------------------------------------------------------------------
        html_perseus = "<div style='font-family: Georgia, serif; font-size: 14.5px; padding: 12px;'>"
        articles_trobats = False
        for l in lemes_trobats:
            c_l = normalitzar_text(l)
            cur.execute("SELECT html FROM diccionari_ls WHERE lema_clean = ?;", (c_l,))
            rows_ls = cur.fetchall()
            if rows_ls:
                articles_trobats = True
                for r in rows_ls: html_perseus += r[0]

        if not articles_trobats:
            html_perseus += f"<p><i>{tr('res.ls.notfound', text_cercat)}</i></p>"
        html_perseus += "</div>"

        text_pla_ls = html_a_text_pla(html_perseus)
        self.export_perseus["plain"] = text_pla_ls
        self.export_perseus["latex"] = (
            f"\\section*{{Lewis \\& Short: \\textit{{{escapar_latex(text_cercat)}}}}}\n"
            f"\\begin{{quote}}\n{escapar_latex(text_pla_ls)}\n\\end{{quote}}"
        )

        conn.close()

        self.browser_flexio.setHtml(html_flex)
        self.browser_perseus.setHtml(html_perseus)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = DiccionariLatinApp()
    window.show()
    sys.exit(app.exec())
