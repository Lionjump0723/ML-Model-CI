import os
from pathlib import Path
from typing import TextIO

env_dir = Path(__file__).absolute().parents[1] / 'modelci'


def _decode_dotenv(env_file: TextIO):
    lines = env_file.readlines()

    env_data = dict()
    for line in lines:
        key, value = line.strip().split('=')
        env_data[key] = value

    return env_data


def _encode_dotenv(env_data: dict, env_file: TextIO):
    lines = [f'{k}={v}' for k, v in env_data.items()]
    env_file.write(f'{os.linesep}'.join(lines))


backend_env, frontend_env = dict(), dict()

with open(env_dir / 'env-backend.env') as f:
    backend_env.update(_decode_dotenv(f))

with open(env_dir / 'env-mongodb.env') as f:
    backend_env.update(_decode_dotenv(f))


with open(env_dir / 'env-frontend.env') as f:
    frontend_env.update(_decode_dotenv(f))


backend_url = f"{backend_env.get('SERVER_HOST', 'http://localhost')}:{backend_env.get('SERVER_PORT', 8000)}"
frontend_url = f"{frontend_env.get('HOST', 'http://localhost')}:{frontend_env.get('PORT', 3333)}"

# Put frontend url into backend CORS origins
cors_origins = backend_env.get('BACKEND_CORS_ORIGINS', '')
backend_env['BACKEND_CORS_ORIGINS'] = ','.join([cors_origins, frontend_url])

# Put backend url into frontend env
frontend_env['REACT_APP_BACKEND_URL'] = backend_url

# save to backend .env
with open(env_dir / '.env', 'w') as f:
    _encode_dotenv(backend_env, f)

# save to frontend .env
with open(env_dir / '../frontend/.env', 'w') as f:
    _encode_dotenv(frontend_env, f)
