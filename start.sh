#!/bin/bash
# Render start script
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
