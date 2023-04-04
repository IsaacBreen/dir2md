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
from funcparserlib.lexer import Token
from funcparserlib.parser import some, finished, maybe, many


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

    return TextFile(text=text.value, path=path.value)


def default_parser(s: str) -> list[TextFile]:
    parser = -maybe(text_token) + many((
                                               path_token + open_code_token + text_token + close_code_token >> to_text_file
                                       ) + -maybe(text_token)) + -maybe(finished)

    tokens = custom_tokenize(s)
    return parser.parse(tokens)


class Position(NamedTuple):
    value: int
    unit: Literal["line", "char"]


def extract_truncation_limits(file_path_with_truncation: str) -> tuple[str, list[str | tuple[int, int, str, str]]]:
    trunc_regex_element_1_unnamed = r"((?:line|char)=)?-?\d*"
    trunc_regex_element_2_unnamed = trunc_regex_element_1_unnamed + "\s*:\s*" + trunc_regex_element_1_unnamed
    trunc_regex = rf"\[(\s*{trunc_regex_element_2_unnamed})*\s*\]$"

    trunc_regex_element_1_named = r"((?P<{unit}>line|char)=)?(?P<{pos}>-?\d*)"
    trunc_regex_element_2_named = (
            trunc_regex_element_1_named.format(unit="start_unit", pos="start_trunc") + "\s*:\s*" +
            trunc_regex_element_1_named.format(unit="end_unit", pos="end_trunc"))

    match = re.search(r"\[.*\]", file_path_with_truncation)

    if match:
        assert match.end() == len(file_path_with_truncation)
        file_path = file_path_with_truncation[:match.start()]
        truncs = []

        trunc_str = file_path_with_truncation[match.start() + 1:-1]
        part_matches = re.finditer(rf"({trunc_regex_element_2_named})", trunc_str)

        last_end = 0

        for part_match in part_matches:
            before = trunc_str[last_end:part_match.start()].strip()

            if before:
                truncs.append(before)

            start_trunc, end_trunc = 0, -1
            start_unit, end_unit = "line", "line"

            if part_match.group("start_trunc"):
                start_trunc = int(part_match.group("start_trunc"))
            if part_match.group("end_trunc"):
                end_trunc = int(part_match.group("end_trunc"))
            if part_match.group("start_unit"):
                start_unit = part_match.group("start_unit")
            if part_match.group("end_unit"):
                end_unit = part_match.group("end_unit")

            truncs.append((start_trunc, end_trunc, start_unit, end_unit))
            last_end = part_match.end()

        after = trunc_str[last_end:].strip()

        if after:
            truncs.append(after)

        for i, trunc in enumerate(truncs):
            if isinstance(trunc, str):
                if trunc.startswith('"') and trunc.endswith('"'):
                    truncs[i] = trunc[1:-1]
                elif trunc.startswith("\"") and trunc.endswith("\""):
                    truncs[i] = f'"{trunc[1:-1]}"'

        return file_path, truncs

    else:
        return file_path_with_truncation, [(0, -1, "char", "char")]


def dir2md(
        *files: str, formatter: str | Callable[[TextFile], str] = default_formatter, no_glob: bool = False,
        on_missing: str = Literal["error", "ignore"]
) -> Generator[str, None, None]:
    for file_or_pattern_with_truncation in files:
        file_or_pattern, truncs = extract_truncation_limits(
            file_or_pattern_with_truncation)
        if not no_glob:
            file_paths = glob.glob(file_or_pattern)
        else:
            file_paths = [file_or_pattern]
        for file_path in file_paths:
            if not os.path.isfile(file_path):
                if on_missing == "error":
                    raise FileNotFoundError(f"File {file_path} not found")
                else:
                    continue
            with open(file_path, "r") as code_file:
                extracted = ""
                code = code_file.read()
                for trunc in truncs:
                    if isinstance(trunc, str):
                        extracted += trunc
                    else:
                        start_trunc, end_trunc, start_unit, end_unit = trunc
                        if start_unit == "line":
                            # Get the character index of the start of the line
                            start_trunc = sum(len(line) + 1 for line in code.splitlines()[:start_trunc])
                            start_unit = "char"
                        if end_unit == "line":
                            # Get the character index of the start of the line
                            end_trunc = sum(len(line) + 1 for line in code.splitlines()[:end_trunc])
                            end_unit = "char"
                        extracted += code[start_trunc:end_trunc]
                code = extracted
                if not code.endswith("\n"):
                    code += "\n"
            yield from formatter(TextFile(path=file_path, text=code)).splitlines()


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
    expected = [TextFile(text="z", path="x")]
    assert result == expected

    result = list(md2dir("x\n```y\nz\n```\n"))
    expected = [TextFile(text="z", path="x")]
    assert result == expected

    result = list(md2dir("path/to/file.md\n```python\nprint('hello world')\n```\n"))
    expected = [
        TextFile(text="print('hello world')", path="path/to/file.md")
    ]
    assert result == expected


if __name__ == "__main__":
    dir2md_cli()
