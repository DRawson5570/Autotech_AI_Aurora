#!/usr/bin/env python3
"""
Test script for Predictive Diagnostics Module

Run with:
    python -m pytest addons/predictive_diagnostics/test_diagnostics.py -v
    
Or directly:
    python addons/predictive_diagnostics/test_diagnostics.py
"""

import sys
from pathlib import Path
from datetime import datetime

# Add parent paths
sys.path.insert(0, str(Path(__file__).parent.parent.parent))


def test_imports():
    """Test that all module components import correctly."""
    print("\n1. Testing imports...")
    
    # Core models
    from addons.predictive_diagnostics.models import (
        Vehicle, ScannerData, PIDReading, DTCCode,
        DiagnosticResult, DiagnosticHypothesis
    )
    print("   ✓ Models imported")
    
    # Taxonomy
    from addons.predictive_diagnostics.taxonomy import (
        ComponentType, FailureMode, FAILURE_TAXONOMY
    )
    print("   ✓ Taxonomy imported")
    
    # Signatures
    from addons.predictive_diagnostics.signatures import (
        SignalPattern, FailureSignature, FAILURE_SIGNATURES
    )
    print("   ✓ Signatures imported")
    
    # Fault trees
    from addons.predictive_diagnostics.fault_tree import (
        FaultNode, FaultTree, FaultTreeGenerator
    )
    print("   ✓ Fault trees imported")
    
    # Classifier
    from addons.predictive_diagnostics.classifier import (
        DiagnosticClassifier, COMMON_PID_FEATURES
    )
    print("   ✓ Classifier imported")
    
    # Genetic algorithm
    from addons.predictive_diagnostics.genetic import (
        GeneticRuleDiscovery, DiagnosticRule, Condition
    )
    print("   ✓ Genetic algorithm imported")
    
    # Synthetic data
    from addons.predictive_diagnostics.synthetic_data import (
        SyntheticDataGenerator, SystemProfile
    )
    print("   ✓ Synthetic data imported")
    
    # Training
    from addons.predictive_diagnostics.training import (
        TrainingPipeline, TrainingConfig
    )
    print("   ✓ Training imported")
    
    # Reasoner
    from addons.predictive_diagnostics.reasoner import (
        DiagnosticReasoner, SymptomReport
    )
    print("   ✓ Reasoner imported")
    
    # Extractor
    from addons.predictive_diagnostics.extractor import (
        MitchellDataExtractor, ExtractionResult
    )
    print("   ✓ Extractor imported")
    
    # Main module
    import addons.predictive_diagnostics as pd
    assert pd.__version__ == "0.1.0"
    print("   ✓ Main module imported, version: " + pd.__version__)
    
    print("\n   All imports successful!")


def test_taxonomy():
    """Test the failure taxonomy database."""
    print("\n2. Testing taxonomy...")
    
    from addons.predictive_diagnostics.taxonomy import (
        ComponentType, FailureMode, FAILURE_TAXONOMY
    )
    
    # Check component types exist
    assert ComponentType.SENSOR is not None
    assert ComponentType.RELAY is not None
    assert ComponentType.MOTOR is not None
    print(f"   ✓ Component types defined: {len(ComponentType)}")
    
    # Check failure modes exist for each type (they are dicts, not lists)
    sensor_failures = FAILURE_TAXONOMY.get(ComponentType.SENSOR, {})
    relay_failures = FAILURE_TAXONOMY.get(ComponentType.RELAY, {})
    motor_failures = FAILURE_TAXONOMY.get(ComponentType.MOTOR, {})
    
    print(f"   ✓ Sensor failure modes: {len(sensor_failures)}")
    print(f"   ✓ Relay failure modes: {len(relay_failures)}")
    print(f"   ✓ Motor failure modes: {len(motor_failures)}")
    
    # Check failure mode structure (dict access with key)
    if sensor_failures:
        first_key = list(sensor_failures.keys())[0]
        fm = sensor_failures[first_key]
        assert fm.name is not None
        assert fm.symptoms is not None
        assert fm.diagnostic_approach is not None
        print(f"   ✓ Failure mode structure valid: {fm.name}")


