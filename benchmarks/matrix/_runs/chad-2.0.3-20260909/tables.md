
### Harness x engine — same tasks, same weights, same laptop

| Arm                 | Passed | Tests   | Median wall (passed) | Total prefill | Total generated | Timeouts |
|---------------------|--------|---------|----------------------|---------------|-----------------|----------|
| chad+llama          | 8/8    | 148/148 | 324s                 | 35,728        | 23,653          | 0        |
| chad+mlx *          | 8/8    | 148/148 | 233s                 | 50,548        | 47,575          | 1        |
| chad+mlx-nodflash * | 7/8    | 136/148 | 207s                 | 28,267        | 34,256          | 1        |
| goose+llama         | 8/8    | 148/148 | 526s                 | 39,453        | 30,617          | 0        |

`*` token counts are the harness's own, not llama-server's: the MLX arm is in-process
and no server sees it. Cached tokens are subtracted so both columns mean the same thing.

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out)

| Task          | chad+llama | chad+mlx | chad+mlx-nodflash | goose+llama |
|---------------|------------|----------|-------------------|-------------|
| bowling       | 651        | 1200     | 1083              | 1099        |
| grade-school  | 185        | 54       | 64                | 213         |
| affine-cipher | 259        | 84       | 111               | 223         |
| transpose     | 651        | 383      | T 0/12            | 653         |
| wordy         | 324        | 227      | 502               | 545         |
| book-store    | 543        | 398      | 110               | 526         |
| dominoes      | 148        | 233      | 655               | 197         |
| go-counting   | 166        | 79       | 207               | 408         |
