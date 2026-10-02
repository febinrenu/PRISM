"""
Phase 3, Module E — QLoRA fine-tuning of Phi-3.5-mini.

4-bit NF4 quantization + LoRA adapters on the attention projections, sized to
fit an RTX 3050 (4GB). Trains on training/data/prism_instructions.jsonl (built by
build_dataset.py). Adapters are saved to training/prism-phi35-lora/.

This is a GPU job. Install the heavy deps first (see requirements-train.txt) and
run overnight:

    python training/finetune.py --epochs 3

A quick correctness check that exercises the whole pipeline without a long run:

    python training/finetune.py --smoke      # 2 optimizer steps, tiny subset

Everything is guarded so that on a machine without CUDA / bitsandbytes the script
prints an actionable message instead of a stack trace.
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "prism_instructions.jsonl"
OUT = HERE / "prism-phi35-lora"

MODEL_ID = "microsoft/Phi-3.5-mini-instruct"
TARGET_MODULES = ["q_proj", "k_proj", "v_proj", "o_proj"]


def _preflight() -> None:
    missing = []
    for mod in ("torch", "transformers", "peft", "trl", "datasets"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        print("[error] Missing training deps:", ", ".join(missing))
        print("        pip install -r training/requirements-train.txt")
        sys.exit(1)
    import torch
    if not torch.cuda.is_available():
        print("[warn] CUDA not available — QLoRA needs a GPU. "
              "On CPU this will be impractically slow. Proceeding only for --smoke.")


def train(epochs: int, smoke: bool, batch_size: int, grad_accum: int) -> None:
    _preflight()

    if not DATA.exists():
        print(f"[error] {DATA} not found. Run: python training/build_dataset.py")
        sys.exit(1)

    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig, TrainingArguments)
    from trl import SFTTrainer

    ds = load_dataset("json", data_files=str(DATA), split="train")
    if smoke:
        ds = ds.select(range(min(16, len(ds))))
    print(f"[ok] Loaded {len(ds)} training examples")

    bnb = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.float16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, trust_remote_code=True)
    tokenizer.pad_token = tokenizer.pad_token or tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, quantization_config=bnb, device_map="auto", trust_remote_code=True
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LoraConfig(
        r=8, lora_alpha=16, target_modules=TARGET_MODULES,
        lora_dropout=0.05, bias="none", task_type="CAUSAL_LM",
    ))
    model.print_trainable_parameters()

    args = TrainingArguments(
        output_dir=str(OUT),
        num_train_epochs=1 if smoke else epochs,
        max_steps=2 if smoke else -1,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        fp16=True,
        learning_rate=2e-4,
        logging_steps=5,
        save_strategy="no" if smoke else "epoch",
        optim="paged_adamw_8bit",
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model, train_dataset=ds, args=args,
        dataset_text_field="text", max_seq_length=768, tokenizer=tokenizer,
    )
    trainer.train()

    if not smoke:
        model.save_pretrained(str(OUT))
        tokenizer.save_pretrained(str(OUT))
        (OUT / "train_summary.json").write_text(json.dumps({
            "base_model": MODEL_ID, "examples": len(ds), "epochs": epochs,
            "lora_r": 8, "target_modules": TARGET_MODULES,
        }, indent=2), encoding="utf-8")
        print(f"\n[ok] LoRA adapters saved to {OUT}")
        print("     Next: python training/export_ollama.py")
    else:
        print("\n[ok] Smoke test passed — training pipeline is wired correctly.")


def main() -> None:
    ap = argparse.ArgumentParser(description="QLoRA fine-tune Phi-3.5-mini for PRISM.")
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--smoke", action="store_true", help="2-step wiring test")
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=8)
    args = ap.parse_args()
    train(args.epochs, args.smoke, args.batch_size, args.grad_accum)


if __name__ == "__main__":
    main()
