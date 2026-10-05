import re

def parse_words(raw_text: str):
    # First, strip common header prefixes like:
    # "2 אותיות:", "מילים בנות 3 אותיות:", "4 אותיות - ", etc.
    cleaned_lines = []
    for line in raw_text.splitlines():
        # Remove patterns like "2 אותיות:", "3 אותיות", "אותיות:" at the start of line
        line = re.sub(r'^\s*\d*\s*(?:מילים\s+בנות\s+)?(?:\d+\s+)?(?:אותיות|אות|אותיות:)\s*[:-]?\s*', '', line, flags=re.IGNORECASE)
        # Also remove any standalone "(X אותיות)" or similar
        line = re.sub(r'\(\s*\d+\s*אותיות\s*\)', '', line)
        cleaned_lines.append(line)
        
    full_text = "\n".join(cleaned_lines)
    # Split on commas, newlines, semicolons, tabs, spaces
    tokens = re.split(r'[\n\r,;\t ]+', full_text)
    words = []
    for t in tokens:
        cleaned = re.sub(r'[^א-ת]', '', t)
        # Exclude common leftover header words if they ever appear alone
        if cleaned in ('אותיות', 'אות', 'מילים', 'מילה', 'ערכים'):
            continue
        if len(cleaned) >= 2:
            words.append(cleaned)
    return words

sample_text = """
2 אותיות: בי, דף, הל, ט"ו, לס, נר, קח.
3 אותיות: בזר, גוף, הבל, ודל, זרע, יוה, יער, לוב, מזה, מרן, נסק, קרן, רבה, רהב, רצד, שצף.
4 אותיות: טופח, מרבה, מרבי, סעוד, רועש.
5 אותיות: בהמות, בצבוץ, גברתן, האנוי, הכרמל, הכתבה, הרעיד, כרכוך, מכינה, נמנמה, ספלון, קממבר.
6 אותיות: האוזנר, נודיזם.
"""

words = parse_words(sample_text)
print(f"Total words parsed: {len(words)}")
print(words)
