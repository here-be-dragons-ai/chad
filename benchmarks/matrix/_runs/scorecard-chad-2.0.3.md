### Local-fitness scorecard — same weights, same laptop, same tasks

#### What it feels like

| Arm                 | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|---------------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| chad+llama          | 2,563                    | 25.5 s                        | 36                              | 0.8 s · 19 s                  | 99%         | 59                     | 7.9        | 24/24       |
| goose+llama         | 9,617                    | 9.5 s                         | 41                              | 1.0 s · 22 s                  | 100%        | 45                     | 8.0        | 22/24 T3    |
| chad+mlx *          | 2,562                    | 4.6 s †                       | 35                              | 0.9 s · 36 s                  | 99%         | 28                     | 17.4       | 22/24 T3    |
| chad+mlx-nodflash * | 2,566                    | 4.7 s †                       | 45                              | 1.0 s · 19 s                  | 99%         | 28                     | 12.4       | 21/24 T3    |

Every column but the last two is llama-server's own accounting, read through the proxy
(`_runs/turns.jsonl`), never a harness's self-report. **tax** = prompt tokens of the
first agent request (`prompt_n + cache_n`: system prompt + tool schemas + task); **wait,
turn 1** = the server's `prompt_ms` for that request; **uncached / later turn** =
`prompt_n` on agent turns 2+, pooled median; **wait / later turn** = `prompt_ms` on those
turns, median and p90; **cache reuse** = `cache_n / (cache_n + prompt_n)` on those turns;
**prefill s / task** = Σ `prompt_ms` over every request of a task, side requests included;
**exp. tok/s** = generated tokens / wall clock. Side requests (title / summary calls with
no tool schemas) are excluded from the per-turn columns and counted in the next table.
The pass column is a gate, not a ranking.
`*` in-process arm: the same fields from chad's own prefill trace, self-reported — no server saw it. `†` includes the system-prompt prefix chad prefills before its first step when its disk checkpoint misses, or restores when it hits (chad+mlx: miss/partial, 3.3 s of it; chad+mlx-nodflash: partial, 3.5 s of it). A miss is the cold prefill of the same prompt the chad+llama row pays; a hit is a disk restore; a partial restores the project-independent head (tool schemas + behavioral prompt) from disk and prefills only the per-project tail.

#### Shape of the harness

| Arm                 | tools | system prompt (chars) | prefix churn | side requests (concurrent · abandoned) | round trips / task | model busy | prefill share | ctx at exit |
|---------------------|-------|-----------------------|--------------|----------------------------------------|--------------------|------------|---------------|-------------|
| chad+llama          | –     | –                     | –            | 0                                      | 7                  | 98%        | 17%           | 8,338       |
| goose+llama         | 18    | 23,924                | 0/132        | 24 (24 · 0)                            | 7                  | 111%       | 14%           | 16,174      |
| chad+mlx *          | –     | –                     | –            | 0                                      | 5                  | 94%        | 23%           | 7,581       |
| chad+mlx-nodflash * | –     | –                     | –            | 0                                      | 6                  | 96%        | 18%           | 7,843       |

**tools** / **system prompt** as the harness sent them on its first agent request;
**prefix churn** = agent turns whose system-message or tool-list hash changed since the
previous agent turn, over turns compared (`–`: chad's raw `/completion` path and the MLX
arms carry no messages to hash — their cache-reuse column is the evidence instead);
**side requests** = no-tools calls beside the agent loop (session titles, summaries),
summed over the arm's grid: how many overlapped an agent turn in time, and how many the
harness abandoned before the server answered (no `timings` came back; counted, not
measured); **model busy** = Σ (`prompt_ms` + `predicted_ms`) /
wall over measured requests — above 100% means two were in flight at once; **round
trips** = agent turns per task; **ctx at exit** = tokens in context at the last agent
turn.

Instrument check: the proxy's own first-byte stamp came back earlier than the server's `prompt_ms` on 15 of 349 requests (llama-server streams a first chunk before a long prefill finishes), so no time-to-first-byte column is printed; the server's prefill time is the wait.

#### Per task — cache reuse (median, agent turns 2+) · wait / later turn (median) · experienced tok/s

| Task          | chad+llama        | goose+llama       | chad+mlx           | chad+mlx-nodflash  |
|---------------|-------------------|-------------------|--------------------|--------------------|
| bowling       | 100% · 1.0s · 7.9 | 100% · 1.8s · 7.1 | 95% · 11.7s · 16.7 | 94% · 17.2s · 10.6 |
| grade-school  | 99% · 0.8s · 6.7  | 100% · 0.8s · 7.2 | 99% · 0.9s · 14.0  | 100% · 0.7s · 11.5 |
| affine-cipher | 99% · 0.8s · 6.2  | 99% · 1.3s · 7.6  | 99% · 0.9s · 18.3  | 97% · 2.0s · 11.3  |
| transpose     | 86% · 6.6s · 8.3  | 100% · 0.9s · 9.2 | 86% · 5.9s · 17.4  | 100% · 0.8s · 14.7 |
| wordy         | 94% · 2.4s · 6.5  | 100% · 0.8s · 9.1 | 99% · 0.7s · 20.9  | 99% · 1.0s · 14.7  |
| book-store    | 99% · 1.0s · 8.1  | 100% · 0.8s · 9.2 | 100% · 0.9s · 19.2 | 87% · 6.4s · 13.8  |
| dominoes      | 99% · 0.8s · 8.6  | 100% · 0.8s · 8.9 | 100% · 0.9s · 18.0 | 100% · 0.9s · 14.1 |
| go-counting   | 99% · 0.8s · 8.6  | 99% · 1.4s · 8.2  | – · – · 0.1 (T)    | 95% · 3.5s · 13.5  |
`(x)` failed tests, `(T)` timed out — the numbers still describe the turns that happened.
