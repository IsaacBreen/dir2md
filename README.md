# dir2md

`dir2md` is a command line utility for creating a markdown file that includes code blocks for all specified files.

## Installation

Install dir2md using pip:

```bash
pip install dir2md
```

## Usage

To use `dir2md`, pass a list of file paths as arguments:

```bash
dir2md file1.py file2.py
```

This will output a markdown file with code blocks for `file1.py` and `file2.py`.

### Wildcard support

You can use wildcards (`*`) to pass multiple files at once.

For example, to include all Python files in the current directory:

```bash
dir2md *.py
```

To do so recursively, use `**`:

```bash
dir2md **/*.py
```

Note that the wildcard statement only works if it is expanded by the shell before the command is run. This means that you must use it in the command line or in a shell script, and it will not work if you pass it as a string to a function that runs the command.


## Options

Use the `--help` flag to view the available options:

```bash
dir2md --help
```
