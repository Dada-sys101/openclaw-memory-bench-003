# MEMORY_BENCH_REPORT

2026-10-28 · **最终结论：不建议共机。**

真实 OpenClaw 2026.10.8 的精简配置，空闲末段约 **820 MiB PSS**，文字、连续对话及联网工具运行时约 **1.35–1.55 GiB PSS**，明显超过现有生产服务器新增服务的 **185–394 MiB** 预算。512 MiB、768 MiB 容器均 OOM；独立 **2 GiB／2 vCPU** 容器通过短时全流程，整体 cgroup 峰值 **1,652.0 MiB**、无 OOM。

**最值得执行的下一步：保持现有生产服务器不变，使用独立 2 vCPU／2 GiB 实例作为成本较低的继续验证环境。** 该规格有本轮短测支持；微信插件、真实 DeepSeek、长时间运行和更长上下文仍需验证。若希望为长期使用预留较宽裕空间，4 GiB 更合适，但这是容量规划建议，不是已完成的部署验收。

## 实际内存与峰值

单位均为 MiB，统计整个 Gateway 进程树。PSS 分摊共享页；RSS 相加可能重复包含共享页。“中位数”为该阶段样本中位数，不是长期稳定承诺。任务按顺序执行，行间差值不能当作某个工具的独立增量。

| 精简配置场景 | PSS 中位数 | PSS 采样峰值 | RSS 采样峰值 | 验证结果 |
|---|---:|---:|---:|---|
| 启动至健康接口可用 | 420.3 | 808.6 | 922.4 | 成功 |
| 启动后空闲 120 秒 | 889.7 | 1,196.9 | 1,362.4 | 最后 30 秒中位数 820.2 |
| 单轮文字对话及短暂停留 | 1,378.3 | 1,457.8 | 1,624.7 | 真实 Gateway 模型路径通过 |
| 同一会话连续 20 轮 | 1,469.8 | 1,512.0 | 1,679.2 | 历史消息数从 2 增至 40 |
| 普通网页获取 3 次 | 1,481.4 | 1,529.1 | 1,696.4 | HTTP 200；首次联网、后两次缓存 |
| 较大网页获取 3 次 | 1,485.5 | 1,488.2 | 1,655.5 | 原始提取正文 345,801 字符 |
| 网页获取失败 3 次 | 1,484.8 | 1,487.4 | 1,654.7 | 正确返回 ENOTFOUND |
| 真实联网搜索 3 次 | 1,468.2 | 1,476.3 | 1,643.6 | 返回 3 个来源；后两次缓存 |
| 任务后空闲 60 秒 | 1,418.0 | 1,460.3 | 1,627.6 | 最后 30 秒中位数 1,402.3 |
| 重启至健康接口可用 | 519.2 | 870.7 | 984.4 | 成功 |
| 重启后空闲 60 秒 | 1,162.0 | 1,418.2 | 1,597.9 | 最后 30 秒中位数 1,077.8 |

健康接口可用后仍有后台初始化。首次启动及随后初始化最高 PSS 为 **1,196.9 MiB**，重启及随后初始化最高 **1,418.2 MiB**，不能只拿“启动至健康接口可用”一行作为完整启动预算。

另有默认内置插件配置的十分钟空闲基线：PSS 中位数 **858.8 MiB**，最后 30 秒 **865.8 MiB**，首轮文字对话峰值 **2,009.7 MiB PSS / 2,176.5 MiB RSS**。默认配置加载 14 个内置插件；精简配置只加载 `openai` 和 `duckduckgo`，禁用长期记忆插件、保留连续会话历史。精简降低了文字任务峰值，仍远超预算。

## 512 MiB、768 MiB 与 2 GiB 限额

最终复核采用匹配插件文件所有者的容器用户、相同精简配置、Node 26.12.1、2 CPU quota，不允许额外 Swap，不发布宿主端口。

| 容器内存上限 | cgroup memory.peak | Docker OOMKilled | 结果 |
|---|---:|---|---|
| 512 MiB | 512.0 MiB | true | 启动阶段失败，Gateway 被 SIGKILL |
| 768 MiB | 768.0 MiB | true | 启动阶段失败，Gateway 被 SIGKILL |
| 2,048 MiB | **1,652.0 MiB** | false | 33 次请求、12 次工具往返、重启及正常退出通过 |

2 GiB 容器内，Gateway 树 PSS 峰值 **1,592.6 MiB**、RSS 峰值 **1,748.1 MiB**；连续对话 PSS 峰值 1,569.1 MiB，搜索峰值 1,570.3 MiB。cgroup 还包含 Python 测量及模拟上游进程、计入容器的缓存与内核开销，与 Gateway PSS 不是同一口径。

