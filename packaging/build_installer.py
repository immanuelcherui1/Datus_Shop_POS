"""Build the Windows installer from pinned, checksum-verified vendor tools."""
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = {
    'postgresql-17.11-1.zip': ('https://get.enterprisedb.com/postgresql/postgresql-17.11-1-windows-x64-binaries.zip',
        '6eabdf00d2893713b75db4336a23c3fdf505f056e217ec6e2e95d901750cfea3'),
    'nsis-3.12.zip': ('https://downloads.sourceforge.net/project/nsis/NSIS%203/3.12/nsis-3.12.zip',
        '56581f90db321581c5381193d796fffcf2d24b2f8fed2160a6c6a3baa67f2c4f'),
    'tcltk-8.6.13.0.zip': ('https://github.com/python/cpython-bin-deps/archive/refs/tags/tcltk-8.6.13.0.zip',
        '2b81b5604a02d362e9a3ed0b9ca352dcea4887ec822ceef3e560daf8e31044e6'),
}


def digest(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream, 'sha256').hexdigest()


def get_tool(cache, name):
    url, expected = TOOLS[name]
    archive = cache / name
    if not archive.exists():
        partial = archive.with_suffix('.partial')
        try:
            with urllib.request.urlopen(url, timeout=90) as response, partial.open('wb') as output:
                shutil.copyfileobj(response, output)
            if digest(partial) != expected: raise RuntimeError(f'Checksum mismatch for {name}; build stopped.')
            partial.replace(archive)
        finally: partial.unlink(missing_ok=True)
    if digest(archive) != expected: raise RuntimeError(f'Checksum mismatch for cached {name}; build stopped.')
    target = cache / archive.stem
    with zipfile.ZipFile(archive) as files:
        for entry in files.infolist():
            # Exclude pgAdmin and developer SDKs, preserving runtime libraries and vendor docs/notices.
            if name.startswith('postgresql') and not (any(entry.filename.startswith('pgsql/' + folder + '/') for folder in ('bin', 'lib', 'share', 'doc')) or entry.filename in ('pgsql/server_license.txt', 'pgsql/commandlinetools_3rd_party_licenses.txt', 'pgsql/StackBuilder_3rd_party_licenses.txt')):
                continue
            destination = (target / entry.filename).resolve()
            if not destination.is_relative_to(target.resolve()): raise RuntimeError('Unsafe archive path.')
            files.extract(entry, target)
    return target


def run(command, **kwargs):
    subprocess.run(command, cwd=ROOT, check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version', default='0.2.1')
    parser.add_argument('--cache', type=Path, default=ROOT / '.packaging-cache')
    parser.add_argument('--skip-frontend', action='store_true', help='Use an already verified frontend production build')
    args = parser.parse_args()
    if sys.platform != 'win32': raise RuntimeError('Build the Windows installer on Windows x64.')
    if not __import__('re').fullmatch(r'\d+\.\d+\.\d+', args.version): raise ValueError('Version must be major.minor.patch.')
    args.cache.mkdir(parents=True, exist_ok=True)
    pg = get_tool(args.cache, 'postgresql-17.11-1.zip') / 'pgsql'
    nsis = get_tool(args.cache, 'nsis-3.12.zip') / 'nsis-3.12' / 'makensis.exe'
    tcltk = get_tool(args.cache, 'tcltk-8.6.13.0.zip') / 'cpython-bin-deps-tcltk-8.6.13.0' / 'amd64'
    if not args.skip_frontend:
        run(['npm.cmd', '--prefix', 'frontend', 'ci'])
        run(['npm.cmd', '--prefix', 'frontend', 'run', 'build'])
    if not (ROOT / 'frontend/dist/index.html').is_file(): raise RuntimeError('Frontend build missing.')
    env = os.environ.copy()
    env['DATUS_POSTGRES_DIR'] = str(pg.resolve())
    env['DATUS_TCLTK_DIR'] = str(tcltk.resolve())
    env['DATUS_VERSION'] = args.version
    env['PYINSTALLER_CONFIG_DIR'] = str((args.cache / 'pyinstaller').resolve())
    from notices import collect
    collect(ROOT, ROOT / 'build/notices', nsis)
    run([sys.executable, '-m', 'PyInstaller', '--noconfirm', 'packaging/datus.spec'], env=env)
    bundle = ROOT / 'dist/DATUS'
    run([str(bundle / 'DATUS.exe'), '--self-test'])
    output = ROOT / 'release'; output.mkdir(exist_ok=True)
    installer = output / f'DATUS-Setup-{args.version}-x64.exe'
    run([str(nsis), f'/DVERSION={args.version}', f'/DBUNDLE={bundle}', f'/DOUTPUT={installer}',
         str(ROOT / 'packaging/installer.nsi')])
    (output / (installer.name + '.sha256')).write_text(digest(installer) + '  ' + installer.name + '\n', encoding='utf-8')
    (output / 'build-info.json').write_text(json.dumps({'version': args.version, 'postgresql': '17.11', 'nsis': '3.12',
        'python': sys.version.split()[0], 'installer_sha256': digest(installer), 'signed': False}, indent=2), encoding='utf-8')
    print(f'Installer created: {installer}')


if __name__ == '__main__': main()
