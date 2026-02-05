#!/bin/bash
# Generate synthetic diagnostic training data for all 19 systems (87 failure modes)
# Uses 12 parallel workers on localhost (pychrono requires AVX2, only available locally)
cd "$(dirname "$0")"

# 45000 samples = ~500 per failure mode across 87 modes
conda run -n chrono_test python batch_generator.py --count 45000 --workers 12 --output ../training_data/chrono_synthetic

echo "Generation complete. To retrain the model:"
echo "  conda run -n open-webui python train_twostage_xgb.py"
