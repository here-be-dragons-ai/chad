
### Harness x engine — same tasks, same weights, same laptop — 3 nights, chad-2.0.3-20260909, chad-2.0.3-20260909b, chad-2.0.3-20260910

| Arm                 | Passed | Tests   | Median wall (passed) | Total prefill | Total generated | Timeouts |
|---------------------|--------|---------|----------------------|---------------|-----------------|----------|
| chad+llama          | 24/24  | 444/444 | 324s                 | 119,076       | 77,819          | 0        |
| chad+mlx *          | 22/24  | 413/444 | 227s                 | 118,975       | 122,380         | 3        |
| chad+mlx-nodflash * | 21/24  | 419/444 | 207s                 | 93,969        | 100,249         | 3        |
| goose+llama         | 22/24  | 412/444 | 545s                 | 120,307       | 125,649         | 3        |

`*` token counts are the harness's own, not llama-server's: the MLX arm is in-process
and no server sees it. Cached tokens are subtracted so both columns mean the same thing.

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out; one entry per night, in order)

| Task          | chad+llama       | chad+mlx           | chad+mlx-nodflash     | goose+llama        |
|---------------|------------------|--------------------|-----------------------|--------------------|
| bowling       | 651 · 709 · 321  | 1200 · 495 · 888   | 1083 · T 30/31 · 848  | 1099 · 1108 · 1200 |
| grade-school  | 185 · 159 · 200  | 54 · 82 · 77       | 64 · 72 · 148         | 213 · 186 · 176    |
| affine-cipher | 259 · 100 · 104  | 84 · 60 · 82       | 111 · 89 · 89         | 223 · 258 · 194    |
| transpose     | 651 · 1131 · 967 | 383 · 1100 · 322   | T 0/12 · T 0/12 · 512 | 653 · T 0/12 · 993 |
| wordy         | 324 · 400 · 399  | 227 · 271 · 106    | 502 · 458 · 356       | 545 · 985 · 618    |
| book-store    | 543 · 750 · 293  | 398 · T 0/20 · 174 | 110 · 209 · 195       | 526 · T 0/20 · 960 |
| dominoes      | 148 · 176 · 372  | 233 · 114 · 459    | 655 · 333 · 217       | 197 · 465 · 534    |
| go-counting   | 166 · 185 · 410  | 79 · 110 · T 0/11  | 207 · 158 · 180       | 408 · 592 · 610    |
