import os


def dir2md(*files: str) -> str:
    # Ignore directories
    files = filter(os.path.isfile, files)
    # Iterate over the list of files
    for file in files:
        # Yield the relative path to the file as a comment
        yield f"<!-- {file} -->"
        # Yield the code block
        with open(file, "r") as code_file:
            yield "```"
            yield from code_file
            yield "```"


def main():
    import fire

    fire.Fire(dir2md)


if __name__ == "__main__":
    main()