2 GiB 限额相对峰值仅剩约 **396 MiB**。容器共享 Runner 内核，不包括一台独立 Ubuntu 主机的全部系统服务，因此不能把这部分全部当作新服务器业务余量。该容器全流程约 87 秒，是短时验证；OOM 计数为 0、退出码 0、无遗留 Gateway 进程组。

512 MiB 末次采样早于 OOM 计数刷新，Docker 最终状态明确为 `OOMKilled=true`；768 MiB 末次采样记录 `oom_kill=1`。以 cgroup 峰值和最终容器状态共同判定，不把非原子采集的 RSS/PSS 与 cgroup 计费页数混为一谈。

## 测试是否真实完成

| 项目 | 证据与边界 |
|---|---|
| Gateway | 实际运行官方包；CLI 输出 `OpenClaw 2026.10.8 (dc2523e)` |
| 模型调用 | 真实 Gateway 进入代理循环，连接本地模拟模型上游；没有用模拟程序替代 Gateway |
| 连续会话 | 20 次同一会话请求，上游消息数 2、4、6……40；证明携带历史，不证明模型理解质量 |
| 网页工具 | 精简轮完成 6 次成功获取和 3 次预期 DNS 失败；真实 HTTP 和工具结果进入后续模型请求 |
| 联网搜索 | 官方 `@openclaw/duckduckgo-plugin@2026.10.8` 真正联网；首次耗时 809 ms，返回 3 个 Python 官方来源；其余两次为缓存 |
| 大正文 | RFC 9110 页面原始提取 345,801 字符；工具截断并溢写临时文件，上游最终收到 8,192 字符的截断工具内容；没有验证完整大正文进入模型或摘要质量 |
| 空闲增长 | 默认十分钟空闲前/后 30 秒中位数 1,119.1 → 865.8 MiB；精简两分钟 1,049.5 → 820.2 MiB。未观察到持续单调增长，不能据此证明长期无泄漏 |
| 重启 | 健康接口重新可用、进程存活和正常退出通过；重启后新对话未单独复测 |
| 未验证 | 实际 DeepSeek 模型、DeepSeek Search、微信插件及真实微信收发、长期记忆、长时间/多用户负载、Node 24 对比 |

