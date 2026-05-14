#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate
python batch_register_protonmail.py "$@"