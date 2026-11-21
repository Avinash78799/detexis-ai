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


def test_legacy_label_encoding_requires_explicit_choice_and_preserves_label(tmp_path):
    path = archive(tmp_path, b'Label\nWeb Attack \x96 XSS\n')
    with pytest.raises(UnicodeDecodeError):
        audit.audit_csv_zip(path)
    result = audit.audit_csv_zip(path, encoding='cp1252')
    assert result['csv_encoding'] == 'cp1252'
    assert result['members'][0]['labels'] == {'Web Attack \u2013 XSS':1}
    with pytest.raises(ValueError, match='explicit CSV encoding'):
        audit.audit_csv_zip(path, encoding='latin-1')


def test_blank_records_need_explicit_exclusion_and_remain_counted(tmp_path):
    path = archive(tmp_path, 'Port,Label\n80,BENIGN\n,\n \n')
    with pytest.raises(ValueError):
        audit.audit_csv_zip(path)
    result = audit.audit_csv_zip(path, exclude_blank_records=True)
    assert result['total_rows'] == 1
    assert result['excluded_blank_records'] == 2
    assert result['members'][0]['excluded_blank_records'] == 2
    assert result['members'][0]['labels'] == {'BENIGN':1}
    with pytest.raises(ValueError, match='label vocabulary'):
        audit.audit_csv_zip(archive(tmp_path, 'Port,Label\n80,\n'), exclude_blank_records=True)


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
