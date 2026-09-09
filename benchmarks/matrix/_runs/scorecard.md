### Local-fitness scorecard — same weights, same laptop, same tasks

#### What it feels like

| Arm                 | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|---------------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| pi+llama            | 2,008                    | 21.6 s                        | 64                              | 1.3 s · 22 s                  | 99%         | 45                     | 8.1        | 19/24 T7    |
| opencode+llama      | 18,046                   | 225.7 s                       | 305                             | 4.6 s · 44 s                  | 99%         | 383                    | 5.7        | 15/24 T13   |
| chad+llama          | 2,562                    | 27.2 s                        | 54                              | 1.1 s · 20 s                  | 99%         | 52                     | 6.9        | 22/24 T2    |
| dsh+llama           | 8,052                    | 94.4 s                        | 110                             | 2.2 s · 34 s                  | 99%         | 133                    | 7.2        | 18/24       |
| goose+llama         | 9,576                    | 112.7 s                       | 2,537                           | 33.2 s · 78 s                 | 78%         | 300                    | 5.0        | 13/24 T5    |
| mini+llama          | 1,171                    | 12.2 s                        | 248                             | 3.6 s · 21 s                  | 96%         | 46                     | 8.0        | 11/24 T14   |
| crush+llama         | 16,263                   | 199.8 s                       | 87                              | 1.8 s · 40 s                  | 100%        | 306                    | 5.8        | 18/24 T8    |
| cline+llama         | 5,876                    | 64.1 s                        | 789                             | 9.9 s · 52 s                  | 94%         | 137                    | 7.3        | 17/24       |
| codex+llama         | 7,804                    | 87.8 s                        | 690                             | 9.6 s · 28 s                  | 94%         | 118                    | 6.9        | 19/24 T5    |
| chad+mlx *          | 2,562                    | 25.3 s †                      | 44                              | 1.0 s · 21 s                  | 99%         | 51                     | 16.0       | 21/24 T4    |
| chad+mlx-nodflash * | 2,564                    | 25.3 s †                      | 48                              | 1.1 s · 18 s                  | 99%         | 53                     | 12.1       | 20/24 T4    |

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
`*` in-process arm: the same fields from chad's own prefill trace, self-reported — no server saw it. `†` includes the system-prompt prefix chad prefills before its first step when its disk checkpoint misses, or restores when it hits (chad+mlx: miss, 24.1 s of it; chad+mlx-nodflash: miss, 24.1 s of it). A miss is the cold prefill of the same prompt the chad+llama row pays; a hit is a disk restore; a partial restores the project-independent head (tool schemas + behavioral prompt) from disk and prefills only the per-project tail. The turn-1 wait and prefill columns of those rows are over the cells whose trace recorded the prefix (chad+mlx 16/24; chad+mlx-nodflash 16/24); the rest of the row, and the pass gate, are over every cell.

#### Shape of the harness

| Arm                 | tools | system prompt (chars) | prefix churn | side requests (concurrent · abandoned) | round trips / task | model busy | prefill share | ctx at exit |
|---------------------|-------|-----------------------|--------------|----------------------------------------|--------------------|------------|---------------|-------------|
| pi+llama            | 4     | 4,052                 | 0/82         | 0                                      | 5                  | 98%        | 15%           | 6,270       |
| opencode+llama      | 10    | 49,078                | 0/58         | 33 (24 · 4)                            | 4                  | 125%       | 43%           | 23,296      |
| chad+llama          | –     | –                     | –            | 0                                      | 6                  | 97%        | 21%           | 6,863       |
| dsh+llama           | 25    | 4,188                 | 0/83         | 24 (24 · 24)                           | 4                  | 99%        | 18%           | 16,361      |
| goose+llama         | 18    | 23,829                | 0/82         | 24 (24 · 0)                            | 6                  | 102%       | 61%           | 13,344      |
| mini+llama          | 1     | 62                    | 0/108        | 0                                      | 4                  | 52%        | 14%           | 6,950       |
| crush+llama         | 26    | 37,456                | 0/99         | 51 (49 · 2)                            | 6                  | 114%       | 47%           | 22,062      |
| cline+llama         | 26    | 4,326                 | 0/97         | 0                                      | 5                  | 99%        | 22%           | 15,232      |
| codex+llama         | 10    | 20,751                | 0/61         | 0                                      | 4                  | 98%        | 35%           | 12,210      |
| chad+mlx *          | –     | –                     | –            | 0                                      | 6                  | 95%        | 31%           | 8,926       |
| chad+mlx-nodflash * | –     | –                     | –            | 0                                      | 6                  | 98%        | 21%           | 8,954       |

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

