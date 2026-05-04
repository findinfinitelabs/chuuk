#!/usr/bin/env python3
"""
Helsinki-NLP Model Fine-tuning System for Chuukese
Implements real fine-tuning of OPUS-MT models with dictionary corrections
"""

import os
import torch
from transformers import (
    MarianMTModel,
    MarianTokenizer,
    Seq2SeqTrainingArguments,
    Seq2SeqTrainer,
    DataCollatorForSeq2Seq,
    TrainerCallback,
    TrainerControl,
    TrainerState,
)
from datasets import Dataset
from collections.abc import Callable
import json


class EpochProgressCallback(TrainerCallback):
    """Reports epoch progress back via the progress_callback"""

    def __init__(self, progress_callback: Callable | None, num_epochs: int, stage_name: str):
        self.progress_callback = progress_callback
        self.num_epochs = num_epochs
        self.stage_name = stage_name

    def on_epoch_begin(self, args, state: TrainerState, control: TrainerControl, **kwargs):
        epoch = int(state.epoch) + 1
        if self.progress_callback:
            self.progress_callback(
                f"Training {self.stage_name} — epoch {epoch}/{self.num_epochs}",
                None,
                epoch=epoch,
                total_epochs=self.num_epochs,
            )

    def on_log(self, args, state: TrainerState, control: TrainerControl, logs=None, **kwargs):
        # within-epoch progress: fractional part of state.epoch
        epoch_frac = state.epoch % 1.0
        # On the very end of an epoch epoch_frac == 0.0, treat as 100%
        step_pct = int(epoch_frac * 100) if epoch_frac > 0 else 100
        loss = (logs or {}).get("loss", None)
        if self.progress_callback:
            self.progress_callback(
                f"Training {self.stage_name} — epoch {int(state.epoch) + 1}/{self.num_epochs}",
                None,
                epoch=int(state.epoch) + 1,
                total_epochs=self.num_epochs,
                epoch_step_pct=step_pct,
                epoch_loss=round(loss, 4) if loss is not None else None,
            )

    def on_epoch_end(self, args, state: TrainerState, control: TrainerControl, **kwargs):
        epoch = int(state.epoch)
        loss = state.log_history[-1].get("loss", None) if state.log_history else None
        if self.progress_callback:
            self.progress_callback(
                f"Finished epoch {epoch}/{self.num_epochs} ({self.stage_name})",
                None,
                epoch=epoch,
                total_epochs=self.num_epochs,
                epoch_step_pct=100,
                epoch_loss=round(loss, 4) if loss is not None else None,
            )


