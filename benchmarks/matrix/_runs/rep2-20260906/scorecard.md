### Local-fitness scorecard — same weights, same laptop, same tasks

#### What it feels like

| Arm                 | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|---------------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| pi+llama            | 2,008                    | 21.0 s                        | 36                              | 0.9 s · 21 s                  | 99%         | 43                     | 8.7        | 6/8 T2      |
| opencode+llama      | 18,046                   | 222.1 s                       | 36                              | 0.9 s · 35 s                  | 100%        | 359                    | 5.4        | 6/8 T4      |
| chad+llama          | 2,562                    | 26.5 s                        | 59                              | 1.1 s · 13 s                  | 99%         | 51                     | 7.2        | 8/8         |
| dsh+llama           | 8,052                    | 92.5 s                        | 93                              | 1.6 s · 31 s                  | 99%         | 126                    | 7.8        | 6/8         |
| goose+llama         | 9,576                    | 108.5 s                       | 1,945                           | 24.4 s · 48 s                 | 83%         | 190                    | 7.3        | 3/8         |
| mini+llama          | 1,171                    | 12.0 s                        | 539                             | 6.7 s · 27 s                  | 88%         | 32                     | 8.2        | 3/8 T5      |
| crush+llama         | 16,264                   | 195.1 s                       | 86                              | 1.7 s · 37 s                  | 100%        | 296                    | 5.3        | 8/8 T2      |
| cline+llama         | 5,875                    | 62.3 s                        | 1,129                           | 14.3 s · 53 s                 | 92%         | 118                    | 7.4        | 5/8         |
| codex+llama         | 7,803                    | 84.3 s                        | 545                             | 7.4 s · 24 s                  | 95%         | 114                    | 6.7        | 7/8 T1      |
| chad+mlx *          | 2,562                    | 25.3 s †                      | 112                             | 1.6 s · 22 s                  | 99%         | 51                     | 16.9       | 7/8 T1      |
| chad+mlx-nodflash * | 2,564                    | 25.3 s †                      | 48                              | 1.0 s · 18 s                  | 99%         | 53                     | 12.1       | 7/8 T1      |

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
`*` in-process arm: the same fields from chad's own prefill trace, self-reported — no server saw it. `†` includes the system-prompt prefix chad prefills before its first step when its disk checkpoint misses, or restores when it hits (chad+mlx: miss, 24.1 s of it; chad+mlx-nodflash: miss, 24.1 s of it). A miss is the cold prefill of the same prompt the chad+llama row pays; a hit is a disk restore.

#### Shape of the harness

| Arm                 | tools | system prompt (chars) | prefix churn | side requests (concurrent · abandoned) | round trips / task | model busy | prefill share | ctx at exit |
|---------------------|-------|-----------------------|--------------|----------------------------------------|--------------------|------------|---------------|-------------|
| pi+llama            | 4     | 4,052                 | 0/26         | 0                                      | 4                  | 98%        | 23%           | 5,664       |
| opencode+llama      | 10    | 49,078                | 0/20         | 10 (8 · 0)                             | 4                  | 117%       | 46%           | 23,296      |
| chad+llama          | –     | –                     | –            | 0                                      | 6                  | 97%        | 23%           | 6,000       |
| dsh+llama           | 25    | 4,188                 | 0/25         | 8 (8 · 8)                              | 4                  | 100%       | 16%           | 17,436      |
| goose+llama         | 18    | 23,829                | 0/23         | 8 (8 · 0)                              | 4                  | 43%        | 65%           | 11,772      |
| mini+llama          | 1     | 62                    | 0/26         | 0                                      | 4                  | 27%        | 34%           | 3,793       |
| crush+llama         | 26    | 37,456                | 0/34         | 17 (16 · 1)                            | 5                  | 115%       | 53%           | 21,660      |
| cline+llama         | 26    | 4,326                 | 0/27         | 0                                      | 5                  | 98%        | 16%           | 17,126      |
| codex+llama         | 10    | 20,751                | 0/22         | 0                                      | 4                  | 99%        | 35%           | 12,454      |
| chad+mlx *          | –     | –                     | –            | 0                                      | 6                  | 94%        | 33%           | 9,650       |
| chad+mlx-nodflash * | –     | –                     | –            | 0                                      | 6                  | 95%        | 26%           | 7,888       |

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

Instrument check: the proxy's own first-byte stamp came back earlier than the server's `prompt_ms` on 97 of 363 requests (llama-server streams a first chunk before a long prefill finishes), so no time-to-first-byte column is printed; the server's prefill time is the wait.

