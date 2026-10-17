"""Optional real system-only API fixture. Reads no dotenv file; does not analyze code."""
import uvicorn
from archguard.api.app import create_app
from archguard.infrastructure.settings import Settings

if __name__ == '__main__':
    uvicorn.run(create_app(Settings(_env_file=None)), host='127.0.0.1', port=8780)
