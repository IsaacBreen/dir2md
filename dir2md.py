import os
import pathlib
import re
from typing import NamedTuple, Generator

import fire


def dir2md(*files: str) -> Generator[str, None, None]:
    # Ignore directories
    files = filter(os.path.isfile, files)
    # Iterate over the list of files
    for file in files:
        # Yield the relative path to the file as a comment
        yield f"<!-- {file} -->"
        # Yield the code block
        with open(file, "r") as code_file:
            code = code_file.read()
            # Decide how many ticks to use
            ticks = "```"
            while re.search(rf"\n\s*{ticks}", code):
                ticks += "`"
            yield ticks
            yield from code.splitlines()
            yield ticks


class TextFile(NamedTuple):
    text: str
    path: str
    partial: bool


def md2dir(text: str) -> Generator[TextFile, None, None]:
    # Split the text into lines
    lines = text.splitlines()
    # Iterate over the lines
    iter_lines = iter(lines)
    for line in iter_lines:
        # If the line is a comment
        if line.startswith("<!-- ") and line.endswith(" -->"):
            # Extract the path from the comment
            path = line[5:-4]
            # Get the number of ticks in the code fence opening
            ticks = re.match(r"(`+)", next(iter_lines)).group(1)
            # Get lines up until the closing code fence
            code = []
            for line in iter_lines:
                if line.startswith(ticks):
                    break
                code.append(line)
            else:
                # If the code fence was never closed, yield the partial file
                yield TextFile("\n".join(code), path, partial=True)
                return
            # Yield the file
            yield TextFile("\n".join(code), path, partial=False)


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
