import re

def clean_markdown(text: str) -> str:
    """
    Cleans markdown by removing code blocks, inline code, images, and HTML.
    Preserves headings, bullet points, and plain text paragraphs.
    """
    if not text:
        return ""
        
    # Remove triple-backtick code blocks (including mermaid)
    text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)

    # Remove inline backticks
    text = re.sub(r"`.*?`", "", text)

    # Remove images
    text = re.sub(r"!\[.*?\]\(.*?\)", "", text)

    # Remove HTML tags
    text = re.sub(r"<.*?>", "", text)

    # Remove excessive whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)

    return text.strip()
