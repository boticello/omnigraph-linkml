"""Reject distribution members outside the deliberate package boundary."""

import argparse
import tarfile
import zipfile
from pathlib import Path, PurePosixPath


def allowed_source(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if name in {
        "pyproject.toml", ".gitignore", "README.package.md", "requirements-dev.txt",
        "requirements-build.in", "PKG-INFO", "scripts/generate_artifacts.py",
        "scripts/check_distribution_contents.py",
        "scripts/check_documentation.py",
        "LICENSE", "README.md", "CONTRIBUTING.md", "CHANGELOG.md",
        "docs/authoring.md", "docs/mapping.md", "docs/validation.md",
        "docs/compatibility.md", "docs/example-ta1044.md",
    }:
        return True
    return path.suffix in {
        "src/linkml_omnigraph": {".py"},
        "tests": {".py"},
        "tests/fixtures/linkml": {".yaml"},
        "tests/fixtures/omnigraph": {".pg", ".gq"},
    }.get(str(path.parent), set())


def allowed_wheel(name: str) -> bool:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if str(path.parent) == "linkml_omnigraph" and path.suffix == ".py":
        return True
    if (
        len(path.parts) == 3
        and path.parts[0].startswith("omnigraph_linkml_generator-")
        and path.parts[0].endswith(".dist-info")
        and path.parts[1:] == ("licenses", "LICENSE")
    ):
        return True
    return (
        len(path.parts) == 2
        and path.parts[0].startswith("omnigraph_linkml_generator-")
        and path.parts[0].endswith(".dist-info")
        and path.name in {"METADATA", "WHEEL", "RECORD", "entry_points.txt"}
    )


def check_archive(archive: Path) -> None:
    if archive.name.endswith(".tar.gz"):
        with tarfile.open(archive) as contents:
            members = contents.getmembers()
        roots = {PurePosixPath(member.name).parts[0] for member in members}
        if len(roots) != 1 or not next(iter(roots)).startswith("omnigraph_linkml_generator-"):
            raise ValueError(f"{archive}: unexpected source archive root")
        files = []
        for member in members:
            if member.isdir():
                continue
            name = "/".join(PurePosixPath(member.name).parts[1:])
            if not member.isfile() or not allowed_source(name):
                raise ValueError(f"{archive}: forbidden member {member.name}")
            files.append(name)
        required = {"pyproject.toml", "README.package.md", "PKG-INFO", "LICENSE",
                    "src/linkml_omnigraph/cli.py", "src/linkml_omnigraph/generator.py"}
    elif archive.suffix == ".whl":
        with zipfile.ZipFile(archive) as contents:
            files = contents.namelist()
        for name in files:
            if not allowed_wheel(name):
                raise ValueError(f"{archive}: forbidden member {name}")
        required = {"linkml_omnigraph/cli.py", "linkml_omnigraph/generator.py"}
        if not any(name.endswith(".dist-info/licenses/LICENSE") for name in files):
            raise ValueError(f"{archive}: missing required licence")
    else:
        raise ValueError(f"{archive}: unsupported distribution format")
    if missing := required - set(files):
        raise ValueError(f"{archive}: missing required members {sorted(missing)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archives", nargs="+", type=Path)
    for archive in parser.parse_args().archives:
        check_archive(archive)
        print(f"{archive}: distribution contents accepted")


if __name__ == "__main__":
    main()
