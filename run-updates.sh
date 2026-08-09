#!/bin/bash
set -e
cd /home/openclaw/monitoring-site

echo "=== [1/4] update-stocks-data-simple.py ==="
python3 update-stocks-data-simple.py 2>&1
STOCKS_EXIT=$?
echo "STOCKS exit: $STOCKS_EXIT"

echo ""
echo "=== [2/4] update-ntv-data.py ==="
python3 update-ntv-data.py 2>&1
NTV_EXIT=$?
echo "NTV exit: $NTV_EXIT"

echo ""
echo "=== [3/4] update-kraken-data.py ==="
python3 update-kraken-data.py 2>&1
KRAKEN_EXIT=$?
echo "KRAKEN exit: $KRAKEN_EXIT"

echo ""
echo "=== [4/4] git add/commit/push ==="
git add data/
git commit -m "auto update" 2>&1
git push origin main 2>&1
GIT_EXIT=$?
echo "GIT exit: $GIT_EXIT"
