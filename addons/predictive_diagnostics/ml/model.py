"""
Neural network model for diagnostic failure classification.

Architecture: 1D CNN + LSTM for time-series classification
- CNN extracts local patterns (rapid temp changes, oscillations)
- LSTM captures temporal dependencies (warmup trajectory)
- Dense layers map to failure probabilities

The model outputs a probability distribution over failure modes,
allowing for uncertainty quantification.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
import json
from pathlib import Path

try:
    import torch
    import torch.nn as nn
    import torch.nn.functional as F
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    # Dummy classes for type hints when torch not installed
    class nn:
        class Module:
            pass


@dataclass
class ModelConfig:
    """Configuration for the diagnostic model."""
    
    # Input features (sensor channels)
    input_features: List[str] = field(default_factory=lambda: [
        "coolant_temp",
        "engine_temp", 
        "thermostat_position",
        "fan_state",
        "coolant_flow",
        "stft",
        "ltft",
    ])
    
    # Sequence length (time steps)
    sequence_length: int = 120  # 2 minutes at 1Hz
    
    # Output classes (failure modes + normal)
    num_classes: int = 13  # 12 failures + normal
    
    # CNN parameters
    cnn_channels: List[int] = field(default_factory=lambda: [32, 64, 64])
    cnn_kernel_size: int = 5
    
    # LSTM parameters
    lstm_hidden_size: int = 128
    lstm_num_layers: int = 2
    lstm_dropout: float = 0.2
    
    # Dense layers
    dense_sizes: List[int] = field(default_factory=lambda: [128, 64])
    dropout: float = 0.3
    
    def to_dict(self) -> dict:
        return {
            "input_features": self.input_features,
            "sequence_length": self.sequence_length,
            "num_classes": self.num_classes,
            "cnn_channels": self.cnn_channels,
            "cnn_kernel_size": self.cnn_kernel_size,
            "lstm_hidden_size": self.lstm_hidden_size,
            "lstm_num_layers": self.lstm_num_layers,
            "lstm_dropout": self.lstm_dropout,
            "dense_sizes": self.dense_sizes,
            "dropout": self.dropout,
        }
    
    @classmethod
    def from_dict(cls, d: dict) -> 'ModelConfig':
        return cls(**d)


class DiagnosticModel(nn.Module if TORCH_AVAILABLE else object):
    """
    Neural network for automotive failure diagnosis.
    
    Architecture:
    1. 1D CNN layers extract local temporal features
    2. LSTM captures long-range dependencies
    3. Dense layers produce failure probabilities
    
    Input shape: (batch, sequence_length, num_features)
    Output shape: (batch, num_classes)
    """
    
    def __init__(self, config: Optional[ModelConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required for DiagnosticModel")
        
        super().__init__()
        self.config = config or ModelConfig()
        
        num_features = len(self.config.input_features)
        
        # Build CNN layers
        # Input: (batch, features, sequence) after transpose
        cnn_layers = []
        in_channels = num_features
        for out_channels in self.config.cnn_channels:
            cnn_layers.extend([
                nn.Conv1d(in_channels, out_channels, 
                         kernel_size=self.config.cnn_kernel_size,
                         padding=self.config.cnn_kernel_size // 2),
                nn.BatchNorm1d(out_channels),
                nn.ReLU(),
                nn.MaxPool1d(2),
            ])
            in_channels = out_channels
        self.cnn = nn.Sequential(*cnn_layers)
        
        # Calculate CNN output size
        # Each MaxPool halves the sequence length
        cnn_seq_len = self.config.sequence_length // (2 ** len(self.config.cnn_channels))
        cnn_out_features = self.config.cnn_channels[-1]
        
        # LSTM layer
        self.lstm = nn.LSTM(
            input_size=cnn_out_features,
            hidden_size=self.config.lstm_hidden_size,
            num_layers=self.config.lstm_num_layers,
            batch_first=True,
            dropout=self.config.lstm_dropout if self.config.lstm_num_layers > 1 else 0,
            bidirectional=True,
        )
        
        # Dense layers
        lstm_out = self.config.lstm_hidden_size * 2  # Bidirectional
        dense_layers = []
        in_size = lstm_out
        for size in self.config.dense_sizes:
            dense_layers.extend([
                nn.Linear(in_size, size),
                nn.ReLU(),
                nn.Dropout(self.config.dropout),
            ])
            in_size = size
        
        # Final output layer
        dense_layers.append(nn.Linear(in_size, self.config.num_classes))
        
        self.dense = nn.Sequential(*dense_layers)
        
        # Store class labels
        self.class_labels: List[str] = []
    
    def forward(self, x: 'torch.Tensor') -> 'torch.Tensor':
        """
        Forward pass.
        
        Args:
            x: Input tensor of shape (batch, sequence_length, num_features)
            
        Returns:
            Logits of shape (batch, num_classes)
        """
        # Transpose for CNN: (batch, features, sequence)
        x = x.transpose(1, 2)
        
        # CNN feature extraction
        x = self.cnn(x)
        
        # Transpose back for LSTM: (batch, sequence, features)
        x = x.transpose(1, 2)
        
        # LSTM
        lstm_out, _ = self.lstm(x)
        
        # Take the last time step
        x = lstm_out[:, -1, :]
        
        # Dense layers
        logits = self.dense(x)
        
        return logits
    
    def predict_proba(self, x: 'torch.Tensor') -> 'torch.Tensor':
        """Get probability distribution over classes."""
        logits = self.forward(x)
        return F.softmax(logits, dim=-1)
    
    def save(self, path: str) -> None:
        """Save model weights and config."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        torch.save({
            'config': self.config.to_dict(),
            'state_dict': self.state_dict(),
            'class_labels': self.class_labels,
        }, path)
    
    @classmethod
    def load(cls, path: str) -> 'DiagnosticModel':
        """Load model from file."""
        checkpoint = torch.load(path, map_location='cpu')
        config = ModelConfig.from_dict(checkpoint['config'])
        model = cls(config)
        model.load_state_dict(checkpoint['state_dict'])
        model.class_labels = checkpoint.get('class_labels', [])
        return model


