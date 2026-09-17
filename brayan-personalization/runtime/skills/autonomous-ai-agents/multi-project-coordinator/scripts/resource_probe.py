#!/usr/bin/env python3
"""Read-only Linux resource probe; optional bounded JSONL sampling."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time


def snapshot():
    mem = {}
    for line in Path('/proc/meminfo').read_text().splitlines():
        key, value = line.split(':', 1)
        mem[key] = int(value.split()[0]) * 1024
    vm = {}
    for line in Path('/proc/vmstat').read_text().splitlines():
        key, value = line.split()
        if key in ('pswpin', 'pswpout', 'oom_kill'):
            vm[key] = int(value)
    disk = shutil.disk_usage(Path.home())
    result = {'time_unix': time.time(), 'cpu_count': os.cpu_count(),
              'load_1_5_15': os.getloadavg(),
              'memory_total_bytes': mem['MemTotal'],
              'memory_available_bytes': mem['MemAvailable'],
              'swap_used_bytes': mem['SwapTotal'] - mem['SwapFree'],
              'vm_counters': vm, 'home_disk_free_bytes': disk.free,
              'pressure': {}}
    for kind in ('cpu', 'memory', 'io'):
        path = Path('/proc/pressure') / kind
        if path.exists():
            result['pressure'][kind] = path.read_text().strip()
    if shutil.which('nvidia-smi'):
        p = subprocess.run(['nvidia-smi', '--query-gpu=name,memory.total,memory.used,utilization.gpu', '--format=csv,noheader,nounits'], capture_output=True, text=True, timeout=8)
        result['gpu'] = {'exit_code': p.returncode, 'rows': p.stdout.strip().splitlines()}
    return result


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--samples', type=int, default=1)
    ap.add_argument('--interval', type=float, default=30)
    ap.add_argument('--output', type=Path)
    args = ap.parse_args()
    if not 1 <= args.samples <= 2880 or not 1 <= args.interval <= 3600:
        ap.error('samples must be 1..2880 and interval 1..3600 seconds')
    previous = None
    for i in range(args.samples):
        data = snapshot()
        if previous:
            data['vm_counter_delta'] = {k: data['vm_counters'][k] - previous[k] for k in data['vm_counters']}
        previous = data['vm_counters']
        line = json.dumps(data)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open('a') as f:
                f.write(line + '\n')
        else:
            print(line, flush=True)
        if i + 1 < args.samples:
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
