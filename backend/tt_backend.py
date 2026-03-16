from __future__ import annotations

import base64
import hashlib
import os
import tarfile
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZIP_DEFLATED, ZipFile

NAME = "time-tracker-tt"
VERSION = "0.1.0"
SUMMARY = "A local CLI time tracker for work hours."
ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "src"


def build_wheel(
    wheel_directory: str,
    config_settings: dict[str, object] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build(wheel_directory, editable=False)


def build_editable(
    wheel_directory: str,
    config_settings: dict[str, object] | None = None,
    metadata_directory: str | None = None,
) -> str:
    return _build(wheel_directory, editable=True)


def build_sdist(
    sdist_directory: str,
    config_settings: dict[str, object] | None = None,
) -> str:
    sdist_name = f"{NAME}-{VERSION}.tar.gz"
    target = Path(sdist_directory) / sdist_name
    with tarfile.open(target, "w:gz") as archive:
        for relative in _source_paths():
            archive.add(ROOT / relative, arcname=f"{NAME}-{VERSION}/{relative.as_posix()}")
    return sdist_name


def get_requires_for_build_wheel(config_settings: dict[str, object] | None = None) -> list[str]:
    return []


def get_requires_for_build_editable(config_settings: dict[str, object] | None = None) -> list[str]:
    return []


def prepare_metadata_for_build_wheel(
    metadata_directory: str,
    config_settings: dict[str, object] | None = None,
) -> str:
    dist_info = f"{_dist_name()}-{VERSION}.dist-info"
    target_dir = Path(metadata_directory) / dist_info
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "METADATA").write_text(_metadata_text())
    (target_dir / "WHEEL").write_text(_wheel_text())
    (target_dir / "entry_points.txt").write_text(_entry_points_text())
    (target_dir / "RECORD").write_text("")
    return dist_info


def _build(wheel_directory: str, editable: bool) -> str:
    dist_name = _dist_name()
    wheel_name = f"{dist_name}-{VERSION}-py3-none-any.whl"
    target = Path(wheel_directory) / wheel_name
    dist_info = f"{dist_name}-{VERSION}.dist-info"
    entries: list[tuple[str, bytes]] = []

    if editable:
        entries.append((f"{dist_name}.pth", (str(SRC.resolve()) + os.linesep).encode()))
    else:
        for path in SRC.rglob("*"):
            if path.is_file():
                entries.append((path.relative_to(SRC).as_posix(), path.read_bytes()))

    entries.extend(
        [
            (f"{dist_info}/METADATA", _metadata_text().encode()),
            (f"{dist_info}/WHEEL", _wheel_text().encode()),
            (f"{dist_info}/entry_points.txt", _entry_points_text().encode()),
        ]
    )

    record_lines: list[str] = []
    with ZipFile(target, "w", compression=ZIP_DEFLATED) as archive:
        for name, data in entries:
            archive.writestr(name, data)
            record_lines.append(f"{name},{_record_hash(data)},{len(data)}")
        record_path = f"{dist_info}/RECORD"
        record_lines.append(f"{record_path},,")
        archive.writestr(record_path, "\n".join(record_lines) + "\n")

    return wheel_name


def _metadata_text() -> str:
    return "\n".join(
        [
            "Metadata-Version: 2.1",
            f"Name: {NAME}",
            f"Version: {VERSION}",
            f"Summary: {SUMMARY}",
            "Requires-Python: >=3.11",
            "",
        ]
    )


def _wheel_text() -> str:
    return "\n".join(
        [
            "Wheel-Version: 1.0",
            "Generator: tt_backend",
            "Root-Is-Purelib: true",
            "Tag: py3-none-any",
            "",
        ]
    )


def _entry_points_text() -> str:
    return "[console_scripts]\ntt = tt_tracker.cli:main\n"


def _dist_name() -> str:
    return NAME.replace("-", "_")


def _record_hash(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    encoded = base64.urlsafe_b64encode(digest).rstrip(b"=").decode()
    return f"sha256={encoded}"


def _source_paths() -> list[Path]:
    files = [Path("pyproject.toml"), Path("README.md")]
    files.extend(path.relative_to(ROOT) for path in SRC.rglob("*") if path.is_file())
    files.extend(path.relative_to(ROOT) for path in (ROOT / "tests").rglob("*") if path.is_file())
    files.extend(path.relative_to(ROOT) for path in (ROOT / "backend").rglob("*") if path.is_file())
    return files
