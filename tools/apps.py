"""
tools/apps.py — Application control tools for JARVIS.

Tools: app_launch, app_close, app_focus, app_list

Uses os.startfile for launching, psutil for listing/closing,
and pywinauto for window focusing.
"""

import os
import subprocess
import time
from pathlib import Path

import psutil
from loguru import logger

from tools.registry import Tool

# pywinauto is optional — focus tool degrades gracefully without it
try:
    import pywinauto
    from pywinauto import Desktop
    _HAS_PYWINAUTO = True
except Exception:
    _HAS_PYWINAUTO = False
    logger.warning("pywinauto not available — app_focus will be limited.")

# Common app name → executable mapping for convenience
APP_ALIASES: dict[str, str] = {
    "notepad": "notepad.exe",
    "calculator": "calc.exe",
    "explorer": "explorer.exe",
    "task manager": "taskmgr.exe",
    "paint": "mspaint.exe",
    "word": "winword.exe",
    "excel": "excel.exe",
    "powerpoint": "powerpnt.exe",
    "chrome": "chrome.exe",
    "firefox": "firefox.exe",
    "edge": "msedge.exe",
    "vs code": "code.exe",
    "vscode": "code.exe",
    "code": "code.exe",
    "terminal": "wt.exe",
    "windows terminal": "wt.exe",
    "cmd": "cmd.exe",
    "powershell": "powershell.exe",
    "spotify": "Spotify.exe",
    "discord": "Discord.exe",
    "slack": "slack.exe",
    "zoom": "Zoom.exe",
    "obs": "obs64.exe",
    "vlc": "vlc.exe",
    "steam": "steam.exe",
}


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------

def _find_app_in_start_menu(query: str) -> str | None:
    """
    Search Start Menu AND Desktop .lnk shortcuts for a fuzzy name match.
    Covers: factory apps, Microsoft Store, Steam, Epic, Xbox, and any
    manually placed desktop shortcuts.
    Returns the full path of the best-matching .lnk or None.
    """
    user_profile = Path(os.environ.get("USERPROFILE", Path.home()))

    search_dirs = [
        # Per-user Start Menu
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        # All-users Start Menu
        Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
        # User Desktop — catches Steam/Epic/Xbox game shortcuts
        user_profile / "Desktop",
        # Public Desktop
        Path(os.environ.get("PUBLIC", "C:\\Users\\Public")) / "Desktop",
        # OneDrive Desktop (common on modern Windows)
        user_profile / "OneDrive" / "Desktop",
    ]

    query_lower = query.lower()
    best: tuple[int, str] | None = None  # (score, path)

    for search_dir in search_dirs:
        if not search_dir.is_dir():
            continue
        for lnk in search_dir.rglob("*.lnk"):
            stem = lnk.stem.lower()
            # Exact match
            if stem == query_lower:
                return str(lnk)
            # Query is fully contained in the shortcut name
            if query_lower in stem:
                score = len(stem)  # prefer shorter (more specific) names
                if best is None or score < best[0]:
                    best = (score, str(lnk))
            # Shortcut name is contained in query (e.g. "word" inside "microsoft word")
            elif stem in query_lower:
                score = len(stem) + 1000  # lower priority
                if best is None or score < best[0]:
                    best = (score, str(lnk))

    return best[1] if best else None


def _find_app_in_registry(query: str) -> str | None:
    """
    Search HKLM\\SOFTWARE\\Microsoft\\Windows\\CurrentVersion\\App Paths
    for a matching executable.
    """
    try:
        import winreg
        key_path = r"SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths"
        query_lower = query.lower()
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    i += 1
                    stem = subkey_name.lower().replace(".exe", "")
                    if query_lower == stem or query_lower in stem or stem in query_lower:
                        with winreg.OpenKey(key, subkey_name) as sub:
                            try:
                                path, _ = winreg.QueryValueEx(sub, "")
                                if path and Path(path).exists():
                                    return path
                            except FileNotFoundError:
                                pass
                except OSError:
                    break
    except Exception:
        pass
    return None


