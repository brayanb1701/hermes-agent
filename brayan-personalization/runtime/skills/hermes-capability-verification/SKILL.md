---
name: hermes-capability-verification
description: Use when auditing live Hermes tool readiness.
---

Load hermes-agent before configuration work and computer-use before GUI tests.

Distinguish exposure, backend readiness, invocation, and verified effect. A skill's presence proves none of the latter.

Check display variables in the actual terminal subprocess: execute_code can have a different environment. A healthy X11 doctor report does not certify native Wayland apps.

Newly enabled computer_use needs a fresh Hermes session. Verify the child tool result, not just its summary. Test GUI input on a disposable GTK X11 app: target exact PID/window, capture, set text, re-snapshot, click with a fresh element token, and verify a callback-written result file. Raw cua-driver CLI requires a daemon and uses different action schemas; inspect describe first. Stop only test-owned services.

Probe the effective browser CDP endpoint at /json/version. Use a loopback-only dedicated automation profile, never normal user cookies. Test navigation, input, click, DOM result and screenshot. For persistent setup, enable a user service and retest after handover.

Prefer existing subscription routes or local execution over separately billed APIs. Preserve Nous image/STT/TTS routing unless explicitly asked to change it; a provider label such as openai in a result can identify the underlying engine rather than direct billing. Verify route before making billing claims.

Native Wayland testing can use a temporary cua-driver daemon with CUA_DRIVER_RS_ENABLE_WAYLAND=1 and a dedicated socket; cua-driver call accepts --socket. Launch a disposable GTK app with GDK_BACKEND=wayland and verify xwayland=false through compositor metadata. Accessibility set-value/click may work while per-window capture fails with surface_identity_unproven. Never substitute full-desktop capture silently. An action can time out after taking effect: verify the callback-written result before retrying. Do not enable the experimental backend globally merely because one test passed.

Test image generation and editing separately: gateways may accept generation but reject editing with HTTP 403. Do not silently switch models, providers or billing. Inspect the generated image for prompt adherence.

On plain CLI, text_to_speech generates a file but does not play it. Use an installed audio player for audible tests; ask the user to confirm hearing it. ffprobe only verifies the file.

Find the live Hermes interpreter before optional dependency installation; do not assume .venv exists. Test an actual search after repairing its SDK.

For faster-whisper GPU failures, distinguish driver-supported CUDA shown by nvidia-smi from installed application libraries. Current CTranslate2 requires CUDA 12 cuBLAS and cuDNN 9; consult the faster-whisper upstream requirements, install matching NVIDIA wheels in the managed venv, and supply their library directories via LD_LIBRARY_PATH before Python starts. Prefer a scoped launcher over global loader or driver changes. Verify actual CUDA inference by consuming transcription segments, then test Hermes local STT using a temporary HERMES_HOME; preserve the live provider unless a switch is requested. A passing launcher test does not prove an ordinary gateway inherits its environment.

Record git status before personalization sync. Inspect sync output for unrelated runtime drift. Restore only sync-produced bundle noise proven clean beforehand, preserve the intended narrow delta, and never overwrite concurrent live changes.
