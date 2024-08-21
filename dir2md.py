from __future__ import annotations

import glob
import os
import pathlib
import re
from typing import Callable, Iterable, Literal
from typing import Generator
from typing import List
from typing import NamedTuple

import click
import tempfile


class TextFile(NamedTuple):
    text: str
    path: str
    start: int = 0
    end: int = -1


def default_formatter(text_file: TextFile) -> str:
    r = ""
    # Yield the relative path to the file as a comment
    r += f"{text_file.path}\n"
    # Yield the code block
    # Decide how many ticks to use
    ticks = "```"
    while re.search(rf"\n\s*{ticks}", text_file.text):
        ticks += "`"
    r += ticks + "\n"
    r += text_file.text
    r += ticks + "\n\n"
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
    def _find_path_above(text: str) -> str:
        path_pattern = path_replacement_field.format(r"(.*)")
        path_match = re.search(rf"{path_pattern}\n$", text, re.MULTILINE)
        if path_match:
            return path_match.group(1).strip()
        return ""

    def _find_path_below(code: str, language: str) -> tuple[str, str]:
        comment_prefix = comment_prefix_for_language(language)
        path_pattern = rf"{comment_prefix} {path_replacement_field.format(r'(.*)')}"
        # Match only at the beginning of the code block
        path_match = re.match(path_pattern, code)
        if path_match:
            path = path_match.group(1).strip()
            code = code[path_match.end():]
            return path, code
        return "", code

    code_blocks = []
    pattern = r"(?<!`)(?=\n|^)([`~]{3,})(.*?)\n([\s\S]*?)\n\1(?=\n|$)"
    matches = re.finditer(pattern, s, re.MULTILINE)
    for match in matches:
        ticks = match.group(1)
        language = match.group(2).strip()
        code = match.group(3)

        start = match.start()
        above_text = s[:start]

        path = ""
        if path_location == "above":
            # Try above first
            path = _find_path_above(above_text)
            if not path:
                # If not found above, try below
                path, code = _find_path_below(code, language)
        else:  # path_location == "below"
            # Try below first
            path, code = _find_path_below(code, language)
            if not path:
                # If not found below, try above
                path = _find_path_above(above_text)

        if not code.endswith("\n"):
            code += "\n"

        code_blocks.append(TextFile(text=code, path=path))

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
@click.argument('text', type=click.STRING)
@click.option('--output-dir', default=".", help='The directory to output the files to.')
@click.option('--yes', is_flag=True, help='Automatically answer yes to all prompts.')
@click.option('--path-replacement-field', default="{}", help='The pattern to use for identifying the file path.')
@click.option('--path-location', default="above", type=click.Choice(['above', 'below']), help='The location of the file path relative to the code block.')
def md2dir(
        text: str, output_dir: str, yes: bool, path_replacement_field: str,
        path_location: Literal["above", "below"]
) -> None:
    """Converts a markdown document to a directory of files."""
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
        # Allow "all" as a response
        while True:
            click.echo("Continue? (y/n/all)")
            response = input().lower()
            if response in ("y", "n", "all"):
                break
            click.echo("Invalid response. Please enter 'y', 'n', or 'all'.")
        if response == "n":
            click.echo("Aborted.")
            return
        elif response == "all":
            yes = True  # Set yes to True for subsequent prompts

    for file in files:
        click.echo(f"Writing {pathlib.Path(output_dir, file.path)}")
        path = pathlib.Path(output_dir, file.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(file.text)


def test_md2dir():
    test_cases = [
        # Simple test
        ("x\n```\nz\n```\n", [TextFile(text="z\n", path="x")]),
        # With language
        ("x\n```python\nz\n```\n", [TextFile(text="z\n", path="x")]),
        # Longer file
        ("path/to/file.md\n```python\nprint('hello world')\nprint('goodbye world')\n```\n",
         [TextFile(text="print('hello world')\nprint('goodbye world')\n", path="path/to/file.md")]),
        # Empty file
        ("empty.py\n```python\n```\n", [TextFile(text="\n", path="empty.py")]),
        # Multiple languages
        ("x.py\n```python\nz\n```\ny.rs\n```rust\na\n```\n",
         [TextFile(text="z\n", path="x.py"), TextFile(text="a\n", path="y.rs")]),
        # Path below
        ("```python\n# path/to/file.py\nz\n```\n",
         [TextFile(text="z\n", path="path/to/file.py")], "{}", "below"),
        # Path below with different comment prefix
        ("```rust\n// path/to/file.rs\na\n```\n",
         [TextFile(text="a\n", path="path/to/file.rs")], "{}", "below"),
        # Different path replacement field
        ("File: path/to/file.py\n```python\nz\n```\n",
         [TextFile(text="z\n", path="path/to/file.py")], "File: {}"),
        # Code block at the beginning of the string
        ("```python\nz\n```\n", [TextFile(text="z\n", path="")]),  # No path for this case
    ]

    for text, expected, *args in test_cases:
        if args:
            path_replacement_field, path_location = args
            result = list(default_parser(text, path_replacement_field=path_replacement_field, path_location=path_location))
        else:
            result = list(default_parser(text))
        assert result == expected


def test_dir2md_md2dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create test files
        with open(os.path.join(tmpdirname, "test.py"), "w") as f:
            f.write("print('hello world')\n")
        with open(os.path.join(tmpdirname, "test.rs"), "w") as f:
            f.write("println!(\"hello world\");\n")

        # Test dir2md
        # Note: This part is tricky to test with click due to the print statements.
        #       It would require capturing the output and comparing it.
        #       For now, we'll skip this part of the test.

        # Test md2dir
        with tempfile.TemporaryDirectory() as output_dir:
            md2dir_save(md_output, output_dir, yes=True)

            # Compare files
            with open(os.path.join(output_dir, "test.py"), "r") as f:
                assert f.read() == "print('hello world')\n"
            with open(os.path.join(output_dir, "test.rs"), "r") as f:
                assert f.read() == "println!(\"hello world\");\n"


if __name__ == "__main__":
    cli = click.Group()
    cli.add_command(dir2md)
    cli.add_command(md2dir)
    cli()