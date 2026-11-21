"""Validate the computer instance with benign text and harmless EICAR test bytes.

Run from the Shield directory. Never downloads, stores or executes malware.
This proves engine wiring, not real-malware recall or false-positive rate.
"""
import argparse
import json
from pathlib import Path

from computer import compose

CODE = r'''
import hashlib
import io
import json
import time
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import urlopen
from app.malware import scan

def ready():
    with urlopen('http://127.0.0.1:8000/ready', timeout=5) as response:
        value = json.load(response)
    assert value == {'ok': True}, value
    return value

before = ready()
test = (b'X5O!P%@AP[4' + bytes([92]) + b'PZX54(P^)7CC)7}' + bytes([36])
        + b'EICAR-STANDARD-ANTIVIRUS-TEST-FILE!' + bytes([36]) + b'H+H*')
def archive(content):
    buffer = io.BytesIO()
    entry = zipfile.ZipInfo('sample.txt', date_time=(2026, 1, 1, 0, 0, 0))
    entry.compress_type = zipfile.ZIP_DEFLATED
    with zipfile.ZipFile(buffer, 'w') as writer:
        writer.writestr(entry, content)
    return buffer.getvalue()

fixtures = [('benign_text', b'Hello from Detexis Shield. This is benign text.', 'no_signature_detected'),
            ('harmless_eicar_test', test, 'signature_detected'),
            ('benign_zip', archive(b'Harmless archive text.'), 'no_signature_detected'),
            ('harmless_eicar_zip', archive(test), 'signature_detected'),
            ('archive_member_over_transport_limit', archive(b'x' * (1024*1024+1)), 'no_signature_detected'),
            ('archive_exceeds_unpacked_scan_limit', archive(b'x' * (8*1024*1024+1)), 'needs_review')]
results = []
for name, content, expected in fixtures:
    started = time.perf_counter()
    value = scan(content)
    assert value['verdict'] == expected, value
    results.append({'sample': name, 'sha256': hashlib.sha256(content).hexdigest(),
                    'bytes': len(content), 'elapsed_ms': (time.perf_counter()-started)*1000, **value})
print(json.dumps({'checked_at': datetime.now(timezone.utc).isoformat(), 'passed': True,
                  'ready_before': before, 'ready_after': ready(), 'results': results,
                  'source_sha256': {name: hashlib.sha256(Path('app', name).read_bytes().replace(b'\r\n', b'\n')).hexdigest()
                                    for name in ['malware.py', 'threat_analysis.py']},
                  'scope': 'Real engine wiring with benign text, harmless EICAR, ZIP wrappers, a 1 MiB+1 member and a bounded 8 MiB+1 unpacked-limit fixture. Not real-malware accuracy, broad file coverage, concurrent load or browser validation.'}))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("threat-analysis-smoke.json"))
    args = parser.parse_args()
    report = json.loads(compose("exec", "-T", "api", "python", "-c", CODE, capture=True))
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "report": str(args.output)}))


if __name__ == "__main__":
    main()