def _find_app_in_common_dirs(query: str) -> str | None:
    """
    Brute-force search through common install directories for a matching .exe.
    """
    search_dirs = [
        Path(os.environ.get("PROGRAMFILES", "C:\\Program Files")),
        Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)")),
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs",
        Path(os.environ.get("LOCALAPPDATA", "")),
        Path("C:\\Windows\\System32"),
        Path("C:\\Windows"),
    ]
    query_lower = query.lower()
    for d in search_dirs:
        if not d.is_dir():
            continue
        # Only go 3 levels deep to keep it fast
        for exe in d.rglob("*.exe"):
            try:
                if query_lower in exe.stem.lower():
                    return str(exe)
            except Exception:
                continue
    return None


# ---------------------------------------------------------------------------
# Steam game finder — reads steamapps manifests
# ---------------------------------------------------------------------------

def _get_steam_library_paths() -> list[Path]:
    """Return all Steam library paths from the registry + libraryfolders.vdf."""
    paths: list[Path] = []
    try:
        import winreg
        for hive in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
            for sub in (r"SOFTWARE\Valve\Steam", r"SOFTWARE\WOW6432Node\Valve\Steam"):
                try:
                    with winreg.OpenKey(hive, sub) as k:
                        install_path, _ = winreg.QueryValueEx(k, "InstallPath")
                        steam_root = Path(install_path)
                        paths.append(steam_root / "steamapps")
                except Exception:
                    pass
    except Exception:
        pass

    # Parse libraryfolders.vdf for extra library locations
    for base in paths[:]:
        vdf = base / "libraryfolders.vdf"
        if not vdf.exists():
            continue
        try:
            text = vdf.read_text(encoding="utf-8", errors="replace")
            import re
            for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                lib = Path(m.group(1)) / "steamapps"
                if lib.is_dir() and lib not in paths:
                    paths.append(lib)
        except Exception:
            pass
    return paths


def _find_steam_game(query: str) -> str | None:
    """
    Parse Steam appmanifest_*.acf files to find a game by name.
    Returns the absolute path to the best-matching game executable, or None.
    """
    import re
    query_lower = query.lower()
    best: tuple[int, str] | None = None  # (score, exe_path)

    for steamapps_dir in _get_steam_library_paths():
        if not steamapps_dir.is_dir():
            continue
        for acf in steamapps_dir.glob("appmanifest_*.acf"):
            try:
                text = acf.read_text(encoding="utf-8", errors="replace")
                name_m = re.search(r'"name"\s+"([^"]+)"', text)
                dir_m  = re.search(r'"installdir"\s+"([^"]+)"', text)
                if not name_m or not dir_m:
                    continue
                game_name = name_m.group(1).lower()
                install_dir = dir_m.group(1)
                game_path = steamapps_dir / "common" / install_dir
                if not game_path.is_dir():
                    continue

                # Score the match
                if query_lower == game_name:
                    score = 0  # perfect
                elif query_lower in game_name:
                    score = len(game_name)
                elif game_name in query_lower:
                    score = len(game_name) + 500
                elif any(w in game_name for w in query_lower.split() if len(w) > 2):
                    score = len(game_name) + 1000
                else:
                    continue

                # Find the best .exe — prefer ones whose name matches the query or game name
                exes = list(game_path.glob("*.exe"))  # top-level only (fast)
                if not exes:
                    exes = list(game_path.rglob("*.exe"))  # deeper scan if needed
                if not exes:
                    continue

                # Prefer exe whose stem is in the game name or query
                def exe_score(e: Path) -> int:
                    s = e.stem.lower()
                    if query_lower in s or s in query_lower:
                        return 0
                    if any(word in s for word in game_name.split() if len(word) > 2):
                        return 1
                    # Penalise launcher/crash-handler/redist exes
                    if any(x in s for x in ("launcher", "crash", "redist", "setup", "install", "unins", "eac", "anti")):
                        return 99
                    return 10

                exes.sort(key=exe_score)
                best_exe = str(exes[0])

                if best is None or score < best[0]:
                    best = (score, best_exe)
            except Exception:
                continue

    return best[1] if best else None


