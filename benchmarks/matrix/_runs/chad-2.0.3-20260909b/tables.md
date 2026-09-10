
### Harness x engine — same tasks, same weights, same laptop

| Arm                 | Passed | Tests   | Median wall (passed) | Total prefill | Total generated | Timeouts |
|---------------------|--------|---------|----------------------|---------------|-----------------|----------|
| chad+llama          | 8/8    | 148/148 | 400s                 | 37,516        | 29,953          | 0        |
| chad+mlx *          | 7/8    | 128/148 | 114s                 | 40,005        | 37,880          | 1        |
| chad+mlx-nodflash * | 6/8    | 135/148 | 209s                 | 31,047        | 33,320          | 2        |
| goose+llama         | 6/8    | 116/148 | 592s                 | 37,950        | 50,371          | 2        |

`*` token counts are the harness's own, not llama-server's: the MLX arm is in-process
and no server sees it. Cached tokens are subtracted so both columns mean the same thing.

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out)

| Task          | chad+llama | chad+mlx | chad+mlx-nodflash | goose+llama |
|---------------|------------|----------|-------------------|-------------|
| bowling       | 709        | 495      | T 30/31           | 1108        |
| grade-school  | 159        | 82       | 72                | 186         |
| affine-cipher | 100        | 60       | 89                | 258         |
| transpose     | 1131       | 1100     | T 0/12            | T 0/12      |
| wordy         | 400        | 271      | 458               | 985         |
| book-store    | 750        | T 0/20   | 209               | T 0/20      |
| dominoes      | 176        | 114      | 333               | 465         |
| go-counting   | 185        | 110      | 158               | 592         |
