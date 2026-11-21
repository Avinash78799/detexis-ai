import hashlib
import importlib.util
from pathlib import Path
import zipfile

import pytest


spec = importlib.util.spec_from_file_location('audit_cic_downloads', Path(__file__).parents[1] / 'ml/audit_cic_downloads.py')
audit = importlib.util.module_from_spec(spec)
spec.loader.exec_module(audit)


def archive(tmp_path, content):
    path = tmp_path / 'fixture.zip'
    with zipfile.ZipFile(path, 'w') as output:
        output.writestr('../never-extracted.csv', content)
    return path


def test_csv_audit_counts_labels_but_does_not_invent_request_join_keys(tmp_path):
    path = archive(tmp_path, ' Destination Port, Label\n80,BENIGN\n80,Web Attack\n443,BENIGN\n')
    manifest = tmp_path / 'fixture.md5'
    manifest.write_text(hashlib.md5(path.read_bytes(), usedforsecurity=False).hexdigest() + '  different-download-name.zip\n')
    result = audit.audit_csv_zip(path, manifest)
    assert result['total_rows'] == 3
    assert result['manifest_md5_matches'] is True
    assert result['members'][0]['labels'] == {'BENIGN':2, 'Web Attack':1}
    assert result['missing_request_join_metadata'] is True
    assert not (tmp_path.parent / 'never-extracted.csv').exists()


def test_duplicate_numeric_feature_names_are_reported_without_guessing_their_meaning(tmp_path):
    result = audit.audit_csv_zip(archive(tmp_path, 'Length,Length,Label\n1,2,BENIGN\n'))
    assert result['members'][0]['duplicate_columns'] == ['length']
    assert result['members'][0]['labels'] == {'BENIGN':1}


@pytest.mark.parametrize('content', ['Label,Label\nBENIGN,BENIGN\n', 'Port,Label\n80\n', 'Port,Other\n80,BENIGN\n'])
def test_bad_schema_or_row_is_not_silently_skipped(tmp_path, content):
    with pytest.raises(ValueError):
        audit.audit_csv_zip(archive(tmp_path, content))


def test_checksum_mismatch_refuses_a_report(tmp_path):
    path = archive(tmp_path, 'Label\nBENIGN\n')
    manifest = tmp_path / 'fixture.md5'
    manifest.write_text('0' * 32 + '  fixture.zip')
    with pytest.raises(ValueError, match='checksum differs'):
        audit.audit_csv_zip(path, manifest)


def test_actual_capture_header_takes_precedence_over_extension(tmp_path):
    path = tmp_path / 'fixture.pcap'
    path.write_bytes(bytes.fromhex('0a0d0d0a480000004d3c2b1a01000000ffffffffffffffff'))
    result = audit.audit_capture(path)
    assert result['header_format'] == 'pcapng'
    assert result['packets_parsed'] is False
    assert result['sha256'] == hashlib.sha256(path.read_bytes()).hexdigest()
    path.write_bytes(b'not-a-capture')
    with pytest.raises(ValueError, match='capture header'):
        audit.audit_capture(path)