# ==============================================================================
# LIGHTWEIGHT ALTERNATIVE: Simple MLP for faster training/inference
# ==============================================================================

class SimpleDiagnosticModel(nn.Module if TORCH_AVAILABLE else object):
    """
    Simpler MLP-based model using statistical features.
    
    Instead of processing raw time series, this model uses
    hand-crafted features (mean, std, slope, etc.) which:
    - Trains faster
    - Requires less data
    - More interpretable
    """
    
    # Statistical features extracted from each sensor channel
    STAT_FEATURES = [
        "mean", "std", "min", "max", "slope", 
        "final", "range", "trend"  # trend = final - initial
    ]
    
    def __init__(self, config: Optional[ModelConfig] = None):
        if not TORCH_AVAILABLE:
            raise ImportError("PyTorch is required")
        
        super().__init__()
        self.config = config or ModelConfig()
        
        # Input size: num_sensors * num_stat_features
        num_sensors = len(self.config.input_features)
        num_stats = len(self.STAT_FEATURES)
        input_size = num_sensors * num_stats
        
        # Simple MLP
        layers = []
        in_size = input_size
        hidden_sizes = [128, 64, 32]
        
        for size in hidden_sizes:
            layers.extend([
                nn.Linear(in_size, size),
                nn.ReLU(),
                nn.Dropout(self.config.dropout),
            ])
            in_size = size
        
        layers.append(nn.Linear(in_size, self.config.num_classes))
        self.mlp = nn.Sequential(*layers)
        
        self.class_labels: List[str] = []
    
    @staticmethod
    def extract_features(time_series: Dict[str, List[float]]) -> 'torch.Tensor':
        """
        Extract statistical features from time series.
        
        Args:
            time_series: Dict mapping sensor name to list of values
            
        Returns:
            Feature tensor of shape (num_sensors * num_stat_features,)
        """
        import numpy as np
        
        features = []
        for sensor_name, values in time_series.items():
            arr = np.array(values)
            if len(arr) == 0:
                arr = np.array([0.0])
            
            features.extend([
                np.mean(arr),                    # mean
                np.std(arr),                     # std
                np.min(arr),                     # min
                np.max(arr),                     # max
                (arr[-1] - arr[0]) / len(arr),   # slope
                arr[-1],                         # final value
                np.max(arr) - np.min(arr),       # range
                arr[-1] - arr[0],                # trend
            ])
        
        return torch.tensor(features, dtype=torch.float32)
    
    def forward(self, x: 'torch.Tensor') -> 'torch.Tensor':
        """Forward pass on feature tensor."""
        return self.mlp(x)
    
    def predict_proba(self, x: 'torch.Tensor') -> 'torch.Tensor':
        """Get probability distribution."""
        return F.softmax(self.forward(x), dim=-1)
    
    def save(self, path: str) -> None:
        """Save model."""
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        torch.save({
            'config': self.config.to_dict(),
            'state_dict': self.state_dict(),
            'class_labels': self.class_labels,
        }, path)
    
    @classmethod
    def load(cls, path: str) -> 'SimpleDiagnosticModel':
        """Load model."""
        checkpoint = torch.load(path, map_location='cpu')
        config = ModelConfig.from_dict(checkpoint['config'])
        model = cls(config)
        model.load_state_dict(checkpoint['state_dict'])
        model.class_labels = checkpoint.get('class_labels', [])
        return model
