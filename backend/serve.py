#!/usr/bin/env python3
"""Bounded, loopback-only WSGI server for the local application."""
import argparse
import os
import tempfile

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from config.wsgi import application
from django.conf import settings
from waitress import serve

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=int(os.environ.get("DRIVE_PORT", "8000")))
    args = parser.parse_args()
    temporary = settings.DRIVE_DATA_DIR / "http-temporary"
    temporary.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(temporary, 0o700)
    tempfile.tempdir = str(temporary)
    # Waitress buffers incoming bodies to bounded-memory temporary files before
    # entering Django. The domain layer then streams those bytes into BlobStore.
    serve(application, host="127.0.0.1", port=args.port, threads=4,
          connection_limit=32, channel_timeout=120, cleanup_interval=5,
          inbuf_overflow=1024 * 1024, max_request_body_size=settings.MAX_FILE_BYTES,
          max_request_header_size=32768, expose_tracebacks=False)
