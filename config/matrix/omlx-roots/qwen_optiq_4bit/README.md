# Qwen OptiQ-4bit oMLX model-dir root

`qwen_optiq_4bit__omlx` uses `--model-dir` pointing here. After HF download,
symlink as `mlx-community__Qwen3.6-35B-A3B-OptiQ-4bit`.

```bash
ln -sfn /Users/jrazz/.cache/huggingface/hub/mlx-community/Qwen3.6-35B-A3B-OptiQ-4bit \
  config/matrix/omlx-roots/qwen_optiq_4bit/mlx-community__Qwen3.6-35B-A3B-OptiQ-4bit
```

Do not commit weight trees or machine-local symlinks into git.
