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
md2dir [options] <input_file>
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

Note that the wildcard statement only works if it is expanded by the shell before the command is run. This means that you must use it in the command line or in a shell script, and it will not work if you pass it as a string to a function that runs the command.

