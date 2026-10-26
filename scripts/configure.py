"""Create a secret-bearing local configuration once; never prints generated secrets."""
import secrets
from pathlib import Path
root = Path(__file__).resolve().parents[1]
text = (root / '.env.example').read_text(encoding='utf-8')
text = text.replace('GENERATE_A_RANDOM_SECRET_AT_LEAST_32_CHARACTERS', secrets.token_hex(32))
text = text.replace('GENERATE_A_DIFFERENT_RANDOM_SECRET_AT_LEAST_32_CHARACTERS', secrets.token_hex(32))
with (root / '.env').open('x', encoding='utf-8') as stream:
    stream.write(text)
print('Created .env with random authentication secrets. Configure PostgreSQL before starting DATUS.')
