import importlib.util
from pathlib import Path
import pytest
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

spec = importlib.util.spec_from_file_location('backup', Path(__file__).resolve().parents[2] / 'scripts' / 'backup.py')
backup = importlib.util.module_from_spec(spec)
spec.loader.exec_module(backup)


def test_streaming_encryption_and_corruption_detection(tmp_path):
    key = AESGCM.generate_key(256)
    src, enc, output = (tmp_path / name for name in ('source', 'encrypted', 'restored'))
    data = b'DATUS test data' * 100000
    src.write_bytes(data)
    backup.encrypt(src, enc, key)
    backup.decrypt(enc, output, key)
    assert output.read_bytes() == data
    broken = tmp_path / 'truncated'
    broken.write_bytes(enc.read_bytes()[:-20])
    with pytest.raises(Exception): backup.decrypt(broken, tmp_path / 'failed', key)
    with pytest.raises(Exception): backup.decrypt(enc, tmp_path / 'wrong-key', AESGCM.generate_key(256))
