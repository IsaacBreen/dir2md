from __future__ import annotations

import os
import pathlib
import re
from typing import Callable, Iterable
from typing import Generator
from typing import List
from typing import NamedTuple

import fire
from funcparserlib.lexer import Token
from funcparserlib.parser import some, finished, maybe, many


class TextFile(NamedTuple):
    text: str
    path: str
    partial: bool


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
    r += text_file.text + "\n"
    r += ticks + "\n\n"
    return r


def custom_tokenize(s: str) -> List[Token]:
    tokens = []
    in_code_block = False
    open_ticks = None
    while s:
        if not in_code_block:
            open_code_match = re.search(
                r"^[^\n\S]*(\S+)[^\n\S]*\n[^\n\S]*(```+)[^\n\S]*(\w*)[^\n\S]*$",
                s,
                flags=re.MULTILINE,
            )
            if open_code_match:
                text = s[: open_code_match.start()]
                path = open_code_match.group(1)
                open_ticks = open_code_match.group(2)
                # format_specifier = open_code_match.group(3)  # Unused

                def append_if_not_empty(type: str, s: str) -> None:
                    if s:
                        tokens.append(Token(type, s))

                append_if_not_empty("text", text)
                append_if_not_empty("path", path)
                append_if_not_empty("OPEN_CODE_BLOCK", open_ticks)
                # append_if_not_empty("format_specifier", format_specifier)

                s = s[open_code_match.end() + 1:]
                in_code_block = True
            else:
                tokens.append(Token("text", s))
                s = ""
        else:
            close_code_match = re.search(
                rf"^[^\n\S]*({open_ticks})[^\n\S]*$", s, flags=re.MULTILINE
            )
            if close_code_match and close_code_match.group(1) == open_ticks:
                text = s[: close_code_match.start() - 1]
                close_ticks = close_code_match.group(1)
                tokens.append(Token("text", text))
                tokens.append(Token("CLOSE_CODE_BLOCK", close_ticks))
                s = s[close_code_match.end():]
                in_code_block = False
            else:
                tokens.append(Token("text", s))
                s = ""

    return tokens


path_token = some(lambda t: t.type == "path").named("path")
open_code_token = some(lambda t: t.type == "OPEN_CODE_BLOCK").named("OPEN_CODE_BLOCK")
text_token = some(lambda t: t.type == "text").named("text")
close_code_token = some(lambda t: t.type == "CLOSE_CODE_BLOCK").named(
    "CLOSE_CODE_BLOCK"
)


def to_text_file(tokens: tuple[Token, Token, Token, Token]) -> TextFile:
    path, open_code, text, close_code = tokens

    # Trim extraneous ":" from end of path
    if path.value.endswith(":"):
        path.value = path.value[:-1]
    
    return TextFile(text=text.value, path=path.value, partial=False)


def default_parser(s: str) -> list[TextFile]:
    parser = -maybe(text_token) + many((
                                               path_token + open_code_token + text_token + close_code_token >> to_text_file
                                       ) + -maybe(text_token)) + -maybe(finished)

    tokens = custom_tokenize(s)
    return parser.parse(tokens)


def dir2md(
        *files: str, formatter: str | Callable[[TextFile], str] = default_formatter
) -> Generator[str, None, None]:
    # Ignore directories
    files = filter(os.path.isfile, files)
    # Iterate over the list of files
    for file in files:
        with open(file, "r") as code_file:
            code = code_file.read()
        yield from formatter(TextFile(text=code, path=file, partial=False)).splitlines()


def md2dir(
        text: str, *, parser: Callable[[str], Iterable[TextFile]] = default_parser
) -> Iterable[TextFile]:
    return parser(text)


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


def md2dir_save(text: str, output_dir: str, yes: bool = False) -> None:
    save_dir(files=list(md2dir(text)), output_dir=output_dir, yes=yes)


def dir2md_cli() -> None:
    fire.Fire(dir2md)


def md2dir_cli() -> None:
    fire.Fire(md2dir_save)


def test_md2dir():
    result = list(md2dir("x\n```\nz\n```\n"))
    expected = [TextFile(text="z", path="x", partial=False)]
    assert result == expected

    result = list(md2dir("x\n```y\nz\n```\n"))
    expected = [TextFile(text="z", path="x", partial=False)]
    assert result == expected

    result = list(md2dir("path/to/file.md\n```python\nprint('hello world')\n```\n"))
    expected = [
        TextFile(text="print('hello world')", path="path/to/file.md", partial=False)
    ]
    assert result == expected
