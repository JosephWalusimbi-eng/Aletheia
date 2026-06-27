# Aletheia Model Files

The GGUF model files are not stored in this repository due to their size.

## Download

```bash
bash models/download_model.sh
```

## Model Variants

| File | Size | RAM | Quality | Use |
|------|------|-----|---------|-----|
| `aletheia_q4km.gguf` | 1.8 GB | ~3,630 MB | Primary | **ADTC submission** |
| `aletheia_q2k.gguf` | 1.19 GB | ~2,990 MB | Fallback | 4 GB RAM devices |

Both files pass the ADTC 2026 memory ceiling of 7,168 MB.

## Manual Download

If the script fails, download manually from Google Drive:

> Link will be provided after model upload

Copy the file to this directory:
```
Aletheia/models/aletheia_q4km.gguf
```

## Model Details

- **Base:** Qwen2.5-3B-Instruct
- **Fine-tuning:** QLoRA (r=32, α=64, 1.94% trainable parameters)
- **Training data:** 27,000 clinical reasoning samples
- **Format:** GGUF Q4_K_M quantisation
- **Inference engine:** llama.cpp (CPU only)