def test_signatures():
    """Test signal signatures."""
    print("\n3. Testing signatures...")
    
    from addons.predictive_diagnostics.signatures import (
        SignalPattern, FailureSignature, FAILURE_SIGNATURES
    )
    
    print(f"   ✓ Signature patterns defined: {len(FAILURE_SIGNATURES)}")
    
    # Check signature structure - FailureSignature has primary_signals, not patterns
    for name, sig in list(FAILURE_SIGNATURES.items())[:3]:
        assert sig.primary_signals is not None
        assert sig.associated_dtcs is not None
        print(f"   ✓ Signature '{name}': {len(sig.primary_signals)} primary signals")


def test_fault_tree():
    """Test fault tree generation."""
    print("\n4. Testing fault trees...")
    
    from addons.predictive_diagnostics.fault_tree import (
        FaultNode, FaultTree, FaultTreeGenerator
    )
    
    # Create mock components as dicts (not ExtractedComponent objects)
    components = [
        {
            "id": "S1",
            "name": "Coolant Temp Sensor",
            "type": "sensor",
            "connected_to": ["K1"],
        },
        {
            "id": "K1",
            "name": "Cooling Relay",
            "type": "relay",
            "connected_to": ["M1"],
        },
        {
            "id": "M1",
            "name": "Coolant Pump Motor",
            "type": "motor",
            "connected_to": [],
        },
    ]
    
    # Generate fault tree
    generator = FaultTreeGenerator()
    tree = generator.generate_from_components(
        vehicle_year=2020,
        vehicle_make="Chevrolet",
        vehicle_model="Bolt",
        vehicle_engine="Electric",
        system="Cooling System",
        components=components,
        tsbs=[],
    )
    
    assert tree is not None
    print(f"   ✓ Fault tree generated for {tree.vehicle_make} {tree.vehicle_model}")
    print(f"   ✓ System: {tree.system}")
    
    # Get all failure modes using the actual attribute
    all_nodes = tree.fault_nodes
    print(f"   ✓ Total fault nodes in tree: {len(all_nodes)}")


def test_classifier():
    """Test the diagnostic classifier."""
    print("\n5. Testing classifier...")
    
    from addons.predictive_diagnostics.classifier import (
        DiagnosticClassifier, COMMON_PID_FEATURES, TrainingExample
    )
    
    # Create classifier
    classifier = DiagnosticClassifier()
    print(f"   ✓ Classifier created")
    print(f"   ✓ Common PID features: {len(COMMON_PID_FEATURES)}")
    
    # Create more mock training examples to satisfy sklearn requirements
    # Need at least 5 samples per class for train_test_split with stratify
    examples = []
    
    # Normal examples
    for i in range(10):
        examples.append(TrainingExample(
            example_id=f"normal_{i}",
            vehicle_year=2020,
            vehicle_make="Chevrolet",
            vehicle_model="Bolt",
            pid_values={"coolant_temp": 85.0 + i, "engine_rpm": 780.0 + i*5},
            dtc_codes=[],
            fault_label="normal",
        ))
    
    # Overheat examples
    for i in range(10):
        examples.append(TrainingExample(
            example_id=f"overheat_{i}",
            vehicle_year=2020,
            vehicle_make="Chevrolet",
            vehicle_model="Bolt",
            pid_values={"coolant_temp": 110.0 + i*2, "engine_rpm": 830.0 + i*5},
            dtc_codes=["P0217"],
            fault_label="coolant_pump_failure",
        ))
    
    # Thermostat stuck examples
    for i in range(10):
        examples.append(TrainingExample(
            example_id=f"thermostat_{i}",
            vehicle_year=2020,
            vehicle_make="Chevrolet",
            vehicle_model="Bolt",
            pid_values={"coolant_temp": 45.0 + i, "engine_rpm": 750.0 + i*5},
            dtc_codes=["P0128"],
            fault_label="thermostat_stuck_open",
        ))
    
    # Train - classifier.train takes List[TrainingExample]
    result = classifier.train(examples)
    print(f"   ✓ Classifier trained on {len(examples)} examples")
    accuracy = result.get('accuracy', 0)
    if isinstance(accuracy, float):
        print(f"   ✓ Training accuracy: {accuracy:.1%}")
    else:
        print(f"   ✓ Training accuracy: {accuracy}")
    
    # Predict - need to create a test TrainingExample
    test_example = TrainingExample(
        example_id="test",
        vehicle_year=2020,
        vehicle_make="Chevrolet",
        vehicle_model="Bolt",
        pid_values={"coolant_temp": 118.0, "engine_rpm": 870.0},
        dtc_codes=["P0217"],
        fault_label="unknown",
    )
    prediction = classifier.predict([test_example])
    
    print(f"   ✓ Prediction: {prediction[0] if prediction else 'N/A'}")


