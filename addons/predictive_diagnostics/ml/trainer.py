"""
Training pipeline for diagnostic models.

Handles:
- Data loading and preprocessing from simulation output
- Train/validation splitting
- Training loop with early stopping
- Model checkpointing
- Training metrics and logging
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple, Any
from pathlib import Path
import json
import random

try:
    import torch
    import torch.nn as nn
    import torch.optim as optim
    from torch.utils.data import Dataset, DataLoader
    import numpy as np
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False

from .model import DiagnosticModel, SimpleDiagnosticModel, ModelConfig


@dataclass
class TrainingConfig:
    """Configuration for model training."""
    
    # Data
    train_split: float = 0.8
    batch_size: int = 32
    
    # Training
    epochs: int = 100
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    
    # Early stopping
    patience: int = 10
    min_delta: float = 0.001
    
    # Checkpointing
    checkpoint_dir: str = "checkpoints"
    save_best: bool = True
    
    # Device
    device: str = "auto"  # "auto", "cuda", "cpu"
    
    # Logging
    log_interval: int = 10


class DiagnosticDataset(Dataset if TORCH_AVAILABLE else object):
    """
    PyTorch dataset for diagnostic training samples.
    
    Handles both:
    - Raw time series data (for CNN+LSTM model)
    - Pre-extracted features (for simple MLP model)
    """
    
    def __init__(self, samples: List[Dict[str, Any]], 
                 feature_names: List[str],
                 label_to_idx: Dict[str, int],
                 sequence_length: int = 120,
                 use_features: bool = True):
        """
        Args:
            samples: List of training samples from DataGenerator
            feature_names: Which sensor channels to use
            label_to_idx: Mapping from label string to class index
            sequence_length: Target sequence length (pad/truncate)
            use_features: If True, extract statistical features
        """
        self.samples = samples
        self.feature_names = feature_names
        self.label_to_idx = label_to_idx
        self.sequence_length = sequence_length
        self.use_features = use_features
    
    def __len__(self) -> int:
        return len(self.samples)
    
    def __getitem__(self, idx: int) -> Tuple['torch.Tensor', int]:
        sample = self.samples[idx]
        label = self.label_to_idx[sample["label"]]
        
        if self.use_features:
            # Extract statistical features
            features = self._extract_features(sample["time_series"])
            return features, label
        else:
            # Return raw time series
            sequence = self._prepare_sequence(sample["time_series"])
            return sequence, label
    
    def _extract_features(self, time_series: Dict[str, List[float]]) -> 'torch.Tensor':
        """Extract statistical features from time series."""
        features = []
        
        for name in self.feature_names:
            values = time_series.get(name, [0.0])
            if not values:
                values = [0.0]
            arr = np.array(values)
            
            features.extend([
                np.mean(arr),
                np.std(arr) if len(arr) > 1 else 0.0,
                np.min(arr),
                np.max(arr),
                (arr[-1] - arr[0]) / max(len(arr), 1),  # slope
                arr[-1],  # final
                np.max(arr) - np.min(arr),  # range
                arr[-1] - arr[0],  # trend
            ])
        
        return torch.tensor(features, dtype=torch.float32)
    
    def _prepare_sequence(self, time_series: Dict[str, List[float]]) -> 'torch.Tensor':
        """Prepare fixed-length sequence from time series."""
        # Build feature matrix
        sequences = []
        for name in self.feature_names:
            values = time_series.get(name, [])
            if not values:
                values = [0.0] * self.sequence_length
            sequences.append(values)
        
        # Stack into (time, features) array
        data = np.array(sequences).T  # (time, features)
        
        # Pad or truncate to sequence_length
        if len(data) < self.sequence_length:
            # Pad with last value
            pad_len = self.sequence_length - len(data)
            padding = np.repeat(data[-1:], pad_len, axis=0)
            data = np.vstack([data, padding])
        elif len(data) > self.sequence_length:
            # Take last sequence_length samples
            data = data[-self.sequence_length:]
        
        return torch.tensor(data, dtype=torch.float32)


class ModelTrainer:
    """
    Training pipeline for diagnostic models.
    
    Usage:
        trainer = ModelTrainer(config)
        trainer.load_data(samples)
        metrics = trainer.train(model)
    """
    
    def __init__(self, config: Optional[TrainingConfig] = None):
        self.config = config or TrainingConfig()
        
        # Determine device
        if self.config.device == "auto":
            self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        else:
            self.device = torch.device(self.config.device)
        
        # Data
        self.train_dataset: Optional[DiagnosticDataset] = None
        self.val_dataset: Optional[DiagnosticDataset] = None
        self.label_to_idx: Dict[str, int] = {}
        self.idx_to_label: Dict[int, str] = {}
        
        # Training state
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        self.history: Dict[str, List[float]] = {
            "train_loss": [],
            "val_loss": [],
            "train_acc": [],
            "val_acc": [],
        }
    
    def load_data(self, samples: List[Dict[str, Any]],
                  feature_names: Optional[List[str]] = None,
                  use_features: bool = True) -> None:
        """
        Load and prepare training data.
        
        Args:
            samples: List of training samples from DataGenerator
            feature_names: Sensor channels to use (default: all cooling sensors)
            use_features: Whether to use statistical features vs raw sequences
        """
        if feature_names is None:
            feature_names = [
                "coolant_temp", "engine_temp", "thermostat_position",
                "fan_state", "coolant_flow", "stft", "ltft"
            ]
        
        # Build label mapping
        labels = sorted(set(s["label"] for s in samples))
        self.label_to_idx = {label: idx for idx, label in enumerate(labels)}
        self.idx_to_label = {idx: label for label, idx in self.label_to_idx.items()}
        
        print(f"Labels: {labels}")
        print(f"Samples per class:")
        for label in labels:
            count = sum(1 for s in samples if s["label"] == label)
            print(f"  {label}: {count}")
        
        # Shuffle and split
        random.shuffle(samples)
        split_idx = int(len(samples) * self.config.train_split)
        train_samples = samples[:split_idx]
        val_samples = samples[split_idx:]
        
        # Create datasets
        self.train_dataset = DiagnosticDataset(
            train_samples, feature_names, self.label_to_idx,
            use_features=use_features
        )
        self.val_dataset = DiagnosticDataset(
            val_samples, feature_names, self.label_to_idx,
            use_features=use_features
        )
        
        print(f"\nData loaded: {len(train_samples)} train, {len(val_samples)} val")
    
    def train(self, model: nn.Module) -> Dict[str, Any]:
        """
        Train the model.
        
        Args:
            model: DiagnosticModel or SimpleDiagnosticModel
            
        Returns:
            Training history and final metrics
        """
        if self.train_dataset is None:
            raise ValueError("Call load_data() first")
        
        # Move model to device
        model = model.to(self.device)
        model.class_labels = list(self.label_to_idx.keys())
        
        # Create data loaders
        train_loader = DataLoader(
            self.train_dataset,
            batch_size=self.config.batch_size,
            shuffle=True,
            num_workers=0,
        )
        val_loader = DataLoader(
            self.val_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=0,
        )
        
        # Loss and optimizer
        criterion = nn.CrossEntropyLoss()
        optimizer = optim.Adam(
            model.parameters(),
            lr=self.config.learning_rate,
            weight_decay=self.config.weight_decay,
        )
        scheduler = optim.lr_scheduler.ReduceLROnPlateau(
            optimizer, mode='min', factor=0.5, patience=5
        )
        
        # Training loop
        print(f"\nTraining on {self.device}...")
        self.best_val_loss = float('inf')
        self.patience_counter = 0
        
        for epoch in range(self.config.epochs):
            # Train
            train_loss, train_acc = self._train_epoch(
                model, train_loader, criterion, optimizer
            )
            
            # Validate
            val_loss, val_acc = self._validate(model, val_loader, criterion)
            
            # Update history
            self.history["train_loss"].append(train_loss)
            self.history["val_loss"].append(val_loss)
            self.history["train_acc"].append(train_acc)
            self.history["val_acc"].append(val_acc)
            
            # Learning rate scheduling
            scheduler.step(val_loss)
            
            # Logging
            if epoch % self.config.log_interval == 0 or epoch == self.config.epochs - 1:
                print(f"Epoch {epoch+1}/{self.config.epochs}: "
                      f"train_loss={train_loss:.4f}, train_acc={train_acc:.3f}, "
                      f"val_loss={val_loss:.4f}, val_acc={val_acc:.3f}")
            
            # Early stopping check
            if val_loss < self.best_val_loss - self.config.min_delta:
                self.best_val_loss = val_loss
                self.patience_counter = 0
                
                # Save best model
                if self.config.save_best:
                    self._save_checkpoint(model, "best_model.pt")
            else:
                self.patience_counter += 1
                if self.patience_counter >= self.config.patience:
                    print(f"\nEarly stopping at epoch {epoch+1}")
                    break
        
        # Load best model if saved
        if self.config.save_best:
            best_path = Path(self.config.checkpoint_dir) / "best_model.pt"
            if best_path.exists():
                model = type(model).load(str(best_path))
                model = model.to(self.device)
        
        return {
            "history": self.history,
            "best_val_loss": self.best_val_loss,
            "final_train_acc": self.history["train_acc"][-1],
            "final_val_acc": self.history["val_acc"][-1],
            "num_epochs": len(self.history["train_loss"]),
        }
    
    def _train_epoch(self, model: nn.Module, loader: DataLoader,
                     criterion: nn.Module, optimizer: optim.Optimizer) -> Tuple[float, float]:
        """Train for one epoch."""
        model.train()
        total_loss = 0.0
        correct = 0
        total = 0
        
        for batch_x, batch_y in loader:
            batch_x = batch_x.to(self.device)
            batch_y = batch_y.to(self.device)
            
            optimizer.zero_grad()
            outputs = model(batch_x)
            loss = criterion(outputs, batch_y)
            loss.backward()
            optimizer.step()
            
            total_loss += loss.item() * len(batch_y)
            _, predicted = outputs.max(1)
            correct += predicted.eq(batch_y).sum().item()
            total += len(batch_y)
        
        return total_loss / total, correct / total
    
    def _validate(self, model: nn.Module, loader: DataLoader,
                  criterion: nn.Module) -> Tuple[float, float]:
        """Validate model."""
        model.eval()
        total_loss = 0.0
        correct = 0
        total = 0
        
        with torch.no_grad():
            for batch_x, batch_y in loader:
                batch_x = batch_x.to(self.device)
                batch_y = batch_y.to(self.device)
                
                outputs = model(batch_x)
                loss = criterion(outputs, batch_y)
                
                total_loss += loss.item() * len(batch_y)
                _, predicted = outputs.max(1)
                correct += predicted.eq(batch_y).sum().item()
                total += len(batch_y)
        
        return total_loss / total, correct / total
    
    def _save_checkpoint(self, model: nn.Module, filename: str) -> None:
        """Save model checkpoint."""
        path = Path(self.config.checkpoint_dir)
        path.mkdir(parents=True, exist_ok=True)
        model.save(str(path / filename))


# ==============================================================================
# CONVENIENCE FUNCTIONS
# ==============================================================================

def train_simple_model(samples: List[Dict[str, Any]],
                       epochs: int = 50,
                       save_path: Optional[str] = None) -> Tuple[SimpleDiagnosticModel, Dict]:
    """
    Quick function to train a simple MLP model.
    
    Args:
        samples: Training samples from DataGenerator
        epochs: Number of training epochs
        save_path: Path to save trained model
        
    Returns:
        Trained model and training metrics
    """
    if not TORCH_AVAILABLE:
        raise ImportError("PyTorch is required for training")
    
    # Count classes
    labels = sorted(set(s["label"] for s in samples))
    num_classes = len(labels)
    
    # Create model
    config = ModelConfig(num_classes=num_classes)
    model = SimpleDiagnosticModel(config)
    
    # Create trainer
    train_config = TrainingConfig(
        epochs=epochs,
        patience=15,
        log_interval=5,
    )
    trainer = ModelTrainer(train_config)
    
    # Train
    trainer.load_data(samples, use_features=True)
    metrics = trainer.train(model)
    
    # Save if requested
    if save_path:
        model.save(save_path)
    
    return model, metrics
