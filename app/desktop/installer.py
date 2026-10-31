import json
import re
from pathlib import Path

from shared.config.settings import ROOT_DIR, settings

CHANNELS = (
    {"id": "windows10-11", "marker": "Windows10-11", "label": "Windows 10 y 11"},
    {"id": "windows7-8", "marker": "Windows7-8", "label": "Windows 7, 8 y 8.1"},
)

DEFAULT_INSTALLER_URLS = {
    "windows10-11": "https://github.com/promethix-IA/promethixia-instaladores/releases/download/instalador-1.0.0/Promethixia-POS-Instalador-1.0.0-Windows10-11.exe",
    "windows7-8": "https://github.com/promethix-IA/promethixia-instaladores/releases/download/instalador-1.0.0/Promethixia-POS-Instalador-1.0.0-Windows7-8.exe",
}


def normalize_channel(value: str | None) -> str:
    raw = re.sub(r"[\s_]+", "-", (value or "").strip().lower())
    if raw in {"windows7-8", "windows7", "win7", "win7-8", "7-8", "7"}:
        return "windows7-8"
    return "windows10-11"


def channel_meta(channel_id: str) -> dict:
    wanted = normalize_channel(channel_id)
    return next((item for item in CHANNELS if item["id"] == wanted), CHANNELS[0])


def _search_roots() -> list[Path]:
    configured = settings.desktop_installer_path.strip()
    roots: list[Path] = []
    if configured:
        roots.append(Path(configured))
    roots.extend(
        [
            ROOT_DIR.parent / "Sistema-Pos-Escritorio" / "instalador",
            ROOT_DIR / "instalador",
            Path("/opt/render/project/src/instalador"),
        ]
    )
    return roots


def find_channel_installer(channel_id: str) -> Path | None:
    marker = channel_meta(channel_id)["marker"]
    for item in _search_roots():
        if item.is_file() and item.suffix.lower() == ".exe" and marker in item.name:
            return item
        if not item.is_dir():
            continue
        matches = sorted(path for path in item.glob("*.exe") if path.is_file() and marker in path.name)
        if matches:
            return matches[0]
    return None


def find_installer(channel: str | None = None) -> Path | None:
    return find_channel_installer(normalize_channel(channel))


def installer_url(channel_id: str) -> str:
    wanted = normalize_channel(channel_id)
    if wanted == "windows7-8":
        configured = settings.desktop_installer_url_windows7_8.strip()
    else:
        configured = settings.desktop_installer_url_windows10_11.strip()
    return configured or DEFAULT_INSTALLER_URLS[wanted]


def published_version() -> str:
    candidates = [
        ROOT_DIR / "version.json",
        ROOT_DIR.parent / "Sistema-Pos-Escritorio" / "electron" / "version.json",
        ROOT_DIR.parent / "Sistema-Pos-Escritorio" / "build" / "PromethixiaPOS" / "version.json",
    ]
    for path in candidates:
        if not path.is_file():
            continue
        try:
            fecha = str(json.loads(path.read_text(encoding="utf-8")).get("fecha") or "").strip()
        except (OSError, ValueError, TypeError):
            continue
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", fecha):
            return fecha
    return ""


def download_name(email: str, source: Path) -> str:
    slug = re.sub(r"[^\w.-]+", "_", (email.split("@")[0] or "negocio"), flags=re.ASCII).strip("._") or "negocio"
    suffix = source.name
    match = re.search(r"(Windows\d[\w.-]*)\.exe$", suffix, flags=re.IGNORECASE)
    channel = match.group(1) if match else "Windows"
    return f"Promethixia-POS-{slug}-{channel}.exe"


def installer_filename(email: str, channel_id: str, path: Path | None) -> str:
    source = path or Path(f"Promethixia-POS-{channel_meta(channel_id)['marker']}.exe")
    return download_name(email, source)


def installer_source(channel_id: str) -> tuple[Path | None, str]:
    wanted = normalize_channel(channel_id)
    return find_channel_installer(wanted), installer_url(wanted)


def list_installers() -> list[dict]:
    items = []
    for channel in CHANNELS:
        path, url = installer_source(channel["id"])
        items.append(
            {
                "id": channel["id"],
                "label": channel["label"],
                "ready": path is not None or bool(url),
                "filename": installer_filename("negocio", channel["id"], path),
                "size": path.stat().st_size if path else 0,
            }
        )
    return items
