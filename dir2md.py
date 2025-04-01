from __future__ import annotations

import glob
import os
import pathlib
import re
import textwrap
import uuid
from dataclasses import dataclass
from typing import Literal, List, Tuple, Union, Optional
from typing import NamedTuple

import click
import pyperclip
import pytest
import tiktoken

# TODO: get rid of the handling of unclosed blocks. It's not worth the added complexity. Newer models will have much larger output limits or will be able to continue generating incomplete messages (or 'prefill', as Anthropic calls it).

# Add color codes
RED = "\033[91m"
YELLOW = "\033[93m"
GREEN = "\033[92m"
RESET = "\033[0m"

enc = tiktoken.encoding_for_model("gpt-4o")
token_fudge_factor = 1.5

class TextFile(NamedTuple):
    text: str
    path: str
    start: int = 0
    end: int = -1
    token_count: int = 0


def default_formatter(text_file: TextFile, path_location: Literal["above", "below"], include_token_count: bool = False) -> str:
    r = ""
    if path_location == "above":
        # Yield the relative path to the file
        r += f"{text_file.path}\n\n"
        # Yield the code block
        # Decide how many ticks to use
        ticks = "```"
        while re.search(rf"\n\s*{ticks}", text_file.text):
            ticks += "`"
        language = infer_language(text_file.path)
        if include_token_count:
            # Add the custom attribute for the token count
            r += f"{ticks}{language} tokens={int(text_file.token_count * token_fudge_factor)}\n"
        else:
            r += f"{ticks}{language}\n"
        r += text_file.text
        r += f"{ticks}\n\n"
    else:
        # For path_location == "below"
        # Yield the code block
        ticks = "```"
        while re.search(rf"\n\s*{ticks}", text_file.text):
            ticks += "`"
        language = infer_language(text_file.path)
        # Add the custom attribute for the token count
        if include_token_count:
            r += f"{ticks}{language} tokens={int(text_file.token_count * token_fudge_factor)}\n"
        else:
            r += f"{ticks}{language}\n"
        comment_prefix = comment_prefix_for_language(language)
        r += f"{comment_prefix} {text_file.path}\n"
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


@dataclass
class ParseResult:
    code_blocks: list[TextFile]
    last_code_block_is_unclosed: bool


def default_parser(s: str, path_replacement_field: str = "{}", path_location: Literal["above", "below"] = "below",
    ignore_missing_path: bool = False) -> ParseResult:
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
        # - don't hardcode the language name
        # - pass this function the full lines and let it choose what to show
        error_message = f"{RED}error: Could not find a path for code block{RESET}\n"
        error_message += f"Error at line {start_line + 1}:6\n"
        error_message += f" |\n"
        error_message += f"{start_line + 1: >3} | {code_block.splitlines()[0]}\n"
        error_message += f" | {RED}^^^^^{RESET} {YELLOW}Expected a commented path above or below the code block:{RESET}\n\n"

        error_message += f" | {YELLOW}Option 1: Add a commented path above the code block start{RESET}\n"
        error_message += f" |\n"
        error_message += f"{GREEN}+{RESET} {start_line: >2} | {path_replacement_field} {YELLOW}<--- Add a path here{RESET}\n"
        error_message += f" {start_line + 1: >3} | ```python\n"
        error_message += f" {start_line + 2: >3} | {code_block.splitlines()[0]}\n"
        error_message += f" {start_line + 3: >3} | ```\n\n"

        error_message += f" | {YELLOW}Option 2: Add a commented path below the code block start{RESET}\n"
        error_message += f" |\n"
        error_message += f" {start_line: >3} | ```python\n"
        error_message += f"{GREEN}+{RESET} {start_line + 1: >2} | # {path_replacement_field} {YELLOW}<--- Add a path here as a comment{RESET}\n"
        error_message += f" {start_line + 2: >3} | {code_block.splitlines()[0]}\n"
        error_message += f" {start_line + 3: >3} | ```\n"

        return error_message

    code_blocks = []
    lines = s.splitlines()
    print(f"Parsing {len(lines)} lines")
    i = 0
    missing_path_count = 0
    last_code_block_is_unclosed = False
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
            while True:
                if i >= len(lines):
                    break
                if lines[i].startswith(ticks):
                    i += 1
                    break
                i += 1

            code = "\n".join(lines[start + 1:i - 1])

            if path_location == "above" and start > 0:
                above_text = lines[start - 1]
                path = _find_path_above(above_text)
                if not path:
                    path, code = _find_path_below(code, language)
            else:
                path, code = _find_path_below(code, language)
                if not path and start > 0:
                    above_text = lines[start - 1]
                    path = _find_path_above(above_text)
            if not path:
                missing_path_count += 1
                if not ignore_missing_path:
                    raise ValueError(_format_error_message(start, code, path_replacement_field))
                else:
                    if i == len(lines) and not lines[i - 1].startswith(ticks):
                        last_code_block_is_unclosed = True
            token_count = len(enc.encode(code, disallowed_special=()))
            code_blocks.append(TextFile(text=code, path=path, token_count=token_count))
        else:
            i += 1

    if missing_path_count > 0 and ignore_missing_path:
        print(f"{YELLOW}Warning: Skipped {missing_path_count} code blocks due to missing paths.{RESET}")

    return ParseResult(code_blocks, last_code_block_is_unclosed)