class HelsinkiFineTuner:
    """Fine-tunes Helsinki-NLP OPUS models with new dictionary data"""

    def __init__(self, progress_callback: Callable | None = None):
        """
        Args:
            progress_callback: Optional function to call with progress updates
                              Should accept (stage: str, progress: float) parameters
        """
        self.progress_callback = progress_callback

        # Enhanced GPU configuration - support both CUDA and MPS (Apple Silicon)
        if torch.cuda.is_available():
            gpu_count = torch.cuda.device_count()
            # Use all available GPUs
            os.environ["CUDA_VISIBLE_DEVICES"] = ",".join(str(i) for i in range(gpu_count))

            # Set memory fraction to 90% to maximize usage while preventing OOM
            for i in range(gpu_count):
                torch.cuda.set_per_process_memory_fraction(0.9, i)

            self.device = "cuda"
            self.num_gpus = gpu_count
            print(f"🎮 Using {gpu_count} CUDA GPU(s) with 90% memory per GPU")
            print(f"🔥 GPU 0: {torch.cuda.get_device_name(0)}")

            # Enable TF32 for faster training on Ampere GPUs
            torch.backends.cuda.matmul.allow_tf32 = True
            torch.backends.cudnn.allow_tf32 = True

            # Enable cuDNN auto-tuner for optimal performance
            torch.backends.cudnn.benchmark = True
            # BF16 is more numerically stable than FP16 on Ampere+ (3000/4000/A100)
            self.use_bf16 = torch.cuda.is_bf16_supported()
            if self.use_bf16:
                print("🧮 BF16 precision enabled (Ampere+ GPU detected)")
        elif torch.backends.mps.is_available() and torch.backends.mps.is_built():
            # Apple Silicon GPU (Metal Performance Shaders)
            self.device = "mps"
            self.num_gpus = 1
            self.use_bf16 = False
            print("🍎 Using Apple Silicon GPU (MPS) for acceleration")
            print("⚡ Metal Performance Shaders enabled")
        else:
            self.device = "cpu"
            self.num_gpus = 0
            self.use_bf16 = False
            # Limit CPU threads to prevent overload
            torch.set_num_threads(min(8, os.cpu_count() or 4))
            print(f"🖥️  Using CPU with {torch.get_num_threads()} threads")
            print("⚠️  Warning: Training on CPU will be slow. GPU recommended for production.")

        # Model paths — use MODEL_STORE_PATH (persistent Azure File Share) when
        # set, so that fine-tuned weights survive container restarts/redeploys.
        # The base models in models/ remain as fallback for loading if the store
        # is empty on first boot.
        _store = os.getenv("MODEL_STORE_PATH", "").strip().rstrip("/")
        if _store:
            os.makedirs(_store, exist_ok=True)
            self.chk_to_en_model_path = f"{_store}/helsinki-chuukese_chuukese_to_english"
            self.en_to_chk_model_path = f"{_store}/helsinki-chuukese_english_to_chuukese"
            # Seed the store from the baked-in image weights on first boot
            for src_dir, dst_dir in [
                ("models/helsinki-chuukese_chuukese_to_english", self.chk_to_en_model_path),
                ("models/helsinki-chuukese_english_to_chuukese", self.en_to_chk_model_path),
            ]:
                if os.path.isdir(src_dir) and not os.path.exists(os.path.join(dst_dir, "config.json")):
                    import shutil as _shutil
                    _shutil.copytree(src_dir, dst_dir, dirs_exist_ok=True)
                    print(f"📂 Seeded model store: {src_dir} → {dst_dir}")
            print(f"📦 Using persistent model store: {_store}")
        else:
            self.chk_to_en_model_path = "models/helsinki-chuukese_chuukese_to_english"
            self.en_to_chk_model_path = "models/helsinki-chuukese_english_to_chuukese"

        # Base model names (for fallback if local models don't exist)
        self.chk_to_en_base = "Helsinki-NLP/opus-mt-mul-en"
        self.en_to_chk_base = "Helsinki-NLP/opus-mt-en-mul"

        # Adjusted safety limits based on hardware
        if self.device in ["cuda", "mps"]:
            self.max_length = 256  # Longer sequences on GPU
            self.gradient_accumulation_steps = 2
        else:
            self.max_length = 128  # Shorter on CPU to save memory
            self.gradient_accumulation_steps = 4  # More accumulation on CPU

    def _update_progress(self, stage: str, progress: float):
        """Update progress through callback if provided"""
        if self.progress_callback:
            self.progress_callback(stage, progress)

    def load_training_data_from_db(self) -> list[dict[str, str]]:
        """Load training data from dictionary database"""
        from src.database.dictionary_db import DictionaryDB

        self._update_progress("Loading dictionary data", 5)

        db = DictionaryDB()
        entries = list(
            db.dictionary_collection.find({"search_direction": {"$ne": "en_to_chk"}})  # Get original entries
        )

        training_pairs = []
        for entry in entries:
            chuukese = entry.get("chuukese_word", "").strip()
            english = entry.get("english_translation", "").strip()

            if chuukese and english and len(chuukese) > 1 and len(english) > 2:
                training_pairs.append({"chuukese": chuukese, "english": english})

        print(f"📚 Loaded {len(training_pairs)} training pairs from database")
        self._update_progress("Data loaded", 10)
        return training_pairs

    def prepare_dataset(self, training_pairs: list[dict[str, str]], direction: str) -> Dataset:
        """
        Prepare dataset for training

        Args:
            training_pairs: List of {'chuukese': str, 'english': str} dicts
            direction: 'chk_to_en' or 'en_to_chk'
        """
        if direction == "chk_to_en":
            data = {
                "source": [pair["chuukese"] for pair in training_pairs],
                "target": [pair["english"] for pair in training_pairs],
            }
        else:  # en_to_chk
            data = {
                "source": [pair["english"] for pair in training_pairs],
                "target": [pair["chuukese"] for pair in training_pairs],
            }

        return Dataset.from_dict(data)

    def tokenize_dataset(self, dataset: Dataset, tokenizer, max_length: int = 128):
        """Tokenize dataset for training"""

        def tokenize_function(examples):
            model_inputs = tokenizer(examples["source"], max_length=max_length, truncation=True, padding="max_length")

            # Use text_target= (replaces deprecated as_target_tokenizer)
            labels = tokenizer(
                text_target=examples["target"], max_length=max_length, truncation=True, padding="max_length"
            )

            # Replace padding token ids with -100 so they are ignored in loss
            label_ids = labels["input_ids"]
            label_ids = [[(t if t != tokenizer.pad_token_id else -100) for t in seq] for seq in label_ids]
            model_inputs["labels"] = label_ids
            return model_inputs

        tokenized_dataset = dataset.map(tokenize_function, batched=True, remove_columns=dataset.column_names)

        return tokenized_dataset

    def fine_tune_model(
        self,
        direction: str,
        training_pairs: list[dict[str, str]] | None = None,
        num_epochs: int = 3,
        batch_size: int = 2,  # Reduced default for safety
        learning_rate: float = 3e-5,
        save_steps: int = 50,
    ) -> bool:
        """
        Fine-tune a Helsinki model

        Args:
            direction: 'chk_to_en' or 'en_to_chk'
            training_pairs: Optional list of training pairs. If None, loads from database.
            num_epochs: Number of training epochs
            batch_size: Training batch size (keep small: 2-4)
            learning_rate: Learning rate for optimizer
            save_steps: Save checkpoint every N steps
        """
        try:
            # Clear CUDA cache if using GPU
            if self.device == "cuda":
                torch.cuda.empty_cache()

            # Determine model paths
            if direction == "chk_to_en":
                model_path = self.chk_to_en_model_path
                base_model = self.chk_to_en_base
                output_dir = f"{model_path}/finetuned"
                stage_name = "Chuukese→English"
            else:
                model_path = self.en_to_chk_model_path
                base_model = self.en_to_chk_base
                output_dir = f"{model_path}/finetuned"
                stage_name = "English→Chuukese"

            print(f"\n🔧 Fine-tuning {stage_name} model...")
            self._update_progress(f"Loading {stage_name} model", 15)

            # Load training data
            if training_pairs is not None:
                print(f"📚 Using provided training pairs: {len(training_pairs)}")
                self._update_progress("Using provided training data", 20)
            else:
                print("📚 Loading training data from database...")
                training_pairs = self.load_training_data_from_db()

            # Load model and tokenizer
            # Check if we have a valid trained model (with actual model files)
            has_model_files = False
            if os.path.exists(model_path):
                # Check for actual model weight files
                model_files = ["pytorch_model.bin", "model.safetensors", "tf_model.h5"]
                has_model_files = any(os.path.exists(os.path.join(model_path, f)) for f in model_files)

            if has_model_files:
                print(f"📂 Loading local model from {model_path}")
                model = MarianMTModel.from_pretrained(model_path)
                tokenizer = MarianTokenizer.from_pretrained(model_path)
            else:
                print(f"📥 Downloading base model: {base_model}")
                print("   This may take a few minutes on first run...")
                model = MarianMTModel.from_pretrained(base_model)
                tokenizer = MarianTokenizer.from_pretrained(base_model)

                # Save the base model locally for future use
                print(f"💾 Saving base model to {model_path}")
                os.makedirs(model_path, exist_ok=True)
                model.save_pretrained(model_path)
                tokenizer.save_pretrained(model_path)

            # Allow forcing CPU to avoid MPS Metal command buffer corruption
            force_cpu = os.environ.get("FORCE_CPU", "0") == "1"
            train_device = "cpu" if force_cpu else self.device
            if force_cpu:
                print("🖥️  FORCE_CPU=1: Using CPU to avoid MPS instability")
            model = model.to(train_device)

            # Load training data
            self._update_progress(f"Preparing {stage_name} data", 20)
            if training_pairs is None:
                training_pairs = self.load_training_data_from_db()

            if len(training_pairs) < 10:
                print(f"⚠️  Warning: Only {len(training_pairs)} training pairs. More data recommended.")

            # Prepare dataset
            dataset = self.prepare_dataset(training_pairs, direction)
            tokenized_dataset = self.tokenize_dataset(dataset, tokenizer)

            # Split into train/eval (90/10)
            split = tokenized_dataset.train_test_split(test_size=0.1, seed=42)
            train_dataset = split["train"]
            eval_dataset = split["test"]

            print(f"📊 Training samples: {len(train_dataset)}, Eval samples: {len(eval_dataset)}")

            # Training arguments
            training_args = Seq2SeqTrainingArguments(
                output_dir=output_dir,
                eval_strategy="steps",
                eval_steps=save_steps,
                save_strategy="steps",
                save_steps=save_steps,
                learning_rate=learning_rate,
                per_device_train_batch_size=batch_size,
                per_device_eval_batch_size=batch_size,
                gradient_accumulation_steps=self.gradient_accumulation_steps,
                num_train_epochs=num_epochs,
                weight_decay=0.01,
                save_total_limit=2,  # Keep only 2 checkpoints
                predict_with_generate=True,
                fp16=self.device == "cuda",  # Use mixed precision on GPU
                fp16_full_eval=False,  # Don't use fp16 for eval to save memory
                logging_steps=10,
                load_best_model_at_end=True,
                metric_for_best_model="eval_loss",
                greater_is_better=False,
                push_to_hub=False,
                dataloader_num_workers=0,  # Single-threaded data loading for stability
                max_grad_norm=1.0,  # Gradient clipping for stability
                use_cpu=force_cpu,  # Force CPU when requested
                use_mps_device=(self.device == "mps" and not force_cpu),  # Disable MPS when forced to CPU
            )

            # Data collator
            data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)

            # Trainer
            self._update_progress(f"Training {stage_name} model", 30)

            epoch_cb = EpochProgressCallback(
                progress_callback=self.progress_callback,
                num_epochs=num_epochs,
                stage_name=stage_name,
            )

            trainer = Seq2SeqTrainer(
                model=model,
                args=training_args,
                train_dataset=train_dataset,
                eval_dataset=eval_dataset,
                data_collator=data_collator,
                tokenizer=tokenizer,
                callbacks=[epoch_cb],
            )

            # Train!
            print(f"🚀 Starting training for {num_epochs} epochs...")
            train_result = trainer.train()

            # Save the fine-tuned model
            self._update_progress(f"Saving {stage_name} model", 90)
            print(f"💾 Saving fine-tuned model to {output_dir}")
            trainer.save_model(output_dir)
            tokenizer.save_pretrained(output_dir)

            # Save training metrics
            metrics_path = f"{output_dir}/training_metrics.json"
            with open(metrics_path, "w") as f:
                json.dump(train_result.metrics, f, indent=2)

            print(f"✅ {stage_name} fine-tuning complete!")
            print(f"   Final loss: {train_result.metrics.get('train_loss', 'N/A')}")

            # Clear memory after training
            if self.device == "cuda":
                del model
                del trainer
                torch.cuda.empty_cache()

            return True

        except Exception as e:
            print(f"❌ Fine-tuning error: {e}")
            import traceback

            traceback.print_exc()
            return False

    def fine_tune_model_lora(
        self,
        direction: str,
        training_pairs: list[dict[str, str]],
        num_epochs: int = 3,
        batch_size: int = 1,
        learning_rate: float = 1e-4,
        adapter_output_dir: str | None = None,
    ) -> bool:
        """
        Apply a LoRA adapter update on top of the existing fine-tuned model.
        Much faster than a full fine-tune — suitable for teaching a single pair.

        Requires: ``peft>=0.10.0`` in the environment.

        Args:
            direction: 'chk_to_en' or 'en_to_chk'
            training_pairs: List of {'chuukese': str, 'english': str} dicts
            num_epochs: Epochs for the quick adapter update (2-5 recommended)
            batch_size: Batch size (1 for single-pair teaching)
            learning_rate: LoRA-specific learning rate (higher than full fine-tune)
            adapter_output_dir: Where to save the LoRA adapter checkpoint.
                                 Defaults to models/{direction}/lora_adapters/
        """
        try:
            from peft import LoraConfig, TaskType, get_peft_model  # type: ignore
        except ImportError:
            print("⚠️  peft not installed — falling back to full fine-tune for LoRA teach")
            return self.fine_tune_model(
                direction=direction,
                training_pairs=training_pairs,
                num_epochs=num_epochs,
                batch_size=batch_size,
                learning_rate=learning_rate,
            )

        try:
            if direction == "chk_to_en":
                model_path = self.chk_to_en_model_path
                stage_name = "Chuukese→English (LoRA)"
            else:
                model_path = self.en_to_chk_model_path
                stage_name = "English→Chuukese (LoRA)"

            finetuned_path = f"{model_path}/finetuned"
            load_path = finetuned_path if os.path.exists(finetuned_path) else model_path

            if adapter_output_dir is None:
                adapter_output_dir = f"{model_path}/lora_adapters"
            os.makedirs(adapter_output_dir, exist_ok=True)

            print(f"\n⚡ LoRA quick-teach: {stage_name} ({len(training_pairs)} pairs)")
            self._update_progress(f"LoRA loading {stage_name}", 10)

            force_cpu = os.environ.get("FORCE_CPU", "0") == "1"
            train_device = "cpu" if force_cpu else self.device

            # Load directly in half-precision so it never lands on CPU in float32
            if train_device == "cuda":
                load_dtype = torch.bfloat16 if self.use_bf16 else torch.float16
            elif train_device == "mps":
                load_dtype = torch.float16
            else:
                load_dtype = torch.float32
            print(f"🔢 Loading model with dtype={load_dtype}, device={train_device}")

            model = MarianMTModel.from_pretrained(load_path, torch_dtype=load_dtype)
            tokenizer = MarianTokenizer.from_pretrained(load_path)

            # LoRA targets the attention projection matrices
            lora_cfg = LoraConfig(
                task_type=TaskType.SEQ_2_SEQ_LM,
                r=8,
                lora_alpha=16,
                target_modules=["q_proj", "v_proj"],
                lora_dropout=0.05,
                bias="none",
            )
            model = get_peft_model(model, lora_cfg)
            model.print_trainable_parameters()
            model = model.to(train_device)

            dataset = self.prepare_dataset(training_pairs, direction)
            tokenized = self.tokenize_dataset(dataset, tokenizer, max_length=self.max_length)

            # Use BF16 on Ampere+, FP16 on older CUDA, or native half on MPS
            use_bf16 = self.use_bf16 and train_device == "cuda"
            use_fp16 = (not use_bf16) and train_device == "cuda"

            training_args = Seq2SeqTrainingArguments(
                output_dir=adapter_output_dir,
                num_train_epochs=num_epochs,
                per_device_train_batch_size=batch_size,
                learning_rate=learning_rate,
                logging_steps=5,
                save_strategy="no",
                predict_with_generate=False,
                bf16=use_bf16,
                fp16=use_fp16,
                use_cpu=force_cpu,
                use_mps_device=(self.device == "mps" and not force_cpu),
                dataloader_num_workers=0,
                max_grad_norm=1.0,
                push_to_hub=False,
                eval_strategy="no",
            )

            data_collator = DataCollatorForSeq2Seq(tokenizer, model=model)
            epoch_cb = EpochProgressCallback(
                progress_callback=self.progress_callback,
                num_epochs=num_epochs,
                stage_name=stage_name,
            )

            trainer = Seq2SeqTrainer(
                model=model,
                args=training_args,
                train_dataset=tokenized,
                data_collator=data_collator,
                tokenizer=tokenizer,
                callbacks=[epoch_cb],
            )

            self._update_progress(f"LoRA training {stage_name}", 30)
            trainer.train()

            # Save only the LoRA adapter weights (tiny)
            model.save_pretrained(adapter_output_dir)
            tokenizer.save_pretrained(adapter_output_dir)

            print(f"✅ LoRA adapter saved to {adapter_output_dir}")
            self._update_progress(f"LoRA saved {stage_name}", 90)

            if self.device == "cuda":
                del model
                del trainer
                torch.cuda.empty_cache()

            return True

        except Exception as e:
            print(f"❌ LoRA fine-tuning error: {e}")
            import traceback
            traceback.print_exc()
            return False

    def fine_tune_both_models(self, num_epochs: int = 3, batch_size: int = 4) -> bool:
        """Fine-tune both translation models"""

        print("🚀 Starting fine-tuning for both Helsinki models")
        print("=" * 60)

        # Fine-tune Chuukese → English
        self._update_progress("Fine-tuning Chuukese→English", 25)
        chk_to_en_success = self.fine_tune_model(direction="chk_to_en", num_epochs=num_epochs, batch_size=batch_size)

        if not chk_to_en_success:
            print("❌ Chuukese→English fine-tuning failed")
            return False

        # Fine-tune English → Chuukese
        self._update_progress("Fine-tuning English→Chuukese", 60)
        en_to_chk_success = self.fine_tune_model(direction="en_to_chk", num_epochs=num_epochs, batch_size=batch_size)

        if not en_to_chk_success:
            print("❌ English→Chuukese fine-tuning failed")
            return False

        self._update_progress("Fine-tuning complete", 95)
        print("\n" + "=" * 60)
        print("🎉 Both models fine-tuned successfully!")
        return True


if __name__ == "__main__":
    # Test the trainer
    def progress_callback(stage, progress):
        print(f"[{progress}%] {stage}")

    trainer = HelsinkiFineTuner(progress_callback=progress_callback)

    # Quick test with small configuration
    success = trainer.fine_tune_both_models(num_epochs=1, batch_size=2)  # Quick test  # Small batch for testing

    if success:
        print("✅ Training test successful!")
    else:
        print("❌ Training test failed")