# ---------------------------------------------------------------------------
# Epic Games finder — reads Epic manifests JSON
# ---------------------------------------------------------------------------

def _find_epic_game(query: str) -> str | None:
    """
    Parse Epic Games Launcher manifest .item files to find a game by name.
    Returns the absolute path to the game executable, or None.
    """
    import json
    query_lower = query.lower()

    manifest_dir = Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / \
        "Epic" / "EpicGamesLauncher" / "Data" / "Manifests"
    if not manifest_dir.is_dir():
        # Alternate location
        manifest_dir = Path(os.environ.get("LOCALAPPDATA", "")) / \
            "EpicGamesLauncher" / "Saved" / "Config" / "Windows"

    best: tuple[int, str] | None = None

    for item_file in manifest_dir.glob("*.item"):
        try:
            data = json.loads(item_file.read_text(encoding="utf-8", errors="replace"))
            display_name = data.get("DisplayName", "").lower()
            launch_exe  = data.get("LaunchExecutable", "")
            install_loc = data.get("InstallLocation", "")
            if not display_name or not install_loc:
                continue

            if query_lower == display_name:
                score = 0
            elif query_lower in display_name:
                score = len(display_name)
            elif display_name in query_lower:
                score = len(display_name) + 500
            elif any(w in display_name for w in query_lower.split() if len(w) > 2):
                score = len(display_name) + 1000
            else:
                continue

            exe_path = Path(install_loc) / launch_exe if launch_exe else None
            if exe_path and exe_path.exists():
                if best is None or score < best[0]:
                    best = (score, str(exe_path))
            else:
                # Fallback: find any .exe in install dir
                install_path = Path(install_loc)
                if install_path.is_dir():
                    exes = sorted(install_path.glob("*.exe"),
                                  key=lambda e: 0 if query_lower in e.stem.lower() else 1)
                    if exes and (best is None or score < best[0]):
                        best = (score, str(exes[0]))
        except Exception:
            continue

    return best[1] if best else None


# ---------------------------------------------------------------------------
# Common game directory scanner (direct downloads / manual installs)
# ---------------------------------------------------------------------------

def _find_in_game_dirs(query: str) -> str | None:
    """
    Search common game installation directories on all drives for a matching exe.
    Covers games downloaded directly from the web (not via a launcher).
    """
    user_profile = Path(os.environ.get("USERPROFILE", Path.home()))
    pf   = Path(os.environ.get("PROGRAMFILES",      "C:\\Program Files"))
    pf86 = Path(os.environ.get("PROGRAMFILES(X86)", "C:\\Program Files (x86)"))

    # Check every available drive letter for game folders
    drive_roots: list[Path] = []
    for letter in "CDEFGHIJKLMNOPQRSTUVWXYZ":
        d = Path(f"{letter}:\\")
        if d.exists():
            drive_roots.append(d)

    game_folder_names = ["Games", "Game", "SteamLibrary", "EpicGames", "GOG Games", "Ubisoft"]

    candidate_dirs: list[Path] = [
        pf / "Games",
        pf86 / "Games",
        pf / "GOG Games",
        user_profile / "Games",
    ]
    for drive in drive_roots:
        for folder in game_folder_names:
            p = drive / folder
            if p.is_dir():
                candidate_dirs.append(p)

    query_lower = query.lower()
    query_words = [w for w in query_lower.split() if len(w) > 2]

    for game_dir in candidate_dirs:
        if not game_dir.is_dir():
            continue
        # Each sub-folder is typically one game
        try:
            for sub in game_dir.iterdir():
                if not sub.is_dir():
                    continue
                sub_name = sub.name.lower()
                if query_lower in sub_name or sub_name in query_lower or \
                   any(w in sub_name for w in query_words):
                    # Find the best exe in this game folder
                    exes = list(sub.glob("*.exe"))
                    if not exes:
                        exes = list(sub.rglob("*.exe"))
                    exes = [e for e in exes if not any(
                        x in e.stem.lower() for x in
                        ("unins", "setup", "install", "crash", "redist", "launcher_old")
                    )]
                    if exes:
                        # Prefer exe whose name matches the query
                        exes.sort(key=lambda e: 0 if query_lower in e.stem.lower() else 1)
                        return str(exes[0])
        except PermissionError:
            continue
    return None


