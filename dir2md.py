from __future__ import annotations

import glob
import os
import pathlib
import re
import textwrap
import uuid
from typing import Literal
from typing import NamedTuple

import click
import pyperclip
import pytest
import tiktoken

# Add color codes
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = "\033[0m"

enc = tiktoken.encoding_for_model("gpt-4o")

class TextFile(NamedTuple):
    text: str
    path: str
    start: int = 0
    end: int = -1
    token_count: int = 0


def default_formatter(text_file: TextFile, path_location: Literal["above", "below"]) -> str:
    r = ""
    if path_location == "above":
        # Yield the relative path to the file as a comment
        r += f"{text_file.path}\n\n"
    # Yield the code block
    # Decide how many ticks to use
    ticks = "```"
    while re.search(rf"\n\s*{ticks}", text_file.text):
        ticks += "`"
    language = infer_language(text_file.path)
    # Add the custom attribute for the token count
    r += f"{ticks}{language} tokens={text_file.token_count}\n"
    if path_location == "below":
        comment_prefix = comment_prefix_for_language(language)
        l = f"{comment_prefix} {text_file.path}\n"
        if not text_file.text.startswith(l):
            r += l
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


def default_parser(s: str, path_replacement_field: str = "{}", path_location: Literal["above", "below"] = "above",
                   ignore_missing_path: bool = False) -> list[TextFile]:
    def _find_path_above(text: str) -> str:
        lines = text.splitlines()
        if lines and path_replacement_field.format(lines[-1].strip()):
            return lines[-1].strip()
        return ""

    def _find_path_below(code: str, language: str) -> tuple[str, str]:
        comment_prefix = comment_prefix_for_language(language)
        lines = code.splitlines()
        random_string = str(uuid.uuid4())
        try:
            path_replacement_field_prefix = path_replacement_field.format(random_string).split(random_string)[0]
        except IndexError:
            path_replacement_field_prefix = path_replacement_field
        if lines and lines[0].startswith(f"{comment_prefix} {path_replacement_field_prefix}"):
            path = lines[0][len(comment_prefix) + 1:].strip()
            code = "\n".join(lines[1:])
            return path, code
        return "", code

    def _format_error_message(start_line: int, code_block: str, path_replacement_field: str) -> str:
        # TODO: fix this
        #  - don't hardcode the language name
        #  - pass this function the full lines and let it choose what to show
        error_message = f"{RED}error: Could not find a path for code block{RESET}\n"
        error_message += f"Error at line {start_line + 1}:6\n"
        error_message += f"     |\n"
        error_message += f"{start_line + 1: >3}  | {code_block.splitlines()[0]}\n"
        error_message += f"     | {RED}^^^^^{RESET} {YELLOW}Expected a commented path above or below the code block:{RESET}\n\n"

        error_message += f"     | {YELLOW}Option 1: Add a commented path above the code block start{RESET}\n"
        error_message += f"     |\n"
        error_message += f"{GREEN}+{RESET} {start_line: >2} | {path_replacement_field} {YELLOW}<--- Add a path here{RESET}\n"
        error_message += f" {start_line + 1: >3} | ```python\n"
        error_message += f" {start_line + 2: >3} | {code_block.splitlines()[0]}\n"
        error_message += f" {start_line + 3: >3} | ```\n\n"

        error_message += f"     | {YELLOW}Option 2: Add a commented path below the code block start{RESET}\n"
        error_message += f"     |\n"
        error_message += f" {start_line: >3} | ```python\n"
        error_message += f"{GREEN}+{RESET} {start_line + 1: >2} | # {path_replacement_field} {YELLOW}<--- Add a path here as a comment{RESET}\n"
        error_message += f" {start_line + 2: >3} | {code_block.splitlines()[0]}\n"
        error_message += f" {start_line + 3: >3} | ```\n"

        return error_message

    code_blocks = []
    lines = s.splitlines()
    i = 0
    missing_path_count = 0
    while i < len(lines):
        line = lines[i]
        if line.startswith("```"):
            start = i
            ticks = line[:len(line) - len(line.lstrip("`"))]
            rest = line[len(ticks):].strip()
            attributes = rest.split(" ")
            if len(attributes) > 0:
                language = attributes[0]
            else:
                language = ""
            i += 1
            while i < len(lines) and not lines[i].startswith(ticks):
                i += 1
            if i < len(lines) and lines[i].startswith(ticks):
                i += 1

            code = "\n".join(lines[start + 1:i - 1])

            if path_location == "above" and start > 0:
                above_text = lines[start - 1]
                path = _find_path_above(above_text)
                if not path:
                    path, code = _find_path_below(code, language)
            else:  # path_location == "below"
                path, code = _find_path_below(code, language)
                if not path and start > 0:
                    above_text = lines[start - 1]
                    path = _find_path_above(above_text)
            if not path:
                missing_path_count += 1
                if not ignore_missing_path:
                    raise ValueError(_format_error_message(start, code, path_replacement_field))
            else:
                token_count = len(enc.encode(code))
                code_blocks.append(TextFile(text=code, path=path, token_count=token_count))
        else:
            i += 1

    if missing_path_count > 0 and ignore_missing_path:
        print(f"{YELLOW}Warning: Skipped {missing_path_count} code blocks due to missing paths.{RESET}")

    return code_blocks


