### Local-fitness scorecard — same weights, same laptop, same tasks

#### What it feels like

| Arm         | tax: turn-1 prompt (tok) | wait before 1st token, turn 1 | uncached tok / later turn (med) | wait / later turn (med · p90) | cache reuse | prefill s / task (med) | exp. tok/s | pass (gate) |
|-------------|--------------------------|-------------------------------|---------------------------------|-------------------------------|-------------|------------------------|------------|-------------|
| goose+llama | 9,617                    | 10.0 s                        | 57                              | 1.4 s · 22 s                  | 100%        | 46                     | 8.0        | 5/8 T3      |

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

#### Shape of the harness

| Arm         | tools | system prompt (chars) | prefix churn | side requests (concurrent · abandoned) | round trips / task | model busy | prefill share | ctx at exit |
|-------------|-------|-----------------------|--------------|----------------------------------------|--------------------|------------|---------------|-------------|
| goose+llama | 18    | 23,924                | 0/36         | 8 (8 · 0)                              | 6                  | 106%       | 14%           | 15,739      |

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

Instrument check: the proxy's own first-byte stamp came back earlier than the server's `prompt_ms` on 3 of 52 requests (llama-server streams a first chunk before a long prefill finishes), so no time-to-first-byte column is printed; the server's prefill time is the wait.

#### Per task — cache reuse (median, agent turns 2+) · wait / later turn (median) · experienced tok/s

| Task          | goose+llama           |
|---------------|-----------------------|
| bowling       | – · – · 7.6 (T)       |
| grade-school  | 99% · 1.5s · 7.1      |
| affine-cipher | 100% · 1.0s · 7.5     |
| transpose     | 99% · 1.7s · 8.4 (T)  |
| wordy         | 100% · 0.9s · 8.3     |
| book-store    | 100% · 1.5s · 8.4 (T) |
| dominoes      | 99% · 1.1s · 8.1      |
| go-counting   | 99% · 1.8s · 7.9      |
`(x)` failed tests, `(T)` timed out — the numbers still describe the turns that happened.