Instrument check: the proxy's own first-byte stamp came back earlier than the server's `prompt_ms` on 331 of 1130 requests (llama-server streams a first chunk before a long prefill finishes), so no time-to-first-byte column is printed; the server's prefill time is the wait.

#### Per task — cache reuse (median, agent turns 2+) · wait / later turn (median) · experienced tok/s

| Task          | pi+llama              | opencode+llama        | chad+llama            | dsh+llama             | goose+llama           | mini+llama            | crush+llama            | cline+llama           | codex+llama           | chad+mlx               | chad+mlx-nodflash      |
|---------------|-----------------------|-----------------------|-----------------------|-----------------------|-----------------------|-----------------------|------------------------|-----------------------|-----------------------|------------------------|------------------------|
| bowling       | 99% · 1.4s · 8.2      | 78% · 72.3s · 6.3 (T) | 100% · 0.9s · 6.8     | 80% · 32.3s · 7.6 (x) | 95% · 7.1s · 6.8 (x)  | – · – · 5.7 (T)       | 76% · 72.2s · 13.4 (T) | 92% · 13.9s · 7.5 (x) | 81% · 27.3s · 7.8 (T) | 99% · 1.6s · 12.2 (T)  | 99% · 2.4s · 12.7      |
| grade-school  | 99% · 0.8s · 5.5      | 100% · 0.9s · 2.4     | 99% · 0.7s · 5.0      | 99% · 2.2s · 4.6      | 71% · 47.1s · 3.3     | 98% · 1.5s · 7.9      | 100% · 1.7s · 3.0      | 95% · 6.6s · 5.1      | 89% · 14.1s · 3.1     | 99% · 0.9s · 9.5       | 96% · 3.1s · 9.5       |
| affine-cipher | 99% · 0.8s · 6.2      | 100% · 0.9s · 3.0     | 99% · 0.7s · 5.2      | 94% · 9.6s · 5.3      | 81% · 29.6s · 4.2     | 98% · 1.8s · 8.4      | 100% · 1.7s · 3.2      | 96% · 4.6s · 5.7      | 99% · 1.6s · 4.0      | 100% · 0.8s · 8.9      | 99% · 0.9s · 9.8       |
| transpose     | – · – · 9.0 (T)       | 96% · 13.0s · 6.7 (T) | 66% · 19.9s · 7.8 (T) | 82% · 21.6s · 7.2     | – · – · 7.3 (x)       | 72% · 5.5s · 7.8 (T)  | 90% · 26.7s · 11.8 (T) | 96% · 5.9s · 7.2      | 93% · 8.3s · 7.4      | 80% · 11.0s · 17.3 (T) | 99% · 1.4s · 13.8      |
| wordy         | 100% · 0.8s · 8.5     | 89% · 32.3s · 5.5     | 98% · 1.8s · 7.7      | 99% · 1.6s · 7.5      | 61% · 72.3s · 4.8     | 99% · 1.3s · 8.7      | 100% · 1.7s · 5.7      | 71% · 29.3s · 7.4     | 92% · 10.1s · 6.8     | 100% · 0.9s · 19.5     | 99% · 1.2s · 12.7      |
| book-store    | 100% · 0.9s · 7.9 (T) | 93% · 20.5s · 5.6     | 98% · 3.9s · 6.8      | 76% · 32.0s · 7.9 (x) | 96% · 5.4s · 7.3 (x)  | 57% · 10.7s · 0.2 (T) | 100% · 1.7s · 21.4     | 68% · 34.1s · 8.3 (x) | – · – · 8.1 (T)       | 100% · 0.8s · 11.0     | 58% · 19.4s · 14.1 (T) |
| dominoes      | 99% · 0.8s · 7.9      | 90% · 25.0s · 5.9     | 99% · 0.9s · 6.2      | 99% · 1.6s · 5.3      | 58% · 84.5s · 4.8 (T) | 98% · 3.1s · 8.9      | 100% · 1.7s · 5.8      | 95% · 9.9s · 7.5      | 85% · 18.6s · 7.0     | 99% · 0.9s · 16.1      | 95% · 3.1s · 10.8      |
| go-counting   | 96% · 2.4s · 8.0      | 94% · 16.8s · 5.1     | 99% · 0.8s · 7.0      | 98% · 2.8s · 7.1      | 78% · 32.3s · 4.8     | 34% · 22.8s · 9.3 (T) | 99% · 2.8s · 5.8 (T)   | 84% · 16.5s · 6.6     | 90% · 11.8s · 7.1     | 99% · 0.9s · 19.9      | 94% · 2.4s · 13.3      |
`(x)` failed tests, `(T)` timed out — the numbers still describe the turns that happened.
