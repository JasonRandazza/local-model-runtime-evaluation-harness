# Ornith OptiQ-4bit oMLX model-dir root

`ornith_optiq_4bit__omlx` uses `--model-dir` pointing here. After downloading
`mlx-community/Ornith-1.0-35B-OptiQ-4bit`, symlink:

```bash
cd config/matrix/omlx-roots/ornith_optiq_4bit
ln -s ~/.cache/huggingface/hub/mlx-community/Ornith-1.0-35B-OptiQ-4bit \
  mlx-community__Ornith-1.0-35B-OptiQ-4bit
```

If the hub uses `models--mlx-community--Ornith-1.0-35B-OptiQ-4bit/snapshots/<rev>/`,
symlink that snapshot directory instead. Until present, live cell reports `N/A`.