搜索返回来源之一为 [Python 官方发布页](https://www.python.org/downloads/release/python-3140/)。所有模型回复均为固定测试文本；本轮没有生产密钥、真实微信、业务 MCP 或浏览器自动化。

## 环境、指标和版本锁定

主测试为 GitHub 标准 `ubuntu-24.04` Runner：Linux `6.17.0-1022-azure`、4 vCPU、约 15.6 GiB RAM。限额测试使用官方 Node Debian Bookworm 容器，共享 Linux 内核。Windows 只负责编排和分析；没有启用 WSL，没有连接阿里云。

每约 0.5 秒读取 `/proc/<pid>/smaps_rollup`、`status`、`stat`，递归汇总 Gateway 子进程；同时保存可用内存、Swap、PSI、CPU ticks、cgroup `memory.current` / `memory.peak` / `memory.events`。主 Runner 的 cgroup 含整个任务，未将其峰值视为 Gateway 独占占用。样本非同时原子快照，可能漏掉极短峰值；真实搜索阶段样本很少，所列峰值不是绝对上限。

主测试通常有 4 个 Gateway 相关进程，重启时短暂增至 7 个；Worker 线程已计入所属进程，不另行重复相加。配置为并发 1、上下文预算 16,384 tokens、loopback 监听、临时认证、独立 HOME/状态/配置目录，设置 `OPENCLAW_NO_RESPAWN=1`。精简轮 Agent 工具只允许 `web_fetch` 和 `web_search`，`tools.toolSearch=false`，`plugins.slots.memory="none"`。

依赖安装单独测量：成功基线 npm 安装最大 RSS **400.0 MiB**、16.61 秒；精简轮 **414.5 MiB**、16.33 秒。此为 `/usr/bin/time -v` 的最大 RSS，并非安装进程树总峰值。无单独源码构建，安装脚本开销包含在安装阶段，未混入运行数据。

| 锁定项 | 记录 |
|---|---|
| Node | 26.12.1 |
| OpenClaw | `openclaw@2026.10.8`，官方 npm registry |
| OpenClaw integrity | `sha512-fWOIOOyddIBqeuPz82DBCdY5kNl1yD51qebAHnxlTN7SmVoH5/WSIudR/N1zDhcIIksgJXe6ZgGy5ngSRxZOrQ==` |
| 搜索插件 | `@openclaw/duckduckgo-plugin@2026.10.8` |
| 最终锁文件 SHA-256 | `c9a38a78fbf2077d6c232db5024de37c70181b91a035ffa5ced18fcf35703254` |
| 容器镜像摘要 | `node@sha256:52dd743dc3b494cba5bc8c13507ac984507addb8a087c626dc98dcffa53133d4` |

`npm ci` 按锁文件下载并校验完整性；没有宣称完成额外发布验签或可复现构建审计。工作流 Action 固定为提交 SHA。

## 可复核证据与命令

| 有效测试 | GitHub 运行日志 | 代码 SHA | 数字证据 |
|---|---|---|---|
| 十分钟默认配置基线 | [运行记录](https://github.com/Dada-sys101/openclaw-memory-bench-003/actions/runs/40657686649) | `fa2fdce` | [baseline](results/baseline/)，1,908 个时间点 |
| 精简配置及真实网页/搜索 | [运行记录](https://github.com/Dada-sys101/openclaw-memory-bench-003/actions/runs/40660214312) | `af4786a` | [minimal](results/minimal/)，629 个时间点 |
| 最终匹配用户限额复核 | [运行记录](https://github.com/Dada-sys101/openclaw-memory-bench-003/actions/runs/40662472795) | `a47edfd` | [512 MiB](results/limit512/)、[768 MiB](results/limit768/)、[2 GiB](results/limit2048/) |

目录包含 `samples.csv`、`analysis.json`、`checksums.json`；限额目录另含 Docker 状态，工具成功轮另含脱敏工具结果。校验文件记录原始 NDJSON 的 SHA-256。完整日志的 `BENCH_DATA:` 数据包可用 [decode_evidence.py](decode_evidence.py) 解出原始时间序列及 Gateway 日志。未上传 Actions 存储制品。

```sh
npm ci --no-audit --no-fund
node node_modules/openclaw/openclaw.mjs --version
BENCH_SEARCH=1 BENCH_LEAN=1 BENCH_IDLE_SECONDS=120 \
  BENCH_POST_SECONDS=60 BENCH_SETTLE_SECONDS=10 python3 bench.py
# 脚本在独立 HOME / 状态 / 配置目录下启动真实程序：
node node_modules/openclaw/openclaw.mjs gateway run
# 精确容器参数、镜像和删除命令见 .github/workflows/limits.yml。
```

本地完整证据根目录：`D:\codex-geren\outputs\memory-bench-003`；`run2/evidence`、`run4/evidence`、`run6/evidence` 对应上表三项有效测试。

早期尝试中的旧配置字段、工具检索层调用方式、采样竞态、插件所有者不匹配和挂载点缺失均已修正或排除。默认配置轮的网页请求没有真正调用工具，未计为网页通过；早期限额不匹配轮保留为 `preliminary-*`，不是最终完整配置的证据。工作流 success 只表示证据收集完成，不能视为内部 OOM 测试通过。

## 三个问题的结论与下一步

**1. 实际内存是多少？** 精简配置空闲末段约 820 MiB PSS；单轮、连续会话、真实搜索中位数约 1,378、1,470、1,468 MiB，峰值约 1,458、1,512、1,476 MiB。网页峰值 1,529 MiB。独立 2 GiB 容器的整体峰值为 1,652 MiB。以上不含真实 DeepSeek/微信插件的额外开销。

**2. 原 1.6 GiB 服务器是否能保证共机稳定？不建议。** 空闲末段已超过 394 MiB 预算两倍，任务峰值约四倍；同时还要保留 MySQL、Nginx、Node API 等生产资源。2 GiB 独立容器成功，不能推出 1.6 GiB 生产主机也能安全共机。没有必要再拿生产服务器尝试同一配置。

**3. 最经济、最简单的解决方向？优先独立实例。** 独立 2 vCPU／2 GiB 是有短测证据、成本较低的继续验证起点；4 GiB 有更宽裕余量。升级原机到 4 GiB 可能比另买实例更便宜，也只需维护一台机器，但阿里云明确升级会重启服务器，部分活动实例升级后失去优惠续费资格，差价以账户页面为准。因此升级不满足“完全不打断日常助手”，未查账户报价前也不能宣称它绝对最便宜。[阿里云升级规则](https://help.aliyun.com/zh/simple-application-server/user-guide/upgrade-a-simple-application-server)

建议以本轮峰值再加约 0.5 GiB 应用缓冲作后续容量规划，并另计系统与新插件开销；这不是已验证的安全阈值。若坚持零新增硬件费用，可以另测只做微信转发、上下文和搜索的专用小程序，但本轮没有测量这种替代实现，不能承诺其符合 185–394 MiB 预算。

本次没有购买服务器、修改计费设置、设置常驻服务、连接或修改生产环境。正常实例退出码 0、无遗留 Gateway 进程组；OOM 实例不算优雅退出，但测试容器均已显式删除，Runner 任务全部结束。未另行探测原生产健康，不声称做过部署前后健康对照。

**FINAL_STATUS：不建议共机；隔离资源验证完成，正式部署未执行。**
