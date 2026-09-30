from __future__ import annotations

from pathlib import Path

from click.testing import CliRunner

from linkml_omnigraph.cli import main

ROOT = Path(__file__).parent


def test_cli_writes_schema_to_stdout() -> None:
    runner = CliRunner()
    schema = ROOT / "fixtures" / "linkml" / "basic.yaml"
    expected = (ROOT / "fixtures" / "omnigraph" / "basic.pg").read_text(encoding="utf-8")

    result = runner.invoke(main, [str(schema)])

    assert result.exit_code == 0
    assert result.output == expected


def test_cli_writes_schema_to_output_file(tmp_path: Path) -> None:
    runner = CliRunner()
    schema = ROOT / "fixtures" / "linkml" / "basic.yaml"
    output = tmp_path / "nested" / "schema.pg"
    expected = (ROOT / "fixtures" / "omnigraph" / "basic.pg").read_text(encoding="utf-8")

    result = runner.invoke(main, [str(schema), "--output", str(output)])

    assert result.exit_code == 0
    assert output.read_text(encoding="utf-8") == expected


def test_cli_reports_generator_errors(tmp_path: Path, schema_prelude: str) -> None:
    from tests.conftest import write_schema

    runner = CliRunner()
    schema = write_schema(
        tmp_path / "invalid.yaml",
        schema_prelude,
        """
classes:
  Broken:
    annotations:
      kind: embedded
""",
    )

    result = runner.invoke(main, [str(schema)])

    assert result.exit_code != 0
    assert "kind: embedded" in result.output

