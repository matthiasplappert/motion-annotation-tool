#!/bin/bash
source ~/dataset-web/bin/activate
python ~/dataset-web/src/manage.py updateperplexity &> /dev/null
