
### Harness x engine — same tasks, same weights, same laptop

| Arm                 | Passed | Tests   | Median wall (passed) | Total prefill | Total generated | Timeouts |
|---------------------|--------|---------|----------------------|---------------|-----------------|----------|
| pi+llama            | 6/8    | 97/148  | 712s                 | 34,037        | 48,703          | 2        |
| opencode+llama      | 6/8    | 97/148  | 589s                 | 194,664?      | 39,040?         | 4        |
| chad+llama          | 8/8    | 148/148 | 239s                 | 49,643?       | 22,814?         | 0        |
| chad+mlx *          | 7/8    | 144/148 | 158s                 | 33,357        | 59,387          | 1        |
| chad+mlx-nodflash * | 7/8    | 136/148 | 349s                 | 28,491        | 32,043          | 1        |
| dsh+llama           | 6/8    | 116/148 | 759s                 | 89,588        | 43,870          | 0        |
| goose+llama         | 3/8    | 49/148  | 408s                 | 135,986       | 35,079          | 0        |
| mini+llama          | 3/8    | 57/148  | 778s                 | 55,895?       | 49,808?         | 5        |
| crush+llama         | 8/8    | 148/148 | 626s                 | 205,003?      | 58,690?         | 2        |
| cline+llama         | 5/8    | 106/148 | 390s                 | 105,105?      | 50,703?         | 0        |
| codex+llama         | 7/8    | 128/148 | 469s                 | 86,835        | 30,631          | 1        |

`*` token counts are the harness's own, not llama-server's: the MLX arm is in-process
and no server sees it. Cached tokens are subtracted so both columns mean the same thing.
`?` the server was still busy when this arm's counters were read — treat the count as a floor.

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out)

| Task          | pi+llama | opencode+llama | chad+llama | chad+mlx | chad+mlx-nodflash | dsh+llama | goose+llama | mini+llama | crush+llama | cline+llama | codex+llama |
|---------------|----------|----------------|------------|----------|-------------------|-----------|-------------|------------|-------------|-------------|-------------|
| bowling       | T 0/31   | T 0/31         | 932        | T 27/31  | 912               | 975       | x 0/31      | T 0/31     | 1200        | 1171        | 645         |
| grade-school  | 152      | 577            | 127        | 78       | 85                | 310       | 461         | 209        | 448         | 252         | 228         |
| affine-cipher | 147      | 378            | 185        | 92       | 123               | 260       | 400         | 964        | 372         | 256         | 254         |
| transpose     | 882      | 1200           | 777        | 485      | T 0/12            | x 0/12    | x 0/12      | T 0/12     | 1200        | 1171        | 643         |
| wordy         | 712      | 1200           | 280        | 382      | 437               | 1035      | x 0/25      | T 0/25     | 889         | x 11/25     | 606         |
| book-store    | T 0/20   | T 0/20         | 239        | 895      | 349               | x 0/20    | x 0/20      | T 0/20     | 626         | x 3/20      | T 0/20      |
| dominoes      | 958      | 513            | 192        | 158      | 516               | 410       | 408         | 778        | 370         | 390         | 272         |
| go-counting   | 282      | 589            | 163        | 148      | 178               | 759       | x 0/11      | T 8/11     | 428         | x 0/11      | 469         |