def parse_file_arg(arg: str) -> Tuple[str, Optional[str]]:
    '''Parses a file argument 'filename[linespec]' and returns filename and line specification'''
    if '[' in arg:
        pos = arg.find('[')
        filename = arg[:pos]
        line_spec = arg[pos:]
        return filename, line_spec
    else:
        return arg, None


def parse_line_specification(line_spec: str):
    class X:
        def __getitem__(self, key):
            return key

    x = X()
    try:
        # Using eval is generally unsafe, but in this specific case,
        # we control the input and only allow indexing operations.
        # It's still recommended to avoid eval if a safer alternative exists.
        result = eval(f"x{line_spec}")  # Evaluate x[line_spec]
        if isinstance(result, tuple):  # Handle slices (a, b) format
            return [slice(*result)]  # Convert to slice object
        elif isinstance(result, list):
            return result
        elif isinstance(result, slice | int):
            return [result]
        else:
            raise ValueError(f"Invalid line specification: {line_spec}. Result: {result}.")
    except (SyntaxError, TypeError, NameError, IndexError) as e:
        raise ValueError(f"Invalid line specification: {line_spec} - {e}")


def dir2md_cli(
    files: List[str], no_glob: bool,
    path_replacement_field: str, path_location: Literal["above", "below"]
) -> None:
    """Converts a directory of files to a markdown document."""
    if isinstance(files, str):
        files = [files]

    output = []
    for file_arg in files:
        filename, line_specification = parse_file_arg(file_arg)
        if not no_glob:
            file_paths = glob.glob(filename)
        else:
            file_paths = [filename]
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File {file_path} not found")
            with open(file_path, "r") as code_file:
                lines = code_file.readlines()
                if line_specification:
                    indices_or_slices = parse_line_specification(line_specification)
                    selected_lines = []
                    for idx in indices_or_slices:
                        if isinstance(idx, slice):
                            selected_lines.extend(lines[idx])
                        else:
                            try:
                                selected_lines.append(lines[idx])
                            except IndexError:
                                continue
                    code = ''.join(selected_lines)
                else:
                    code = ''.join(lines)
                if not code.endswith("\n"):
                    code += "\n"
                token_count = len(enc.encode(code))
                output.append(default_formatter(TextFile(path=file_path, text=code, token_count=token_count), path_location=path_location))
    # Join all formatted outputs and remove trailing newlines
    click.echo(("".join(output)).rstrip())


@click.command(name="dir2md")
@click.argument('files', nargs=-1, required=True)
@click.option('--no-glob', is_flag=True, default=True, help='Disable globbing for file arguments.')
@click.option('--path-replacement-field', default="{}", help='The pattern to use for identifying the file path.')
@click.option('--path-location', default="below", type=click.Choice(['above', 'below']),
    help='The location of the file path relative to the code block.')
def dir2md_command(
    files: list[str], no_glob: bool,
    path_replacement_field: str, path_location: Literal["above", "below"]
) -> None:
    """Converts a directory of files to a markdown document."""
    dir2md_cli(
        files=files,
        no_glob=no_glob,
        path_replacement_field=path_replacement_field,
        path_location=path_location
    )


def dir2md(
    files: List[str], no_glob: bool = False,
    path_replacement_field: str = "{}", path_location: Literal["above", "below"] = "below"
) -> str:
    """Converts a directory of files to a markdown document."""
    if isinstance(files, str):
        files = [files]

    output = []
    for file_arg in files:
        filename, line_specification = parse_file_arg(file_arg)
        if not no_glob:
            file_paths = glob.glob(filename)
        else:
            file_paths = [filename]
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                raise FileNotFoundError(f"File {file_path} not found")
            with open(file_path, "r") as code_file:
                lines = code_file.readlines()
                if line_specification:
                    indices_or_slices = parse_line_specification(line_specification)
                    selected_lines = []
                    for idx in indices_or_slices:
                        if isinstance(idx, slice):
                            selected_lines.extend(lines[idx])
                        else:
                            try:
                                selected_lines.append(lines[idx])
                            except IndexError:
                                continue
                    code = ''.join(selected_lines)
                else:
                    code = ''.join(lines)
                if not code.endswith("\n"):
                    code += "\n"
                token_count = len(enc.encode(code))
                output.append(default_formatter(TextFile(path=file_path, text=code, token_count=token_count), path_location=path_location))

    # Join all formatted outputs and remove trailing newlines
    return ("".join(output)).rstrip()


