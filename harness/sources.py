"""Snapshot small reference documents, leaving large libraries in place."""
import json
from pathlib import Path
import subprocess
import zipfile
from xml.etree import ElementTree

from .contracts import digest, ContractError


def extract(path):
    p = Path(path)
    if p.stat().st_size > 30 * 1024 * 1024:
        raise ContractError(f'Document exceeds 30 MB: {p}')
    if p.suffix.lower() == '.pdf':
        r = subprocess.run(['pdftotext', str(p), '-'], capture_output=True, timeout=60)
        if r.returncode:
            raise ContractError(f'PDF extraction failed: {p}')
        value = r.stdout.decode('utf-8', 'replace')
    elif p.suffix.lower() == '.docx':
        with zipfile.ZipFile(p) as z:
            if z.getinfo('word/document.xml').file_size > 5 * 1024 * 1024:
                raise ContractError('DOCX text exceeds extraction limit')
            root = ElementTree.fromstring(z.read('word/document.xml'))
            value = '\n'.join(t.text or '' for t in root.iter() if t.tag.endswith('}t'))
    else:
        value = p.read_text(encoding='utf-8')
    if not value.strip():
        raise ContractError(f'No extractable text: {p}; supply text or an OCR copy')
    if len(value) > 300000:
        raise ContractError(f'Document text exceeds 300,000 characters: {p}; supply relevant excerpts')
    return value


def snapshot(config, dest):
    dest = Path(dest); dest.mkdir(parents=True, exist_ok=True)
    records = []
    for kind, values in [('brand', config['brand']['documents']), ('scripts', config['sources']['scripts']),
                         ('inspiration', config['sources']['inspiration'])]:
        for value in values:
            if value.startswith(('http://', 'https://')):
                records.append({'kind': kind, 'url': value, 'instruction': 'Research worker must fetch and cite; report inaccessible sources'})
                continue
            p = Path(value)
            if not p.is_file():
                raise ContractError(f'Missing configured source: {p}')
            target = dest / f'{len(records):03d}-{kind}.txt'
            target.write_text(extract(p))
            records.append({'kind': kind, 'source': str(p), 'source_sha256': digest(p),
                            'text': str(target), 'sha256': digest(target)})
    for value in config['sources']['assets']:
        if not Path(value).is_dir():
            raise ContractError(f'Missing asset library: {value}')
    (dest/'index.json').write_text(json.dumps(records, indent=2))
    return records
