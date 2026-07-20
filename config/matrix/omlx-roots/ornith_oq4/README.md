# Ornith oQ4 oMLX model-dir root

oMLX `--model-dir` for `ornith_oq4__omlx` expects a directory containing one
model subdirectory named `Ornith-1.0-35B-MLX-oQ4`.

## Prepare the artifact

Download from Hugging Face:

```bash
huggingface-cli download georgeis55/Ornith-1.0-35B-MLX-oQ4 \
  --local-dir ~/.cache/huggingface/hub/georgeis55/Ornith-1.0-35B-MLX-oQ4
```

Then symlink into this root (mirrors the Gemma `oq4_fp16` layout):

```bash
cd config/matrix/omlx-roots/ornith_oq4
ln -s ~/.cache/huggingface/hub/georgeis55/Ornith-1.0-35B-MLX-oQ4 Ornith-1.0-35B-MLX-oQ4
```

If your hub layout uses `models--georgeis55--Ornith-1.0-35B-MLX-oQ4/snapshots/<rev>/`
instead, symlink that snapshot directory to `Ornith-1.0-35B-MLX-oQ4` here.

Until the artifact is present, matrix dry-config succeeds but live `ornith_oq4__omlx`
will report `N/A`.
