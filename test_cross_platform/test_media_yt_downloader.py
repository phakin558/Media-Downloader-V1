"""Smoke tests for the Windows/macOS compatibility layer."""

import importlib.util
import os
import tempfile
from pathlib import Path


PROJECT_DIR = Path(__file__).resolve().parents[1]
MODULE_PATH = PROJECT_DIR / "Media_yt_downloader.py"
spec = importlib.util.spec_from_file_location("media_yt_downloader", MODULE_PATH)
module = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)


def test_import_and_basic_helpers():
    assert module.normalize_url("https://youtu.be/abc123") == "https://youtu.be/abc123"
    assert module.normalize_url("https://www.youtube.com/shorts/abc123?feature=share") == (
        "https://www.youtube.com/watch?v=abc123"
    )
    assert module.get_download_path() == Path.home() / "Downloads"


def test_resolve_macos_bundled_ffmpeg():
    original_base = module.BASE_DIR
    original_system = module.platform.system
    original_path = module.shutil.which
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_root = Path(temp_dir)
            ffmpeg = fake_root / "ffmpeg" / "bin" / "ffmpeg"
            ffmpeg.parent.mkdir(parents=True)
            ffmpeg.write_bytes(b"test")
            module.BASE_DIR = fake_root
            module.platform.system = lambda: "Darwin"
            module.shutil.which = lambda _: None
            assert module.resolve_ffmpeg() == str(ffmpeg)
    finally:
        module.BASE_DIR = original_base
        module.platform.system = original_system
        module.shutil.which = original_path


def test_resolve_windows_bundled_ffmpeg():
    original_base = module.BASE_DIR
    original_system = module.platform.system
    original_path = module.shutil.which
    try:
        with tempfile.TemporaryDirectory() as temp_dir:
            fake_root = Path(temp_dir)
            ffmpeg = fake_root / "tools" / "windows" / "ffmpeg" / "bin" / "ffmpeg.exe"
            ffmpeg.parent.mkdir(parents=True)
            ffmpeg.write_bytes(b"test")
            module.BASE_DIR = fake_root
            module.platform.system = lambda: "Windows"
            module.shutil.which = lambda _: None
            assert module.resolve_ffmpeg() == str(ffmpeg)
    finally:
        module.BASE_DIR = original_base
        module.platform.system = original_system
        module.shutil.which = original_path


def test_macos_download_bundle_layout():
    original_system = module.platform.system
    original_machine = module.platform.machine
    original_path = module.shutil.which
    try:
        module.platform.system = lambda: "Darwin"
        module.platform.machine = lambda: "x86_64"
        module.shutil.which = lambda _: None
        expected = PROJECT_DIR / "macOS" / "tools" / "ffmpeg" / "ffmpeg"
        assert expected.is_file()
        assert module.resolve_ffmpeg() == str(expected)
    finally:
        module.platform.system = original_system
        module.platform.machine = original_machine
        module.shutil.which = original_path


if __name__ == "__main__":
    test_import_and_basic_helpers()
    test_resolve_macos_bundled_ffmpeg()
    test_resolve_windows_bundled_ffmpeg()
    test_macos_download_bundle_layout()
    print("Cross-platform smoke tests passed")
