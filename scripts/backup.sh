#!/bin/bash
source ~/dataset-web/bin/activate
python ~/dataset-web/src/manage.py archive &> /dev/null
rsync -r -c ~/dataset-web/backups plappert@i61pc019:~/home/PdF/dataset-web-backups
