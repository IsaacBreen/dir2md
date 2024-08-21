import re
import os
import pathlib
from typing import Callable, Iterable, NamedTuple, Optional
import fire


class TextFile(NamedTuple):
    text: str
    path: str
    language: Optional[str] = None


def default_formatter(text_file: TextFile) -> str:
    ticks = "```"
    while ticks in text_file.text:
        ticks += "`"
    return f"{text_file.path}\n{ticks}{text_file.language or ''}\n{text_file.text}{ticks}\n\n"


def extract_code_blocks(s: str, path_format: str = "{}", path_below: bool = False) -> Iterable[TextFile]:
    code_block_pattern = r'(?:^|\n)(?P<ticks>[`~]{3,})(?P<lang>\w*)\s*\n(?P<content>.*?)\n(?P=ticks)(?=\n|$)'
    for match in re.finditer(code_block_pattern, s, re.DOTALL):
        content = match.group('content')
        lang = match.group('lang') or None

        path_pattern = re.escape(path_format).replace(r'\{\}', r'(.*?)')
        if path_below:
            comment_prefix = '#' if lang == 'python' else '//'
            path_pattern = f"{comment_prefix} {path_pattern}"

        path_search = re.search(path_pattern, content if path_below else s[:match.start()], re.MULTILINE)
        if path_search:
            path = path_search.group(1)
            if path_below:
                content = re.sub(f'^{re.escape(path_search.group(0))}$\n?', '', content, flags=re.MULTILINE)
            yield TextFile(text=content.rstrip(), path=path, language=lang)


def dir2md(
        *files: str,
        formatter: Callable[[TextFile], str] = default_formatter,
) -> Iterable[str]:
    for file_path in files:
        if not os.path.isfile(file_path):
            raise FileNotFoundError(f"File {file_path} not found")

        with open(file_path, "r") as f:
            content = f.read()

        _, ext = os.path.splitext(file_path)
        lang = ext[1:] if ext else None

        yield from formatter(TextFile(text=content, path=file_path, language=lang)).splitlines()


def md2dir(
        text: str,
        parser: Callable[[str], Iterable[TextFile]] = extract_code_blocks
) -> Iterable[TextFile]:
    return parser(text)


def save_dir(files: Iterable[TextFile], output_dir: str, yes: bool = False) -> None:
    files = list(files)
    if files and not yes:
        for file in files:
            path = pathlib.Path(output_dir, file.path)
            print(f"{'Overwriting' if path.exists() else 'Creating'} {path}")
        if input("Continue? (y/n) ") != "y":
            print("Aborted.")
            return

    for file in files:
        path = pathlib.Path(output_dir, file.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w") as f:
            f.write(file.text)


def md2dir_save(text: str, output_dir: str, yes: bool = False) -> None:
    save_dir(md2dir(text), output_dir, yes)


def dir2md_cli() -> None:
    fire.Fire(dir2md)


def md2dir_cli() -> None:
    fire.Fire(md2dir_save)


if __name__ == "__main__":
    dir2md_cli()