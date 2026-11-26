from __future__ import annotations

import json
import subprocess
from pathlib import Path

import pytest

from scripts import release


def _create_repo_fixture(tmp_path: Path, version: str = "9.0.0") -> Path:
    (tmp_path / "backend").mkdir(parents=True, exist_ok=True)
    (tmp_path / "frontend").mkdir(parents=True, exist_ok=True)
    (tmp_path / "desktop").mkdir(parents=True, exist_ok=True)

    (tmp_path / "pyproject.toml").write_text(
        f'[project]\nname = "learnedleague-tool"\nversion = "{version}"\n',
        encoding="utf-8",
    )
    (tmp_path / "backend" / "config.py").write_text(
        f'class AppSettings:\n    app_version: str = "{version}"\n',
        encoding="utf-8",
    )
    (tmp_path / "frontend" / "package.json").write_text(
        json.dumps(
            {
                "name": "learnedleague-frontend",
                "private": True,
                "version": version,
                "dependencies": {
                    "react": "^19.0.0",
                    "react-dom": "^19.0.0",
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (tmp_path / "desktop" / "learnedleague.spec").write_text(
        (
            "info_plist={\n"
            f'    "CFBundleShortVersionString": "{version}",\n'
            f'    "CFBundleVersion": "{version}",\n'
            '    "NSHighResolutionCapable": True,\n'
            "}\n"
        ),
        encoding="utf-8",
    )
    (tmp_path / "changelog.md").write_text(
        (
            "# Changelog\n\n"
            "### [v9.0.0] - 2026-11-19\n"
            "- Feature A\n"
            "- Feature B\n\n"
            "### [v8.1.0] - 2026-05-26\n"
            "Fixed header issue.\n"
        ),
        encoding="utf-8",
    )
    return tmp_path


def test_normalize_and_compute_next_version() -> None:
    assert release.normalize_version("9.0.0") == "9.0.0"
    assert release.normalize_version("v9.1.2") == "9.1.2"
    assert release.normalize_version("9.1.0-rc.1") == "9.1.0-rc.1"

    assert release.compute_next_version("9.0.0", "patch") == "9.0.1"
    assert release.compute_next_version("9.0.0", "minor") == "9.1.0"
    assert release.compute_next_version("9.0.0", "major") == "10.0.0"
    assert release.compute_next_version("9.2.3-beta.1", "patch") == "9.2.4"
    assert release.compute_next_version("9.0.0", "current") == "9.0.0"
    assert release.compute_next_version("9.0.0", "v9.5.0") == "9.5.0"

    for bad in ("", "9.0", "abc", "01.0.0", "9.0.0+meta"):
        with pytest.raises(ValueError):
            release.normalize_version(bad)


def test_read_check_and_write_versions(tmp_path: Path) -> None:
    repo = _create_repo_fixture(tmp_path, version="9.0.0")

    versions = release.read_versions(repo)
    assert len(versions) == 5
    assert set(versions.values()) == {"9.0.0"}

    ok, msg, _ = release.check_version_consistency(repo, expect_tag="v9.0.0")
    assert ok is True
    assert "9.0.0" in msg

    modified = release.write_version(repo, "v9.1.0")
    assert len(modified) == 4

    ok_after, _, versions_after = release.check_version_consistency(repo, expect_tag="v9.1.0")
    assert ok_after is True
    assert set(versions_after.values()) == {"9.1.0"}

    pkg = json.loads((repo / "frontend" / "package.json").read_text(encoding="utf-8"))
    assert pkg["version"] == "9.1.0"
    assert pkg["dependencies"]["react"] == "^19.0.0"
    assert pkg["dependencies"]["react-dom"] == "^19.0.0"


def test_check_version_detects_drift_and_tag_mismatch(tmp_path: Path) -> None:
    repo = _create_repo_fixture(tmp_path, version="9.0.0")

    ok_tag, tag_msg, _ = release.check_version_consistency(repo, expect_tag="v9.0.1")
    assert ok_tag is False
    assert "expected 9.0.1" in tag_msg

    spec_path = repo / "desktop" / "learnedleague.spec"
    updated_spec = spec_path.read_text(encoding="utf-8").replace(
        '"CFBundleVersion": "9.0.0"',
        '"CFBundleVersion": "8.9.9"',
    )
    spec_path.write_text(updated_spec, encoding="utf-8")
    ok_drift, drift_msg, _ = release.check_version_consistency(repo)
    assert ok_drift is False
    assert "mismatch" in drift_msg.lower()


def test_extract_changelog_section(tmp_path: Path) -> None:
    repo = _create_repo_fixture(tmp_path)
    changelog = repo / "changelog.md"

    v9_notes = release.extract_changelog_section(changelog, "v9.0.0")
    assert v9_notes == "- Feature A\n- Feature B"

    v8_notes = release.extract_changelog_section(changelog, "8.1.0")
    assert v8_notes == "Fixed header issue."

    assert release.extract_changelog_section(changelog, "9.9.9") is None


def test_cli_check_version_and_dry_run_do_not_mutate_files(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repo = _create_repo_fixture(tmp_path, version="9.0.0")
    subprocess.run(["git", "init"], cwd=repo, check=True, capture_output=True)

    assert release.main(["--check-version"], root=repo) == 0
    assert "9.0.0" in capsys.readouterr().out

    assert release.main(["--check-version", "--expect-tag", "v9.0.1"], root=repo) == 1
    capsys.readouterr()

    monkeypatch.setattr(release, "_remote_tag_exists", lambda *_args, **_kwargs: False)

    snapshot_before = {
        rel: (repo / rel).read_text(encoding="utf-8")
        for rel in release.TRACKED_VERSION_FILES
    }

    rc = release.main(["patch", "--dry-run", "--allow-dirty"], root=repo)
    assert rc == 0
    out = capsys.readouterr().out
    assert "9.0.0 -> 9.0.1" in out
    assert "[dry-run] Update" in out
    assert "gh release create v9.0.1" in out

    snapshot_after = {
        rel: (repo / rel).read_text(encoding="utf-8")
        for rel in release.TRACKED_VERSION_FILES
    }
    assert snapshot_after == snapshot_before
