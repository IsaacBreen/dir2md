from __future__ import annotations

import glob
import os
import pathlib
import re
import textwrap
from typing import Literal
from typing import NamedTuple

import click
import pyperclip
import pytest


class TextFile(NamedTuple):
    text: str
    path: str
    start: int = 0
    end: int = -1


def default_formatter(text_file: TextFile) -> str:
    r = ""
    # Yield the relative path to the file as a comment
    r += f"{text_file.path}\n\n"
    # Yield the code block
    # Decide how many ticks to use
    ticks = "```"
    while re.search(rf"\n\s*{ticks}", text_file.text):
        ticks += "`"
    language = infer_language(text_file.path)
    r += f"{ticks}{language}\n"
    r += text_file.text
    r += f"{ticks}\n\n"
    return r


def infer_language(path: str) -> str:
    _, ext = os.path.splitext(path)
    ext = ext.lower()
    if ext == ".py":
        return "python"
    elif ext == ".rs":
        return "rust"
    # Add more mappings as needed
    return ""


def comment_prefix_for_language(language: str) -> str:
    if language == "python":
        return "#"
    elif language == "rust":
        return "//"
    # Add more mappings as needed
    return ""


def default_parser(s: str, path_replacement_field: str = "{}", path_location: Literal["above", "below"] = "above") -> list[TextFile]:
    def _find_path_above(lines: list[str], i: int) -> str:
        path_pattern = path_replacement_field.format(r"(.*)")
        if i > 0 and re.match(path_pattern, lines[i - 1]):
            return lines[i - 1].strip()[len(path_replacement_field.format("")):]
        return ""

    def _find_path_below(lines: list[str], i: int, language: str) -> tuple[str, int]:
        comment_prefix = comment_prefix_for_language(language)
        path_pattern = rf"{comment_prefix} {path_replacement_field.format(r'(.*)')}"
        if i + 1 < len(lines) and re.match(path_pattern, lines[i + 1]):
            path = lines[i + 1][len(f"{comment_prefix} {path_replacement_field.format('')}"):].strip()
            return path, i + 2
        return "", i + 1

    code_blocks = []
    lines = s.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            ticks = line
            language = line[len(ticks):].strip()
            code = []
            i += 1
            while i < len(lines) and not lines[i].startswith(ticks):
                code.append(lines[i])
                i += 1
            if i < len(lines) and lines[i].startswith(ticks):
                i += 1

            if path_location == "above":
                path = _find_path_above(lines, i - len(code) - 1)
                if not path:
                    path, new_i = _find_path_below(lines, i - len(code) - 1, language)
                    if path:
                        code = lines[new_i:i - 1]
            else:  # path_location == "below"
                path, new_i = _find_path_below(lines, i - len(code) - 1, language)
                if not path:
                    path = _find_path_above(lines, i - len(code) - 1)
                else:
                    code = lines[new_i:i - 1]

            code = "\n".join(code)
            if not code.endswith("\n"):
                code += "\n"

            code_blocks.append(TextFile(text=code, path=path))
        else:
            i += 1

    return code_blocks


@click.command()
@click.argument('files', nargs=-1)
@click.option('--no-glob', is_flag=True, help='Disable globbing for file arguments.')
@click.option('--path-replacement-field', default="{}", help='The pattern to use for identifying the file path.')
@click.option('--path-location', default="above", type=click.Choice(['above', 'below']), help='The location of the file path relative to the code block.')
def dir2md(
        files: str, no_glob: bool,
        path_replacement_field: str, path_location: Literal["above", "below"]
) -> None:
    """Converts a directory of files to a markdown document."""
    for file_or_pattern in files:
        if not no_glob:
            file_paths = glob.glob(file_or_pattern)
        else:
            file_paths = [file_or_pattern]
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File {file_path} not found")
            with open(file_path, "r") as code_file:
                code = code_file.read()
                if not code.endswith("\n"):
                    code += "\n"
            language = infer_language(file_path)
            click.echo(''.join(default_formatter(TextFile(path=file_path, text=code)).splitlines()))


