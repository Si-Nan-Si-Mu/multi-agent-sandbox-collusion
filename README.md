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

## 主实验矩阵（摘要）

| 代号 | 模型 | Agent 数 |
|---|---|---|
| M14-N16 | Qwen2.5-14B fp16 | 12 / 16 |
| M32Q-N8 | Qwen2.5-32B INT4/AWQ | 4 / 8 |

## Smoke

- 本地 mock smoke：`python scripts/run_local_mock.py --n-agents 2 --max-steps 5`（使用 `MockLLM`，不依赖 DCU）。
- 远端 14B smoke：**手动执行**，不在 CI/本地自动跑。步骤见 [`docs/REMOTE_SETUP.md`](docs/REMOTE_SETUP.md)（`remote_bootstrap.sh` 建目录、下载 Qwen2.5-14B、`hy-smi`、起 `scripts/serve_llm_transformers.py`、curl 一次补全、再跑 N=2/max_steps=3）。完成后在本节追加一行记录：日期、机型、模型、N、max_steps、run dir 路径与 milestones 路径。

## 安全

- 受控沙箱实验；默认限制出网；不放入真实密钥。
- 仓库内勿提交 `.env`、SSH 密码、API Key。
