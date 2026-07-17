"""libusb deployment tests.

Candidate DLLs are forged as minimal-but-genuine PE structures so the parser,
arch matcher, and every refusal path are exercised for real — no mocking of
the validation logic itself.
"""

import struct
import zipfile
from pathlib import Path

from usb_toolkit.core.libusb_deploy import (
    DLL_NAME,
    MACHINE_ARM64,
    MACHINE_X64,
    MACHINE_X86,
    deploy,
    host_machine,
    parse_pe,
)


def _fake_pe(machine: int, is_dll: bool = True) -> bytes:
    """Forge a minimal valid PE: MZ header, e_lfanew, PE sig, COFF header."""
    e_lfanew = 0x80
    data = bytearray(e_lfanew + 24)
    data[0:2] = b"MZ"
    struct.pack_into("<I", data, 0x3C, e_lfanew)
    data[e_lfanew : e_lfanew + 4] = b"PE\x00\x00"
    struct.pack_into("<H", data, e_lfanew + 4, machine)
    characteristics = 0x2000 if is_dll else 0x0002  # IMAGE_FILE_DLL vs EXE
    struct.pack_into("<H", data, e_lfanew + 22, characteristics)
    return bytes(data)


# -- PE parsing --------------------------------------------------------------

def test_parse_pe_valid_x64_dll():
    info = parse_pe(_fake_pe(MACHINE_X64))
    assert info.valid and info.is_dll
    assert info.machine == MACHINE_X64
    assert info.machine_name == "x64"


def test_parse_pe_rejects_non_pe():
    assert not parse_pe(b"not a dll at all").valid
    assert not parse_pe(b"").valid


def test_parse_pe_rejects_exe():
    info = parse_pe(_fake_pe(MACHINE_X64, is_dll=False))
    assert not info.valid
    assert "not a DLL" in info.reason


def test_parse_pe_rejects_truncated():
    data = _fake_pe(MACHINE_X64)[:0x50]
    assert not parse_pe(data).valid


def test_host_machine_mapping():
    assert host_machine("AMD64") == MACHINE_X64
    assert host_machine("x86_64") == MACHINE_X64
    assert host_machine("aarch64") == MACHINE_ARM64
    assert host_machine("i686") == MACHINE_X86
    assert host_machine("mystery") == 0


# -- deployment: loose DLL ---------------------------------------------------

def _dirs(tmp_path: Path) -> tuple[Path, Path]:
    assets = tmp_path / "assets"
    staging = tmp_path / "staging"
    assets.mkdir()
    return assets, staging


def test_deploy_loose_dll(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / DLL_NAME).write_bytes(_fake_pe(MACHINE_X64))
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert result.ok
    assert result.dll_path == staging / DLL_NAME
    assert result.dll_path.read_bytes() == _fake_pe(MACHINE_X64)


def test_deploy_refuses_wrong_arch_loose_dll(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / DLL_NAME).write_bytes(_fake_pe(MACHINE_X86))
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert not result.ok
    assert "x86" in result.detail
    assert not (staging / DLL_NAME).exists()


def test_deploy_refuses_garbage_loose_dll(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / DLL_NAME).write_bytes(b"MZ this is not really a dll")
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert not result.ok
    assert not (staging / DLL_NAME).exists()


# -- deployment: zip ---------------------------------------------------------

def test_deploy_from_zip_picks_matching_arch(tmp_path):
    # Official-release layout: multiple arch builds in one zip.
    assets, staging = _dirs(tmp_path)
    with zipfile.ZipFile(assets / "libusb-1.0.zip", "w") as zf:
        zf.writestr(f"MinGW32/dll/{DLL_NAME}", _fake_pe(MACHINE_X86))
        zf.writestr(f"MinGW64/dll/{DLL_NAME}", _fake_pe(MACHINE_X64))
        zf.writestr("README.txt", "hello")
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert result.ok
    assert "MinGW64" in result.source
    assert result.dll_path.read_bytes() == _fake_pe(MACHINE_X64)


def test_deploy_zip_with_only_wrong_arch_is_refused(tmp_path):
    assets, staging = _dirs(tmp_path)
    with zipfile.ZipFile(assets / "libusb.zip", "w") as zf:
        zf.writestr(f"dll/{DLL_NAME}", _fake_pe(MACHINE_ARM64))
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert not result.ok
    assert "wrong arch" in result.detail


def test_deploy_bad_zip_is_refused_not_raised(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / "broken.zip").write_bytes(b"PK\x03\x04 truncated nonsense")
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert not result.ok


def test_loose_dll_wins_over_zip(tmp_path):
    assets, staging = _dirs(tmp_path)
    loose = _fake_pe(MACHINE_X64)
    (assets / DLL_NAME).write_bytes(loose)
    with zipfile.ZipFile(assets / "libusb.zip", "w") as zf:
        zf.writestr(f"dll/{DLL_NAME}", _fake_pe(MACHINE_X64))
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert result.ok
    assert result.source == f"assets/{DLL_NAME}"


# -- idempotence, platform gating, diagnostics -------------------------------

def test_deploy_is_idempotent(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / DLL_NAME).write_bytes(_fake_pe(MACHINE_X64))
    first = deploy(assets, staging, arch="AMD64", system="Windows")
    second = deploy(assets, staging, arch="AMD64", system="Windows")
    assert first.ok and second.ok
    assert "already staged" in second.detail


def test_deploy_updates_changed_dll(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / DLL_NAME).write_bytes(_fake_pe(MACHINE_X64))
    deploy(assets, staging, arch="AMD64", system="Windows")
    # New build appears in assets (different bytes, same arch).
    newer = _fake_pe(MACHINE_X64) + b"\x00" * 16
    (assets / DLL_NAME).write_bytes(newer)
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert result.ok
    assert (staging / DLL_NAME).read_bytes() == newer


def test_deploy_non_windows_is_declined(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / DLL_NAME).write_bytes(_fake_pe(MACHINE_X64))
    result = deploy(assets, staging, arch="AMD64", system="Linux")
    assert not result.ok
    assert "Windows-only" in result.detail


def test_deploy_reports_rar_hint(tmp_path):
    assets, staging = _dirs(tmp_path)
    (assets / "libusb-1.0.rar").write_bytes(b"Rar!\x1a\x07\x01\x00")
    result = deploy(assets, staging, arch="AMD64", system="Windows")
    assert not result.ok
    assert ".rar" in result.detail
    assert "zip" in result.detail.lower()


def test_deploy_missing_assets_dir(tmp_path):
    result = deploy(tmp_path / "nope", tmp_path / "staging", arch="AMD64", system="Windows")
    assert not result.ok
    assert "not found" in result.detail
