# usb_toolkit.core.libusb_deploy
#
# Deploys libusb-1.0.dll from the assets/ folder so pyusb has a backend on
# Windows with zero manual setup.
#
# Accepted sources, in priority order:
#   1. assets/libusb-1.0.dll                 (loose DLL)
#   2. assets/*.zip containing libusb-1.0.dll (any depth; official release
#      zips carry several arch builds — the matching one is selected)
#
# .rar archives are NOT supported (no stdlib reader); they are detected and
# reported so the user knows to re-zip.
#
# Deny-first rules:
#   * A candidate must parse as a genuine PE DLL (MZ + PE\0\0 + DLL flag).
#   * Its machine type must match the running interpreter's architecture.
#     A wrong-arch or malformed file is refused, never "tried anyway".
#   * The DLL is only ever COPIED to the staging dir and handed to pyusb by
#     explicit path. PATH is never mutated; nothing is executed by this module.
#   * Staging is atomic (temp file + os.replace) and idempotent (SHA-256
#     compare — an unchanged DLL is not rewritten).
#
# Copyright 2026 Leon Priest (7h3v01d) — PETL v1.0.

from __future__ import annotations

import hashlib
import os
import platform
import struct
import tempfile
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DLL_NAME = "libusb-1.0.dll"

# PE machine types.
MACHINE_X86 = 0x014C
MACHINE_X64 = 0x8664
MACHINE_ARM64 = 0xAA64

_MACHINE_NAMES = {MACHINE_X86: "x86", MACHINE_X64: "x64", MACHINE_ARM64: "arm64"}

# IMAGE_FILE_DLL flag in the COFF characteristics field.
_IMAGE_FILE_DLL = 0x2000


@dataclass(frozen=True)
class PeInfo:
    """Result of parsing a candidate PE file."""

    valid: bool
    machine: int = 0
    is_dll: bool = False
    reason: str = ""

    @property
    def machine_name(self) -> str:
        return _MACHINE_NAMES.get(self.machine, f"0x{self.machine:04x}")


@dataclass(frozen=True)
class DeployResult:
    """Outcome of a deployment attempt. Never raises to the caller."""

    ok: bool
    dll_path: Optional[Path] = None
    source: str = ""
    detail: str = ""


def parse_pe(data: bytes) -> PeInfo:
    """Validate PE structure and extract machine type + DLL flag.

    Minimal, offline parse: MZ magic, e_lfanew, 'PE\\0\\0' signature, then the
    COFF header's machine and characteristics fields. Anything malformed is
    refused with a reason.
    """
    if len(data) < 0x40 or data[:2] != b"MZ":
        return PeInfo(False, reason="not a PE file (missing MZ header)")
    (e_lfanew,) = struct.unpack_from("<I", data, 0x3C)
    if e_lfanew + 24 > len(data):
        return PeInfo(False, reason="truncated PE header")
    if data[e_lfanew : e_lfanew + 4] != b"PE\x00\x00":
        return PeInfo(False, reason="missing PE signature")
    (machine,) = struct.unpack_from("<H", data, e_lfanew + 4)
    (characteristics,) = struct.unpack_from("<H", data, e_lfanew + 22)
    is_dll = bool(characteristics & _IMAGE_FILE_DLL)
    if not is_dll:
        return PeInfo(False, machine, False, "PE file is not a DLL")
    return PeInfo(True, machine, True)


def host_machine(arch: Optional[str] = None) -> int:
    """Map the *interpreter's* architecture to a PE machine type.

    The DLL must match the Python process loading it, not the OS — a 32-bit
    Python on 64-bit Windows needs the x86 DLL.
    """
    arch = (arch or platform.machine()).lower()
    if arch in ("amd64", "x86_64"):
        return MACHINE_X64
    if arch in ("arm64", "aarch64"):
        return MACHINE_ARM64
    if arch in ("x86", "i386", "i486", "i586", "i686"):
        return MACHINE_X86
    return 0


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _sha256_file(path: Path) -> Optional[str]:
    try:
        return _sha256(path.read_bytes())
    except OSError:
        return None


def _candidate_from_loose(
    assets: Path, want: int
) -> Optional[tuple[Optional[bytes], str, str]]:
    """Return (dll_bytes_or_None, source_label, detail) for a loose assets DLL.

    Returns None only when no loose DLL exists at all; a present-but-refused
    DLL returns (None, source, reason) so the refusal reaches the user.
    """
    loose = assets / DLL_NAME
    if not loose.is_file():
        return None
    try:
        data = loose.read_bytes()
    except OSError as exc:
        return None, f"assets/{DLL_NAME}", f"refused: unreadable ({exc})"
    info = parse_pe(data)
    if not info.valid:
        return None, f"assets/{DLL_NAME}", f"refused: {info.reason}"
    if info.machine != want:
        return (
            None,
            f"assets/{DLL_NAME}",
            f"refused: DLL is {info.machine_name}, interpreter needs "
            f"{_MACHINE_NAMES.get(want, 'unknown')}",
        )
    return data, f"assets/{DLL_NAME}", "loose DLL, arch verified"


