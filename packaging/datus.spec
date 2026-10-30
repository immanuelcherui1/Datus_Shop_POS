# PyInstaller one-folder bundle. Runtime data is NEVER collected from the working tree.
import os
from pathlib import Path
from PyInstaller.utils.hooks import collect_data_files, collect_submodules, copy_metadata

root = Path(SPECPATH).parent
version_file = root / 'build/generated/version.txt'
version_file.parent.mkdir(parents=True, exist_ok=True)
version_file.write_text(os.environ.get('DATUS_VERSION', '0.4.0'), encoding='utf-8')
postgres = Path(os.environ['DATUS_POSTGRES_DIR']).resolve()
if not (postgres / 'bin' / 'postgres.exe').is_file():
    raise RuntimeError('DATUS_POSTGRES_DIR must point to verified PostgreSQL 17 Windows binaries.')
datas = [(str(root / 'scripts/funnel.ps1'), 'setup'), (str(root / 'frontend/dist'), 'frontend/dist'),
         (str(root / 'backend/migrations'), 'backend/migrations'),
         (str(root / 'docs'), 'docs'),
         (str(root / 'README.md'), '.'),
         (str(version_file), '.'),
         (str(postgres), 'postgresql')]
if (root / 'build/notices').exists():
    datas.append((str(root / 'build/notices'), 'licenses'))
for package in ['flask', 'flask_migrate', 'flask_limiter', 'marshmallow', 'tzdata', 'psycopg', 'psycopg_binary']:
    datas += collect_data_files(package)
for distribution in ['Flask', 'Flask-Limiter', 'limits', 'marshmallow']:
    datas += copy_metadata(distribution)
hidden = collect_submodules('psycopg') + ['sqlalchemy.dialects.postgresql.psycopg', 'scripts.backup', 'desktop.smoke', 'logging.config']
a = Analysis([str(root / 'desktop/launcher.py')], pathex=[str(root), str(root / 'backend')], hookspath=[str(root / 'packaging/hooks')],
             binaries=[], datas=datas, hiddenimports=hidden, excludes=['pytest'], noarchive=False)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name='DATUS', console=False,
          debug=False, strip=False, upx=False, icon=str(root / 'frontend/public/branding/datus.ico'))
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='DATUS')
