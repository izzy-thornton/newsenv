# news_gui.spec (patched header)
from PyInstaller.utils.hooks import collect_submodules, collect_data_files
from PyInstaller.building.build_main import Analysis, PYZ, EXE, COLLECT
import os

# Use CWD instead of __file__
proj_root = os.getcwd()


# ---- Hidden imports (force-bundle modules that are sometimes missed) ----
hidden = []

# Core GUI stack
hidden += ['PySimpleGUI', 'tkinter']
hidden += collect_submodules('PySimpleGUI')

# Matplotlib (incl. backends commonly used by Tkinter UIs)
hidden += [
    'matplotlib.backends',
    'matplotlib.backends.backend_tkagg',
    'matplotlib.backends.backend_agg',
    'matplotlib.backends.backend_pdf',
    'matplotlib.backends.backend_ps',
    'matplotlib.backends.backend_svg',
]
hidden += collect_submodules('matplotlib')

# Data / parsing libs your script likely uses
for pkg in ['pandas', 'lxml', 'bs4', 'newspaper', 'PIL']:
    try:
        hidden += collect_submodules(pkg)
    except Exception:
        pass

# ---- Data files to include ----
datas = []

# matplotlib's mpl-data (fonts, styles, etc.)
try:
    datas += collect_data_files('matplotlib', subdir='mpl-data', includes=['**/*'])
except Exception:
    pass

# newspaper3k resource files (stopwords, patterns, etc.)
try:
    datas += collect_data_files('newspaper', includes=['resources/**/*', 'resources/*'])
except Exception:
    pass

# Pillow (PIL) image plugins sometimes need explicit collection
# (PyInstaller usually handles these, but this keeps it rock-solid.)
try:
    datas += collect_data_files('PIL', includes=['*.icns', '*.ico'])
except Exception:
    pass

# NOTE on NLTK:
# If your app downloads NLTK corpora at runtime, you do NOT need to bundle them.
# If you want fully offline use, add specific corpora paths here, e.g.:
# from nltk import data as nltk_data
# datas += [(os.path.join(nltk_data.find('tokenizers/punkt').path, 'english.pickle'),
#            'nltk_data/tokenizers/punkt')]

# ---- Analysis ----
a = Analysis(
    ['news_gui.py'],
    pathex=[proj_root],
    binaries=[],
    datas=datas,
    hiddenimports=hidden,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=None)

# macOS: keep console=True while debugging; set to False for a “windowed” app
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='news_gui',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=True,        # change to False when you’re done debugging
    disable_windowed_traceback=False,
    target_arch=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    name='news_gui'
)