def test_genetic():
    """Test genetic algorithm rule discovery."""
    print("\n6. Testing genetic algorithm...")
    
    from addons.predictive_diagnostics.genetic import (
        GeneticRuleDiscovery, DiagnosticRule, Condition, Operator
    )
    from addons.predictive_diagnostics.classifier import TrainingExample
    
    # Create GA
    ga = GeneticRuleDiscovery(
        population_size=20,
        max_generations=5,  # Small for testing
    )
    print(f"   ✓ GA created with pop={ga.population_size}")
    
    # Create mock training examples using the classifier's TrainingExample
    examples = [
        TrainingExample(
            example_id="1",
            vehicle_year=2020,
            vehicle_make="Chevrolet",
            vehicle_model="Bolt",
            pid_values={"coolant_temp": 90.0, "engine_rpm": 800.0},
            dtc_codes=[],
            fault_label="normal",
        ),
        TrainingExample(
            example_id="2",
            vehicle_year=2020,
            vehicle_make="Chevrolet",
            vehicle_model="Bolt",
            pid_values={"coolant_temp": 115.0, "engine_rpm": 850.0},
            dtc_codes=["P0217"],
            fault_label="fault_a",
        ),
        TrainingExample(
            example_id="3",
            vehicle_year=2020,
            vehicle_make="Chevrolet",
            vehicle_model="Bolt",
            pid_values={"coolant_temp": 50.0, "engine_rpm": 780.0},
            dtc_codes=["P0128"],
            fault_label="fault_b",
        ),
    ]
    
    # Evolve rules - method takes List[TrainingExample]
    rules = ga.evolve(examples)
    
    print(f"   ✓ Rules evolved: {len(rules)}")
    
    # Check rule structure
    if rules:
        first_key = list(rules.keys())[0]
        rule = rules[first_key]
        assert rule.diagnosis is not None
        assert rule.conditions is not None
        print(f"   ✓ Best rule diagnosis: {rule.diagnosis}")
        print(f"   ✓ Rule fitness: {rule.fitness:.3f}")


