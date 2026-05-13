from pathlib import Path

def discover_images(folder, extensions):
    folder = Path(folder)

    files = {}

    if not folder.exists():
        return files

    for path in folder.rglob("*"):
        if path.is_file() and path.suffix.lower() in extensions:
            rel = path.relative_to(folder).as_posix()
            files[rel] = path

    return files