from __future__ import annotations

from pathlib import Path

import click

from linkml_omnigraph.generator import OmnigraphGenerator, OmnigraphGeneratorError


@click.command(context_settings={"help_option_names": ["-h", "--help"]})
@click.argument("schema", type=click.Path(exists=True, dir_okay=False, path_type=Path))
@click.option("-o", "--output", type=click.Path(dir_okay=False, path_type=Path), help="Write .pg output to this file.")
def main(schema: Path, output: Path | None) -> None:
    """Generate Omnigraph .pg schema from a LinkML schema."""

    try:
        text = OmnigraphGenerator(schema).serialize()
    except OmnigraphGeneratorError as exc:
        raise click.ClickException(str(exc)) from exc

    if output is None:
        click.echo(text, nl=False)
    else:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()

