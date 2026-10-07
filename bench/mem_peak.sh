#!/bin/sh
# Peak memory of the whole process tree (parent + workers), in bytes,
# read from a transient systemd cgroup.
# Usage: bench/mem_peak.sh SCRIPT GPX_DIR [CPUS]
here=$(dirname "$(readlink -f "$0")")
exec systemd-run --user --scope -q -p MemoryAccounting=yes sh -c \
  "taskset -c ${3:-12-19} python '$here/run_scan.py' '$1' '$2' >/dev/null &&
   cat /sys/fs/cgroup\$(cut -d: -f3 /proc/self/cgroup)/memory.peak"
