from __future__ import annotations

import glob
import os
import pathlib
import re
from typing import Callable, Iterable, Literal
from typing import Generator
from typing import List
from typing import NamedTuple

import fire
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
    code_blocks = []
    pattern = r"(?<!`)(?=\n)([`~]{3,})(.*?)\n([\s\S]*?)\n\1(?=\n|$)"  # Corrected pattern
    matches = re.finditer(pattern, s, re.MULTILINE)
    for match in matches:
        ticks = match.group(1)
        language = match.group(2).strip()
        code = match.group(3)

        path_pattern = path_replacement_field.format(r"(.*)")
        if path_location == "below":
            comment_prefix = comment_prefix_for_language(language)
            path_pattern = rf"{comment_prefix} {path_pattern}"
            path_match = re.search(path_pattern, code, re.MULTILINE)
            if path_match:
                path = path_match.group(1).strip()
                code = code[:path_match.start()] + code[path_match.end():]
            else:
                continue
        else:  # path_location == "above"
            start = match.start()
            above_text = s[:start]
            path_match = re.search(rf"{path_pattern}\n$", above_text, re.MULTILINE)
            if path_match:
                path = path_match.group(1).strip()
            else:
                continue

        code_blocks.append(TextFile(text=code, path=path))

    # Handle the case where the code block is at the beginning of the string
    pattern = r"(?<!`)(?<=^)([`~]{3,})(.*?)\n([\s\S]*?)\n\1(?=\n|$)"  # Pattern for start of string
    matches = re.finditer(pattern, s, re.MULTILINE)
    for match in matches:
        ticks = match.group(1)
        language = match.group(2).strip()
        code = match.group(3)

        path_pattern = path_replacement_field.format(r"(.*)")
        if path_location == "below":
            comment_prefix = comment_prefix_for_language(language)
            path_pattern = rf"{comment_prefix} {path_pattern}"
            path_match = re.search(path_pattern, code, re.MULTILINE)
            if path_match:
                path = path_match.group(1).strip()
                code = code[:path_match.start()] + code[path_match.end():]
            else:
                continue
        else:  # path_location == "above"
            # No need to search above for the start of string case

            code_blocks.append(TextFile(text=code, path=""))  # Assuming no path for start of string case

    return code_blocks


def dir2md(
        *files: str, formatter: str | Callable[[TextFile], str] = default_formatter, no_glob: bool = False,
        path_replacement_field: str = "{}", path_location: Literal["above", "below"] = "above"
) -> Generator[str, None, None]:
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
            yield from formatter(TextFile(path=file_path, text=code)).splitlines()


def md2dir(
        text: str, *, parser: Callable[[str], Iterable[TextFile]] = default_parser,
        path_replacement_field: str = "{}", path_location: Literal["above", "below"] = "above"
) -> Iterable[TextFile]:
    return parser(text, path_replacement_field=path_replacement_field, path_location=path_location)


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
            print("The following directories will be created:")
            for directory in new_directories:
                print(f"  {directory!r}")
        if new_files:
            print("The following files will be created:")
            for file in new_files:
                print(f"  {pathlib.Path(output_dir, file)}")
        if existing_files:
            print("The following files will be overwritten:")
            for file in existing_files:
                print(f"  {pathlib.Path(output_dir, file)}")
        print("Continue? (y/n)")
        if input() != "y":
            print("Aborted.")
            return
    for file in files:
        print(f"Writing {pathlib.Path(output_dir, file.path)}")
        path = pathlib.Path(output_dir, file.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(file.text)


def md2dir_save(text: str, output_dir: str, yes: bool = False, path_replacement_field: str = "{}",
                path_location: Literal["above", "below"] = "above") -> None:
    save_dir(files=list(md2dir(text, path_replacement_field=path_replacement_field, path_location=path_location)),
             output_dir=output_dir, yes=yes)


def dir2md_cli() -> None:
    fire.Fire(dir2md)


def md2dir_cli() -> None:
    fire.Fire(md2dir_save)


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
        ("```python\nz\n```\n", [TextFile(text="z\n", path="")]),
    ]

    for text, expected, *args in test_cases:
        if args:
            path_replacement_field, path_location = args
            result = list(md2dir(text, path_replacement_field=path_replacement_field, path_location=path_location))
        else:
            result = list(md2dir(text))
        assert result == expected


def test_dir2md_md2dir():
    with tempfile.TemporaryDirectory() as tmpdirname:
        # Create test files
        with open(os.path.join(tmpdirname, "test.py"), "w") as f:
            f.write("print('hello world')\n")
        with open(os.path.join(tmpdirname, "test.rs"), "w") as f:
            f.write("println!(\"hello world\");\n")

        # Test dir2md
        md_output = "\n".join(dir2md(os.path.join(tmpdirname, "*")))

        # Test md2dir
        with tempfile.TemporaryDirectory() as output_dir:
            md2dir_save(md_output, output_dir, yes=True)

            # Compare files
            with open(os.path.join(output_dir, "test.py"), "r") as f:
                assert f.read() == "print('hello world')\n"
            with open(os.path.join(output_dir, "test.rs"), "r") as f:
                assert f.read() == "println!(\"hello world\");\n"


if __name__ == "__main__":
    dir2md_cli()