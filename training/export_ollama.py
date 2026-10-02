"""
Phase 3, Module E — merge LoRA adapters and register the model with Ollama.

After finetune.py produces training/prism-phi35-lora/, this merges the adapters
into the base weights, writes an Ollama Modelfile, and (if `ollama` is on PATH)
creates the `prism-legal` model. Then set LLM_BACKEND=ollama_finetuned to serve
it across the whole platform.

    python training/export_ollama.py

Merging needs enough RAM/VRAM to hold the full-precision model briefly; if that
fails on a 4GB card, run this step on any machine with the adapters copied over
(the merge is CPU-capable, just slow).
"""
import shutil
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ADAPTERS = HERE / "prism-phi35-lora"
MERGED = HERE / "prism-phi35-lora-merged"
MODELFILE = HERE / "Modelfile"
BASE_MODEL = "microsoft/Phi-3.5-mini-instruct"
OLLAMA_NAME = "prism-legal"

_MODELFILE_TEXT = f"""FROM {MERGED}
SYSTEM \"\"\"You are PRISM Legal AI, fine-tuned on Indian legal documents. You extract causal policy rules, identify legal entities, and answer questions grounded in statute.\"\"\"
PARAMETER temperature 0.1
PARAMETER top_p 0.9
PARAMETER num_ctx 4096
"""


def merge() -> None:
    if not ADAPTERS.exists():
        print(f"[error] {ADAPTERS} not found. Run: python training/finetune.py")
        sys.exit(1)
    try:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer
    except ImportError:
        print("[error] Install training deps: pip install -r training/requirements-train.txt")
        sys.exit(1)

    print("[..] Loading base model (fp16) for merge…")
    base = AutoModelForCausalLM.from_pretrained(
        BASE_MODEL, torch_dtype=torch.float16, trust_remote_code=True, device_map="cpu"
    )
    model = PeftModel.from_pretrained(base, str(ADAPTERS))
    print("[..] Merging adapters…")
    model = model.merge_and_unload()
    MERGED.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(str(MERGED), safe_serialization=True)
    AutoTokenizer.from_pretrained(BASE_MODEL, trust_remote_code=True).save_pretrained(str(MERGED))
    print(f"[ok] Merged model → {MERGED}")


def write_modelfile() -> None:
    MODELFILE.write_text(_MODELFILE_TEXT, encoding="utf-8")
    print(f"[ok] Wrote {MODELFILE}")


def register() -> None:
    if shutil.which("ollama") is None:
        print("[warn] `ollama` not on PATH — skipping model creation.")
        print(f"       Run manually: ollama create {OLLAMA_NAME} -f {MODELFILE}")
        return
    print(f"[..] ollama create {OLLAMA_NAME}…")
    try:
        subprocess.run(["ollama", "create", OLLAMA_NAME, "-f", str(MODELFILE)], check=True)
        print(f"[ok] Created Ollama model '{OLLAMA_NAME}'.")
        print("     Serve it platform-wide: set LLM_BACKEND=ollama_finetuned")
    except subprocess.CalledProcessError as e:
        print(f"[error] ollama create failed: {e}")


def main() -> None:
    merge()
    write_modelfile()
    register()


if __name__ == "__main__":
    main()
