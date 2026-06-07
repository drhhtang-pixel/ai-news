import os
from datetime import datetime


def append_summary(text: str, output_file: str) -> None:
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
    header = f"## {timestamp}"

    file_exists = os.path.exists(output_file)

    with open(output_file, "a", encoding="utf-8") as f:
        if file_exists:
            f.write("\n")
        f.write(f"{header}\n\n{text}\n")

    print(f"Summary written to {output_file}")