#### Per task — cache reuse (median, agent turns 2+) · wait / later turn (median) · experienced tok/s

| Task          | pi+llama              | opencode+llama        | chad+llama       | dsh+llama             | goose+llama           | mini+llama            | crush+llama        | cline+llama           | codex+llama       | chad+mlx              | chad+mlx-nodflash  |
|---------------|-----------------------|-----------------------|------------------|-----------------------|-----------------------|-----------------------|--------------------|-----------------------|-------------------|-----------------------|--------------------|
| bowling       | – · – · 8.5 (T)       | 78% · 73.5s · 6.2 (T) | 99% · 1.4s · 8.3 | 99% · 2.0s · 7.9      | 95% · 6.7s · 7.3 (x)  | 60% · 8.6s · 0.2 (T)  | 87% · 36.9s · 19.6 | 91% · 14.1s · 7.3     | 95% · 9.6s · 6.4  | 98% · 7.0s · 17.0 (T) | 99% · 2.9s · 13.1  |
| grade-school  | 99% · 0.8s · 6.0      | 100% · 0.9s · 4.5     | 88% · 4.9s · 5.2 | 99% · 1.6s · 5.0      | 71% · 47.7s · 3.3     | 99% · 1.1s · 7.4      | 100% · 1.7s · 3.8  | 95% · 6.4s · 5.4      | 96% · 5.2s · 4.5  | 98% · 1.6s · 8.5      | 99% · 0.9s · 6.3   |
| affine-cipher | 99% · 0.9s · 6.8      | 100% · 0.9s · 3.0     | 99% · 0.7s · 5.9 | 99% · 1.5s · 4.8      | 78% · 30.8s · 3.2     | 97% · 3.1s · 8.8      | 100% · 1.6s · 3.5  | 93% · 9.1s · 5.7      | 89% · 12.5s · 5.2 | 99% · 0.8s · 12.7     | 99% · 0.7s · 10.0  |
| transpose     | 100% · 0.8s · 9.4     | 91% · 23.0s · 6.2     | 99% · 1.0s · 9.0 | 91% · 11.0s · 8.4 (x) | 96% · 5.0s · 7.9 (x)  | 72% · 5.1s · 0.2 (T)  | 95% · 14.4s · 10.9 | 92% · 15.4s · 8.1     | 93% · 8.4s · 8.0  | 86% · 5.8s · 17.1     | – · – · 0.1 (T)    |
| wordy         | 100% · 0.9s · 9.0     | 89% · 34.9s · 5.8     | 99% · 0.7s · 7.3 | 99% · 1.8s · 7.9      | 95% · 6.4s · 7.5 (x)  | 68% · 6.7s · 10.4 (T) | 100% · 1.6s · 6.6  | 91% · 21.2s · 8.1 (x) | 88% · 14.6s · 7.0 | 100% · 1.0s · 14.9    | 100% · 1.0s · 12.3 |
| book-store    | 52% · 21.4s · 9.2 (T) | – · – · 6.9 (T)       | 99% · 0.7s · 7.6 | 76% · 31.2s · 8.1 (x) | 89% · 14.5s · 7.3 (x) | 58% · 10.5s · 7.7 (T) | 100% · 1.6s · 16.3 | 81% · 20.0s · 7.7 (x) | – · – · 8.4 (T)   | 99% · 1.9s · 20.1     | 83% · 9.3s · 12.6  |
| dominoes      | 99% · 1.1s · 9.0      | 100% · 0.9s · 4.4     | 89% · 4.1s · 7.1 | 99% · 1.5s · 6.4      | 76% · 36.6s · 4.4     | 95% · 6.8s · 8.7      | 100% · 1.7s · 3.2  | 97% · 4.4s · 6.8      | 97% · 4.1s · 5.0  | 95% · 2.2s · 17.2     | 100% · 1.2s · 12.2 |
| go-counting   | 94% · 3.0s · 8.1      | 99% · 3.7s · 5.0      | 91% · 3.6s · 6.6 | 99% · 1.6s · 7.7      | 97% · 4.7s · 7.3 (x)  | 39% · 22.0s · 9.1 (T) | 98% · 4.7s · 4.0   | 85% · 15.1s · 7.5 (x) | 90% · 12.0s · 7.1 | 99% · 1.2s · 16.9     | 99% · 0.9s · 12.0  |
`(x)` failed tests, `(T)` timed out — the numbers still describe the turns that happened.
