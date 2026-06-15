from __future__ import annotations


def frontmatter_metadata(template: str) -> dict[str, str]:
    frontmatter, _body = split_frontmatter(template)
    return parse_frontmatter(frontmatter)


def frontmatter_body(template: str) -> str:
    _frontmatter, body = split_frontmatter(template)
    return body


def split_frontmatter(template: str) -> tuple[str, str]:
    if not template.startswith("---\n"):
        return "", template
    frontmatter, separator, body = template[4:].partition("\n---\n")
    if not separator:
        return "", template
    return frontmatter, body


def parse_frontmatter(frontmatter: str) -> dict[str, str]:
    metadata: dict[str, str] = {}
    lines = frontmatter.splitlines()
    index = 0
    while index < len(lines):
        line = lines[index]
        if not line.strip() or line.startswith((" ", "\t")) or ":" not in line:
            index += 1
            continue
        key, raw_value = line.split(":", 1)
        key = key.strip().lower()
        value = raw_value.strip()
        if not key:
            index += 1
            continue
        if value in {">", "|"}:
            block_lines: list[str] = []
            index += 1
            while index < len(lines):
                candidate = lines[index]
                if candidate and not candidate.startswith((" ", "\t")):
                    break
                block_lines.append(candidate.strip())
                index += 1
            metadata[key] = (
                "\n".join(block_lines).strip()
                if value == "|"
                else " ".join(part for part in block_lines if part).strip()
            )
            continue
        metadata[key] = _strip_frontmatter_value(value)
        index += 1
    return {key: value for key, value in metadata.items() if value}


def _strip_frontmatter_value(value: str) -> str:
    if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
        return value[1:-1]
    return value