@click.command(name="md2dir")
@click.option('--output-dir', default=".", help='The directory to output the files to.')
@click.option('--yes', is_flag=True, help='Automatically answer yes to all prompts.')
@click.option('--path-replacement-field', default="{}", help='The pattern to use for identifying the file path.')
@click.option('--path-location', default="below", type=click.Choice(['above', 'below']),
    help='The location of the file path relative to the code block.')
@click.option('--paste', is_flag=True, help='Read the markdown text from the clipboard.')
@click.option('--path', type=click.Path(exists=True), help='Read the markdown text from a file.')
@click.option('--ignore-missing-path', is_flag=True, default=False, help='Ignore code blocks without a specified path.')
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

    files = default_parser(
        text,
        path_replacement_field=path_replacement_field,
        path_location=path_location,
        ignore_missing_path=ignore_missing_path
    ).code_blocks
    files = list(files)
    save_dir(files=files, output_dir=output_dir, yes=yes)


def md2dir(
    text: str, output_dir: str, yes: bool = False, path_replacement_field: str = "{}",
    path_location: Literal["above", "below"] = "below", ignore_missing_path: bool = False,
    on_unclosed: Literal["proceed", "omit_last_line", "skip", "error"] = "omit_last_line"
) -> ParseResult:
    """Converts a markdown document to a directory of files."""
    parse_result = default_parser(
        text,
        path_replacement_field=path_replacement_field,
        path_location=path_location,
        ignore_missing_path=ignore_missing_path
    )
    if parse_result.last_code_block_is_unclosed:
        match on_unclosed:
            case "proceed":
                pass
            case "omit_last_line":
                parse_result.code_blocks[-1].text = "\n".join(parse_result.code_blocks[-1].text.splitlines()[:-1])
                parse_result.code_blocks[-1].token_count = len(enc.encode(parse_result.code_blocks[-1].text))
            case "skip":
                parse_result.code_blocks.pop()
            case "error":
                raise ValueError("Last code block is unclosed")
            case _:
                raise ValueError(f"Invalid value for on_unclosed: {on_unclosed}")
    save_dir(files=parse_result.code_blocks, output_dir=output_dir, yes=yes)
    return parse_result


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
                click.echo(f" {directory!r}")
        if new_files:
            click.echo("The following files will be created:")
            for file in new_files:
                click.echo(f" {pathlib.Path(output_dir, file)}")
        if existing_files:
            click.echo("The following files will be overwritten:")
            for file in existing_files:
                click.echo(f" {pathlib.Path(output_dir, file)}")
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
    assert list(default_parser(md).code_blocks) == expected


@pytest.mark.parametrize("text_file, expected", [
    (TextFile(text="x = 1\n", path="out.py"), "out.py\n\n```python\nx = 1\n```\n\n"),
    (TextFile(text="let x = 1;\n", path="out.rs"), "out.rs\n\n```rust\nlet x = 1;\n```\n\n"),
    ])
def test_default_formatter(text_file: TextFile, expected: str) -> None:
    assert default_formatter(text_file, path_location="below") == expected


def test_parse_file_arg():
    assert parse_file_arg('a.py[:2]') == ('a.py', '[:2]')
    assert parse_file_arg('b.py[-5:]') == ('b.py', '[-5:]')
    assert parse_file_arg('c.py[0:10]') == ('c.py', '[0:10]')
    assert parse_file_arg('d.py [[0, 2, 4, 6:-8, -5, -3, -1]]') == ('d.py ', '[[0, 2, 4, 6:-8, -5, -3, -1]]')


def test_parse_line_specification():
    assert parse_line_specification('[:2]') == [slice(None, 2)]
    assert parse_line_specification('[-5:]') == [slice(-5, None)]
    assert parse_line_specification('[0:10]') == [slice(0, 10)]
    assert parse_line_specification('[[0, 2, 4, 6:-8, -5, -3, -1]]') == [0, 2, 4, slice(6, -8), -5, -3, -1]


def test_with_test_input_file():
    test_input = open("test_input", "r").read()
    print(md2dir(test_input, output_dir="test_output", yes=True))


if __name__ == "__main__":
    cli = click.Group()
    cli.add_command(dir2md_command)
    cli.add_command(md2dir_cli)
    cli()