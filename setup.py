"""cx_Freeze build script -> produces a Windows .msi installer.

Build the installer with:

    .venv\\Scripts\\python.exe setup.py bdist_msi

The resulting .msi appears in the dist\\ folder. (The standalone single-file
.exe is built separately with PyInstaller - see build_exe.ps1.)
"""

import os

from cx_Freeze import Executable, setup

# Run from this file's directory so relative paths resolve regardless of cwd.
os.chdir(os.path.dirname(os.path.abspath(__file__)))

from seedmapper import __version__  # noqa: E402

# Locate the cubiomes DLL that cubiomespi loads at runtime via ctypes.
import cubiomespi  # noqa: E402

_cub_dir = os.path.dirname(cubiomespi.__file__)
_dll_src = os.path.join(_cub_dir, "lib", "lib.dll")

build_exe_options = {
    "packages": ["seedmapper", "cubiomespi", "PIL", "tkinter"],
    "excludes": ["test", "unittest", "pydoc_data"],
    # Keep cubiomespi as loose files (not zipped) so ctypes can find its DLL,
    # and copy the DLL into the matching lib/ subfolder.
    "zip_exclude_packages": ["cubiomespi"],
    "include_files": [
        (_dll_src, os.path.join("lib", "cubiomespi", "lib", "lib.dll")),
    ],
    "include_msvcr": True,
}

# Stable upgrade code so future MSIs upgrade in place instead of installing twice.
bdist_msi_options = {
    "upgrade_code": "{B7E9C3A2-5D41-4F8B-9C2E-1A6F3D8E7B04}",
    "add_to_path": False,
    "initial_target_dir": r"[ProgramFilesFolder]\SeedMapper",
    "all_users": False,
}

executables = [
    Executable(
        "main.py",
        base="Win32GUI",              # windowed app, no console
        target_name="SeedMapper.exe",
        shortcut_name="SeedMapper",
        shortcut_dir="ProgramMenuFolder",
        copyright="SeedMapper",
    )
]

setup(
    name="SeedMapper",
    version=__version__,
    description="Minecraft seed map with custom waypoints",
    options={
        "build_exe": build_exe_options,
        "bdist_msi": bdist_msi_options,
    },
    executables=executables,
)
