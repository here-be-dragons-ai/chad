from chad.engine import Engine
from chad.cli import _pick_model
import mlx.core as mx
mid, _ = _pick_model()
eng = Engine(model_id=mid, cache_dir=None)
eng.load()
eng.temp = 0.0
ids = eng.tok.apply_chat_template(
    [{"role": "user", "content": "Write a Python function that returns the sum of a list. Code only."}],
    add_generation_prompt=True, enable_thinking=False)
buf = []
eng.generate(list(ids), max_tokens=100, on_token=buf.append)
print("MLX", mx.__version__, "|", repr("".join(buf))[:600])
