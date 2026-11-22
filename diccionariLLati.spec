# -*- mode: python ; coding: utf-8 -*-
import os
import sys
from PyInstaller.utils.hooks import collect_all, copy_metadata

# ==============================================================================
# CONFIGURACIÓ DE COMPILACIÓ (diccionariLlati.spec)
# ==============================================================================
# Empaqueta spaCy i els motors neuronals base perquè l'executable pugui
# descarregar i carregar automàticament qualsevol model LatinCy (sm, md, lg, trf)
# configurat a config.yaml dins la carpeta externa 'models/'.
#
# Si vols generar una versió mínima sense spaCy, defineix INCLOU_SPACY=0 abans
# d'executar pyinstaller.

INCLOU_SPACY = os.environ.get("INCLOU_SPACY", "1") == "1"

datas = [
    ("config.yaml", "."),
    ("i18n.properties", "."),
]
binaries = []
hiddenimports = [
    "yaml",
    "sqlite3",
    "zipfile",
    "configparser",
]
excludes = []

if INCLOU_SPACY:
    # Recollim spaCy i totes les seves dependències compilades
    for pkg in ("spacy", "thinc", "srsly", "catalogue", "cymem", "preshed", "murmurhash", "blis", "wasabi", "confection", "weasel"):
        try:
            d, b, h = collect_all(pkg)
            datas += d
            binaries += b
            hiddenimports += h
            datas += copy_metadata(pkg)
        except Exception:
            pass

    # Suport opcional per a models basats en transformers o floret (ex. la_core_web_trf / _lg)
    for opt_pkg in ("spacy_transformers", "transformers", "floret"):
        try:
            d_opt, b_opt, h_opt = collect_all(opt_pkg)
            datas += d_opt
            binaries += b_opt
            hiddenimports += h_opt
            datas += copy_metadata(opt_pkg)
        except Exception:
            pass
else:
    excludes += ["spacy", "thinc", "torch", "transformers", "numpy", "scipy", "pandas"]

block_cipher = None

a = Analysis(
    ["diccionariLlati.py"],
    pathex=["."],
    binaries=binaries,
    datas=datas,
    hiddenimports=list(set(hiddenimports)),
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=excludes,
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="diccionariLlati",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="diccionariLlati",
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
        name="diccionariLlati.app",
        icon=None,
        bundle_identifier="cat.filologia.diccionarillati",
        info_plist={
            "NSHighResolutionCapable": "True",
            "CFBundleShortVersionString": "1.0.0",
        },
    )