#!/usr/bin/env python3
"""
Analyze model confusion to understand which failure modes look similar.
"""

import sys
import json
import numpy as np
sys.path.insert(0, "/home/drawson/autotech_ai")

import torch
from torch.utils.data import DataLoader
from addons.predictive_diagnostics.ml import (
    DiagnosticModel,
    ModelConfig,
)
from addons.predictive_diagnostics.ml.trainer import DiagnosticDataset

def analyze_confusion():
    # Load dataset
    dataset_path = "/tmp/pd_training_data/cooling_dataset.json"
    with open(dataset_path) as f:
        samples = json.load(f)
    
    # Build label mapping
    labels = sorted(set(s["label"] for s in samples))
    label_to_idx = {label: idx for idx, label in enumerate(labels)}
    idx_to_label = {idx: label for label, idx in label_to_idx.items()}
    
    # Create dataset with raw sequences
    feature_names = [
        "coolant_temp", "engine_temp", "thermostat_position",
        "fan_state", "coolant_flow", "stft", "ltft"
    ]
    
    dataset = DiagnosticDataset(
        samples, feature_names, label_to_idx, use_features=False
    )
    loader = DataLoader(dataset, batch_size=64, shuffle=False)
    
    # Load trained model
    config = ModelConfig(
        num_classes=len(labels),
        cnn_channels=[64, 128, 128],
        lstm_hidden_size=256,
        lstm_num_layers=2,
        dense_sizes=[256, 128],
        dropout=0.3,
    )
    model = DiagnosticModel(config)
    
    checkpoint = torch.load("/tmp/pd_trained_model.pt", map_location="cpu")
    model.load_state_dict(checkpoint["state_dict"])
    model.eval()
    
    # Get predictions
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = model.to(device)
    
    all_preds = []
    all_labels = []
    
    with torch.no_grad():
        for X, y in loader:
            X, y = X.to(device), y.to(device)
            outputs = model(X)
            preds = outputs.argmax(dim=1)
            all_preds.extend(preds.cpu().numpy())
            all_labels.extend(y.cpu().numpy())
    
    all_preds = np.array(all_preds)
    all_labels = np.array(all_labels)
    
    # Build confusion matrix
    num_classes = len(labels)
    confusion = np.zeros((num_classes, num_classes), dtype=int)
    
    for true, pred in zip(all_labels, all_preds):
        confusion[true, pred] += 1
    
    print("=" * 80)
    print("CONFUSION MATRIX ANALYSIS")
    print("=" * 80)
    
    # Find most confused pairs
    confusions = []
    for i in range(num_classes):
        for j in range(num_classes):
            if i != j and confusion[i, j] > 0:
                confusions.append({
                    'true': idx_to_label[i],
                    'pred': idx_to_label[j],
                    'count': confusion[i, j],
                    'true_total': confusion[i].sum(),
                    'pct': confusion[i, j] / confusion[i].sum() * 100
                })
    
    confusions.sort(key=lambda x: -x['count'])
    
    print("\nTop 20 Confusion Pairs:")
    print("-" * 80)
    for c in confusions[:20]:
        print(f"  {c['true']:30} → {c['pred']:30} : {c['count']:3} ({c['pct']:.1f}%)")
    
    # Per-class accuracy
    print("\n" + "=" * 80)
    print("PER-CLASS ACCURACY")
    print("=" * 80)
    
    class_accs = []
    for i in range(num_classes):
        correct = confusion[i, i]
        total = confusion[i].sum()
        acc = correct / total if total > 0 else 0
        class_accs.append((idx_to_label[i], acc, correct, total))
    
    class_accs.sort(key=lambda x: x[1])
    
    for label, acc, correct, total in class_accs:
        status = "✅" if acc >= 0.7 else "⚠️" if acc >= 0.5 else "❌"
        print(f"  {status} {label:35}: {acc:.1%} ({correct}/{total})")
    
    # Find similar failure modes in physics
    print("\n" + "=" * 80)
    print("PHYSICS ANALYSIS - Why these get confused?")
    print("=" * 80)
    
    # Group failures by symptom signature
    from addons.predictive_diagnostics.knowledge.failures import get_all_failure_modes
    
    failures = get_all_failure_modes()
    
    # Group by primary symptom
    by_symptom = {}
    for f in failures:
        for s in f.symptoms:
            if s not in by_symptom:
                by_symptom[s] = []
            by_symptom[s].append(f.name)
    
    print("\nFailure modes sharing symptoms:")
    for symptom, failure_names in sorted(by_symptom.items(), key=lambda x: -len(x[1])):
        if len(failure_names) > 1:
            print(f"\n  {symptom}:")
            for name in failure_names:
                print(f"    - {name}")


if __name__ == "__main__":
    analyze_confusion()
