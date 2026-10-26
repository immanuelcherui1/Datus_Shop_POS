"""Collect original redistribution notices into the frozen application, not user data."""
import importlib.metadata
import shutil
import sys
from pathlib import Path


def collect(root, target, nsis):
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(root / 'packaging/THIRD_PARTY_NOTICES.md', target / 'README.md')
    shutil.copy2(Path(sys.base_prefix) / 'LICENSE.txt', target / 'Python-LICENSE.txt')
    shutil.copy2(nsis.parent / 'COPYING', target / 'NSIS-COPYING.txt')
    for distribution in importlib.metadata.distributions():
        name = distribution.metadata.get('Name', 'unknown').replace('/', '_')
        for file in distribution.files or []:
            if any(part.lower().startswith(('license', 'licence', 'copying', 'notice')) for part in file.parts):
                source = Path(distribution.locate_file(file))
                if source.is_file():
                    folder = target / 'python' / name
                    folder.mkdir(parents=True, exist_ok=True)
                    shutil.copy2(source, folder / file.name)
    for package in ['react', 'react-dom', 'scheduler', 'lucide-react', 'tailwindcss']:
        source = root / 'frontend/node_modules' / package
        for file in source.glob('*'):
            if file.is_file() and file.name.lower().startswith(('license', 'licence', 'copying', 'notice')):
                folder = target / 'frontend' / package
                folder.mkdir(parents=True, exist_ok=True)
                shutil.copy2(file, folder / file.name)
