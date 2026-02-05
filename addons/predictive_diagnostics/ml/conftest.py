"""
Pytest fixtures for ML tests.
"""
import pytest
import sys
sys.path.insert(0, "/home/drawson/autotech_ai")

from addons.predictive_diagnostics.simulation import (
    TrainingDataGenerator,
    DataGeneratorConfig,
)
from addons.predictive_diagnostics.ml import (
    SimpleDiagnosticModel,
    ModelConfig,
    ModelTrainer,
    TrainingConfig,
)


@pytest.fixture(scope="module")
def samples():
    """Generate training samples for ML tests."""
    config = DataGeneratorConfig(
        samples_per_failure=50,
        normal_samples=100,
    )
    
    generator = TrainingDataGenerator(config)
    return generator.generate_dataset_for_system("cooling")


@pytest.fixture(scope="module")
def model_and_trainer(samples):
    """Train a model and return model + trainer."""
    # Count classes
    labels = sorted(set(s["label"] for s in samples))
    num_classes = len(labels)
    
    # Create model
    config = ModelConfig(num_classes=num_classes)
    model = SimpleDiagnosticModel(config)
    
    # Create trainer
    train_config = TrainingConfig(
        epochs=50,
        patience=15,
        batch_size=32,
        learning_rate=5e-3,
        log_interval=10,
        checkpoint_dir="/tmp/predictive_diagnostics_checkpoints",
    )
    trainer = ModelTrainer(train_config)
    
    # Train
    trainer.load_data(samples, use_features=True)
    trainer.train(model)
    
    return model, trainer


@pytest.fixture(scope="module")
def model(model_and_trainer):
    """Get trained model."""
    return model_and_trainer[0]


@pytest.fixture(scope="module")
def trainer(model_and_trainer):
    """Get trainer."""
    return model_and_trainer[1]
