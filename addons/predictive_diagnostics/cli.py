#!/usr/bin/env python3
"""
Command Line Interface for Predictive Diagnostics Module

Usage:
    # Train on a vehicle system (mock data)
    python -m addons.predictive_diagnostics.cli train --year 2020 --make Chevrolet --model Bolt --system "Cooling System"
    
    # Train from extracted data
    python -m addons.predictive_diagnostics.cli train --input extracted_data.json
    
    # Diagnose with scanner data
    python -m addons.predictive_diagnostics.cli diagnose --model models/bolt_cooling --scanner scanner_data.json
    
    # Quick diagnosis from symptoms
    python -m addons.predictive_diagnostics.cli quick "2020 Bolt overheating warning, P0217"
    
    # List trained models
    python -m addons.predictive_diagnostics.cli list-models
    
    # Show system info
    python -m addons.predictive_diagnostics.cli info
"""

import asyncio
import argparse
import json
import sys
import os
from pathlib import Path
from datetime import datetime

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def cmd_train(args):
    """Train models on a vehicle system."""
    from addons.predictive_diagnostics.extractor import MitchellDataExtractor
    from addons.predictive_diagnostics.training import TrainingPipeline, TrainingConfig
    
    async def do_train():
        print(f"\n{'='*60}")
        print("PREDICTIVE DIAGNOSTICS - TRAINING")
        print(f"{'='*60}\n")
        
        if args.input:
            # Load from extracted data file
            print(f"Loading extracted data from: {args.input}")
            with open(args.input, 'r') as f:
                data = json.load(f)
            # Parse data into ExtractionResult...
            print("TODO: Parse extraction result from JSON")
            return
        
        # Extract data (mock if Mitchell not available)
        print(f"Vehicle: {args.year} {args.make} {args.model}")
        print(f"System:  {args.system}")
        if args.engine:
            print(f"Engine:  {args.engine}")
        print()
        
        extractor = MitchellDataExtractor()
        print("Extracting data from Mitchell (or mock)...")
        extraction = await extractor.extract_for_vehicle(
            year=args.year,
            make=args.make,
            model=args.model,
            system=args.system,
            engine=args.engine,
        )
        
        print(f"\nExtraction complete in {extraction.extraction_time_seconds:.1f}s:")
        print(f"  - {len(extraction.components)} components")
        print(f"  - {len(extraction.tsbs)} TSBs")
        print(f"  - {len(extraction.dtc_info)} DTCs")
        
        if extraction.errors:
            print(f"  - Errors: {extraction.errors}")
        
        # Configure training
        config = TrainingConfig(
            n_trees=100,
            max_depth=15,
            ga_population=100,
            ga_generations=50,
            synthetic_samples_per_fault=200,
        )
        
        # Determine output path
        output_dir = Path(args.output) if args.output else Path("models")
        model_name = f"{args.make.lower()}_{args.model.lower()}_{args.system.lower().replace(' ', '_')}"
        model_path = output_dir / model_name
        
        print(f"\nTraining configuration:")
        print(f"  - Random Forest: {config.n_trees} trees, max_depth={config.max_depth}")
        print(f"  - Genetic Algorithm: pop={config.ga_population}, gens={config.ga_generations}")
        print(f"  - Synthetic samples per fault: {config.synthetic_samples_per_fault}")
        print(f"  - Output: {model_path}")
        print()
        
        # Run training
        pipeline = TrainingPipeline(config)
        print("Starting training pipeline...")
        
        result = await pipeline.train(extraction, model_path)
        
        print(f"\n{'='*60}")
        print("TRAINING COMPLETE")
        print(f"{'='*60}")
        print(f"Random Forest accuracy: {result.rf_accuracy:.1%}")
        print(f"GA rules discovered: {result.ga_rules_count}")
        print(f"Total training time: {result.training_time:.1f}s")
        print(f"Models saved to: {model_path}")
        
        if result.top_features:
            print(f"\nTop 5 predictive features:")
            for feat, imp in result.top_features[:5]:
                print(f"  {feat}: {imp:.3f}")
    
    asyncio.run(do_train())


def cmd_diagnose(args):
    """Diagnose using trained models and scanner data."""
    from addons.predictive_diagnostics.reasoner import DiagnosticReasoner, SymptomReport
    from addons.predictive_diagnostics.models import ScannerData, PIDReading, DTCCode
    
    print(f"\n{'='*60}")
    print("PREDICTIVE DIAGNOSTICS - DIAGNOSIS")
    print(f"{'='*60}\n")
    
    # Load scanner data
    if args.scanner:
        print(f"Loading scanner data from: {args.scanner}")
        with open(args.scanner, 'r') as f:
            data = json.load(f)
        
        scanner_data = ScannerData(
            timestamp=datetime.now(),
            pids=[PIDReading(**p) for p in data.get('pids', [])],
            dtcs=[DTCCode(**d) for d in data.get('dtcs', [])],
            vehicle_year=data.get('year'),
            vehicle_make=data.get('make'),
            vehicle_model=data.get('model'),
        )
    else:
        print("No scanner data provided, using example data...")
        scanner_data = ScannerData(
            timestamp=datetime.now(),
            pids=[
                PIDReading(pid_id="0x05", name="COOLANT_TEMP", value=115.0, unit="°C"),
                PIDReading(pid_id="0x0C", name="ENGINE_RPM", value=850.0, unit="RPM"),
            ],
            dtcs=[
                DTCCode(code="P0217", description="Coolant Overtemperature"),
            ],
        )
    
    # Parse symptoms
    symptoms = SymptomReport(
        reported_symptoms=args.symptoms or [],
    )
    
    # Load reasoner
    print(f"Loading models from: {args.model}")
    reasoner = DiagnosticReasoner()
    reasoner.load_models(args.model)
    
    # Run diagnosis
    print("\nRunning diagnostic analysis...")
    result = reasoner.diagnose(scanner_data, symptoms)
    
    # Display results
    print(f"\n{'='*60}")
    print("DIAGNOSIS RESULTS")
    print(f"{'='*60}")
    print(reasoner.format_diagnosis_text(result))


