import re

_SENTENCE_END = frozenset(".!?")


def clean_text(text: str) -> str:
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)
    lines = [re.sub(r"[ \t]+", " ", line).strip() for line in text.split("\n")]
    lines = [line for line in lines if line]
    if not lines:
        return ""

    paragraphs = [lines[0]]
    for line in lines[1:]:
        previous = paragraphs[-1]
        if previous[-1] in _SENTENCE_END:
            paragraphs.append(line)
        else:
            paragraphs[-1] = f"{previous} {line}"
    return "\n\n".join(paragraphs)
