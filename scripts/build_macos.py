"""Build the native app with a relocatable managed Python and locked dependencies."""

import hashlib
import json
import os
import platform
import plistlib
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "dist/macos"
PYTHON_VERSION = "3.13.14"


def run(*args: str | Path) -> None:
    subprocess.run([str(arg) for arg in args], cwd=ROOT, check=True)


def main() -> None:
    if sys.platform != "darwin" or platform.machine() != "arm64":
        raise SystemExit("This build recipe targets macOS Apple Silicon.")
    if platform.python_version() != PYTHON_VERSION:
        raise SystemExit(f"Use uv run --python {PYTHON_VERSION} --locked --extra dev ...")
    uv = shutil.which("uv")
    if not uv or not Path(sys.base_prefix).name.startswith("cpython-3.13.14-macos-aarch64"):
        raise SystemExit("A uv-managed python-build-standalone runtime is required.")
    OUTPUT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="archguard-build-") as tmp:
        stage = Path(tmp)
        app = stage / "ArchGuard.app"
        contents = app / "Contents"
        resources = contents / "Resources"
        executable = contents / "MacOS/ArchGuard"
        executable.parent.mkdir(parents=True)
        resources.mkdir()
        runtime = resources / "python"
        shutil.copytree(sys.base_prefix, runtime, symlinks=True)
        for link in runtime.rglob("*"):
            if link.is_symlink() and os.path.isabs(os.readlink(link)):
                relative = link.resolve().relative_to(Path(sys.base_prefix).resolve())
                link.unlink()
                link.symlink_to(os.path.relpath(runtime / relative, link.parent))
        python = runtime / "bin/python3.13"
        requirements = stage / "requirements.txt"
        run(
            uv, "export", "--locked", "--no-dev", "--no-emit-project", "--output-file", requirements
        )
        run(
            uv,
            "pip",
            "install",
            "--python",
            python,
            "--break-system-packages",
            "--require-hashes",
            "-r",
            requirements,
        )
        wheels = stage / "wheels"
        run(uv, "build", "--wheel", "--out-dir", wheels)
        run(
            uv,
            "pip",
            "install",
            "--python",
            python,
            "--break-system-packages",
            "--no-deps",
            next(wheels.glob("*.whl")),
        )
        for direct in runtime.rglob("direct_url.json"):
            direct.unlink()
        for file in (runtime / "bin").iterdir():
            if not file.name.startswith("python"):
                file.unlink()
        for file in runtime.rglob("*.pyc"):
            file.unlink()
        for link in runtime.rglob("*"):
            if link.is_symlink() and not link.resolve().is_relative_to(runtime.resolve()):
                raise SystemExit("External runtime symlink")
        shutil.copytree(
            ROOT / "examples/product/observatory-ts", resources / "Examples/observatory-ts"
        )
        if (ROOT / "LICENSE").exists():
            shutil.copy(ROOT / "LICENSE", resources / "LICENSE")
        run(
            "xcrun",
            "swiftc",
            "-O",
            "-target",
            "arm64-apple-macosx13.0",
            ROOT / "native/macos/ArchGuard.swift",
            "-o",
            executable,
            "-framework",
            "AppKit",
            "-framework",
            "WebKit",
        )
        icon_tool = stage / "make-icon"
        run(
            "xcrun",
            "swiftc",
            ROOT / "native/macos/Icon.swift",
            "-o",
            icon_tool,
            "-framework",
            "AppKit",
        )
        iconset = stage / "ArchGuard.iconset"
        run(icon_tool, iconset)
        run("iconutil", "-c", "icns", iconset, "-o", resources / "ArchGuard.icns")
        info = {
            "CFBundleName": "ArchGuard",
            "CFBundleDisplayName": "ArchGuard",
            "CFBundleIdentifier": "com.archguard.observatory",
            "CFBundleExecutable": "ArchGuard",
            "CFBundlePackageType": "APPL",
            "CFBundleIconFile": "ArchGuard.icns",
            "CFBundleShortVersionString": "0.1.0",
            "CFBundleVersion": "41",
            "LSMinimumSystemVersion": "13.0",
            "NSHighResolutionCapable": True,
            "NSPrincipalClass": "NSApplication",
            "LSMultipleInstancesProhibited": True,
            "NSAppTransportSecurity": {"NSAllowsLocalNetworking": True},
        }
        (contents / "Info.plist").write_bytes(plistlib.dumps(info))
        receipt = {
            "python": PYTHON_VERSION,
            "architecture": "arm64",
            "version": "0.1.0",
            "build": 41,
            "uv_lock_sha256": hashlib.sha256((ROOT / "uv.lock").read_bytes()).hexdigest(),
            "signing": "ad-hoc",
            "notarized": False,
        }
        (resources / "build-info.json").write_text(json.dumps(receipt, indent=2) + "\n")
        # Sign nested native images before sealing the outer bundle; no signing credentials.
        magic = {b"\xcf\xfa\xed\xfe", b"\xce\xfa\xed\xfe", b"\xca\xfe\xba\xbe", b"\xbe\xba\xfe\xca"}
        for file in runtime.rglob("*"):
            if file.is_file() and not file.is_symlink():
                with file.open("rb") as stream:
                    native = stream.read(4) in magic
                if native:
                    run("codesign", "--force", "--sign", "-", file)
        run("codesign", "--force", "--sign", "-", "--identifier", info["CFBundleIdentifier"], app)
        run("codesign", "--verify", "--deep", "--strict", app)
        destination = OUTPUT / "ArchGuard.app"
        if destination.exists():
            shutil.rmtree(destination)
        shutil.move(app, destination)
    run(
        "ditto",
        "-c",
        "-k",
        "--sequesterRsrc",
        "--keepParent",
        destination,
        OUTPUT / "ArchGuard-macos-arm64.zip",
    )
    with tempfile.TemporaryDirectory(prefix="archguard-dmg-") as temp:
        volume = Path(temp)
        run("ditto", destination, volume / "ArchGuard.app")
        (volume / "Applications").symlink_to("/Applications")
        (volume / "Install.txt").write_text(
            "ArchGuard · macOS Apple Silicon\n\n"
            "Drag ArchGuard.app to Applications, then open it from Finder.\n"
            "Перетащите ArchGuard.app в Applications и откройте из Finder.\n\n"
            "Local ad-hoc signature; no Developer ID or Apple notarization.\n"
            "macOS may require explicit approval in Privacy & Security.\n"
            "File > Choose Projects Folder selects a parent folder of projects.\n"
        )
        run(
            "hdiutil",
            "create",
            "-volname",
            "ArchGuard",
            "-srcfolder",
            volume,
            "-format",
            "UDZO",
            "-ov",
            OUTPUT / "ArchGuard-macos-arm64.dmg",
        )
    print(f"Built {destination}")


if __name__ == "__main__":
    main()
