"""Fix f-strings that have no placeholders by removing the f prefix."""

import re
import subprocess

# Get files with F541 from flake8
result = subprocess.run(
    ["./venv/bin/flake8", "scripts/", "src/", "app.py", "--select=F541", "--format=%(path)s:%(row)d"],
    capture_output=True,
    text=True,
)

files_lines = {}
for line in result.stdout.strip().split("\n"):
    if ":" in line:
        path, lineno = line.rsplit(":", 1)
        files_lines.setdefault(path, []).append(int(lineno))

print(f"Files to fix: {len(files_lines)}")
total_fixed = 0

for filepath, line_numbers in files_lines.items():
    with open(filepath, "r") as f:
        lines = f.readlines()

    changed = False
    for ln in line_numbers:
        idx = ln - 1
        if idx < len(lines):
            original = lines[idx]
            # Remove f prefix from f-strings that don't contain {
            # Handle f"..." f'...' f"""...""" f'''...'''
            new_line = re.sub(
                r'''\bf("""[^{]*?"""|\'\'\'[^{]*?\'\'\'|"[^{"]*"|'[^{']*')''', lambda m: m.group(0)[1:], original
            )
            if new_line != original:
                lines[idx] = new_line
                changed = True
                total_fixed += 1

    if changed:
        with open(filepath, "w") as f:
            f.writelines(lines)
        print(f"  Fixed: {filepath} ({len([ln for ln in line_numbers])} issues)")

print(f"\nTotal fixed: {total_fixed}")
