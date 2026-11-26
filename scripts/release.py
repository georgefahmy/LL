#!/usr/bin/env python3
"""Release, version-sync, macOS DMG packaging, and GitHub Releases CLI."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

SEMVER_RE = re.compile(
    r"^(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)(?:-([0-9A-Za-z.-]+))?$"
)


@dataclass(frozen=True)
class VersionSlot:
    """Single version field inside a tracked repository file."""

    label: str
    rel_path: str
    pattern: re.Pattern[str]


VERSION_SLOTS: tuple[VersionSlot, ...] = (
    VersionSlot(
        label="pyproject.toml",
        rel_path="pyproject.toml",
        pattern=re.compile(r'^(version\s*=\s*")([^"]+)(")', re.MULTILINE),
    ),
    VersionSlot(
        label="backend/config.py",
        rel_path="backend/config.py",
        pattern=re.compile(r'^(\s*app_version\s*:\s*str\s*=\s*")([^"]+)(")', re.MULTILINE),
    ),
    VersionSlot(
        label="frontend/package.json",
        rel_path="frontend/package.json",
        pattern=re.compile(r'^(\s*"version"\s*:\s*")([^"]+)(")', re.MULTILINE),
    ),
    VersionSlot(
        label="desktop/learnedleague.spec (CFBundleShortVersionString)",
        rel_path="desktop/learnedleague.spec",
        pattern=re.compile(r'("CFBundleShortVersionString"\s*:\s*")([^"]+)(")'),
    ),
    VersionSlot(
        label="desktop/learnedleague.spec (CFBundleVersion)",
        rel_path="desktop/learnedleague.spec",
        pattern=re.compile(r'("CFBundleVersion"\s*:\s*")([^"]+)(")'),
    ),
)

TRACKED_VERSION_FILES: tuple[str, ...] = tuple(dict.fromkeys(s.rel_path for s in VERSION_SLOTS))

EXTENSION_VERSION_SLOTS: tuple[VersionSlot, ...] = (
    VersionSlot(
        label="extension/manifest.json",
        rel_path="extension/manifest.json",
        pattern=re.compile(r'^(\s*"version"\s*:\s*")([^"]+)(")', re.MULTILINE),
    ),
    VersionSlot(
        label="backend/config.py (extension_version)",
        rel_path="backend/config.py",
        pattern=re.compile(
            r'^(\s*extension_version\s*:\s*str\s*=\s*")([^"]+)(")',
            re.MULTILINE,
        ),
    ),
)

JSON_VERSION_FILES: frozenset[str] = frozenset({"frontend/package.json", "extension/manifest.json"})


class ReleaseError(RuntimeError):
    """Raised when a preflight, build, packaging, or publish step fails."""


def normalize_version(raw: str) -> str:
    """Validate a semantic version string (optional leading 'v') and return X.Y.Z[-pre]."""
    cleaned = raw.strip()
    if cleaned.startswith(("v", "V")):
        cleaned = cleaned[1:]
    if not SEMVER_RE.match(cleaned):
        raise ValueError(
            f"Invalid semantic version '{raw}'. Expected X.Y.Z or X.Y.Z-prerelease."
        )
    return cleaned


def compute_next_version(current: str, target: str) -> str:
    """Compute target version from bump keyword (patch/minor/major/current) or explicit semver."""
    norm_current = normalize_version(current)
    cmd = target.strip().lower()
    if cmd == "current":
        return norm_current

    match = SEMVER_RE.match(norm_current)
    assert match is not None
    major, minor, patch = int(match.group(1)), int(match.group(2)), int(match.group(3))

    if cmd == "patch":
        return f"{major}.{minor}.{patch + 1}"
    if cmd == "minor":
        return f"{major}.{minor + 1}.0"
    if cmd == "major":
        return f"{major + 1}.0.0"

    return normalize_version(target)


def _read_slots(root: Path, slots: tuple[VersionSlot, ...]) -> dict[str, str]:
    """Read version values for a given set of version slots."""
    file_cache: dict[str, str] = {}
    versions: dict[str, str] = {}

    for slot in slots:
        if slot.rel_path not in file_cache:
            path = root / slot.rel_path
            if not path.is_file():
                raise ReleaseError(f"Missing version file: {path}")
            file_cache[slot.rel_path] = path.read_text(encoding="utf-8")

        text = file_cache[slot.rel_path]
        match = slot.pattern.search(text)
        if match is None:
            raise ReleaseError(f"Could not locate version field for {slot.label}")

        value = match.group(2).strip()
        if slot.rel_path in JSON_VERSION_FILES:
            pkg = json.loads(text)
            json_ver = str(pkg.get("version", "")).strip()
            if json_ver != value:
                raise ReleaseError(
                    f"{slot.rel_path} version mismatch between regex ({value}) "
                    f"and JSON ({json_ver})"
                )
        versions[slot.label] = value

    return versions


def _check_slots(
    root: Path,
    slots: tuple[VersionSlot, ...],
    *,
    expect_tag: str | None = None,
    group_name: str = "",
) -> tuple[bool, str, dict[str, str]]:
    """Verify every slot in a group agrees (and matches expect_tag if provided)."""
    versions = _read_slots(root, slots)
    unique_values = set(versions.values())
    prefix = f"{group_name} " if group_name else ""

    if len(unique_values) != 1:
        details = ", ".join(f"{k}={v}" for k, v in versions.items())
        return False, f"{prefix}Version mismatch across files: {details}", versions

    current = next(iter(unique_values))
    try:
        norm_current = normalize_version(current)
    except ValueError as exc:
        return False, str(exc), versions

    if expect_tag is not None:
        try:
            expected = normalize_version(expect_tag)
        except ValueError as exc:
            return False, str(exc), versions
        if norm_current != expected:
            return (
                False,
                f"{prefix}Version mismatch: files are at {norm_current}, expected {expected} "
                f"(from {expect_tag})",
                versions,
            )

    msg = f"All {len(versions)} {prefix.lower()}version slots match ({norm_current})."
    return True, msg, versions


def _write_slots(root: Path, slots: tuple[VersionSlot, ...], new_version: str) -> list[Path]:
    """Update all slots in a group to new_version and return modified paths."""
    norm_version = normalize_version(new_version)
    modified: list[Path] = []

    slots_by_file: dict[str, list[VersionSlot]] = {}
    for slot in slots:
        slots_by_file.setdefault(slot.rel_path, []).append(slot)

    for rel_path, file_slots in slots_by_file.items():
        path = root / rel_path
        if not path.is_file():
            raise ReleaseError(f"Missing version file: {path}")

        original = path.read_text(encoding="utf-8")
        updated = original
        for slot in file_slots:
            updated, count = slot.pattern.subn(
                rf"\g<1>{norm_version}\g<3>",
                updated,
                count=1,
            )
            if count != 1:
                raise ReleaseError(f"Failed to update {slot.label} in {path}")

        if updated != original:
            path.write_text(updated, encoding="utf-8")
            modified.append(path)

    return modified


def read_versions(root: Path = ROOT_DIR) -> dict[str, str]:
    """Read all tracked desktop/app version fields from repository files."""
    return _read_slots(root, VERSION_SLOTS)


def check_version_consistency(
    root: Path = ROOT_DIR,
    expect_tag: str | None = None,
) -> tuple[bool, str, dict[str, str]]:
    """Verify every desktop/app version slot agrees (and matches expect_tag if provided)."""
    return _check_slots(root, VERSION_SLOTS, expect_tag=expect_tag)


def write_version(root: Path, new_version: str) -> list[Path]:
    """Update all tracked desktop/app version files to new_version."""
    return _write_slots(root, VERSION_SLOTS, new_version)


def read_extension_versions(root: Path = ROOT_DIR) -> dict[str, str]:
    """Read all tracked Chrome Extension version fields."""
    return _read_slots(root, EXTENSION_VERSION_SLOTS)


def check_extension_version_consistency(
    root: Path = ROOT_DIR,
    expect_tag: str | None = None,
) -> tuple[bool, str, dict[str, str]]:
    """Verify all Chrome Extension version fields agree."""
    return _check_slots(
        root,
        EXTENSION_VERSION_SLOTS,
        expect_tag=expect_tag,
        group_name="Extension",
    )


def write_extension_version(root: Path, new_version: str) -> list[Path]:
    """Update all tracked Chrome Extension version files to new_version."""
    return _write_slots(root, EXTENSION_VERSION_SLOTS, new_version)


def extract_changelog_section(changelog_path: Path, target_version: str) -> str | None:
    """Return markdown body for target_version from changelog.md, or None if absent."""
    if not changelog_path.is_file():
        return None

    norm_ver = normalize_version(target_version)
    heading_re = re.compile(
        rf"^###\s+(?:\[v?{re.escape(norm_ver)}\]|v?{re.escape(norm_ver)})(?:\s|$)",
        re.IGNORECASE,
    )
    next_section_re = re.compile(r"^#{2,3}\s+")

    lines = changelog_path.read_text(encoding="utf-8").splitlines()
    capturing = False
    captured: list[str] = []

    for line in lines:
        if capturing:
            if next_section_re.match(line):
                break
            captured.append(line)
        elif heading_re.match(line):
            capturing = True

    body = "\n".join(captured).strip()
    return body or None


def _run(
    cmd: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    dry_run: bool = False,
    capture_output: bool = False,
) -> subprocess.CompletedProcess[str]:
    """Execute a subprocess command (or log and short-circuit on dry_run)."""
    cmd_str = " ".join(str(part) for part in cmd)
    if dry_run:
        prefix = f"({cwd}) " if cwd else ""
        print(f"[dry-run] {prefix}{cmd_str}")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    print(f"==> Running: {cmd_str}")
    try:
        return subprocess.run(
            list(cmd),
            cwd=cwd,
            env=env,
            check=True,
            text=True,
            capture_output=capture_output,
        )
    except subprocess.CalledProcessError as exc:
        stderr = (exc.stderr or "").strip()
        detail = f": {stderr}" if stderr else ""
        raise ReleaseError(f"Command failed ({exc.returncode}): {cmd_str}{detail}") from exc


def _pyinstaller_env(*, create: bool = True) -> dict[str, str]:
    """Build subprocess environment with writable PYINSTALLER_CONFIG_DIR fallback."""
    env = os.environ.copy()
    if env.get("PYINSTALLER_CONFIG_DIR"):
        return env

    writable = False
    try:
        default_dir = Path.home() / "Library" / "Application Support" / "pyinstaller"
        probe_dir = default_dir if default_dir.exists() else default_dir.parent
        writable = probe_dir.exists() and os.access(probe_dir, os.W_OK)
    except OSError:
        writable = False

    if not writable:
        cache_dir = Path("/tmp/pyinstaller_cache")
        if create:
            cache_dir.mkdir(parents=True, exist_ok=True)
        env["PYINSTALLER_CONFIG_DIR"] = str(cache_dir)
    return env


def run_pre_release_checks(root: Path, *, dry_run: bool = False) -> None:
    """Run linter, test suite, and frontend TypeScript typecheck."""
    _run(
        ["uv", "run", "ruff", "check", "backend", "desktop", "scripts/release.py", "tests"],
        cwd=root,
        dry_run=dry_run,
    )
    _run(["uv", "run", "pytest", "-q"], cwd=root, dry_run=dry_run)
    _run(["npm", "run", "typecheck"], cwd=root / "frontend", dry_run=dry_run)


def build_frontend(root: Path, *, dry_run: bool = False) -> None:
    """Build production React/Vite bundle into frontend/dist."""
    _run(["npm", "run", "build"], cwd=root / "frontend", dry_run=dry_run)


def build_macos_app(root: Path, *, dry_run: bool = False) -> None:
    """Build dist/LearnedLeague.app with PyInstaller."""
    _run(
        ["uv", "run", "pyinstaller", "desktop/learnedleague.spec", "--noconfirm", "--clean"],
        cwd=root,
        env=_pyinstaller_env(create=not dry_run),
        dry_run=dry_run,
    )


def smoke_test_macos_app(root: Path, *, dry_run: bool = False) -> None:
    """Run bundled macOS binary with --self-test to catch startup import crashes."""
    exe_path = root / "dist" / "LearnedLeague.app" / "Contents" / "MacOS" / "LearnedLeague"
    if dry_run:
        print(f"[dry-run] {exe_path} --self-test")
        return
    if not exe_path.is_file():
        raise ReleaseError(f"Missing macOS binary for smoke test: {exe_path}")
    res = _run([str(exe_path), "--self-test"], cwd=root, capture_output=True)
    if "OK" not in res.stdout.splitlines():
        raise ReleaseError(
            f"Desktop smoke test failed (missing OK): stdout={res.stdout!r} stderr={res.stderr!r}"
        )


def dmg_artifact_paths(root: Path, version: str, arch: str | None = None) -> tuple[Path, Path]:
    """Return canonical (dmg_path, sha256_path) for a versioned macOS release."""
    norm_ver = normalize_version(version)
    resolved_arch = arch or platform.machine() or "arm64"
    dmg_path = root / "dist" / f"LearnedLeague-{norm_ver}-macos-{resolved_arch}.dmg"
    sha_path = Path(f"{dmg_path}.sha256")
    return dmg_path, sha_path


def write_sha256_file(artifact_path: Path, sha_path: Path | None = None) -> Path:
    """Compute SHA-256 digest of artifact_path and write `<hex>  <filename>`."""
    out_path = sha_path or Path(f"{artifact_path}.sha256")
    digest = hashlib.sha256()
    with artifact_path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    out_path.write_text(f"{digest.hexdigest()}  {artifact_path.name}\n", encoding="utf-8")
    return out_path


def package_dmg(
    root: Path,
    version: str,
    *,
    arch: str | None = None,
    dry_run: bool = False,
) -> tuple[Path, Path]:
    """Package dist/LearnedLeague.app into a verified UDZO .dmg + .sha256 checksum."""
    dmg_path, sha_path = dmg_artifact_paths(root, version, arch=arch)
    app_path = root / "dist" / "LearnedLeague.app"
    staging_dir = root / "dist" / "dmg_staging"

    if dry_run:
        print(f"[dry-run] Stage {app_path} + /Applications symlink in {staging_dir}")
        print(
            "[dry-run] hdiutil create -volname LearnedLeague "
            f"-srcfolder {staging_dir} -ov -format UDZO {dmg_path}"
        )
        print(f"[dry-run] hdiutil verify {dmg_path}")
        print(f"[dry-run] Write SHA-256 checksum -> {sha_path}")
        return dmg_path, sha_path

    if sys.platform != "darwin":
        raise ReleaseError("macOS .dmg packaging requires macOS (darwin).")

    if not app_path.is_dir():
        raise ReleaseError(
            f"Missing app bundle at {app_path}. Run build first or omit --package-dmg-only."
        )

    dmg_path.parent.mkdir(parents=True, exist_ok=True)
    if staging_dir.exists():
        shutil.rmtree(staging_dir)

    try:
        staging_dir.mkdir(parents=True)
        _run(["ditto", str(app_path), str(staging_dir / "LearnedLeague.app")], cwd=root)
        os.symlink("/Applications", staging_dir / "Applications")
        _run(
            [
                "hdiutil",
                "create",
                "-volname",
                "LearnedLeague",
                "-srcfolder",
                str(staging_dir),
                "-ov",
                "-format",
                "UDZO",
                str(dmg_path),
            ],
            cwd=root,
        )
        _run(["hdiutil", "verify", str(dmg_path)], cwd=root)
        write_sha256_file(dmg_path, sha_path)
    finally:
        if staging_dir.exists():
            shutil.rmtree(staging_dir, ignore_errors=True)

    return dmg_path, sha_path


def package_extension_zip(
    root: Path,
    version: str,
    *,
    dry_run: bool = False,
) -> tuple[Path, Path]:
    """Package Chrome Extension directory into dist/LearnedLeague-Extension-<version>.zip."""
    ext_dir = root / "extension"
    norm_ver = normalize_version(version)
    zip_path = root / "dist" / f"LearnedLeague-Extension-{norm_ver}.zip"
    sha_path = Path(f"{zip_path}.sha256")

    if dry_run:
        print(f"[dry-run] Package {ext_dir} -> {zip_path}")
        return zip_path, sha_path

    if not ext_dir.is_dir():
        raise ReleaseError(f"Missing Chrome Extension directory at {ext_dir}")

    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for file_path in sorted(ext_dir.rglob("*")):
            if not file_path.is_file() or file_path.name == ".DS_Store":
                continue
            zf.write(file_path, arcname=file_path.relative_to(ext_dir).as_posix())
    write_sha256_file(zip_path, sha_path)
    return zip_path, sha_path


def _ensure_binary(name: str) -> None:
    if shutil.which(name) is None:
        raise ReleaseError(f"Required executable '{name}' was not found on PATH.")


def _has_uncommitted_changes(root: Path) -> bool:
    res = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    )
    return bool(res.stdout.strip())


def _check_git_clean(root: Path) -> None:
    if _has_uncommitted_changes(root):
        raise ReleaseError(
            "Git working tree has uncommitted changes. "
            "Commit or stash them before publishing (or use 'dry-run' to preview)."
        )


def _local_tag_exists(root: Path, tag: str) -> bool:
    res = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", f"refs/tags/{tag}"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    return res.returncode == 0


def _remote_tag_exists(root: Path, tag: str, *, allow_offline: bool = False) -> bool:
    res = subprocess.run(
        ["git", "ls-remote", "--tags", "origin", f"refs/tags/{tag}"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if res.returncode != 0:
        if allow_offline:
            print(f"[dry-run] Warning: could not query origin for tag {tag}: {res.stderr.strip()}")
            return False
        raise ReleaseError(f"Failed to query origin tags: {res.stderr.strip()}")
    return bool(res.stdout.strip())


def _check_gh_auth(root: Path) -> None:
    res = subprocess.run(
        ["gh", "auth", "status"],
        cwd=root,
        text=True,
        capture_output=True,
    )
    if res.returncode != 0:
        detail = res.stderr.strip() or res.stdout.strip()
        raise ReleaseError(f"GitHub CLI is not authenticated. Run 'gh auth login'. ({detail})")


def run_release(args: argparse.Namespace, root: Path = ROOT_DIR) -> int:
    """Execute the requested release workflow command."""
    if args.check_version:
        ok, message, versions = check_version_consistency(root, expect_tag=args.expect_tag)
        for label, value in versions.items():
            print(f"  {label}: {value}")
        print(message)

        ext_ok = True
        if (root / "extension" / "manifest.json").is_file():
            ext_ok, ext_msg, ext_versions = check_extension_version_consistency(root)
            for label, value in ext_versions.items():
                print(f"  {label}: {value}")
            print(ext_msg)
        return 0 if (ok and ext_ok) else 1

    if args.extract_notes:
        notes = extract_changelog_section(root / "changelog.md", args.extract_notes)
        if notes:
            print(notes)
        return 0

    if args.command == "extension":
        ext_ok, ext_msg, ext_versions = check_extension_version_consistency(root)
        if not ext_ok:
            raise ReleaseError(ext_msg)
        cur_ext = next(iter(ext_versions.values()))
        target_ext = compute_next_version(cur_ext, args.version)
        if target_ext != cur_ext:
            write_extension_version(root, target_ext)
            print(f"Updated extension version: {cur_ext} -> {target_ext}")
        zip_path, sha_path = package_extension_zip(root, target_ext)
        print(f"Packaged extension: {zip_path}")
        print(f"Checksum: {sha_path}")
        return 0

    ok, message, versions = check_version_consistency(root)
    if not ok:
        raise ReleaseError(message)
    current_version = next(iter(versions.values()))

    if args.package_dmg_only:
        pkg_version = compute_next_version(current_version, args.package_dmg_only)
        dmg_path, sha_path = package_dmg(root, pkg_version)
        print(f"Packaged: {dmg_path}")
        print(f"Checksum: {sha_path}")
        return 0

    if args.command == "build":
        target_version = compute_next_version(current_version, args.version)
        run_pre_release_checks(root)
        if target_version != current_version:
            bumped_paths = write_version(root, target_version)
            print(f"Updated version in {len(bumped_paths)} file(s) to {target_version}.")
        build_frontend(root)
        build_macos_app(root)
        smoke_test_macos_app(root)
        dmg_path, sha_path = package_dmg(root, target_version)
        print(f"Built & packaged: {dmg_path}")
        print(f"Checksum: {sha_path}")
        return 0

    dry_run = args.command == "dry-run"
    target_version = compute_next_version(current_version, args.version)
    tag_name = f"v{target_version}"

    _ensure_binary("git")
    _ensure_binary("gh")
    if dry_run:
        if _has_uncommitted_changes(root):
            print(
                "[dry-run] Note: working tree has uncommitted changes "
                "(publish needs a clean tree)."
            )
    else:
        _check_gh_auth(root)
        _check_git_clean(root)

    if _local_tag_exists(root, tag_name):
        raise ReleaseError(f"Git tag {tag_name} already exists locally.")
    if _remote_tag_exists(root, tag_name, allow_offline=dry_run):
        raise ReleaseError(f"Git tag {tag_name} already exists on origin.")

    print(f"Release version: {current_version} -> {target_version} (tag {tag_name})")

    run_pre_release_checks(root, dry_run=dry_run)

    bumped_paths: list[Path] = []
    if target_version != current_version:
        if dry_run:
            for rel_path in TRACKED_VERSION_FILES:
                print(
                    f"[dry-run] Update {root / rel_path}: "
                    f"{current_version} -> {target_version}"
                )
        else:
            bumped_paths = write_version(root, target_version)
            print(f"Updated version in {len(bumped_paths)} file(s) to {target_version}.")

    build_frontend(root, dry_run=dry_run)
    build_macos_app(root, dry_run=dry_run)
    smoke_test_macos_app(root, dry_run=dry_run)
    dmg_path, sha_path = package_dmg(root, target_version, dry_run=dry_run)

    if bumped_paths or (dry_run and target_version != current_version):
        _run(["git", "add", *TRACKED_VERSION_FILES], cwd=root, dry_run=dry_run)
        _run(
            ["git", "commit", "-m", f"chore(release): {tag_name}"],
            cwd=root,
            dry_run=dry_run,
        )

    _run(
        ["git", "tag", "-a", tag_name, "-m", f"Release {tag_name}"],
        cwd=root,
        dry_run=dry_run,
    )
    _run(["git", "push", "origin", "HEAD"], cwd=root, dry_run=dry_run)
    _run(["git", "push", "origin", tag_name], cwd=root, dry_run=dry_run)

    _publish_github_release(
        root=root,
        tag_name=tag_name,
        version=target_version,
        dmg_path=dmg_path,
        sha_path=sha_path,
        draft=args.draft,
        dry_run=dry_run,
    )
    return 0


def _publish_github_release(
    *,
    root: Path,
    tag_name: str,
    version: str,
    dmg_path: Path,
    sha_path: Path,
    draft: bool,
    dry_run: bool,
) -> None:
    """Create a GitHub Release with the packaged DMG and checksum."""
    assets = [str(dmg_path), str(sha_path)]
    temp_notes_path: Path | None = None
    extracted = extract_changelog_section(root / "changelog.md", version)
    if extracted:
        if dry_run:
            notes_flag = ["--notes-file", "<changelog-section>"]
        else:
            with tempfile.NamedTemporaryFile(
                "w",
                encoding="utf-8",
                suffix=".md",
                delete=False,
            ) as tmp:
                tmp.write(extracted + "\n")
                temp_notes_path = Path(tmp.name)
            notes_flag = ["--notes-file", str(temp_notes_path)]
    else:
        notes_flag = ["--generate-notes"]

    cmd = [
        "gh",
        "release",
        "create",
        tag_name,
        *assets,
        "--title",
        f"LearnedLeague {tag_name}",
        *notes_flag,
    ]
    if draft:
        cmd.append("--draft")

    try:
        _run(cmd, cwd=root, dry_run=dry_run)
    finally:
        if temp_notes_path and temp_notes_path.exists():
            temp_notes_path.unlink(missing_ok=True)


def build_parser() -> argparse.ArgumentParser:
    """Create simplified 3-command CLI argument parser."""
    parser = argparse.ArgumentParser(
        description=(
            "Build LearnedLeague .app/.dmg locally, dry-run a release, or publish to GitHub."
        ),
    )
    parser.add_argument("--check-version", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--expect-tag", help=argparse.SUPPRESS)
    parser.add_argument("--extract-notes", metavar="VERSION", help=argparse.SUPPRESS)
    parser.add_argument("--package-dmg-only", metavar="VERSION", help=argparse.SUPPRESS)

    subparsers = parser.add_subparsers(
        dest="command", metavar="{build,dry-run,publish,extension}"
    )
    p_build = subparsers.add_parser(
        "build",
        help="Build .app and .dmg locally (dist/) without touching git or GitHub.",
    )
    p_build.add_argument(
        "version",
        nargs="?",
        default="current",
        help="Optional bump before building (current, patch, minor, major, or X.Y.Z).",
    )

    p_dry = subparsers.add_parser(
        "dry-run",
        help="Preview version bump, build, git tag, and GitHub Release without making changes.",
    )
    p_dry.add_argument(
        "version",
        nargs="?",
        default="patch",
        help="patch, minor, major, current, or explicit X.Y.Z (default: patch).",
    )
    p_dry.add_argument(
        "--draft",
        action="store_true",
        help="Preview creating the GitHub Release as a draft.",
    )

    p_pub = subparsers.add_parser(
        "publish",
        help="Bump version, build .dmg, commit & tag git, and publish to GitHub Releases.",
    )
    p_pub.add_argument(
        "version",
        help="patch, minor, major, current, or explicit X.Y.Z.",
    )
    p_pub.add_argument(
        "--draft",
        action="store_true",
        help="Create the GitHub Release as a draft.",
    )

    p_ext = subparsers.add_parser(
        "extension",
        help="Bump (optional) and package the Chrome Extension zip into dist/.",
    )
    p_ext.add_argument(
        "version",
        nargs="?",
        default="current",
        help="Optional bump (current, patch, minor, major, or X.Y.Z).",
    )
    return parser


def main(argv: Sequence[str] | None = None, *, root: Path = ROOT_DIR) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if not (args.check_version or args.extract_notes or args.package_dmg_only or args.command):
        parser.print_help()
        return 2
    try:
        return run_release(args, root=root)
    except ReleaseError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