def _candidates_from_zips(assets: Path, want: int) -> tuple[Optional[bytes], str, str]:
    """Search every assets/*.zip for a matching-arch libusb-1.0.dll.

    Official libusb release zips contain multiple builds (MinGW64, VS2019/x64,
    x86 ...). Every member named libusb-1.0.dll is PE-parsed and the first one
    matching the interpreter's architecture wins.
    """
    zips = sorted(assets.glob("*.zip"))
    if not zips:
        return None, "", "no zip archives in assets/"
    rejected: list[str] = []
    for zpath in zips:
        try:
            with zipfile.ZipFile(zpath) as zf:
                members = [
                    m for m in zf.namelist()
                    if Path(m).name.lower() == DLL_NAME and not m.endswith("/")
                ]
                for member in members:
                    try:
                        data = zf.read(member)
                    except (zipfile.BadZipFile, KeyError, OSError):
                        rejected.append(f"{zpath.name}:{member} (unreadable)")
                        continue
                    info = parse_pe(data)
                    if not info.valid:
                        rejected.append(f"{zpath.name}:{member} ({info.reason})")
                        continue
                    if info.machine != want:
                        rejected.append(
                            f"{zpath.name}:{member} ({info.machine_name}, wrong arch)"
                        )
                        continue
                    return data, f"{zpath.name} → {member}", "zip member, arch verified"
        except (zipfile.BadZipFile, OSError) as exc:
            rejected.append(f"{zpath.name} (bad zip: {exc})")
    if rejected:
        return None, "", "no matching DLL; rejected: " + "; ".join(rejected[:4])
    return None, "", f"no {DLL_NAME} inside any assets zip"


def _detect_rar(assets: Path) -> Optional[str]:
    rars = sorted(assets.glob("*.rar"))
    if rars:
        return (
            f"{rars[0].name} found but .rar cannot be read — "
            f"re-pack as .zip (or drop the loose {DLL_NAME}) in assets/"
        )
    return None


def deploy(
    assets_dir: Path,
    staging_dir: Path,
    arch: Optional[str] = None,
    system: Optional[str] = None,
) -> DeployResult:
    """Stage a validated, arch-matched libusb-1.0.dll and return its path.

    Idempotent: if the staged DLL already matches the source byte-for-byte
    (SHA-256), nothing is rewritten. All failure modes return DeployResult
    with ok=False and a human-readable detail — this function never raises.
    """
    system = system or platform.system()
    if system != "Windows":
        return DeployResult(False, detail=f"deployment is Windows-only (running on {system})")

    want = host_machine(arch)
    if want == 0:
        return DeployResult(False, detail=f"unrecognized interpreter architecture: {arch or platform.machine()}")

    assets = Path(assets_dir)
    if not assets.is_dir():
        return DeployResult(False, detail=f"assets folder not found: {assets}")

    data: Optional[bytes] = None
    source = ""
    detail = ""

    loose = _candidate_from_loose(assets, want)
    if loose is not None:
        data, source, detail = loose
    if data is None:
        zdata, zsource, zdetail = _candidates_from_zips(assets, want)
        if zdata is not None:
            data, source, detail = zdata, zsource, zdetail
        else:
            # Keep the most informative failure message.
            if detail:
                detail = f"{detail}; {zdetail}"
            else:
                detail = zdetail

    if data is None:
        rar_note = _detect_rar(assets)
        if rar_note:
            detail = f"{detail}; {rar_note}" if detail else rar_note
        return DeployResult(False, detail=detail)

    staging = Path(staging_dir)
    try:
        staging.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return DeployResult(False, detail=f"cannot create staging dir: {exc}")

    target = staging / DLL_NAME
    if _sha256_file(target) == _sha256(data):
        return DeployResult(True, target, source, "already staged (hash match)")

    # Atomic write: temp file in the same dir, then os.replace.
    try:
        fd, tmp = tempfile.mkstemp(dir=str(staging), suffix=".tmp")
        try:
            with os.fdopen(fd, "wb") as fh:
                fh.write(data)
                fh.flush()
                os.fsync(fh.fileno())
            os.replace(tmp, target)
        finally:
            if os.path.exists(tmp):
                os.unlink(tmp)
    except OSError as exc:
        return DeployResult(False, detail=f"staging write failed: {exc}")

    return DeployResult(True, target, source, f"deployed ({detail})")
