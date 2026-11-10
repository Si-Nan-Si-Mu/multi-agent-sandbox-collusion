# M32Q status

not verified on DCU yet

The M32Q-N4 / M32Q-N8 half of the experiment matrix
(Qwen2.5-32B INT4/AWQ, `max_num_seqs=1`) has not been loaded or run on the
蜂群 HCU/DCU host. No load error is recorded because the quant checkpoint was
not attempted in this task.

Treat the 32B half as **partial** until someone:

1. Places an INT4/AWQ (or equivalent) checkpoint where the serve script can see it.
2. Confirms `hy-smi` shows the card idle, starts `scripts/serve_llm_transformers.py`
   with `MAX_NUM_SEQS=1`, and curls one completion.
3. Runs `bash scripts/run_matrix.sh configs/m32q_n4.json configs/m32q_n8.json`
   (seeds `1 2 3`).

If that load fails, replace this note with the error and keep the matrix
partial. M14-N12 / M14-N16 remain the primary deliverable either way.
Configs: `configs/m32q_n4.json`, `configs/m32q_n8.json`.
