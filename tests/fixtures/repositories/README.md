# Physical source discovery fixtures

Small hand-authored Java/Maven, TypeScript/Node, mixed and unsupported projects. Their source
text is treated as data, never parsed or executed. Empty directories, ignored files, symlinks,
safe ZIPs, ZIP Slip/bomb cases and local Git repositories are constructed under pytest tmp_path
so no machine-specific paths, binary archives or workspaces are committed.
