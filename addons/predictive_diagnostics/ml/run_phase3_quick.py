"""
Quick Phase 3 runner for CI / smoke tests.
Generates smaller dataset and runs a short training session to validate the ML pipeline.
"""

import sys
sys.path.insert(0, "/home/drawson/autotech_ai")

from addons.predictive_diagnostics.simulation import DataGeneratorConfig, TrainingDataGenerator
from addons.predictive_diagnostics.ml.model import ModelConfig, SimpleDiagnosticModel
from addons.predictive_diagnostics.ml.trainer import TrainingConfig, ModelTrainer


def run_quick():
    print("\n=== Quick Phase 3 Runner ===\n")

    # Generate small dataset for cooling system
    cfg = DataGeneratorConfig(
        samples_per_failure=20,
        normal_samples=40,
        min_duration=60.0,
        max_duration=120.0,
    )

    gen = TrainingDataGenerator(cfg)
    samples = gen.generate_dataset_for_system("cooling")

    print(f"Generated {len(samples)} samples for quick training")

    # Create simple model and trainer
    labels = sorted(set(s["label"] for s in samples))
    num_classes = len(labels)

    model_cfg = ModelConfig(num_classes=num_classes)
    model = SimpleDiagnosticModel(model_cfg)

    train_cfg = TrainingConfig(
        epochs=8,
        batch_size=16,
        patience=4,
        checkpoint_dir="/tmp/pd_quick_checkpoints",
        log_interval=2,
    )

    trainer = ModelTrainer(train_cfg)
    trainer.load_data(samples, use_features=True)
    metrics = trainer.train(model)

    print("\nQuick training metrics:")
    print(metrics)

    # Save model
    model.save("/tmp/pd_quick_model.pt")
    print("Saved quick model to /tmp/pd_quick_model.pt")

    return metrics


if __name__ == '__main__':
    run_quick()
