"""Read-only download/CSV audit. Does not extract packets, join labels or train ML."""
import argparse
from collections import Counter
import csv
import hashlib
import io
import json
from pathlib import Path
import re
import zipfile


def digest_file(path):
    sha256, md5 = hashlib.sha256(), hashlib.md5(usedforsecurity=False)
    with path.open('rb') as source:
        header = source.read(24)
        sha256.update(header)
        md5.update(header)
        while chunk := source.read(1024 * 1024):
            sha256.update(chunk)
            md5.update(chunk)
    return {'bytes':path.stat().st_size, 'sha256':sha256.hexdigest(), 'md5':md5.hexdigest()}, header


def audit_csv_zip(path, manifest=None):
    result, _ = digest_file(path)
    if manifest:
        # MD5 is a transfer-corruption check, not proof of authenticity.
        if manifest.stat().st_size > 4096:
            raise ValueError('Checksum manifest exceeds limit')
        match = re.fullmatch(r'([a-fA-F0-9]{32})\s+\*?([^\r\n]+)\s*', manifest.read_text().strip())
        if not match:
            raise ValueError('Expected one MD5 entry')
        result['manifest_filename'] = match[2]
        result['manifest_md5_matches'] = result['md5'] == match[1].lower()
        if not result['manifest_md5_matches']:
            raise ValueError('CSV archive checksum differs from supplied manifest')
    entries = []
    with zipfile.ZipFile(path) as archive:
        members = [info for info in archive.infolist() if info.filename.lower().endswith('.csv')]
        if not 1 <= len(members) <= 32 or sum(info.file_size for info in members) > 4 * 1024**3:
            raise ValueError('Unexpected CSV archive size or member count')
        for info in members:
            with archive.open(info) as raw:
                rows = csv.reader(io.TextIOWrapper(raw, encoding='utf-8-sig', errors='strict'))
                columns = [value.strip().lower() for value in next(rows)]
                if columns.count('label') != 1:
                    raise ValueError('Expected exactly one Label column')
                label_index = columns.index('label')
                labels, count = Counter(), 0
                for row in rows:
                    if len(row) != len(columns):
                        raise ValueError('CSV row width differs from header')
                    label = row[label_index].strip()
                    if not label or len(label) > 128 or len(labels) >= 64 and label not in labels:
                        raise ValueError('Unexpected label vocabulary')
                    labels[label] += 1
                    count += 1
            entries.append({'member':info.filename, 'bytes':info.file_size,
                            'rows':count, 'labels':dict(labels), 'columns':len(columns),
                            'duplicate_columns':[name for name, number in Counter(columns).items() if number > 1],
                            'has_timestamp':'timestamp' in columns,
                            'has_flow_id':'flow id' in columns,
                            'has_source_ip':'source ip' in columns,
                            'has_destination_ip':'destination ip' in columns})
    result['members'] = entries
    result['total_rows'] = sum(entry['rows'] for entry in entries)
    result['missing_request_join_metadata'] = any(not entry['has_timestamp'] or not entry['has_source_ip']
                                                or not entry['has_destination_ip'] for entry in entries)
    return result


def audit_capture(path):
    result, header = digest_file(path)
    formats = {b'\x0a\x0d\x0d\x0a':'pcapng', b'\xd4\xc3\xb2\xa1':'pcap-microseconds-le',
               b'\xa1\xb2\xc3\xd4':'pcap-microseconds-be', b'\x4d\x3c\xb2\xa1':'pcap-nanoseconds-le',
               b'\xa1\xb2\x3c\x4d':'pcap-nanoseconds-be'}
    if len(header) < 24 or header[:4] not in formats:
        raise ValueError('Unsupported or incomplete capture header')
    result['header_format'] = formats[header[:4]]
    result['packets_parsed'] = False
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--capture', type=Path, required=True)
    parser.add_argument('--csv-zip', type=Path, required=True)
    parser.add_argument('--csv-md5', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    if args.report.exists():
        parser.error('Refusing to overwrite an existing report')
    result = {'release_evidence':False, 'model_trained':False,
              'scope':'Transfer hashes and CSV schema/counts only. No packet reassembly, request labels, FPR or recall claim.',
              'csv_zip':audit_csv_zip(args.csv_zip, args.csv_md5)}
    print('CSV archive checked; streaming capture hashes without copying the capture.', flush=True)
    result['capture'] = audit_capture(args.capture)
    with args.report.open('x', encoding='utf-8') as output:
        json.dump(result, output, indent=2, ensure_ascii=False)
        output.write('\n')
    print(json.dumps({'report':str(args.report), 'csv_rows':result['csv_zip']['total_rows'],
                      'capture_bytes':result['capture']['bytes'], 'model_trained':False}), flush=True)


if __name__ == '__main__':
    main()
