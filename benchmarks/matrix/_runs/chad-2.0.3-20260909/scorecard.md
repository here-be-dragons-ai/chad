### Local-fitness scorecard — same weights, same laptop, same tasks

#### What it feels like

| Arm                 | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|---------------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| chad+llama          | 2,562                    | 25.6 s                        | 36                              | 0.8 s · 14 s                  | 99%         | 58                     | 7.8        | 8/8         |
| goose+llama         | 9,617                    | 9.5 s                         | 52                              | 1.4 s · 21 s                  | 100%        | 46                     | 7.9        | 8/8         |
| chad+mlx *          | 2,562                    | 4.6 s †                       | 35                              | 1.0 s · 41 s                  | 99%         | 28                     | 17.7       | 8/8 T1      |
| chad+mlx-nodflash * | 2,566                    | 4.7 s †                       | 35                              | 0.9 s · 17 s                  | 99%         | 27                     | 12.3       | 7/8 T1      |

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
`*` in-process arm: the same fields from chad's own prefill trace, self-reported — no server saw it. `†` includes the system-prompt prefix chad prefills before its first step when its disk checkpoint misses, or restores when it hits (chad+mlx: miss/partial, 3.4 s of it; chad+mlx-nodflash: partial, 3.5 s of it). A miss is the cold prefill of the same prompt the chad+llama row pays; a hit is a disk restore; a partial restores the project-independent head (tool schemas + behavioral prompt) from disk and prefills only the per-project tail.

#### Shape of the harness

| Arm                 | tools | system prompt (chars) | prefix churn | side requests (concurrent · abandoned) | round trips / task | model busy | prefill share | ctx at exit |
|---------------------|-------|-----------------------|--------------|----------------------------------------|--------------------|------------|---------------|-------------|
| chad+llama          | –     | –                     | –            | 0                                      | 8                  | 98%        | 18%           | 8,816       |
| goose+llama         | 18    | 23,924                | 0/44         | 8 (8 · 0)                              | 6                  | 116%       | 16%           | 16,208      |
| chad+mlx *          | –     | –                     | –            | 0                                      | 5                  | 96%        | 27%           | 8,882       |
| chad+mlx-nodflash * | –     | –                     | –            | 0                                      | 6                  | 94%        | 19%           | 6,678       |

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

Instrument check: the proxy's own first-byte stamp came back earlier than the server's `prompt_ms` on 3 of 125 requests (llama-server streams a first chunk before a long prefill finishes), so no time-to-first-byte column is printed; the server's prefill time is the wait.

#### Per task — cache reuse (median, agent turns 2+) · wait / later turn (median) · experienced tok/s

| Task          | chad+llama        | goose+llama       | chad+mlx           | chad+mlx-nodflash  |
|---------------|-------------------|-------------------|--------------------|--------------------|
| bowling       | 99% · 0.8s · 8.9  | 100% · 1.6s · 7.2 | 91% · 18.1s · 14.3 | 100% · 1.1s · 12.4 |
| grade-school  | 99% · 1.1s · 6.3  | 99% · 1.6s · 7.2  | 99% · 0.9s · 9.8   | 99% · 0.9s · 8.1   |
| affine-cipher | 90% · 11.3s · 6.2 | 100% · 0.9s · 7.4 | 94% · 3.8s · 16.5  | 99% · 0.9s · 12.3  |
| transpose     | 99% · 0.8s · 8.1  | 100% · 0.8s · 8.8 | 100% · 1.0s · 22.7 | – · – · 0.1 (T)    |
| wordy         | 99% · 0.8s · 7.7  | 100% · 1.5s · 8.0 | 97% · 2.9s · 17.5  | 95% · 4.6s · 14.1  |
| book-store    | 100% · 1.1s · 9.2 | 96% · 5.9s · 8.7  | 90% · 4.1s · 23.4  | 90% · 3.8s · 12.2  |
| dominoes      | 97% · 1.7s · 6.9  | 100% · 0.8s · 7.8 | 100% · 0.6s · 21.8 | 100% · 0.9s · 11.3 |
| go-counting   | 96% · 2.4s · 7.9  | 100% · 0.8s · 7.9 | 91% · 3.4s · 17.9  | 100% · 0.7s · 14.4 |
`(x)` failed tests, `(T)` timed out — the numbers still describe the turns that happened.
