
### Harness x engine — same tasks, same weights, same laptop

| Arm                 | Passed | Tests   | Median wall (passed) | Total prefill | Total generated | Timeouts |
|---------------------|--------|---------|----------------------|---------------|-----------------|----------|
| chad+llama          | 8/8    | 148/148 | 372s                 | 45,832        | 24,213          | 0        |
| chad+mlx *          | 7/8    | 137/148 | 174s                 | 28,422        | 36,925          | 1        |
| chad+mlx-nodflash * | 8/8    | 148/148 | 217s                 | 34,655        | 32,673          | 0        |
| goose+llama         | 8/8    | 148/148 | 618s                 | 42,904        | 44,661          | 1        |

`*` token counts are the harness's own, not llama-server's: the MLX arm is in-process
and no server sees it. Cached tokens are subtracted so both columns mean the same thing.

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out)

| Task          | chad+llama | chad+mlx | chad+mlx-nodflash | goose+llama |
|---------------|------------|----------|-------------------|-------------|
| bowling       | 321        | 888      | 848               | 1200        |
| grade-school  | 200        | 77       | 148               | 176         |
| affine-cipher | 104        | 82       | 89                | 194         |
| transpose     | 967        | 322      | 512               | 993         |
| wordy         | 399        | 106      | 356               | 618         |
| book-store    | 293        | 174      | 195               | 960         |
| dominoes      | 372        | 459      | 217               | 534         |
| go-counting   | 410        | T 0/11   | 180               | 610         |
