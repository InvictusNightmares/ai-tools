#!/bin/bash
cd "$(dirname "$0")"
exec ./venv/bin/python batch_register_protonmail.py "$@"
