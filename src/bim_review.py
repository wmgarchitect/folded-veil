"""Offline review page, generated only from IFC geometry-engine readback."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    records = json.loads((ROOT / 'exports/FV-05-readback.json').read_text())
    report = json.loads((ROOT / 'exports/FV-05-validation.json').read_text())
    template = (ROOT / 'docs/bim-review-template.html').read_text(encoding='utf-8')
    html = template.replace('__RECORDS__', json.dumps(records)).replace('__REPORT__', json.dumps(report))
    target = ROOT / 'exports/FV-05-review.html'
    target.write_text(html, encoding='utf-8')
    print(target)


if __name__ == '__main__':
    main()
