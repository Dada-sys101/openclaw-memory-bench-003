# Isolated OpenClaw memory benchmark

Status: prepared, not yet executed on Linux. This repository payload contains no production configuration or credentials.

Pinned OpenClaw: 2026.10.8. Node: 26.12.1. Dependencies are locked by package-lock.json. Run only in a fresh, disposable Linux environment.

## Execution

The manually dispatched GitHub Actions workflow installs locked packages and runs `python3 bench.py`. It does not install a system service. Gateway and the synthetic upstream bind to loopback. Only web_fetch is allowed as an agent tool; no IM channel or production credential is configured.

The benchmark observes the actual OpenClaw Gateway process tree every 0.5 seconds. It records RSS, PSS, CPU ticks, system memory availability, PSI and available runner-wide cgroup data. The latter is not exclusive Gateway accounting. npm installation is measured separately by `/usr/bin/time -v`.

Phases: startup, ten-minute idle, single conversation, twenty turns with a shared session identifier, public-page fetches of small and large pages, failed fetches, two-minute idle, restart, two-minute idle, and cleanup.

The model upstream emits synthetic responses and tool requests. Successful HTTP alone is insufficient: provider calls and tool-result roundtrips must be checked. This measures actual Gateway orchestration overhead, not DeepSeek model quality. Real search, authenticated providers, WeChat and memory-limited cgroups are NOT_VERIFIED. A web_fetch result must also be inspected to distinguish fetched content from a returned error. Session message counts must demonstrate history growth before interpreting the continuous-session measurements.

Evidence is bundled into marked base64 gzip-tar blocks in the job log, rather than Actions artifact storage. Config and local authentication token are excluded. Gateway logs are scrubbed of the ephemeral token before evidence export. No production data should ever enter this directory.

Do not infer production safety from a successful run or a sampled peak below 394 MiB. Sampling can miss short peaks; the runner has different memory pressure and CPU resources from the production server. The twenty-turn test and idle window cannot establish long-term leak freedom.

## Local static validation

On a local Python installation, `ast.parse(Path('bench.py').read_text())` verifies syntax without starting the benchmark. Windows execution is explicitly rejected. Static validation is not runtime verification.