@click.command()
@click.option('--output-dir', default=".", help='The directory to output the files to.')
@click.option('--yes', is_flag=True, help='Automatically answer yes to all prompts.')
@click.option('--path-replacement-field', default="{}", help='The pattern to use for identifying the file path.')
@click.option('--path-location', default="above", type=click.Choice(['above', 'below']), help='The location of the file path relative to the code block.')
@click.option('--paste', is_flag=True, help='Read the markdown text from the clipboard.')
@click.option('--path', type=click.Path(exists=True), help='Read the markdown text from a file.')
def md2dir(
        output_dir: str, yes: bool, path_replacement_field: str,
        path_location: Literal["above", "below"], paste: bool, path: str
) -> None:
    """Converts a markdown document to a directory of files."""
    if paste and path:
        raise click.UsageError("You cannot specify both --paste and --path.")
    if not paste and not path:
        raise click.UsageError("You must specify either --paste or --path.")

    if paste:
        text = pyperclip.paste()
    elif path:
        with open(path, 'r') as f:
            text = f.read()

    save_dir(files=list(default_parser(text, path_replacement_field=path_replacement_field, path_location=path_location)),
             output_dir=output_dir, yes=yes)


def md2dir_save(text: str, output_dir: str, yes: bool = False, path_replacement_field: str = "{}",
                path_location: Literal["above", "below"] = "above") -> None:
    save_dir(files=list(default_parser(text, path_replacement_field=path_replacement_field, path_location=path_location)),
             output_dir=output_dir, yes=yes)


def save_dir(files: list[TextFile], output_dir: str, yes: bool = False) -> None:
    if files and not yes:
        filenames = [file.path for file in files]
        new_directories = []
        for filename in filenames:
            directory = os.path.dirname(filename)
            if (
                    directory
                    and not os.path.exists(directory)
                    and directory not in new_directories
            ):
                new_directories.append(directory)
        new_files = [
            file for file in filenames if not pathlib.Path(output_dir, file).exists()
        ]
        existing_files = [
            file for file in filenames if pathlib.Path(output_dir, file).exists()
        ]
        if new_directories:
            click.echo("The following directories will be created:")
            for directory in new_directories:
                click.echo(f"  {directory!r}")
        if new_files:
            click.echo("The following files will be created:")
            for file in new_files:
                click.echo(f"  {pathlib.Path(output_dir, file)}")
        if existing_files:
            click.echo("The following files will be overwritten:")
            for file in existing_files:
                click.echo(f"  {pathlib.Path(output_dir, file)}")
        click.echo("Continue? (y/n)")
        if input() != "y":
            click.echo("Aborted.")
            return
    for file in files:
        click.echo(f"Writing {pathlib.Path(output_dir, file.path)}")
        path = pathlib.Path(output_dir, file.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(file.text)


def test_default_parser():
    md = textwrap.dedent(
        """
        ```python
        # out.py
        x = 1
        ```
        
        ```rust
        // out.rs
        let x = 1;
        ```
        """
    )
    expected = [
        TextFile(text="x = 1\n", path="out.py"),
        TextFile(text="let x = 1;\n", path="out.rs"),
    ]
    assert list(default_parser(md)) == expected


@pytest.mark.parametrize("text_file, expected", [
    (TextFile(text="x = 1\n", path="out.py"), "out.py\n\n```python\nx = 1\n```\n\n"),
    (TextFile(text="let x = 1;\n", path="out.rs"), "out.rs\n\n```rust\nlet x = 1;\n```\n\n"),
])
def test_default_formatter(text_file: TextFile, expected: str) -> None:
    assert default_formatter(text_file) == expected


if __name__ == "__main__":
    cli = click.Group()
    cli.add_command(dir2md)
    cli.add_command(md2dir)
    cli()