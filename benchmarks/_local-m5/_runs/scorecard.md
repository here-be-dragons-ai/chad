### Local-fitness scorecard — same weights, same laptop, same tasks

#### What it feels like

| Arm             | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|-----------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| pi+m532         | 11,010                   | 24.6 s                        | 532                             | 1.6 s · 5 s                   | 96%         | 33                     | 18.2       | 5/8         |
| pi+m532-lean    | 3,499                    | 7.9 s                         | 952                             | 2.6 s · 5 s                   | 83%         | 19                     | 20.2       | 7/8         |
| chad+mlx *      | 2,566                    | 1.4 s †                       | 70                              | 0.6 s · 5 s                   | 99%         | 16                     | 26.3       | 8/8         |
| chad+mlx-4bit * | 2,606                    | 1.4 s †                       | 55                              | 0.5 s · 4 s                   | 99%         | 9                      | 27.9       | 8/8         |

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
`*` in-process arm: the same fields from chad's own prefill trace, self-reported — no server saw it. `†` includes the system-prompt prefix chad prefills before its first step when its disk checkpoint misses, or restores when it hits (chad+mlx: partial, 0.9 s of it; chad+mlx-4bit: partial, 0.9 s of it). A miss is the cold prefill of the same prompt the chad+llama row pays; a hit is a disk restore; a partial restores the project-independent head (tool schemas + behavioral prompt) from disk and prefills only the per-project tail.

#### Shape of the harness

| Arm             | tools | system prompt (chars) | prefix churn | side requests (concurrent · abandoned) | round trips / task | model busy | prefill share | ctx at exit |
|-----------------|-------|-----------------------|--------------|----------------------------------------|--------------------|------------|---------------|-------------|
| pi+m532         | 22    | 11,238                | 0/32         | 0                                      | 4                  | 99%        | 28%           | 15,767      |
| pi+m532-lean    | 4     | 7,814                 | 0/30         | 0                                      | 4                  | 99%        | 21%           | 7,958       |
| chad+mlx *      | –     | –                     | –            | 0                                      | 8                  | 97%        | 7%            | 14,304      |
| chad+mlx-4bit * | –     | –                     | –            | 0                                      | 8                  | 94%        | 14%           | 7,009       |

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

Instrument check: the proxy's own first-byte stamp came back earlier than the server's `prompt_ms` on 0 of 78 requests (llama-server streams a first chunk before a long prefill finishes), so no time-to-first-byte column is printed; the server's prefill time is the wait.

#### Per task — cache reuse (median, agent turns 2+) · wait / later turn (median) · experienced tok/s

| Task          | pi+m532               | pi+m532-lean          | chad+mlx           | chad+mlx-4bit      |
|---------------|-----------------------|-----------------------|--------------------|--------------------|
| bowling       | 73% · 9.4s · 18.7 (x) | 68% · 4.7s · 22.5 (x) | 100% · 0.5s · 40.6 | 100% · 0.6s · 32.4 |
| grade-school  | 98% · 0.8s · 11.9     | 95% · 0.8s · 17.0     | 99% · 0.4s · 23.6  | 99% · 0.4s · 24.6  |
| affine-cipher | 97% · 1.2s · 13.4     | 93% · 1.1s · 20.8     | 92% · 2.5s · 28.1  | 99% · 0.4s · 30.7  |
| transpose     | 91% · 2.7s · 18.8 (x) | 83% · 2.6s · 20.5     | 90% · 1.5s · 29.7  | 99% · 0.4s · 31.6  |
| wordy         | 93% · 2.5s · 18.7     | 82% · 2.7s · 19.9     | 99% · 0.8s · 26.8  | 100% · 0.5s · 27.2 |
| book-store    | 91% · 4.5s · 17.8     | 83% · 2.6s · 19.9     | 99% · 0.6s · 25.7  | 90% · 1.1s · 28.7  |
| dominoes      | 97% · 1.3s · 14.9     | 94% · 1.0s · 12.9     | 99% · 0.6s · 25.3  | 98% · 0.6s · 24.7  |
| go-counting   | 97% · 1.3s · 19.3 (x) | 81% · 2.4s · 23.7     | 100% · 0.8s · 21.7 | 98% · 0.8s · 22.6  |
`(x)` failed tests, `(T)` timed out — the numbers still describe the turns that happened.