def test_synthetic_data():
    """Test synthetic data generation."""
    print("\n7. Testing synthetic data generation...")
    
    from addons.predictive_diagnostics.synthetic_data import SyntheticDataGenerator
    from addons.predictive_diagnostics.fault_tree import FaultTree, FaultTreeGenerator
    
    # Create a fault tree using the generator
    components = [
        {
            "id": "S1",
            "name": "Coolant Temp Sensor",
            "type": "sensor",
            "connected_to": [],
        },
        {
            "id": "R1",
            "name": "Coolant Pump Relay",
            "type": "relay",
            "connected_to": ["M1"],
        },
    ]
    
    generator = FaultTreeGenerator()
    tree = generator.generate_from_components(
        vehicle_year=2020,
        vehicle_make="Chevrolet",
        vehicle_model="Bolt",
        vehicle_engine="Electric",
        system="Cooling System",
        components=components,
        tsbs=[],
    )
    
    # Generate synthetic data
    data_generator = SyntheticDataGenerator()
    examples = data_generator.generate_from_fault_tree(
        fault_tree=tree,
        n_examples_per_fault=10,
        system_profile="engine_idle",
    )
    
    print(f"   ✓ Generated {len(examples)} training examples")
    
    if examples:
        example = examples[0]
        print(f"   ✓ Example label: {example.fault_label}")
        print(f"   ✓ Example features: {len(example.pid_values)}")


def test_reasoner():
    """Test the diagnostic reasoner."""
    print("\n8. Testing diagnostic reasoner...")
    
    from addons.predictive_diagnostics.reasoner import DiagnosticReasoner, SymptomReport
    from addons.predictive_diagnostics.models import Vehicle, ScannerData, PIDReading, DTCCode
    
    # Create vehicle first
    vehicle = Vehicle(
        year=2020,
        make="Chevrolet",
        model="Bolt",
        engine="Electric",
    )
    
    # Create scanner data - requires vehicle
    scanner_data = ScannerData(
        vehicle=vehicle,
        pids=[
            PIDReading(pid="0x05", name="COOLANT_TEMP", value=115.0, unit="°C"),
            PIDReading(pid="0x0C", name="ENGINE_RPM", value=850.0, unit="RPM"),
        ],
        dtcs=[
            DTCCode(code="P0217", description="Coolant Overtemperature"),
        ],
    )
    
    symptoms = SymptomReport(
        descriptions=["Engine overheating warning light"],
    )
    
    # Create reasoner
    reasoner = DiagnosticReasoner()
    print(f"   ✓ Reasoner created")
    
    # Run diagnosis (without trained models - should still work with rules)
    result = reasoner.diagnose(vehicle, scanner_data, symptoms)
    
    assert result is not None
    print(f"   ✓ Diagnosis complete")
    print(f"   ✓ Hypotheses: {len(result.hypotheses)}")
    
    if result.hypotheses:
        top = result.hypotheses[0]
        print(f"   ✓ Top hypothesis: {top.fault_node_id}")
        print(f"   ✓ Confidence: {top.probability:.1%}")
    
    # Format output
    formatted = reasoner.format_diagnosis_text(result)
    assert len(formatted) > 0
    print(f"   ✓ Formatted output: {len(formatted)} chars")


def test_extractor():
    """Test the Mitchell data extractor."""
    print("\n9. Testing Mitchell extractor...")
    
    import asyncio
    from addons.predictive_diagnostics.extractor import MitchellDataExtractor
    
    async def do_test():
        extractor = MitchellDataExtractor()
        
        # Extract mock data
        result = await extractor.extract_for_vehicle(
            year=2020,
            make="Chevrolet",
            model="Bolt",
            system="Cooling System",
        )
        
        assert result is not None
        print(f"   ✓ Extraction complete in {result.extraction_time_seconds:.2f}s")
        print(f"   ✓ Components: {len(result.components)}")
        print(f"   ✓ TSBs: {len(result.tsbs)}")
        print(f"   ✓ DTCs: {len(result.dtc_info)}")
        
        if result.components:
            comp = result.components[0]
            print(f"   ✓ First component: {comp.name} ({comp.component_type})")
    
    asyncio.run(do_test())


