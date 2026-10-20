#!/usr/bin/env python3
"""Prepare already extracted local reference images/fonts for GTK.

Run with system Python (Pillow and fontTools). No downloads or device writes.
Original files and prepared assets remain under ignored artifacts/.
"""
from pathlib import Path
from PIL import Image
from fontTools.ttLib import TTFont
root = Path(__file__).resolve().parents[1]
target = root / 'artifacts/ui-reference'
for name in ('mouse-front', 'mouse-side', 'mouse-haptic-zone', 'keyboard-front'):
    with Image.open(target / f'{name}.webp') as image:
        image.save(target / f'{name}.png')
for source, weight in [('8c6a18fd7d9468524945', 'regular'),
                       ('669ffb72bcc1521bf72c', 'bold'), ('c941ba321f86c9065492', 'light')]:
    font = TTFont(root / f'artifacts/mac-live-2.9/ui/assets/{source}.woff2')
    font.flavor = None
    font.save(target / f'BrownPro-{weight}.ttf')
