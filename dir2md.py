import glob
import os
import pathlib
import re
from typing import Callable, Generator, List, NamedTuple, Literal

import fire


class TextFile(NamedTuple):
    text: str
    path: str


def infer_language_from_extension(file_path: str) -> str:
    ext_to_lang = {
        '.py': 'python',
        '.rs': 'rust',
        '.js': 'javascript',
        '.java': 'java',
        '.cpp': 'cpp',
        '.c': 'c',
        '.html': 'html',
        '.css': 'css',
        '.md': 'markdown',
    }
    _, ext = os.path.splitext(file_path)
    return ext_to_lang.get(ext, '')


def format_path(path: str, lang: str, formatter: str) -> str:
    if lang == 'python':
        comment_prefix = '# '
    elif lang == 'rust':
        comment_prefix = '// '
    else:
        comment_prefix = '# '  # default

    return formatter.format(path).replace('{}', f'{comment_prefix}{{}}')


def default_formatter(text_file: TextFile) -> str:
    ticks = '```'
    lang = infer_language_from_extension(text_file.path)
    while re.search(rf'^{ticks}', text_file.text, flags=re.MULTILINE):
        ticks += "`"
    return f"{format_path(text_file.path, lang, '{}')}\n{ticks}{lang}\n{text_file.text}\n{ticks}\n\n"


def parse_code_blocks(text: str, formatter: str, path_above: bool) -> List[TextFile]:
    code_blocks = []
    pattern = re.compile(
        r'(?P<path>.*?)\n(?P<ticks>[`~]{3,})(?P<lang>\w*)\n(?P<code>.*?)\n(?P=ticks)\n',
        flags=re.DOTALL,
    )
    matches = pattern.finditer(text)

    for match in matches:
        path = match.group('path').strip()
        code = match.group('code')
        lang = match.group('lang')

        # Adjust path placement based on user configuration
        if not path_above:
            code = re.sub(rf'^{format_path(path, lang, formatter)}$', '', code, flags=re.MULTILINE)

        code_blocks.append(TextFile(text=code, path=path))

    return code_blocks


def dir2md(
    *files: str,
    formatter: str = '{}',
    path_above: bool = True,
    no_glob: bool = False,
    on_missing: Literal['error', 'ignore'] = 'error',
) -> Generator[str, None, None]:
    for file_pattern in files:
        file_paths = glob.glob(file_pattern) if not no_glob else [file_pattern]

        for file_path in file_paths:
            if not os.path.isfile(file_path):
                if on_missing == 'error':
                    raise FileNotFoundError(f"File {file_path} not found")
                continue

            with open(file_path, 'r') as code_file:
                code_blocks = parse_code_blocks(code_file.read(), formatter, path_above)
                for block in code_blocks:
                    yield from default_formatter(block).splitlines()


def md2dir(
    text: str,
    parser: Callable[[str], List[TextFile]] = parse_code_blocks,
    formatter: str = '{}',
    path_above: bool = True,
) -> List[TextFile]:
    return parser(text, formatter, path_above)


def save_dir(files: List[TextFile], output_dir: str, yes: bool = False) -> None:
    if files and not yes:
        filenames = [file.path for file in files]
        new_directories = set(os.path.dirname(file) for file in filenames if file)
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
        path = pathlib.Path(output_dir, file.path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, 'w') as f:
            f.write(file.text)


def md2dir_save(text: str, output_dir: str, yes: bool = False, formatter: str = '{}', path_above: bool = True) -> None:
    save_dir(md2dir(text, formatter=formatter, path_above=path_above), output_dir=output_dir, yes=yes)


def dir2md_cli() -> None:
    fire.Fire(dir2md)


def md2dir_cli() -> None:
    fire.Fire(md2dir_save)


if __name__ == "__main__":
    dir2md_cli()