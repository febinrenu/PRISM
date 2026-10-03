"""
Merge the LoRA adapters, convert to GGUF Q4_K_M, and register with Ollama.

    python training/export_ollama.py merge  --llama-cpp /path/to/llama.cpp   # on the GPU host (Kaggle)
    python training/export_ollama.py register --gguf prism-legal-q4_k_m.gguf # on the machine running Ollama

`merge` writes the merged fp16 model, converts it with llama.cpp's
convert_hf_to_gguf.py and quantises it to Q4_K_M (about 2.4 GB, runs in
4 GB of VRAM). `register` writes a Modelfile with Phi-3.5's chat template and
creates the Ollama model `prism-legal`, which the extraction code knows as
system "prism-legal" (pipeline/extraction/backends.py).
"""
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTERS = HERE / "prism-phi35-lora"
MERGED = HERE / "prism-phi35-merged"
GGUF_F16 = HERE / "prism-legal-f16.gguf"
GGUF_Q4 = HERE / "prism-legal-q4_k_m.gguf"
BASE_MODEL = "microsoft/Phi-3.5-mini-instruct"
OLLAMA_NAME = "prism-legal"

# Phi-3.5 instruct template, as in Ollama's phi3.5 model; no system prompt
# (the extraction prompt is self-contained, exactly as for the base model).
MODELFILE = '''FROM {gguf}
TEMPLATE """{{{{ if .System }}}}<|system|>
{{{{ .System }}}}<|end|>
{{{{ end }}}}{{{{ if .Prompt }}}}<|user|>
{{{{ .Prompt }}}}<|end|>
{{{{ end }}}}<|assistant|>
{{{{ .Response }}}}<|end|>
"""
PARAMETER stop <|end|>
PARAMETER stop <|user|>
PARAMETER stop <|assistant|>
'''


def merge(llama_cpp: Path) -> None:
    import torch
    from peft import PeftModel
    from transformers import AutoModelForCausalLM, AutoTokenizer

    if not ADAPTERS.exists():
        sys.exit(f"[error] {ADAPTERS} not found. Run training/finetune.py first.")
    base = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.float16, device_map="cpu")
    model = PeftModel.from_pretrained(base, str(ADAPTERS)).merge_and_unload()
    model.save_pretrained(str(MERGED), safe_serialization=True)
    AutoTokenizer.from_pretrained(BASE_MODEL).save_pretrained(str(MERGED))
    print(f"[ok] merged model: {MERGED}")

    convert = llama_cpp / "convert_hf_to_gguf.py"
    quantize = next((p for p in (llama_cpp / "build" / "bin" / "llama-quantize", llama_cpp / "llama-quantize")
                     if p.exists()), None)
    if not convert.exists() or quantize is None:
        sys.exit(f"[error] llama.cpp with a built llama-quantize not found at {llama_cpp}")
    subprocess.run([sys.executable, str(convert), str(MERGED), "--outtype", "f16", "--outfile", str(GGUF_F16)], check=True)
    subprocess.run([str(quantize), str(GGUF_F16), str(GGUF_Q4), "Q4_K_M"], check=True)
    GGUF_F16.unlink(missing_ok=True)
    print(f"[ok] {GGUF_Q4} ({GGUF_Q4.stat().st_size / 1e9:.2f} GB)")


def register(gguf: Path) -> None:
    gguf = gguf.resolve()
    if not gguf.exists():
        sys.exit(f"[error] {gguf} not found")
    modelfile = HERE / "Modelfile"
    modelfile.write_text(MODELFILE.format(gguf=gguf), encoding="utf-8")
    if shutil.which("ollama") is None:
        sys.exit(f"[error] ollama not on PATH. Run: ollama create {OLLAMA_NAME} -f {modelfile}")
    subprocess.run(["ollama", "create", OLLAMA_NAME, "-f", str(modelfile)], check=True)
    print(f"[ok] Ollama model '{OLLAMA_NAME}' created. Evaluate it with:\n"
          f"     cd backend && python -m cli eval-run --system {OLLAMA_NAME} --split test")


def main() -> None:
    ap = argparse.ArgumentParser(description="Merge, quantise and register the fine-tuned model.")
    sub = ap.add_subparsers(dest="cmd", required=True)
    m = sub.add_parser("merge")
    m.add_argument("--llama-cpp", type=Path, required=True)
    r = sub.add_parser("register")
    r.add_argument("--gguf", type=Path, default=GGUF_Q4)
    a = ap.parse_args()
    merge(a.llama_cpp) if a.cmd == "merge" else register(a.gguf)


if __name__ == "__main__":
    main()
