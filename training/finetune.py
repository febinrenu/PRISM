"""
QLoRA fine-tuning of Phi-3.5-mini on the silver extraction data.

Trains on training/data/sft.jsonl (build_dataset.py): the production
extraction prompt as the user turn and a grounded, teacher-agreed rule record
as the assistant turn. Loss is computed on the assistant turn only.

Phi-3.5 fuses its projections, so the adapters go on qkv_proj, o_proj,
gate_up_proj and down_proj (attention and MLP). After training the script
checks that every one of those module types received a non-zero update and
writes the result to train_summary.json; a run that fails the check exits
with an error.

Runs on a 16 GB GPU (Kaggle T4 / Colab); see kaggle_qlora.ipynb.

    python training/finetune.py --epochs 2
    python training/finetune.py --smoke          # a few steps on 16 examples
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data" / "sft.jsonl"
OUT = HERE / "prism-phi35-lora"

MODEL_ID = "microsoft/Phi-3.5-mini-instruct"
TARGET_MODULES = ["qkv_proj", "o_proj", "gate_up_proj", "down_proj"]
MAX_LENGTH = 3072
SEED = 42


def _preflight() -> None:
    missing = []
    for mod in ("torch", "transformers", "peft", "trl", "datasets", "bitsandbytes"):
        try:
            __import__(mod)
        except ImportError:
            missing.append(mod)
    if missing:
        sys.exit(f"[error] missing training packages: {', '.join(missing)}\n"
                 f"        pip install -r training/requirements-train.txt")
    import torch
    if not torch.cuda.is_available():
        sys.exit("[error] no CUDA device: QLoRA needs a GPU (use the Kaggle notebook).")


def lora_update_check(model) -> dict[str, float]:
    """Norm of lora_B per target module type. lora_B starts at zero, so a
    non-zero norm means that module type was trained."""
    norms = {m: 0.0 for m in TARGET_MODULES}
    for name, p in model.named_parameters():
        if "lora_B" not in name:
            continue
        for m in TARGET_MODULES:
            if f".{m}." in name:
                norms[m] += float(p.detach().float().norm() ** 2)
    return {m: v ** 0.5 for m, v in norms.items()}


def train(epochs: float, smoke: bool, batch_size: int, grad_accum: int, lr: float, rank: int) -> None:
    _preflight()
    if not DATA.exists():
        sys.exit(f"[error] {DATA} not found. Run: python training/build_dataset.py")

    import torch
    from datasets import load_dataset
    from peft import LoraConfig
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from trl import SFTConfig, SFTTrainer

    ds = load_dataset("json", data_files=str(DATA), split="train").select_columns(["prompt", "completion"])
    if smoke:
        ds = ds.select(range(min(16, len(ds))))
    split = ds.train_test_split(test_size=0.05, seed=SEED) if len(ds) >= 40 else None
    train_ds, eval_ds = (split["train"], split["test"]) if split else (ds, None)
    print(f"[ok] {len(train_ds)} training examples, {len(eval_ds) if eval_ds else 0} validation")

    bf16 = torch.cuda.is_bf16_supported()
    dtype = torch.bfloat16 if bf16 else torch.float16
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    if tokenizer.pad_token is None or tokenizer.pad_token == tokenizer.eos_token:
        tokenizer.pad_token = tokenizer.unk_token or tokenizer.eos_token
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, device_map="auto", torch_dtype=dtype, attn_implementation="sdpa",
        quantization_config=BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                                               bnb_4bit_compute_dtype=dtype, bnb_4bit_use_double_quant=True),
    )

    config = SFTConfig(
        output_dir=str(OUT),
        num_train_epochs=epochs,
        max_steps=4 if smoke else -1,
        per_device_train_batch_size=batch_size,
        gradient_accumulation_steps=grad_accum,
        gradient_checkpointing=True,
        learning_rate=lr,
        lr_scheduler_type="cosine",
        warmup_ratio=0.05,
        optim="paged_adamw_8bit",
        bf16=bf16, fp16=not bf16,
        max_length=MAX_LENGTH,
        completion_only_loss=True,
        logging_steps=5,
        eval_strategy="epoch" if eval_ds is not None and not smoke else "no",
        save_strategy="no",
        seed=SEED,
        report_to=[],
    )
    trainer = SFTTrainer(
        model=model, args=config, train_dataset=train_ds, eval_dataset=eval_ds,
        processing_class=tokenizer,
        peft_config=LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05, bias="none",
                               target_modules=TARGET_MODULES, task_type="CAUSAL_LM"),
    )
    trainer.model.print_trainable_parameters()
    result = trainer.train()

    norms = lora_update_check(trainer.model)
    untrained = [m for m, v in norms.items() if v == 0.0]
    print("[check] lora_B norm per module type:", {m: round(v, 4) for m, v in norms.items()})
    summary = {
        "base_model": MODEL_ID, "target_modules": TARGET_MODULES, "lora_r": rank, "lora_alpha": 2 * rank,
        "epochs": epochs, "learning_rate": lr, "effective_batch": batch_size * grad_accum,
        "max_length": MAX_LENGTH, "seed": SEED, "smoke": smoke,
        "train_examples": len(train_ds), "validation_examples": len(eval_ds) if eval_ds else 0,
        "data_sha256": hashlib.sha256(DATA.read_bytes()).hexdigest(),
        "train_loss": result.training_loss, "log": trainer.state.log_history,
        "lora_b_norm": norms, "all_modules_trained": not untrained,
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "train_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    if untrained:
        sys.exit(f"[error] no update reached: {', '.join(untrained)}")
    if smoke:
        print("[ok] smoke run passed: every target module type was updated.")
        return
    trainer.model.save_pretrained(str(OUT))
    tokenizer.save_pretrained(str(OUT))
    print(f"[ok] adapters saved to {OUT}. Next: python training/export_ollama.py")


def main() -> None:
    ap = argparse.ArgumentParser(description="QLoRA fine-tuning of Phi-3.5-mini on silver extraction data.")
    ap.add_argument("--epochs", type=float, default=2)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--batch-size", type=int, default=1)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=16)
    a = ap.parse_args()
    train(a.epochs, a.smoke, a.batch_size, a.grad_accum, a.lr, a.rank)


if __name__ == "__main__":
    main()
