# XLSM memory-exhaustion forensics and prevention

Use this reference when a document/workbook workflow coincides with a frozen desktop, closed terminal, `received signal 1`, an interrupted Hermes turn, or a delegation owner disappearing.

## Proven diagnosis pattern

1. Establish whether the event was an OOM kill rather than a kernel panic or subagent-framework crash:
   - inspect `journalctl --list-boots`;
   - inspect the relevant boot/window for `oom-kill`, `Out of memory`, `Killed process`, `systemd-oomd`, and the containing `app-gnome-sh-*.scope`;
   - record PID, anonymous RSS, virtual memory, swap entries, cgroup path, and timestamp.
2. Correlate that timestamp and PID lifetime with Hermes history in the profile-local `state.db`:
   - identify the parent session and any child session IDs;
   - inspect assistant tool calls and terminal results immediately before the OOM timestamp;
   - distinguish the lightweight Hermes/subagent threads from external Python processes launched through terminal tools.
3. Attribute the allocation to the exact command, not merely to the presence of parallel subagents. A batch can increase overlap and the chance of an unsafe command, but remote model calls are not themselves consuming tens of GiB of local RAM.
4. Explain terminal closure separately: when the victim runs inside a GNOME shell/terminal systemd scope, kernel OOM plus scope failure can terminate or hang the terminal and surface SIGHUP (`signal 1`) to Hermes even without a full machine reboot.

## Confirmed dangerous workbook pattern

A large, highly styled, macro-enabled workbook can explode in memory when code does all of the following:

```python
wb = openpyxl.load_workbook(path, read_only=False, keep_vba=True)
for ws in wb.worksheets:
    for row in ws.iter_rows():
        for cell in row:
            ...
```

On a 191-sheet DIAN XLSM, this pattern produced about 27 GiB anonymous RSS in a single Python process on two separate runs, exhausted available RAM/swap, and triggered the kernel OOM killer. One incident occurred in the parent session; another occurred inside one child of a three-subagent batch. That comparison proves the allocator was the workbook scan, not subagent spawning by itself.

## Safer alternatives

- Search OOXML members directly with `zipfile`, parsing one XML member at a time.
- Reuse formula/constant indexes already extracted from the package.
- If OpenPyXL is unavoidable, use `read_only=True`, open once, inspect only named sheets/ranges, and close promptly.
- Measure RSS on one representative sheet before scaling.
- Never run multiple full workbook loaders alongside local OCR/VLM work.
- Prefer a memory-limited cgroup/process boundary for untrusted or exploratory workbook probes; concurrency limits alone cannot prevent one child from exhausting the machine.

## Reporting standard

Separate three claims:

- **Trigger:** the exact memory-heavy command/process.
- **Amplifier:** parallel agents or simultaneous workloads that increased overlap.
- **Visible symptom:** OOM-killed process, failed terminal scope, interrupted owner session, or later unknown delegation result.

Do not report “subagents crashed the PC” when logs show one external process consumed nearly all memory.