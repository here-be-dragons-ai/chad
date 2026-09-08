
### Harness x engine — same tasks, same weights, same laptop

| Arm                 | Passed | Tests   | Median wall (passed) | Total prefill | Total generated | Timeouts |
|---------------------|--------|---------|----------------------|---------------|-----------------|----------|
| pi+llama            | 6/8    | 134/148 | 339s                 | 41,875        | 36,757          | 2        |
| opencode+llama      | 6/8    | 121/148 | 1062s                | 221,183?      | 41,082?         | 4        |
| chad+llama          | 7/8    | 143/148 | 228s                 | 65,628        | 25,484          | 1        |
| chad+mlx *          | 6/8    | 131/148 | 156s                 | 29,248        | 49,158          | 2        |
| chad+mlx-nodflash * | 7/8    | 128/148 | 444s                 | 32,374        | 52,605          | 1        |
| dsh+llama           | 6/8    | 97/148  | 595s                 | 97,844        | 39,434          | 0        |
| goose+llama         | 4/8    | 80/148  | 606s                 | 200,981?      | 33,475?         | 1        |
| mini+llama          | 4/8    | 74/148  | 614s                 | 48,395?       | 51,587?         | 5        |
| crush+llama         | 5/8    | 99/148  | 707s                 | 208,440?      | 71,111?         | 3        |
| cline+llama         | 6/8    | 102/148 | 958s                 | 105,721       | 49,407          | 0        |
| codex+llama         | 6/8    | 97/148  | 505s                 | 92,283        | 40,630          | 2        |

`*` token counts are the harness's own, not llama-server's: the MLX arm is in-process
and no server sees it. Cached tokens are subtracted so both columns mean the same thing.
`?` the server was still busy when this arm's counters were read — treat the count as a floor.

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out)

| Task          | pi+llama | opencode+llama | chad+llama | chad+mlx | chad+mlx-nodflash | dsh+llama | goose+llama | mini+llama | crush+llama | cline+llama | codex+llama |
|---------------|----------|----------------|------------|----------|-------------------|-----------|-------------|------------|-------------|-------------|-------------|
| bowling       | 742      | T 7/31         | 826        | T 18/31  | 903               | x 0/31    | x 0/31      | T 0/31     | T 0/31      | x 5/31      | T 0/31      |
| grade-school  | 122      | 383            | 123        | 79       | 474               | 285       | 546         | 360        | 384         | 265         | 182         |
| affine-cipher | 143      | 406            | 117        | 156      | 125               | 344       | 555         | 614        | 450         | 319         | 218         |
| transpose     | T 0/12   | T 9/12         | T 7/12     | T 8/12   | 350               | 1112      | x 0/12      | T 0/12     | T 0/12      | 958         | 1075        |
| wordy         | 470      | 1200           | 318        | 233      | 444               | 741       | 966         | 607        | 751         | 1160        | 438         |
| book-store    | T 18/20  | 1200           | 622        | 142      | T 0/20            | x 0/20    | x 0/20      | T 0/20     | 1071        | x 0/20      | T 0/20      |
| dominoes      | 279      | 1062           | 162        | 152      | 449               | 313       | T 8/13      | 1200       | 707         | 1128        | 797         |
| go-counting   | 339      | 724            | 228        | 159      | 233               | 595       | 606         | T 0/11     | T 5/11      | 571         | 505         |
