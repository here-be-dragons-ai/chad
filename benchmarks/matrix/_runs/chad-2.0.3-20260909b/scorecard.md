### Local-fitness scorecard — same weights, same laptop, same tasks

#### What it feels like

| Arm                 | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|---------------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| chad+llama          | 2,562                    | 15.7 s                        | 36                              | 0.8 s · 20 s                  | 99%         | 65                     | 7.8        | 8/8         |
| goose+llama         | 9,617                    | 9.5 s                         | 44                              | 1.0 s · 23 s                  | 100%        | 45                     | 8.2        | 6/8 T2      |
| chad+mlx *          | 2,562                    | 4.5 s †                       | 35                              | 0.9 s · 36 s                  | 99%         | 35                     | 16.5       | 7/8 T1      |
| chad+mlx-nodflash * | 2,566                    | 4.7 s †                       | 65                              | 1.1 s · 18 s                  | 99%         | 27                     | 12.4       | 6/8 T2      |

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
`*` in-process arm: the same fields from chad's own prefill trace, self-reported — no server saw it. `†` includes the system-prompt prefix chad prefills before its first step when its disk checkpoint misses, or restores when it hits (chad+mlx: partial, 3.3 s of it; chad+mlx-nodflash: partial, 3.5 s of it). A miss is the cold prefill of the same prompt the chad+llama row pays; a hit is a disk restore; a partial restores the project-independent head (tool schemas + behavioral prompt) from disk and prefills only the per-project tail.

#### Shape of the harness

| Arm                 | tools | system prompt (chars) | prefix churn | side requests (concurrent · abandoned) | round trips / task | model busy | prefill share | ctx at exit |
|---------------------|-------|-----------------------|--------------|----------------------------------------|--------------------|------------|---------------|-------------|
| chad+llama          | –     | –                     | –            | 0                                      | 6                  | 98%        | 16%           | 7,938       |
| goose+llama         | 18    | 23,924                | 0/40         | 8 (8 · 0)                              | 7                  | 107%       | 14%           | 14,513      |
| chad+mlx *          | –     | –                     | –            | 0                                      | 6                  | 93%        | 26%           | 6,946       |
| chad+mlx-nodflash * | –     | –                     | –            | 0                                      | 6                  | 96%        | 24%           | 7,498       |

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

Instrument check: the proxy's own first-byte stamp came back earlier than the server's `prompt_ms` on 5 of 107 requests (llama-server streams a first chunk before a long prefill finishes), so no time-to-first-byte column is printed; the server's prefill time is the wait.

#### Per task — cache reuse (median, agent turns 2+) · wait / later turn (median) · experienced tok/s

| Task          | chad+llama        | goose+llama           | chad+mlx           | chad+mlx-nodflash      |
|---------------|-------------------|-----------------------|--------------------|------------------------|
| bowling       | 100% · 1.0s · 8.8 | 100% · 1.1s · 7.6     | 100% · 0.9s · 16.9 | 100% · 1.8s · 13.7 (T) |
| grade-school  | 99% · 0.8s · 5.1  | 99% · 1.4s · 7.4      | 100% · 0.8s · 11.4 | 93% · 2.4s · 9.1       |
| affine-cipher | 99% · 0.8s · 6.3  | 100% · 1.2s · 7.7     | 99% · 1.2s · 13.3  | 99% · 0.9s · 11.3      |
| transpose     | 92% · 3.2s · 8.6  | 89% · 15.7s · 8.7 (T) | 83% · 7.4s · 16.2  | – · – · 0.1 (T)        |
| wordy         | 99% · 0.8s · 7.7  | 100% · 0.9s · 8.9     | 99% · 0.7s · 20.4  | 98% · 2.5s · 10.9      |
| book-store    | 90% · 4.0s · 9.4  | 99% · 1.4s · 8.9 (T)  | – · – · 0.1 (T)    | 99% · 0.9s · 13.9      |
| dominoes      | 99% · 0.7s · 5.8  | 100% · 0.8s · 8.7     | 99% · 0.9s · 18.8  | 100% · 0.6s · 15.2     |
| go-counting   | 99% · 1.1s · 8.0  | 99% · 2.2s · 7.8      | 99% · 0.9s · 19.5  | 98% · 1.8s · 13.6      |
`(x)` failed tests, `(T)` timed out — the numbers still describe the turns that happened.
