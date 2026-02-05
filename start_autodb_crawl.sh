#!/bin/bash
# Start AutoDB full site crawl in screen session
# Run this on prod: ./start_autodb_crawl.sh

cd /prod/autotech_ai

# Activate conda (anaconda3 on prod)
source /home/drawson/anaconda3/etc/profile.d/conda.sh
conda activate open-webui

# Start in screen
screen -dmS autodb_crawl bash -c "
    source /home/drawson/anaconda3/etc/profile.d/conda.sh
    conda activate open-webui
    cd /prod/autotech_ai
    python -m addons.autodb_agent.build_full_index --full --shallow 50 --prod --resume --concurrency 50 2>&1 | tee /tmp/autodb_crawl.log
"

echo "Started crawl in screen session 'autodb_crawl'"
echo "Monitor with: screen -r autodb_crawl"
echo "Or: tail -f /tmp/autodb_crawl.log"
