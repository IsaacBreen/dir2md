from __future__ import annotations

import glob
import os
import pathlib
import re
from typing import Callable, Generator, Iterable, Literal
from typing import List, NamedTuple

import fire


class TextFile(NamedTuple):
    text: str
    path: str


def default_formatter(text_file: TextFile) -> str:
    ticks = "```"
    while ticks in text_file.text:
        ticks += "`"
    return f"{text_file.path}\n{ticks}\n{text_file.text}\n{ticks}\n\n"


def extract_truncation_limits(file_path_with_truncation: str) -> tuple[str, list[str | tuple[int, int, str, str]]]:
    trunc_regex_element_1_named = r"((?P<{unit}>line|char)=)?(?P<{pos}>-?\d*)"
    trunc_regex_element_2_named = (
            trunc_regex_element_1_named.format(unit="start_unit", pos="start_trunc") + r"\s*:\s*" +
            trunc_regex_element_1_named.format(unit="end_unit", pos="end_trunc"))

    match = re.search(r"\[.*\]", file_path_with_truncation)
    if match:
        file_path = file_path_with_truncation[:match.start()]
        trunc_str = file_path_with_truncation[match.start() + 1:-1]
        truncs = []

        part_matches = re.finditer(rf"({trunc_regex_element_2_named})", trunc_str)

        for part_match in part_matches:
            start_trunc = int(part_match.group("start_trunc") or 0)
            end_trunc = int(part_match.group("end_trunc") or -1)
            start_unit = part_match.group("start_unit") or "line"
            end_unit = part_match.group("end_unit") or "line"
            truncs.append((start_trunc, end_trunc, start_unit, end_unit))

        return file_path, truncs

    else:
        return file_path_with_truncation, [(0, -1, "char", "char")]


def infer_language(path: str) -> str:
    ext_to_lang = {
        ".py": "python",
        ".rs": "rust",
        ".js": "javascript",
        ".ts": "typescript",
        ".cpp": "cpp",
        ".html": "html",
        ".css": "css",
        # Add more extensions and languages as needed
    }
    ext = pathlib.Path(path).suffix
    return ext_to_lang.get(ext, "")


def dir2md(
        *files: str,
        formatter: Callable[[TextFile], str] = default_formatter,
        no_glob: bool = False,
        on_missing: Literal["error", "ignore"] = "error",
        path_placeholder: str = "# {}",
        path_above: bool = True
) -> Generator[str, None, None]:
    for file_or_pattern_with_truncation in files:
        file_or_pattern, truncs = extract_truncation_limits(file_or_pattern_with_truncation)
        if not no_glob:
            file_paths = glob.glob(file_or_pattern)
        else:
            file_paths = [file_or_pattern]

        for file_path in file_paths:
            if not os.path.isfile(file_path):
                if on_missing == "error":
                    raise FileNotFoundError(f"File {file_path} not found")
                continue

            with open(file_path, "r") as code_file:
                code = code_file.read()
                for trunc in truncs:
                    if isinstance(trunc, str):
                        code = trunc
                    else:
                        start_trunc, end_trunc, start_unit, end_unit = trunc
                        if start_unit == "line":
                            start_trunc = sum(len(line) + 1 for line in code.splitlines()[:start_trunc])
                            start_unit = "char"
                        if end_unit == "line":
                            end_trunc = sum(len(line) + 1 for line in code.splitlines()[:end_trunc])
                            end_unit = "char"
                        code = code[start_trunc:end_trunc]

                if not code.endswith("\n"):
                    code += "\n"

                lang = infer_language(file_path)
                ticks_pattern = r"(```+|~~~+)"
                open_code_match = re.search(
                    rf"(?<=\n|^)(\s*{ticks_pattern})\s*({lang})?\s*(\n|$)", code, flags=re.MULTILINE
                )

                if open_code_match:
                    ticks = open_code_match.group(1)
                    closing_pattern = rf"(?<=\n|^)(\s*{ticks}\s*)(\n|$)"
                    close_code_match = re.search(closing_pattern, code[open_code_match.end():], flags=re.MULTILINE)

                    if close_code_match:
                        code_block = code[open_code_match.end():open_code_match.end() + close_code_match.start()].strip()
                        path_str = path_placeholder.format(file_path)

                        if not path_above:
                            path_str = path_str.replace("{}", "")
                            comment_prefix = {
                                "python": "# ",
                                "rust": "// ",
                                "cpp": "// ",
                                "html": "<!-- ",
                                "css": "/* ",
                                "javascript": "// ",
                                "typescript": "// ",
                            }.get(lang, "# ")
                            code_block = f"{comment_prefix}{path_str}\n{code_block}"
                        else:
                            code_block = f"{path_str}\n{ticks}\n{code_block}"

                        code_block += f"\n{ticks}"
                        yield from formatter(TextFile(path=file_path, text=code_block)).splitlines()


def md2dir(
        text: str, *,
        parser: Callable[[str], Iterable[TextFile]] = None
) -> Iterable[TextFile]:
    ticks_pattern = r"(```+|~~~+)"
    code_block_pattern = re.compile(
        rf"(?<=\n|^)(?P<path>[^\n]+)\n(?P<ticks>{ticks_pattern})\s*(?P<lang>\w*)\s*\n(?P<code>.*?)(?P=ticks)(\n|$)",
        flags=re.DOTALL
    )

    files = []
    for match in code_block_pattern.finditer(text):
        path = match.group("path").strip()
        code = match.group("code").strip()
        files.append(TextFile(text=code, path=path))

    return files


def save_dir(files: list[TextFile], output_dir: str, yes: bool = False) -> None:
    if files and not yes:
        new_directories, new_files, existing_files = set(), [], []

        for file in files:
            directory = os.path.dirname(file.path)
            if directory and not os.path.exists(directory):
                new_directories.add(directory)

            if not pathlib.Path(output_dir, file.path).exists():
                new_files.append(file.path)
            else:
                existing_files.append(file.path)

        if new_directories or new_files or existing_files:
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