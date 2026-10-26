# PyInstaller spec for the one-file Windows program:  pyinstaller packaging/atlasforge.spec
import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

HERE = os.path.dirname(os.path.abspath(SPEC))
datas = collect_data_files("atlasforge")                 # web page, thumbnails, font, Lua gadgets
datas += collect_data_files("archspec")                  # CPU tables etcpak uses to pick its fastest code
hidden = collect_submodules("atlasforge") + collect_submodules("etcpak") + collect_submodules("archspec")

a = Analysis(
    [os.path.join(HERE, "forge_app.py")],
    pathex=[os.path.dirname(HERE)],
    datas=datas,
    hiddenimports=hidden,
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "lupa", "PyQt5", "PyQt6", "PySide2", "PySide6"],
    noarchive=False,
    module_collection_mode={"archspec": "py"},        # archspec opens "cpu/../json/...": cpu/ must exist on disk
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, a.binaries, a.datas, [],
    name="AtlasMapForge",
    icon=os.path.join(HERE, "forge.ico"),
    console=False,
    upx=False,
    runtime_tmpdir=None,
)
