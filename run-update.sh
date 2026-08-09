#!/bin/bash
set -e
echo "=== Step 1: update-stocks-data-simple.py ==="
cd /home/openclaw/monitoring-site && python3 update-stocks-data-simple.py
echo "---EXIT_1=$?"

echo "=== Step 2: update-ntv-data.py ==="
cd /home/openclaw/monitoring-site && python3 update-ntv-data.py
echo "---EXIT_2=$?"

echo "=== Step 3: update-kraken-data.py ==="
cd /home/openclaw/monitoring-site && python3 update-kraken-data.py
echo "---EXIT_3=$?"

echo "=== Step 4: git commit & push ==="
cd /home/openclaw/monitoring-site && git add data/ && git commit -m "auto update" && git push origin main
echo "---EXIT_4=$?"
