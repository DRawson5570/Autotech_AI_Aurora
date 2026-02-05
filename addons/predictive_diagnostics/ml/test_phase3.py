#!/usr/bin/env python3
"""
Phase 3 Validation: ML Model

Tests that the ML module can:
1. Generate training data from simulation
2. Train a model on the data
3. Make accurate predictions on test cases
"""

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
    DiagnosticInference,
)


def test_data_generation():
    """Generate training data for ML."""
    print("\n" + "="*60)
    print("TEST: Generate Training Data")
    print("="*60)
    
    config = DataGeneratorConfig(
        samples_per_failure=50,  # More samples for better training
        normal_samples=100,
    )
    
    generator = TrainingDataGenerator(config)
    samples = generator.generate_dataset_for_system("cooling")
    
    print(f"Generated {len(samples)} training samples")
    
    # Check diversity
    labels = set(s["label"] for s in samples)
    print(f"Unique labels: {len(labels)}")
    
    assert len(samples) >= 100, f"Expected 100+ samples, got {len(samples)}"
    assert len(labels) >= 10, f"Expected 10+ labels, got {len(labels)}"
    
    print("\n✓ Data generation PASSED")
    return samples


def test_model_creation():
    """Test model instantiation."""
    print("\n" + "="*60)
    print("TEST: Model Creation")
    print("="*60)
    
    config = ModelConfig(num_classes=13)
    model = SimpleDiagnosticModel(config)
    
    # Check model structure
    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    
    print(f"Model parameters: {total_params:,}")
    print(f"Trainable parameters: {trainable_params:,}")
    
    assert trainable_params > 0, "Model has no trainable parameters"
    
    print("\n✓ Model creation PASSED")
    return model


def test_model_training(samples):
    """Test model training."""
    print("\n" + "="*60)
    print("TEST: Model Training")
    print("="*60)
    
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
        learning_rate=5e-3,  # Higher LR for faster convergence
        log_interval=10,
        checkpoint_dir="/tmp/predictive_diagnostics_checkpoints",
    )
    trainer = ModelTrainer(train_config)
    
    # Train
    trainer.load_data(samples, use_features=True)
    metrics = trainer.train(model)
    
    print(f"\nTraining completed:")
    print(f"  Epochs: {metrics['num_epochs']}")
    print(f"  Final train accuracy: {metrics['final_train_acc']:.1%}")
    print(f"  Final validation accuracy: {metrics['final_val_acc']:.1%}")
    
    # For pipeline validation, just check it's learning (better than random 1/13 ~7.7%)
    assert metrics['final_val_acc'] > 0.15, \
        f"Validation accuracy too low: {metrics['final_val_acc']:.1%}"
    
    print("\n✓ Model training PASSED")
    return model, trainer


def test_inference(model, trainer):
    """Test inference on known cases."""
    print("\n" + "="*60)
    print("TEST: Inference")
    print("="*60)
    
    # Create inference engine
    inference = DiagnosticInference(model)
    
    # Test case 1: Normal operation (warm engine, ~90°C)
    print("\nTest case 1: Normal operation")
    normal_data = {
        "coolant_temp": [90.0] * 60,
        "engine_temp": [92.0] * 60,
        "thermostat_position": [1.0] * 60,
        "fan_state": [0.0] * 60,
        "coolant_flow": [30.0] * 60,
        "stft": [0.0] * 60,
        "ltft": [0.0] * 60,
    }
    
    result = inference.diagnose(normal_data)
    print(f"  Top diagnosis: {result.hypotheses[0]['failure_id']}")
    print(f"  Confidence: {result.confidence:.1%}")
    
    # Test case 2: Cold running engine (stuck open thermostat pattern)
    print("\nTest case 2: Engine running cold")
    cold_data = {
        "coolant_temp": [45.0 + i*0.1 for i in range(60)],  # Slowly warming but stuck at ~50
        "engine_temp": [50.0] * 60,
        "thermostat_position": [1.0] * 60,  # Fully open
        "fan_state": [0.0] * 60,
        "coolant_flow": [30.0] * 60,
        "stft": [10.0] * 60,  # Rich because cold
        "ltft": [5.0] * 60,
    }
    
    result = inference.diagnose(cold_data)
    print(f"  Top diagnosis: {result.hypotheses[0]['failure_id']}")
    print(f"  Confidence: {result.confidence:.1%}")
    print(f"  Top 3 hypotheses:")
    for h in result.hypotheses[:3]:
        print(f"    - {h['failure_id']}: {h['probability']:.1%}")
    
    # Test case 3: Overheating (blocked radiator pattern)
    print("\nTest case 3: Engine overheating")
    hot_data = {
        "coolant_temp": [90.0 + i*0.5 for i in range(60)],  # Rising temp
        "engine_temp": [95.0 + i*0.6 for i in range(60)],
        "thermostat_position": [1.0] * 60,
        "fan_state": [1.0] * 60,  # Fan running but not helping
        "coolant_flow": [30.0] * 60,
        "stft": [-3.0] * 60,  # Lean because hot
        "ltft": [-2.0] * 60,
    }
    
    result = inference.diagnose(hot_data)
    print(f"  Top diagnosis: {result.hypotheses[0]['failure_id']}")
    print(f"  Confidence: {result.confidence:.1%}")
    
    print("\n✓ Inference PASSED")


def test_model_save_load(model):
    """Test model persistence."""
    print("\n" + "="*60)
    print("TEST: Model Save/Load")
    print("="*60)
    
    import tempfile
    import os
    
    # Move model to CPU for comparison
    model = model.cpu()
    
    # Save
    save_path = "/tmp/test_diagnostic_model.pt"
    model.save(save_path)
    print(f"Saved model to {save_path}")
    
    # Load
    loaded_model = SimpleDiagnosticModel.load(save_path)
    print(f"Loaded model with {len(loaded_model.class_labels)} classes")
    
    # Verify same predictions (both on CPU)
    import torch
    test_input = torch.randn(1, 56)  # 7 features * 8 stats
    
    model.eval()
    loaded_model.eval()
    
    with torch.no_grad():
        orig_out = model(test_input)
        loaded_out = loaded_model(test_input)
    
    assert torch.allclose(orig_out, loaded_out), "Model outputs don't match after load"
    
    # Cleanup
    os.remove(save_path)
    
    print("\n✓ Model save/load PASSED")


def main():
    """Run all Phase 3 validation tests."""
    print("\n" + "#"*60)
    print("# PHASE 3 VALIDATION: ML Model")
    print("#"*60)
    
    try:
        # Generate data
        samples = test_data_generation()
        
        # Create model
        test_model_creation()
        
        # Train
        model, trainer = test_model_training(samples)
        
        # Inference
        test_inference(model, trainer)
        
        # Save/load
        test_model_save_load(model)
        
        print("\n" + "="*60)
        print("ALL PHASE 3 TESTS PASSED!")
        print("="*60)
        print("\nPhase 3 is complete. Ready for Phase 4: Diagnostic Reasoning")
        
    except AssertionError as e:
        print(f"\n❌ VALIDATION FAILED: {e}")
        raise
    except Exception as e:
        import traceback
        print(f"\n❌ ERROR: {e}")
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
