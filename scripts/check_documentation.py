"""Check local documentation links and execute the complete authoring example."""

import re
import subprocess
import tempfile
from pathlib import Path

from linkml_omnigraph import OmnigraphGenerator

ROOT = Path(__file__).resolve().parent.parent


def main() -> None:
    documents = [*ROOT.glob("*.md"), *ROOT.joinpath("docs").glob("*.md")]
    count = 0
    for document in documents:
        for target in re.findall(r"\[[^\]]+\]\(([^)]+)\)", document.read_text()):
            if "://" in target or target.startswith("#"):
                continue
            path = (document.parent / target.split("#", 1)[0]).resolve()
            if not path.is_relative_to(ROOT) or not path.exists():
                raise ValueError(f"{document}: unresolved local link {target}")
            count += 1
    example = ROOT.joinpath("docs/authoring.md").read_text()
    yaml = re.search(r"```yaml\n(.*?)```", example, re.DOTALL)
    pg = re.search(r"```pg\n(.*?)```", example, re.DOTALL)
    if yaml is None or pg is None:
        raise ValueError("The authoring guide must contain its model and projection")
    with tempfile.TemporaryDirectory(prefix="omnigraph-docs-") as temporary:
        directory = Path(temporary)
        model = directory / "model.yaml"
        model.write_text(yaml.group(1))
        output = OmnigraphGenerator(model).serialize()
        if pg.group(1).strip() not in output:
            raise ValueError("The documented projection differs from generated output")
        schema = directory / "model.pg"
        schema.write_text(output)
        subprocess.run([
            "omnigraph", "init", "--schema", str(schema), str(directory / "example.omni")
        ], check=True, capture_output=True, text=True)
    print(f"{count} local links and the generated authoring example accepted")


if __name__ == "__main__":
    main()
