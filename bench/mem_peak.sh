#!/bin/sh
# Peak memory (bytes) and CPU time (s) of the whole process tree, parent and
# workers included, read from a transient systemd cgroup. /usr/bin/time misses
# workers: they are children of the multiprocessing forkserver.
# Usage: bench/mem_peak.sh SCRIPT GPX_DIR [CPUS]
here=$(dirname "$(readlink -f "$0")")
exec systemd-run --user --scope -q -p MemoryAccounting=yes sh -c \
  "taskset -c ${3:-12-19} python '$here/run_scan.py' '$1' '$2' >/dev/null &&
   cg=/sys/fs/cgroup\$(cut -d: -f3 /proc/self/cgroup) &&
   echo \"memory_peak_bytes \$(cat \$cg/memory.peak)\" &&
   awk '/^usage_usec/ {print \"cpu_s\", \$2 / 1e6}' \$cg/cpu.stat"
