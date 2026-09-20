#!/usr/bin/env python3
from pathlib import Path

MORE_ANCHOR = '<a href="/more/index.html">More</a>'
DROPDOWN = (
    '<div class="nav-more">'
    '<button class="nav-more-trigger" type="button" aria-label="More" aria-haspopup="true">⋯</button>'
    '<div class="nav-more-menu">'
    '<a href="/more/research-notes.html">Research Notes</a>'
    '<a href="/more/resources.html">Tutorials &amp; Resources</a>'
    '<a href="/more/poetry.html">Poetry</a>'
    '</div></div>'
)

STYLE_LINK = '<link rel="stylesheet" href="/nav-more.css" />'

changed = []
for path in Path('.').rglob('*.html'):
    text = path.read_text(encoding='utf-8')
    original = text

    # Remove the retired Essays & Reflections entry from existing dropdowns.
    text = text.replace('<a href="/more/writing.html">Essays &amp; Reflections</a>', '')

    # Keep internal links on the preferred canonical URL form.
    text = text.replace('href="/index.html"', 'href="/"')
    text = text.replace('href="/news/index.html"', 'href="/news/"')

    # Replace the visible More tab with a compact three-dot menu.
    text = text.replace(MORE_ANCHOR, DROPDOWN)

    # Also handle pages that have not yet received any More navigation.
    old_nav = '<a href="/news/">News</a><a href="/assets/Dhrubajyoti_Ghosh_CV.pdf">CV</a>'
    new_nav = f'<a href="/news/">News</a>{DROPDOWN}<a href="/assets/Dhrubajyoti_Ghosh_CV.pdf">CV</a>'
    text = text.replace(old_nav, new_nav)

    # Load the shared dropdown styling once per page.
    if 'class="nav-more"' in text and '/nav-more.css' not in text:
        if '<link rel="stylesheet" href="styles.css" />' in text:
            text = text.replace('<link rel="stylesheet" href="styles.css" />', '<link rel="stylesheet" href="styles.css" />\n  ' + STYLE_LINK, 1)
        elif '<link rel="stylesheet" href="../styles.css" />' in text:
            text = text.replace('<link rel="stylesheet" href="../styles.css" />', '<link rel="stylesheet" href="../styles.css" />\n  ' + STYLE_LINK, 1)
        else:
            text = text.replace('</head>', f'  {STYLE_LINK}\n</head>', 1)

    if text != original:
        path.write_text(text, encoding='utf-8')
        changed.append(str(path))

print(f'Updated navigation in {len(changed)} files')
for path in changed:
    print(' -', path)
