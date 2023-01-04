# Code to Markdown Converter

This script converts code files to Markdown code blocks. It searches for files in a specified directory that match a specified pattern, and converts each matching file to a Markdown code block.

## Usage

To use the script, run the following command:

```bash
python code_to_markdown.py --directory <directory> --pattern <pattern>
```


`directory` is a required argument that specifies the directory to search for files. `pattern` is an optional argument that specifies a pattern to match against the names of files in the specified directory. If `pattern` is not specified, the script will search for all files in the directory.

The script will print the resulting Markdown code blocks to the console.

## Examples

To search for all Python files in the current directory and convert them to Markdown code blocks:

```bash
python code_to_markdown.py --pattern "*.py"
```


To search for all files in a subdirectory called "code" and convert them to Markdown code blocks:

```bash
python code_to_markdown.py --directory code
```

To search for all files in the current directory that have the word "example" in their name and convert them to Markdown code blocks:

```bash
python code_to_markdown.py --pattern "example"
```

## Requirements

- Python 3.6 or higher
- The `glob` and `pathlib` modules, which are part of the Python standard library.
- The `fire` module, which can be installed using `pip install fire`.

## Notes

- The resulting Markdown code blocks will include a comment at the top containing the relative path to the file within the specified directory.
- The script will recursively search the specified directory for matching files.
- The script does not modify the original files in any way. It only generates new Markdown code blocks based on the contents of the original files.
