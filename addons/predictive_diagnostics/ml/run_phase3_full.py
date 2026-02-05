"""
Longer Phase 3 training run for improved model accuracy.
Generates a larger dataset and trains for more epochs, saving the best model.
"""
import sys
sys.path.insert(0, "/home/drawson/autotech_ai")

from addons.predictive_diagnostics.simulation import DataGeneratorConfig, TrainingDataGenerator
from addons.predictive_diagnostics.ml.model import ModelConfig, SimpleDiagnosticModel
from addons.predictive_diagnostics.ml.trainer import TrainingConfig, ModelTrainer


def run_full():
    print("\n=== Full Phase 3 Training Run ===\n")

    # Larger dataset configuration
    cfg = DataGeneratorConfig(
        samples_per_failure=100,
        normal_samples=200,
        min_duration=60.0,
        max_duration=300.0,
        add_noise=True,
    )

    gen = TrainingDataGenerator(cfg)
    samples = gen.generate_dataset_for_system("cooling")

    print(f"Generated {len(samples)} samples for full training")

    labels = sorted(set(s["label"] for s in samples))
    num_classes = len(labels)

    model_cfg = ModelConfig(num_classes=num_classes)
    model = SimpleDiagnosticModel(model_cfg)

    train_cfg = TrainingConfig(
        epochs=30,
        batch_size=32,
        patience=8,
        checkpoint_dir="/tmp/pd_full_checkpoints",
        log_interval=2,
    )

    trainer = ModelTrainer(train_cfg)
    trainer.load_data(samples, use_features=True)
    metrics = trainer.train(model)

    print("\nFull training metrics:")
    print(metrics)

    # Save final model
    model.save("/tmp/pd_full_model.pt")
    print("Saved full model to /tmp/pd_full_model.pt")

    return metrics


if __name__ == '__main__':
    run_full()
