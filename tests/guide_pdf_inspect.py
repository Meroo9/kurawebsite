"""Inspect the browser-generated PDF for nonblank pages and in-page text bounds."""
import json
from pathlib import Path

import pymupdf as fitz
from PIL import Image

OUT = Path('/app/test_reports/guide')
pdf = fitz.open(OUT / 'guide-filtered-all-chapters.pdf')
metrics = {'pages': len(pdf), 'text_lengths': [], 'clipped_text': [], 'chapter_numbers': []}
all_text = ''
for index, page in enumerate(pdf):
    text = page.get_text()
    all_text += text
    metrics['text_lengths'].append(len(text.strip()))
    for block in page.get_text('dict')['blocks']:
        for line in block.get('lines', []):
            for span in line['spans']:
                x0, y0, x1, y1 = span['bbox']
                if x0 < -1 or y0 < -1 or x1 > page.rect.width + 1 or y1 > page.rect.height + 1:
                    metrics['clipped_text'].append({'page': index + 1, 'text': span['text'], 'bbox': span['bbox']})
for index in [0, len(pdf)-1]:
    pixmap = pdf[index].get_pixmap(matrix=fitz.Matrix(1, 1))
    image = Image.frombytes('RGB', (pixmap.width, pixmap.height), pixmap.samples)
    image.save(OUT / f'pdf-page-{index+1}.jpg', quality=40)
lines = [line.strip() for line in all_text.splitlines()]
for index in range(1, 13):
    number = f'{index:02}'
    metrics['chapter_numbers'].append({'number': number, 'present': number in lines})
metrics['file_size_bytes'] = (OUT / 'guide-filtered-all-chapters.pdf').stat().st_size
(OUT / 'pdf-metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
(OUT / 'pdf-extracted-text.txt').write_text(all_text)
print(json.dumps(metrics, ensure_ascii=False, indent=2))
assert len(pdf) > 1
assert all(length > 50 for length in metrics['text_lengths'])
assert not metrics['clipped_text']
assert all(chapter['present'] for chapter in metrics['chapter_numbers'])