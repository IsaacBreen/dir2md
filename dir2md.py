from __future__ import annotations

import os
import pathlib
import re
from typing import Callable
from typing import Generator, List
from typing import NamedTuple

import fire
from funcparserlib.lexer import make_tokenizer, TokenSpec, Token
from funcparserlib.parser import many
from funcparserlib.parser import some, skip, finished


class TextFile(NamedTuple):
    text: str
    path: str
    partial: bool


def default_formatter(text_file: TextFile) -> str:
    r = ""
    # Yield the relative path to the file as a comment
    r += f"{text_file.path}"
    # Yield the code block
    # Decide how many ticks to use
    ticks = "```"
    while re.search(rf"\n\s*{ticks}", text_file.text):
        ticks += "`"
    r += ticks
    r += text_file.text
    r += ticks
    return r

import re
from typing import List
from dataclasses import dataclass

from funcparserlib.parser import some, Parser, finished, maybe

@dataclass
class TextFile:
    path: str
    text: str
    
def custom_tokenize(s: str) -> List[Token]:
    tokens = []
    in_code_block = False
    open_ticks = None
    while s:
        if not in_code_block:
            open_code_match = re.search(r"(\n^\s*(.+)\s*\n\s*(```+)\s*(\w*)\s*(\n|$)", s, flags=re.MULTILINE)
            if open_code_match:
                text = s[:open_code_match.start()]
                path = open_code_match.group(1).strip()
                open_ticks = open_code_match.group(2).strip()
                print(text)
                format_specifier = open_code_match.group(3).strip()
                tokens.append(Token("text", text))
                tokens.append(Token("path", path))
                tokens.append(Token("OPEN_CODE_BLOCK", open_ticks))
                s = s[open_code_match.end():]
                in_code_block = True
            else:
                tokens.append(Token("text", s))
                s = ""
        else:
            close_code_match = re.search(rf"\n\s*({open_ticks})\s*\n", s, flags=re.MULTILINE)
            if close_code_match and close_code_match.group(1) == open_ticks:
                text = s[:close_code_match.start()]
                close_ticks = close_code_match.group(1).strip()
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
close_code_token = some(lambda t: t.type == "CLOSE_CODE_BLOCK").named("CLOSE_CODE_BLOCK")

def to_text_file(path: str, open_code: str, text: List[str], close_code: str) -> TextFile:
    # Combine text into a single string and remove code fence ticks
    text = ''.join(text)[len(open_code):-len(close_code)]
    return TextFile(path, text)

default_parser = (
    path_token
    + open_code_token
    + many(text_token | close_code_token)
    + close_code_token
    >> to_text_file
) + -finished

def parse(s: str) -> TextFile:
    tokens = custom_tokenize(s)
    return default_parser.parse(tokens)


def dir2md(*files: str, formatter: str | Callable[[TextFile], str] = default_formatter) -> Generator[str, None, None]:
    # Ignore directories
    files = filter(os.path.isfile, files)
    # Iterate over the list of files
    for file in files:
        with open(file, "r") as code_file:
            code = code_file.read()
        yield from formatter(TextFile(text=code, path=file, partial=False)).splitlines()


def md2dir(text: str, *, parser: Callable[[str], Generator[TextFile, None, None]] = default_parser) -> Generator[
    TextFile, None, None]:
    yield from parser(text)


def save_dir(files: list[TextFile], output_dir: str, yes: bool = False) -> None:
    if files and not yes:
        filenames = [file.path for file in files]
        new_directories = []
        for filename in filenames:
            directory = os.path.dirname(filename)
            if directory and not os.path.exists(directory) and directory not in new_directories:
                new_directories.append(directory)
        new_files = [file for file in filenames if not pathlib.Path(output_dir, file).exists()]
        existing_files = [file for file in filenames if pathlib.Path(output_dir, file).exists()]
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
