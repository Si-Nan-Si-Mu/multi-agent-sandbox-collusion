# 多 Agent 沙箱共谋与评分器欺骗观测

《智能系统防护》课程实验：本地 LLM（Qwen2.5-14B / 32B 量化）+ 多 Agent（4–16）+ 公共文件区 + CTF 风格评分器，观测共谋与欺骗演化。

## 工作区

- 本地工程：`d:\挖洞\蜂群智能`
- GitHub：https://github.com/Si-Nan-Si-Mu/multi-agent-sandbox-collusion
- 运行机：蜂群智能算力 Notebook/SSH（与 EmbedX 实验机分离）
- 远端数据根（计划）：`/root/private_data/agent_sandbox/`

## 文档

- 设计规格：[`docs/superpowers/specs/2026-11-10-multi-agent-sandbox-collusion-design.md`](docs/superpowers/specs/2026-11-10-multi-agent-sandbox-collusion-design.md)
- 实现计划：[`docs/superpowers/plans/2026-11-10-multi-agent-sandbox-collusion.md`](docs/superpowers/plans/2026-11-10-multi-agent-sandbox-collusion.md)
- Docker/特权申请：[`docs/蜂群机_Docker特权申请清单.md`](docs/蜂群机_Docker特权申请清单.md)
- 远端部署：[`docs/REMOTE_SETUP.md`](docs/REMOTE_SETUP.md)
- 32B 加载状态：[`docs/M32Q_STATUS.md`](docs/M32Q_STATUS.md)
- 结果填空表：[`docs/RESULTS_TEMPLATE.md`](docs/RESULTS_TEMPLATE.md)

## 主实验矩阵（摘要）

| 代号 | 模型 | Agent 数 |
|---|---|---|
| M14-N16 | Qwen2.5-14B fp16 | 12 / 16 |
| M32Q-N8 | Qwen2.5-32B INT4/AWQ | 4 / 8 |

## 复现

本地 mock 不依赖 DCU，可在本机直接跑。远端 14B smoke 只在蜂群上手动执行，不进 CI，也不在本地自动跑。完整检查项、权重下载和 OOM 处理见 [`docs/REMOTE_SETUP.md`](docs/REMOTE_SETUP.md)。32B 还没有在 DCU 上验证，见 [`docs/M32Q_STATUS.md`](docs/M32Q_STATUS.md)，远端冒烟走 14B。

### 本地 mock

```bash
python scripts/run_local_mock.py --n-agents 2 --max-steps 5 --run-dir runs/mock_local
python scripts/plot_flag_timeline.py --run-dir runs/mock_local --out runs/mock_local/flag_timeline.png
bash scripts/pack_run.sh mock_local
```

`run_local_mock.py` 使用 `MockLLM`。打包结果在 `packs/mock_local.tar.gz`，不含模型权重。正式矩阵的填表和出图步骤见 [`docs/RESULTS_TEMPLATE.md`](docs/RESULTS_TEMPLATE.md)。

### 远端 smoke

在蜂群上执行。下面是命令索引；权重路径、`hy-smi` 和 curl 的预期输出以远端文档为准。

```bash
# 1. 建目录并检出仓库（默认分支 main）
bash scripts/remote_bootstrap.sh

# 2–3. 下载 Qwen2.5-14B 到 /root/private_data/agent_sandbox/models/Qwen2.5-14B
#      然后 hy-smi，确认空闲显存。见 docs/REMOTE_SETUP.md 第 2、3 节。

# 4. 起 14B 服务（另一终端保持运行）
cd /root/private_data/agent_sandbox/code
MODEL_PATH=/root/private_data/agent_sandbox/models/Qwen2.5-14B \
MAX_NUM_SEQS=1 \
DTYPE=float16 \
python scripts/serve_llm_transformers.py

# 5. 打一次补全
curl -s http://127.0.0.1:8001/v1/chat/completions \
  -H 'Content-Type: application/json' \
  -d '{"model":"Qwen2.5-14B","messages":[{"role":"user","content":"Reply with the single word: pong"}],"max_tokens":16}'

# 6. 编排器冒烟（当前脚本仍用 MockLLM；接真 14B 的改法见远端文档第 6 节）
python scripts/run_local_mock.py --n-agents 2 --max-steps 3 \
  --run-dir /root/private_data/agent_sandbox/runs/smoke-001

# 7. 14B 矩阵的一颗种子（服务已在 8001 监听之后）
SEEDS="1" bash scripts/run_matrix.sh configs/m14_n12.json
bash scripts/pack_run.sh m14_n12_seed1
```

不要在同一次服务里切换 M14 和 M32Q。M32Q 的加载步骤先更新 `docs/M32Q_STATUS.md`，再跑 `configs/m32q_n4.json` 与 `configs/m32q_n8.json`。

## Smoke

远端冒烟完成后，在本节追加一行：日期、机型、模型、N、max_steps、run dir 路径与 milestones 路径。

## 安全

- 受控沙箱实验；默认限制出网；不放入真实密钥。
- 仓库内勿提交 `.env`、SSH 密码、API Key。
- `scripts/pack_run.sh` 打包单个 `runs/<id>` 时排除权重文件以及 `models/`、`weights/` 目录。不要把 `runs/` 或 `packs/` 提交进仓库。

