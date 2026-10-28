"""Decode only benchmark evidence files from a downloaded GitHub job log."""
import base64,io,tarfile,sys
from pathlib import Path
source=Path(sys.argv[1]); dest=Path(sys.argv[2]).resolve(); dest.mkdir(exist_ok=True)
chunks=[]
for line in source.read_text(encoding='utf-8-sig').splitlines():
    if 'BENCH_DATA:' in line:
        candidate=line.split('BENCH_DATA:',1)[1].strip()
        if candidate and all(c in 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/=' for c in candidate):chunks.append(candidate)
if not chunks:raise SystemExit('No evidence payload in logs')
payload=base64.b64decode(''.join(chunks),validate=True)
with tarfile.open(fileobj=io.BytesIO(payload),mode='r:gz') as archive:
    for member in archive.getmembers():
        if member.isdir():continue
        target=(dest/member.name).resolve()
        if not target.is_relative_to(dest) or not member.isfile() or member.size>50*1024*1024:raise RuntimeError('Unsafe archive entry')
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_bytes(archive.extractfile(member).read())
print(f'Decoded {len(payload)} compressed bytes into {dest}')