def app_launch(name: str) -> str:
    """
    Launch any application or game on this Windows PC by name.

    Search order:
      0. Direct existing file path
      1. Hardcoded alias table (common apps)
      2. Start Menu + Desktop shortcuts (.lnk)
      3. Windows Registry App Paths
      4. Steam game manifests (all library folders)
      5. Epic Games manifests
      6. Common game directories on all drives (C:\\Games, D:\\Games, etc.)
      7. System PATH subprocess
      8. Program Files / AppData directory scan (slow last resort)
    """
    original_name = name
    name_lower = name.lower().strip()

    # 0. Direct existing path
    p = Path(name)
    if p.exists():
        try:
            os.startfile(str(p))
            kind = "folder" if p.is_dir() else "file"
            return f"Opened {kind}: {p.name}"
        except Exception as e:
            return f"Error opening '{name}': {e}"

    # 1. Hardcoded alias
    target = APP_ALIASES.get(name_lower)

    # 2. Start Menu + Desktop shortcuts
    if not target:
        lnk = _find_app_in_start_menu(name_lower)
        if lnk:
            try:
                os.startfile(lnk)
                logger.info(f"Launched via shortcut: {lnk}")
                return f"Launched {original_name}."
            except Exception as e:
                logger.warning(f"Shortcut launch failed for {lnk}: {e}")

    # 3. Registry App Paths
    if not target:
        reg_path = _find_app_in_registry(name_lower)
        if reg_path:
            target = reg_path

    # 4. Launch alias/registry hit
    if target:
        try:
            os.startfile(target)
            logger.info(f"Launched via alias/registry: {target}")
            return f"Launched {original_name}."
        except FileNotFoundError:
            pass
        try:
            subprocess.Popen([target], shell=True,
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            return f"Launched {original_name}."
        except Exception as e:
            logger.warning(f"subprocess launch failed for {target}: {e}")

    # 5. Steam
    steam_exe = _find_steam_game(name_lower)
    if steam_exe:
        try:
            subprocess.Popen([steam_exe],
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            logger.info(f"Launched Steam game: {steam_exe}")
            return f"Launched {original_name} (Steam)."
        except Exception as e:
            logger.warning(f"Steam launch failed: {e}")

    # 6. Epic Games
    epic_exe = _find_epic_game(name_lower)
    if epic_exe:
        try:
            subprocess.Popen([epic_exe],
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            logger.info(f"Launched Epic game: {epic_exe}")
            return f"Launched {original_name} (Epic Games)."
        except Exception as e:
            logger.warning(f"Epic launch failed: {e}")

    # 7. Common game directories (direct downloads, D:\Games, etc.)
    game_exe = _find_in_game_dirs(name_lower)
    if game_exe:
        try:
            subprocess.Popen([game_exe],
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            logger.info(f"Launched from game dir: {game_exe}")
            return f"Launched {original_name}."
        except Exception as e:
            logger.warning(f"Game dir launch failed: {e}")

    # 8. Try raw name on PATH
    try:
        subprocess.Popen([name], shell=True,
                         creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
        logger.info(f"Launched via shell PATH: {name}")
        return f"Launched {original_name}."
    except Exception:
        pass

    # 9. Program Files / AppData deep scan (slow, last resort)
    exe_path = _find_app_in_common_dirs(name_lower)
    if exe_path:
        try:
            subprocess.Popen([exe_path],
                             creationflags=subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP)
            logger.info(f"Launched via dir scan: {exe_path}")
            return f"Launched {original_name}."
        except Exception as e:
            return f"Found '{original_name}' at {exe_path} but couldn't launch it: {e}"

    return (
        f"Could not find '{original_name}' on this PC. "
        "Check that it's installed, or try the full path to the .exe."
    )



def open_path(path: str) -> str:
    """
    Open any file, folder, or executable using the Windows default handler.
    Supports: images, PDFs, Word/Excel docs, videos, folders, zip files, executables, etc.
    Also supports glob patterns (e.g. 'C:\\Users\\me\\Desktop\\*.jpg') and
    vague paths — will auto-search and open the first matching file.
    """
    import glob as _glob

    # Step 1: expand ~ and %ENVVARS%
    expanded_str = os.path.expandvars(os.path.expanduser(path))

    # Step 2: if the path contains a glob wildcard, resolve it
    if "*" in expanded_str or "?" in expanded_str:
        matches = _glob.glob(expanded_str, recursive=True)
        if not matches:
            # Try a broader search: take the directory part and search for any matching ext
            parent = str(Path(expanded_str).parent)
            pattern = str(Path(expanded_str).name)
            matches = _glob.glob(os.path.join(parent, "**", pattern), recursive=True)
        if matches:
            target = Path(matches[0])
            try:
                os.startfile(str(target))
                kind = "folder" if target.is_dir() else target.suffix.upper().lstrip(".") or "file"
                logger.info(f"Opened glob match: {target}")
                return f"Opened {kind}: {target.name}"
            except Exception as e:
                return f"Error opening '{target}': {e}"
        return f"No files found matching pattern: {path}"

    # Step 3: try the exact expanded path
    p = Path(expanded_str)
    if p.exists():
        try:
            os.startfile(str(p))
            kind = "folder" if p.is_dir() else p.suffix.upper().lstrip(".") or "file"
            logger.info(f"Opened via os.startfile: {p}")
            return f"Opened {kind}: {p.name}"
        except Exception as e:
            return f"Error opening '{path}': {e}"

    # Step 4: file not found — if a parent dir exists, search it for the extension
    p_obj = Path(expanded_str)
    parent_dir = p_obj.parent
    ext = p_obj.suffix.lower()  # e.g. ".jpg"
    if parent_dir.is_dir() and ext:
        candidates = sorted(parent_dir.glob(f"*{ext}"), key=lambda f: f.stat().st_mtime, reverse=True)
        if candidates:
            first = candidates[0]
            try:
                os.startfile(str(first))
                kind = first.suffix.upper().lstrip(".")
                logger.info(f"Opened nearest match in dir: {first}")
                return f"Opened {kind}: {first.name}"
            except Exception as e:
                return f"Error opening '{first}': {e}"

    return f"Error: Path not found: {path}"


def app_close(name: str) -> str:
    """
    Close all running instances of an application by name.

    Args:
        name: Application name (e.g. 'notepad', 'chrome'). Case-insensitive.
    """
    name_lower = name.lower().replace(".exe", "")
    closed = 0
    errors = []

    for p in psutil.process_iter(["pid", "name"]):
        try:
            pname = (p.info["name"] or "").lower().replace(".exe", "")
            if pname == name_lower or name_lower in pname:
                p.terminate()
                closed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied) as e:
            errors.append(str(e))

    if closed == 0 and not errors:
        return f"No running process found matching '{name}'."
    parts = []
    if closed:
        parts.append(f"Closed {closed} instance(s) of '{name}'.")
    if errors:
        parts.append(f"Could not close {len(errors)} instance(s).")
    return " ".join(parts)


def app_focus(name: str) -> str:
    """
    Bring a running application window to the foreground by name.

    Args:
        name: Application or window title (partial match accepted).
    """
    if not _HAS_PYWINAUTO:
        return "Error: pywinauto not available — cannot focus windows."
    try:
        desktop = Desktop(backend="uia")
        windows = desktop.windows()
        name_lower = name.lower()
        matched = [w for w in windows if name_lower in (w.window_text() or "").lower()]
        if not matched:
            return f"No open window matching '{name}' found."
        matched[0].set_focus()
        return f"Focused window: {matched[0].window_text()}"
    except Exception as e:
        return f"Error focusing '{name}': {e}"


def app_list() -> str:
    """Return a list of all currently running application windows (unique app names)."""
    try:
        seen = set()
        names = []
        for p in psutil.process_iter(["pid", "name", "status"]):
            try:
                n = p.info["name"]
                if n and n not in seen and p.info["status"] == psutil.STATUS_RUNNING:
                    seen.add(n)
                    names.append(n)
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        names.sort()
        if not names:
            return "No running processes found."
        return f"Running processes ({len(names)}):\n" + "\n".join(f"  {n}" for n in names)
    except Exception as e:
        return f"Error listing apps: {e}"


# ---------------------------------------------------------------------------
# Tool definitions
# ---------------------------------------------------------------------------

APP_TOOLS = [
    Tool(
        name="app_launch",
        description=(
            "Launch ANY application installed on this Windows PC by name. "
            "Searches Start Menu shortcuts, Windows registry, PATH, and install directories. "
            "Use when the user says 'open X', 'launch X', or 'start X' by APP NAME "
            "(e.g. 'teams', 'chrome', 'photoshop', 'steam'). "
            "If the user gives a FILE PATH or FOLDER PATH, use open_path instead."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "App name (e.g. 'notepad', 'vs code', 'spotify') or executable path."
                }
            },
            "required": ["name"]
        },
        handler=app_launch,
        risk_level="medium",
    ),
    Tool(
        name="open_path",
        description=(
            "Open any file, folder, image, video, document, or executable using Windows' default program — "
            "exactly like double-clicking it in File Explorer. "
            "Use this when the user provides a FILE PATH or FOLDER PATH, or says things like: "
            "'open this image', 'open the downloads folder', 'open C:\\\\Users\\\\me\\\\photo.jpg', "
            "'show me that PDF', 'open my desktop', 'open the zip file'. "
            "Supports: images, PDFs, Word docs, Excel sheets, videos, folders, .exe files, .lnk shortcuts, etc."
        ),
        args_schema={
            "type": "object",
            "properties": {
                "path": {
                    "type": "string",
                    "description": (
                        "Absolute path to open, e.g. 'C:\\\\Users\\\\me\\\\Downloads', "
                        "'C:\\\\Users\\\\me\\\\photo.jpg', '%USERPROFILE%\\\\Desktop'."
                    )
                }
            },
            "required": ["path"]
        },
        handler=open_path,
        risk_level="low",
    ),
    Tool(
        name="app_close",
        description="Close/terminate all running instances of an application by name. Use when the user says 'close X' or 'quit X'.",
        args_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Application name to close (e.g. 'notepad', 'chrome'). Case-insensitive."
                }
            },
            "required": ["name"]
        },
        handler=app_close,
        risk_level="medium",
    ),
    Tool(
        name="app_focus",
        description="Bring a running application window to the foreground. Use when the user wants to switch to or focus a specific app.",
        args_schema={
            "type": "object",
            "properties": {
                "name": {
                    "type": "string",
                    "description": "Application name or part of window title to match."
                }
            },
            "required": ["name"]
        },
        handler=app_focus,
        risk_level="medium",
    ),
    Tool(
        name="app_list",
        description="List all currently running applications and processes. Use when the user asks what apps are open or running.",
        args_schema={"type": "object", "properties": {}, "required": []},
        handler=app_list,
        risk_level="low",
    ),
]