@click.command()
@click.argument('files', nargs=-1)
@click.option('--no-glob', is_flag=True, help='Disable globbing for file arguments.')
@click.option('--path-replacement-field', default="{}", help='The pattern to use for identifying the file path.')
@click.option('--path-location', default="below", type=click.Choice(['above', 'below']),
              help='The location of the file path relative to the code block.')
def dir2md_cli(
        files: str, no_glob: bool,
        path_replacement_field: str, path_location: Literal["above", "below"]
) -> None:
    """Converts a directory of files to a markdown document."""
    output = []
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
            token_count = len(enc.encode(code))
            output.append(default_formatter(TextFile(path=file_path, text=code, token_count=token_count), path_location=path_location))

    # Join all formatted outputs and remove trailing newlines
    click.echo(("".join(output)).rstrip())


def dir2md(
        files: list[str] | str, no_glob: bool = False,
        path_replacement_field: str = "{}", path_location: Literal["above", "below"] = "below"
) -> str:
    """Converts a directory of files to a markdown document."""
    if isinstance(files, str):
        files = [files]

    output = []
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
            token_count = len(enc.encode(code))
            output.append(default_formatter(TextFile(path=file_path, text=code, token_count=token_count), path_location=path_location))

    # Join all formatted outputs and remove trailing newlines
    return ("".join(output)).rstrip()


@click.command()
@click.option('--output-dir', default=".", help='The directory to output the files to.')
@click.option('--yes', is_flag=True, help='Automatically answer yes to all prompts.')
@click.option('--path-replacement-field', default="{}", help='The pattern to use for identifying the file path.')
@click.option('--path-location', default="above", type=click.Choice(['above', 'below']),
              help='The location of the file path relative to the code block.')
@click.option('--paste', is_flag=True, help='Read the markdown text from the clipboard.')
@click.option('--path', type=click.Path(exists=True), help='Read the markdown text from a file.')
@click.option('--ignore-missing-path', is_flag=True, help='Ignore code blocks without a specified path.')
def md2dir_cli(
        output_dir: str, yes: bool, path_replacement_field: str,
        path_location: Literal["above", "below"], paste: bool, path: str, ignore_missing_path: bool
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

    save_dir(files=list(default_parser(text, path_replacement_field=path_replacement_field,
                                       path_location=path_location, ignore_missing_path=ignore_missing_path)),
             output_dir=output_dir, yes=yes)


def md2dir(
        text: str, output_dir: str, yes: bool = False, path_replacement_field: str = "{}",
        path_location: Literal["above", "below"] = "above", ignore_missing_path: bool = False
) -> None:
    """Converts a markdown document to a directory of files."""
    save_dir(files=list(default_parser(text, path_replacement_field=path_replacement_field, path_location=path_location,
                                       ignore_missing_path=ignore_missing_path)),
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
        TextFile(text="x = 1", path="out.py"),
        TextFile(text="let x = 1;", path="out.rs"),
    ]
    assert list(default_parser(md)) == expected


@pytest.mark.parametrize("text_file, expected", [
    (TextFile(text="x = 1\n", path="out.py"), "out.py\n\n```python\nx = 1\n```\n\n"),
    (TextFile(text="let x = 1;\n", path="out.rs"), "out.rs\n\n```rust\nlet x = 1;\n```\n\n"),
])
def test_default_formatter(text_file: TextFile, expected: str) -> None:
    assert default_formatter(text_file, path_location="above") == expected


def test_with_test_input_file():
    test_input = open("test_input", "r").read()
    print(md2dir(test_input, output_dir="test_output", yes=True))


if __name__ == "__main__":
    cli = click.Group()
    cli.add_command(dir2md_cli)
    cli.add_command(md2dir_cli)
    cli()
