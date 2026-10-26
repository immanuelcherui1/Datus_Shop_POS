"""Single-PC production entry point; Waitress supports Windows without a development server."""
import os
from waitress import serve
from datus import create_app

app = create_app()

if __name__ == '__main__':
    serve(app, host=os.getenv('HOST', '127.0.0.1'), port=int(os.getenv('PORT', '8080')), threads=8)
