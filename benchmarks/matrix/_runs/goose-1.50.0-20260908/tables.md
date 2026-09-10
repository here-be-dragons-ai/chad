
### Harness x engine — same tasks, same weights, same laptop

| Arm         | Passed | Tests  | Median wall (passed) | Total prefill | Total generated | Timeouts |
|-------------|--------|--------|----------------------|---------------|-----------------|----------|
| goose+llama | 5/8    | 96/148 | 455s                 | 40,441        | 51,272          | 3        |

Sampler, forced identically on every arm (proxy for the llama arms, `CHAD_*` for the
MLX arms, cross-checked): min_p 0.05, presence_penalty 0.0, repeat_penalty 1.0, temperature 1.0, top_k 20, top_p 0.95

### Per task (wall seconds if passed; otherwise tests passed, `T` = timed out)

| Task          | goose+llama |
|---------------|-------------|
| bowling       | T 0/31      |
| grade-school  | 173         |
| affine-cipher | 331         |
| transpose     | T 11/12     |
| wordy         | 779         |
| book-store    | T 0/20      |
| dominoes      | 455         |
| go-counting   | 1031        |
