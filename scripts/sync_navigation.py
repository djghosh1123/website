#!/usr/bin/env python3
from pathlib import Path

OLD = '<a href="/news/index.html">News</a><a href="/assets/Dhrubajyoti_Ghosh_CV.pdf">CV</a>'
NEW = '<a href="/news/index.html">News</a><a href="/more/index.html">More</a><a href="/assets/Dhrubajyoti_Ghosh_CV.pdf">CV</a>'

changed = []
for path in Path('.').rglob('*.html'):
    text = path.read_text(encoding='utf-8')
    if '/more/index.html">More</a>' in text:
        continue
    if OLD in text:
        path.write_text(text.replace(OLD, NEW), encoding='utf-8')
        changed.append(str(path))

print(f'Updated navigation in {len(changed)} files')
for path in changed:
    print(' -', path)
