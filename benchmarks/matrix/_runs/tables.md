
### Harness x engine — same tasks, same weights, same laptop — 2 nights, rep1-20260901, rep2-20260906

| Arm                 | Passed | Tests   | Median wall (passed) | Total prefill | Total generated | Timeouts |
|---------------------|--------|---------|----------------------|---------------|-----------------|----------|
| pi+llama            | 13/16  | 225/296 | 388s                 | 75,668        | 91,025          | 5        |
| opencode+llama      | 9/16   | 179/296 | 577s                 | 371,163?      | 81,897?         | 9        |
| chad+llama          | 15/16  | 289/296 | 280s                 | 93,869?       | 51,496?         | 1        |
| chad+mlx *          | 15/16  | 292/296 | 297s                 | 69,355        | 108,652         | 2        |
| chad+mlx-nodflash * | 13/16  | 233/296 | 310s                 | 46,633        | 52,175          | 3        |
| dsh+llama           | 12/16  | 221/296 | 528s                 | 183,154       | 84,396          | 0        |
| goose+llama         | 9/16   | 141/296 | 587s                 | 320,124?      | 74,193?         | 4        |
| mini+llama          | 7/16   | 144/296 | 745s                 | 122,130?      | 92,176?         | 9        |
| crush+llama         | 13/16  | 236/296 | 580s                 | 383,680?      | 122,591?        | 5        |
| cline+llama         | 11/16  | 222/296 | 549s                 | 200,619?      | 102,492?        | 0        |
| codex+llama         | 13/16  | 225/296 | 379s                 | 175,448       | 67,153          | 3        |

`*` token counts are the harness's own, not llama-server's: the MLX arm is in-process
and no server sees it. Cached tokens are subtracted so both columns mean the same thing.
`?` the server was still busy when this arm's counters were read — treat the count as a floor.

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out; one entry per night, in order)

| Task          | pi+llama        | opencode+llama  | chad+llama    | chad+mlx      | chad+mlx-nodflash | dsh+llama       | goose+llama     | mini+llama      | crush+llama   | cline+llama     | codex+llama     |
|---------------|-----------------|-----------------|---------------|---------------|-------------------|-----------------|-----------------|-----------------|---------------|-----------------|-----------------|
| bowling       | 1200 · T 0/31   | T 9/31 · T 0/31 | 825 · 932     | 955 · T 27/31 | T 0/31 · 912      | x 0/31 · 975    | x 0/31 · x 0/31 | T 0/31 · T 0/31 | T 0/31 · 1200 | 1171 · 1171     | T 0/31 · 645    |
| grade-school  | 141 · 152       | 408 · 577       | 111 · 127     | 70 · 78       | 97 · 85           | 289 · 310       | 395 · 461       | 398 · 209       | 349 · 448     | 339 · 252       | 247 · 228       |
| affine-cipher | 148 · 147       | 446 · 378       | 110 · 185     | 90 · 92       | 256 · 123         | 463 · 260       | 587 · 400       | 818 · 964       | 453 · 372     | 462 · 256       | 274 · 254       |
| transpose     | 1200 · 882      | T 0/12 · 1200   | 736 · 777     | 589 · 485     | 401 · T 0/12      | x 0/12 · x 0/12 | 1200 · x 0/12   | T 9/12 · T 0/12 | T 8/12 · 1200 | x 0/12 · 1171   | 1021 · 643      |
| wordy         | 655 · 712       | T 24/25 · 1200  | 375 · 280     | 124 · 382     | 316 · 437         | 1086 · 1035     | x 0/25 · x 0/25 | 725 · T 0/25    | T 0/25 · 889  | 1073 · x 11/25  | 645 · 606       |
| book-store    | T 0/20 · T 0/20 | T 0/20 · T 0/20 | T 13/20 · 239 | 852 · 895     | T 0/20 · 349      | 955 · x 0/20    | 1200 · x 0/20   | T 0/20 · T 0/20 | 1124 · 626    | x 0/20 · x 3/20 | T 0/20 · T 0/20 |
| dominoes      | 326 · 958       | 596 · 513       | 284 · 192     | 297 · 158     | 300 · 516         | 390 · 410       | 1200 · 408      | T 6/13 · 778    | 580 · 370     | 1171 · 390      | 341 · 272       |
| go-counting   | 388 · 282       | T 0/11 · 589    | 419 · 163     | 1200 · 148    | 310 · 178         | 528 · 759       | 1200 · x 0/11   | 745 · T 8/11    | 591 · 428     | 549 · x 0/11    | 379 · 469       |
