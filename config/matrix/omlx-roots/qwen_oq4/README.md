# Qwen oQ4 oMLX model-dir root

`qwen_oq4__omlx` uses `--model-dir` pointing here. After HF download, symlink the
flat hub path (or snapshot) as `Qwen3.6-35B-A3B-oQ4-mtp`.

```bash
ln -sfn /Users/jrazz/.cache/huggingface/hub/Jundot/Qwen3.6-35B-A3B-oQ4-mtp \
  config/matrix/omlx-roots/qwen_oq4/Qwen3.6-35B-A3B-oQ4-mtp
```

Do not commit weight trees or machine-local symlinks into git.
