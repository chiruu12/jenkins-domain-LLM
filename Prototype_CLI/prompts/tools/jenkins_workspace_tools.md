### Jenkins Workspace Tools

**Protocol:** Your primary method for interacting with files is a two-step process: discover, then read. You must follow this to avoid errors.

1.  First, call **`list_files_in_workspace()`** to get a reliable map of all available files and their exact paths.
2.  Next, analyze the output and use an exact path from that list to call **`read_file_from_workspace(file_path="...")`** to inspect a specific file's content.

Do not guess file paths; always list before you read.
