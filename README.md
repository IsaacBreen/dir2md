# dir2md

`dir2md` is a command-line tool that converts directories of files into Markdown code blocks. It also provides a reverse function, md2dir, which converts Markdown code blocks back into their original files.

## Installation

Install `dir2md` using `pip`:

```bash
pip install dir2md
```

## Usage

`dir2md` can be used as a command-line tool or imported as a module.

### Command-Line Tool

To convert a directory of files to Markdown code blocks, run:

```bash
dir2md [files...]
```

This will print the resulting Markdown to the console.

To convert Markdown code blocks back into their original files, run:

```bash
md2dir [options] 
```

This will create the files in the current working directory.

For more options and usage details, use the `--help` flag.

### Module

```bash
import dir2md

# Convert a directory of files to Markdown code blocks
markdown = dir2md.dir2md("file1.py", "file2.py")

# Convert Markdown code blocks back into their original files
dir2md.md2dir_save(markdown, output_dir="output/")
```

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

`dir2md` uses `glob` to parse your path pattern. To turn this off, use the `--no-glob` flag.

#### Truncation

`dir2md` now supports truncating long files with the `{start_line,end_line}` syntax added to the file or directory path.

For example:

- Get the first 10 lines of a file: `dir2md "path/to/file.py[:10]"`
- Get lines 10 to 20: `dir2md "path/to/file.py[10:20]"`
- Get everything from line 10 until the end of the file: `dir2md "path/to/file.py[10:]"`
- Get the first 10 lines of a file followed by an ellpsis: `dir2md "path/to/file.py[:10...]"`
- Negative indices: `dir2md "path/to/file.py[-10:]"`
- Multiple truncations: `dir2md "path/to/file.py[:10 20:]"`
- Omit the entire contents of the file with an ellipsis: `dir2md "path/to/file.py[..]"`

This syntax can be used with wildcards as well.

The quotation marks are required to prevent your shell from interpreting the brackets as special characters.

```bash
dir2md *.py[:10]   # First 10 lines of all .py files
dir2md **/*.py[5:]  # All lines after the first 5 lines in all .py files recursively
```

### Handling missing files

You can customize the behavior when a specified file is not found using the `on_missing` option. By default, it is set to `"error"` which will raise a `FileNotFoundError`. To ignore the missing file and continue processing other files, pass `on_missing="ignore"` as an argument to the `dir2md` function.

```python
dir2md("missing_file.py", on_missing="ignore")
```