def cmd_quick(args):
    """Quick diagnosis from natural language input."""
    from addons.predictive_diagnostics.reasoner import DiagnosticReasoner
    
    print(f"\n{'='*60}")
    print("PREDICTIVE DIAGNOSTICS - QUICK DIAGNOSIS")
    print(f"{'='*60}\n")
    
    print(f"Input: {args.query}")
    print()
    
    reasoner = DiagnosticReasoner()
    
    # For quick diagnosis, we don't need trained models - use rules
    result = reasoner.quick_diagnosis(args.query)
    
    print(result)


def cmd_list_models(args):
    """List trained models."""
    from addons.predictive_diagnostics.training import ModelManager
    
    print(f"\n{'='*60}")
    print("TRAINED MODELS")
    print(f"{'='*60}\n")
    
    models_dir = Path(args.dir) if args.dir else Path("models")
    
    if not models_dir.exists():
        print(f"Models directory not found: {models_dir}")
        return
    
    manager = ModelManager()
    models = list(models_dir.glob("*/metadata.json"))
    
    if not models:
        print("No trained models found.")
        return
    
    for meta_path in models:
        model_dir = meta_path.parent
        with open(meta_path, 'r') as f:
            meta = json.load(f)
        
        print(f"Model: {model_dir.name}")
        print(f"  Vehicle: {meta.get('vehicle', 'Unknown')}")
        print(f"  System: {meta.get('system', 'Unknown')}")
        print(f"  Trained: {meta.get('trained_at', 'Unknown')}")
        print(f"  Accuracy: {meta.get('accuracy', 'Unknown')}")
        print()


def cmd_info(args):
    """Show system information."""
    import addons.predictive_diagnostics as pd
    
    print(f"\n{'='*60}")
    print("PREDICTIVE DIAGNOSTICS - SYSTEM INFO")
    print(f"{'='*60}\n")
    
    print(f"Version: {pd.__version__}")
    print()
    
    print("Components:")
    print("  - Failure Taxonomy: Defines component types and failure modes")
    print("  - Signal Signatures: Maps failures to observable patterns")
    print("  - Fault Trees: First principles failure modeling")
    print("  - Random Forest: PID-based fault classification")
    print("  - Genetic Algorithm: Automated rule discovery")
    print("  - Synthetic Data: Training data generation")
    print("  - Diagnostic Reasoner: Runtime inference engine")
    print("  - Mitchell Extractor: Training data extraction")
    print()
    
    # Check dependencies
    print("Dependencies:")
    deps = [
        ("scikit-learn", "sklearn"),
        ("numpy", "numpy"),
        ("pydantic", "pydantic"),
    ]
    
    for name, module in deps:
        try:
            m = __import__(module)
            version = getattr(m, '__version__', 'unknown')
            print(f"  ✓ {name}: {version}")
        except ImportError:
            print(f"  ✗ {name}: NOT INSTALLED")


def main():
    parser = argparse.ArgumentParser(
        description="Predictive Diagnostics CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__,
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # Train command
    train_parser = subparsers.add_parser("train", help="Train models on a vehicle system")
    train_parser.add_argument("--year", type=int, help="Vehicle year")
    train_parser.add_argument("--make", help="Vehicle make")
    train_parser.add_argument("--model", help="Vehicle model")
    train_parser.add_argument("--engine", help="Engine specification")
    train_parser.add_argument("--system", help="System to train on (e.g., 'Cooling System')")
    train_parser.add_argument("--input", help="Input extracted data JSON file")
    train_parser.add_argument("--output", help="Output directory for models")
    train_parser.set_defaults(func=cmd_train)
    
    # Diagnose command
    diagnose_parser = subparsers.add_parser("diagnose", help="Diagnose using trained models")
    diagnose_parser.add_argument("--model", required=True, help="Path to trained model directory")
    diagnose_parser.add_argument("--scanner", help="Scanner data JSON file")
    diagnose_parser.add_argument("--symptoms", nargs="+", help="Reported symptoms")
    diagnose_parser.set_defaults(func=cmd_diagnose)
    
    # Quick command
    quick_parser = subparsers.add_parser("quick", help="Quick diagnosis from natural language")
    quick_parser.add_argument("query", help="Natural language query (e.g., '2020 Bolt overheating')")
    quick_parser.set_defaults(func=cmd_quick)
    
    # List models command
    list_parser = subparsers.add_parser("list-models", help="List trained models")
    list_parser.add_argument("--dir", help="Models directory")
    list_parser.set_defaults(func=cmd_list_models)
    
    # Info command
    info_parser = subparsers.add_parser("info", help="Show system information")
    info_parser.set_defaults(func=cmd_info)
    
    args = parser.parse_args()
    
    if args.command is None:
        parser.print_help()
        return
    
    args.func(args)


if __name__ == "__main__":
    main()
