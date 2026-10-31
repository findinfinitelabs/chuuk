#!/bin/zsh
# Run a memory-heavy command (MADLAD training) under a watchdog.
#
#   scripts/guarded_train.sh logs/train.log .venv/bin/python scripts/train_madlad.py --epochs 2
#
# Refuses to start while app.py or another trainer is running (two 3B model
# processes locked the machine on 2026-10-28). Then polls every 5 s and kills
# the whole process group if the machine is close to exhausting memory:
#   - free RAM (macOS memory_pressure free %, which counts reclaimable cache)
#     below MIN_FREE_MB (default 2048), or
#   - swap grew by more than MAX_SWAP_GROWTH_MB (default 3000) since start AND
#     free RAM is under 2×MIN_FREE_MB
# for two consecutive polls. Thresholds are overridable via env.
set -u
LOG=${1:?log file}; shift
MIN_FREE_MB=${MIN_FREE_MB:-2048}
MAX_SWAP_GROWTH_MB=${MAX_SWAP_GROWTH_MB:-3000}   # macOS keeps stale swap around, so judge growth since start
TOTAL_MB=$(( $(sysctl -n hw.memsize) / 1048576 ))

if pgrep -f "app\.py" >/dev/null || pgrep -f "train_madlad|retrain_with_latest|madlad_trainer" >/dev/null; then
  echo "refusing to start: app.py or another trainer is running" | tee -a "$LOG"; exit 2
fi

SWAP0=$(sysctl -n vm.swapusage | awk '{print $6}' | tr -d 'M' | cut -d. -f1); : ${SWAP0:=0}
export PYTORCH_MPS_HIGH_WATERMARK_RATIO=${PYTORCH_MPS_HIGH_WATERMARK_RATIO:-0.6}
export PYTORCH_MPS_LOW_WATERMARK_RATIO=${PYTORCH_MPS_LOW_WATERMARK_RATIO:-0.5}

perl -e 'setpgrp(0, 0); exec @ARGV or die "exec: $!"' -- "$@" >>"$LOG" 2>&1 &
PID=$!
PGID=$PID  # setpgrp(0,0) in the perl launcher makes the child its own group leader
echo "[guard] started pid $PID pgid $PGID; min_free=${MIN_FREE_MB}MB swap_now=${SWAP0}MB max_swap_growth=${MAX_SWAP_GROWTH_MB}MB" | tee -a "$LOG"

strikes=0; tick=0
while kill -0 $PID 2>/dev/null; do
  sleep 5
  free_pct=$(memory_pressure -Q 2>/dev/null | awk '/free percentage/ {gsub("%","",$NF); print int($NF)}')
  : ${free_pct:=100}
  free_mb=$(( free_pct * TOTAL_MB / 100 ))
  swap_mb=$(sysctl -n vm.swapusage | awk '{print $6}' | tr -d 'M' | cut -d. -f1)
  : ${swap_mb:=0}
  rss_mb=$(ps -o rss= -g $PGID 2>/dev/null | awk '{s+=$1} END {printf "%d", s/1024}')
  tick=$((tick+1))
  if (( tick % 60 == 0 )); then
    echo "[guard $(date +%H:%M:%S)] free=${free_mb}MB swap=${swap_mb}MB train_rss=${rss_mb}MB" >>"$LOG"
  fi
  # macOS pages out the idle CPU side of a GPU-bound trainer, so swap growth on
  # its own is benign (it hit +4 GB with 12 GB still free on 2026-10-30). Only
  # treat it as danger when free memory is also getting tight.
  if (( free_mb < MIN_FREE_MB || (swap_mb - SWAP0 > MAX_SWAP_GROWTH_MB && free_mb < 2 * MIN_FREE_MB) )); then
    strikes=$((strikes+1))
    echo "[guard $(date +%H:%M:%S)] LOW MEMORY strike $strikes: free=${free_mb}MB swap=${swap_mb}MB rss=${rss_mb}MB" >>"$LOG"
    if (( strikes >= 2 )); then
      echo "[guard] killing process group $PGID to protect the machine" | tee -a "$LOG"
      kill -TERM -- -$PGID 2>/dev/null; sleep 10; kill -KILL -- -$PGID 2>/dev/null
      exit 3
    fi
  else
    strikes=0
  fi
done
wait $PID; rc=$?
echo "[guard] finished with exit code $rc" | tee -a "$LOG"
exit $rc