def test_integration():
    """Test full integration: extract -> train -> diagnose."""
    print("\n10. Testing full integration...")
    
    import asyncio
    from addons.predictive_diagnostics.extractor import MitchellDataExtractor
    from addons.predictive_diagnostics.training import TrainingPipeline, TrainingConfig
    from addons.predictive_diagnostics.reasoner import DiagnosticReasoner, SymptomReport
    from addons.predictive_diagnostics.models import Vehicle, ScannerData, PIDReading, DTCCode
    import tempfile
    
    async def do_integration():
        # 1. Extract data
        print("   Step 1: Extracting data...")
        extractor = MitchellDataExtractor()
        extraction = await extractor.extract_for_vehicle(
            year=2020,
            make="Chevrolet",
            model="Bolt",
            system="Cooling System",
        )
        print(f"   ✓ Extracted {len(extraction.components)} components")
        
        # Convert ExtractedComponent objects to dicts for training
        components = [
            {
                "id": comp.id,
                "name": comp.name,
                "type": comp.component_type,
                "connected_to": comp.connected_to,
                "specifications": comp.specifications,
            }
            for comp in extraction.components
        ]
        
        tsbs = [
            {
                "id": tsb.id,
                "title": tsb.title,
                "affected_components": tsb.affected_components,
            }
            for tsb in extraction.tsbs
        ]
        
        # If no components from extractor, skip training test
        if not components:
            print("   ⚠ No components extracted (mock mode), skipping training test")
            print("   Integration test complete (partial)!")
            return
        
        # 2. Train models
        print("   Step 2: Training models...")
        
        # Use correct parameter names
        config = TrainingConfig(
            rf_n_estimators=10,  # Small for testing
            rf_max_depth=5,
            ga_population_size=10,
            ga_max_generations=3,
            n_synthetic_examples_per_fault=20,
        )
        
        with tempfile.TemporaryDirectory() as tmpdir:
            config.model_output_dir = tmpdir
            
            pipeline = TrainingPipeline(config)
            
            # Use the correct train() signature
            result = pipeline.train(
                year=extraction.vehicle_year,
                make=extraction.vehicle_make,
                model=extraction.vehicle_model,
                system=extraction.system,
                components=components,
                tsbs=tsbs,
                engine=extraction.vehicle_engine,
            )
            
            if result.success:
                print(f"   ✓ Training complete: accuracy={result.rf_validation_accuracy:.1%}")
            else:
                print(f"   ⚠ Training had issues: {result.error_message}")
            
            # 3. Diagnose
            print("   Step 3: Running diagnosis...")
            reasoner = DiagnosticReasoner(model_dir=tmpdir)
            
            vehicle = Vehicle(
                year=2020,
                make="Chevrolet",
                model="Bolt",
                engine="Electric",
            )
            
            scanner_data = ScannerData(
                vehicle=vehicle,
                pids=[
                    PIDReading(pid="0x05", name="COOLANT_TEMP", value=118.0, unit="°C"),
                ],
                dtcs=[
                    DTCCode(code="P0217", description="Coolant Overtemperature"),
                ],
            )
            
            symptoms = SymptomReport(
                descriptions=["Overheating warning"],
            )
            
            diagnosis = reasoner.diagnose(vehicle, scanner_data, symptoms)
            print(f"   ✓ Diagnosis complete: {len(diagnosis.hypotheses)} hypotheses")
            
            if diagnosis.hypotheses:
                print(f"   ✓ Top diagnosis: {diagnosis.hypotheses[0].fault_node_id}")
    
    asyncio.run(do_integration())
    
    print("\n   Integration test complete!")


def run_all_tests():
    """Run all tests."""
    print("=" * 60)
    print("PREDICTIVE DIAGNOSTICS MODULE - TEST SUITE")
    print("=" * 60)
    
    tests = [
        test_imports,
        test_taxonomy,
        test_signatures,
        test_fault_tree,
        test_classifier,
        test_genetic,
        test_synthetic_data,
        test_reasoner,
        test_extractor,
        test_integration,
    ]
    
    passed = 0
    failed = 0
    
    for test in tests:
        try:
            test()
            passed += 1
        except Exception as e:
            print(f"\n   ✗ FAILED: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"RESULTS: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
