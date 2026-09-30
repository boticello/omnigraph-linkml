"""Exercise the archive gate with reachable leaking distributions."""

import io
import tarfile
import zipfile

import pytest

from scripts.check_distribution_contents import check_archive


@pytest.mark.parametrize("leak", [
    "docs/design/secret.md", "plans/pilot.md", "reports/results.md",
    ".beads/beads.db-wal", "AGENTS.md", "README.internal.md",
    "tests/fixtures/linkml/notes.md", "src/linkml_omnigraph/notes.md",
])
def test_source_archive_rejects_internal_material(tmp_path, leak):
    archive = tmp_path / "package.tar.gz"
    with tarfile.open(archive, "w:gz") as contents:
        member = tarfile.TarInfo(f"omnigraph_linkml_generator-0.1.0/{leak}")
        member.size = 6
        contents.addfile(member, io.BytesIO(b"secret"))
    with pytest.raises(ValueError, match="forbidden member"):
        check_archive(archive)


def test_wheel_rejects_internal_material(tmp_path):
    archive = tmp_path / "package.whl"
    with zipfile.ZipFile(archive, "w") as contents:
        contents.writestr("linkml_omnigraph/design.md", "secret")
    with pytest.raises(ValueError, match="forbidden member"):
        check_archive(archive)


def test_source_archive_rejects_symlinks(tmp_path):
    archive = tmp_path / "package.tar.gz"
    with tarfile.open(archive, "w:gz") as contents:
        member = tarfile.TarInfo("omnigraph_linkml_generator-0.1.0/README.package.md")
        member.type = tarfile.SYMTYPE
        member.linkname = "../README.md"
        contents.addfile(member)
    with pytest.raises(ValueError, match="forbidden member"):
        check_archive(archive)


def test_archive_requires_generator(tmp_path):
    archive = tmp_path / "package.whl"
    with zipfile.ZipFile(archive, "w") as contents:
        contents.writestr("linkml_omnigraph/__init__.py", "")
        contents.writestr("omnigraph_linkml_generator-0.1.0.dist-info/licenses/LICENSE", "MIT")
    with pytest.raises(ValueError, match="missing required"):
        check_archive(archive)


def test_wheel_requires_licence(tmp_path):
    archive = tmp_path / "package.whl"
    with zipfile.ZipFile(archive, "w") as contents:
        contents.writestr("linkml_omnigraph/cli.py", "")
        contents.writestr("linkml_omnigraph/generator.py", "")
    with pytest.raises(ValueError, match="missing required licence"):
        check_archive(archive)
