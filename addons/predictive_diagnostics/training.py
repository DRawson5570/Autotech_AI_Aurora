"""
Training Pipeline

End-to-end training pipeline for the predictive diagnostics system.
Orchestrates:
1. Mitchell data extraction (learning phase)
2. Fault tree generation
3. Synthetic data generation
4. Model training (Random Forest + GA)
5. Model evaluation and saving

This is the main entry point for training the diagnostic system.
After training, the model can diagnose faults WITHOUT Mitchell queries.
"""

import logging
import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime

from .fault_tree import FaultTree, FaultTreeGenerator, FaultTreeCache, Component
from .taxonomy import ComponentType, FAILURE_TAXONOMY
from .classifier import DiagnosticClassifier, TrainingExample, EnsembleClassifier
from .genetic import GeneticRuleDiscovery
from .synthetic_data import SyntheticDataGenerator

logger = logging.getLogger(__name__)


@dataclass
class TrainingConfig:
    """Configuration for the training pipeline."""
    # Data generation
    n_synthetic_examples_per_fault: int = 100
    system_profile: str = "engine_idle"
    noise_level: float = 0.1
    include_normal_ratio: float = 0.2
    
    # Random Forest
    rf_n_estimators: int = 100
    rf_max_depth: int = 15
    rf_min_samples_leaf: int = 5
    
    # Genetic Algorithm
    ga_population_size: int = 100
    ga_max_generations: int = 50
    ga_min_precision: float = 0.6
    ga_min_recall: float = 0.1
    
    # Output paths
    model_output_dir: str = "/tmp/predictive_diagnostics/models"
    fault_tree_cache_dir: str = "/tmp/predictive_diagnostics/fault_trees"
    
    def to_dict(self) -> Dict:
        return {
            "n_synthetic_examples_per_fault": self.n_synthetic_examples_per_fault,
            "system_profile": self.system_profile,
            "noise_level": self.noise_level,
            "include_normal_ratio": self.include_normal_ratio,
            "rf_n_estimators": self.rf_n_estimators,
            "rf_max_depth": self.rf_max_depth,
            "rf_min_samples_leaf": self.rf_min_samples_leaf,
            "ga_population_size": self.ga_population_size,
            "ga_max_generations": self.ga_max_generations,
            "ga_min_precision": self.ga_min_precision,
            "ga_min_recall": self.ga_min_recall,
            "model_output_dir": self.model_output_dir,
            "fault_tree_cache_dir": self.fault_tree_cache_dir,
        }


@dataclass
class TrainingResult:
    """Results from a training run."""
    success: bool
    vehicle: str
    system: str
    training_time_seconds: float
    
    # Data statistics
    n_fault_nodes: int = 0
    n_training_examples: int = 0
    n_validation_examples: int = 0
    
    # Model performance
    rf_train_accuracy: float = 0.0
    rf_validation_accuracy: float = 0.0
    rf_top_features: List[tuple] = field(default_factory=list)
    
    ga_n_rules_discovered: int = 0
    ga_best_fitness: float = 0.0
    
    # Paths
    rf_model_path: Optional[str] = None
    ga_rules_path: Optional[str] = None
    fault_tree_path: Optional[str] = None
    
    # Errors
    error_message: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "success": self.success,
            "vehicle": self.vehicle,
            "system": self.system,
            "training_time_seconds": self.training_time_seconds,
            "n_fault_nodes": self.n_fault_nodes,
            "n_training_examples": self.n_training_examples,
            "n_validation_examples": self.n_validation_examples,
            "rf_train_accuracy": self.rf_train_accuracy,
            "rf_validation_accuracy": self.rf_validation_accuracy,
            "rf_top_features": self.rf_top_features,
            "ga_n_rules_discovered": self.ga_n_rules_discovered,
            "ga_best_fitness": self.ga_best_fitness,
            "rf_model_path": self.rf_model_path,
            "ga_rules_path": self.ga_rules_path,
            "fault_tree_path": self.fault_tree_path,
            "error_message": self.error_message,
        }


class TrainingPipeline:
    """
    End-to-end training pipeline.
    
    Usage:
        pipeline = TrainingPipeline()
        result = pipeline.train(
            year=2020,
            make="Chevrolet",
            model="Bolt EV",
            system="Cooling System",
            components=[...],  # From Mitchell extraction
            tsbs=[...],        # From Mitchell extraction
        )
    """
    
    def __init__(self, config: TrainingConfig = None):
        """
        Initialize the pipeline.
        
        Args:
            config: Training configuration (uses defaults if not provided)
        """
        self.config = config or TrainingConfig()
        
        # Ensure output directories exist
        os.makedirs(self.config.model_output_dir, exist_ok=True)
        os.makedirs(self.config.fault_tree_cache_dir, exist_ok=True)
        
        # Initialize components
        self.fault_tree_generator = FaultTreeGenerator()
        self.fault_tree_cache = FaultTreeCache(self.config.fault_tree_cache_dir)
        self.synthetic_generator = SyntheticDataGenerator(
            noise_level=self.config.noise_level,
            include_normal_ratio=self.config.include_normal_ratio,
        )
        
        self.classifier = DiagnosticClassifier(
            n_estimators=self.config.rf_n_estimators,
            max_depth=self.config.rf_max_depth,
            min_samples_leaf=self.config.rf_min_samples_leaf,
        )
        
        self.ga_discovery = GeneticRuleDiscovery(
            population_size=self.config.ga_population_size,
            max_generations=self.config.ga_max_generations,
            min_precision=self.config.ga_min_precision,
            min_recall=self.config.ga_min_recall,
        )
    
    def _get_output_prefix(self, year: int, make: str, model: str, system: str) -> str:
        """Generate output filename prefix."""
        safe_make = make.lower().replace(" ", "_")
        safe_model = model.lower().replace(" ", "_")
        safe_system = system.lower().replace(" ", "_")
        return f"{year}_{safe_make}_{safe_model}_{safe_system}"
    
    def train(
        self,
        year: int,
        make: str,
        model: str,
        system: str,
        components: List[Dict[str, Any]],
        tsbs: List[Dict[str, Any]] = None,
        engine: str = None,
        real_examples: List[TrainingExample] = None,
        progress_callback: Callable[[str, float], None] = None,
    ) -> TrainingResult:
        """
        Run the complete training pipeline.
        
        Args:
            year: Vehicle year
            make: Vehicle make
            model: Vehicle model
            system: System name (e.g., "Cooling System")
            components: List of component dicts extracted from Mitchell
            tsbs: Optional list of TSB dicts
            engine: Optional engine specification
            real_examples: Optional real-world training examples
            progress_callback: Optional callback(stage, progress) for UI
            
        Returns:
            TrainingResult with model paths and performance metrics
        """
        start_time = datetime.now()
        vehicle_str = f"{year} {make} {model}"
        
        def report_progress(stage: str, progress: float):
            logger.info(f"Training progress: {stage} ({progress:.0%})")
            if progress_callback:
                progress_callback(stage, progress)
        
        try:
            report_progress("Initializing", 0.0)
            
            # Step 1: Generate or load fault tree
            report_progress("Generating fault tree", 0.1)
            
            # Check cache first
            fault_tree = self.fault_tree_cache.get(year, make, model, engine, system)
            
            if fault_tree is None:
                # Generate new fault tree
                fault_tree = self.fault_tree_generator.generate_from_components(
                    vehicle_year=year,
                    vehicle_make=make,
                    vehicle_model=model,
                    vehicle_engine=engine,
                    system=system,
                    components=components,
                    tsbs=tsbs or [],
                )
                # Cache it
                self.fault_tree_cache.put(fault_tree)
            
            n_fault_nodes = len(fault_tree.fault_nodes)
            logger.info(f"Fault tree has {n_fault_nodes} fault nodes")
            
            # Step 2: Generate synthetic training data
            report_progress("Generating synthetic data", 0.25)
            
            synthetic_examples = self.synthetic_generator.generate_from_fault_tree(
                fault_tree=fault_tree,
                n_examples_per_fault=self.config.n_synthetic_examples_per_fault,
                system_profile=self.config.system_profile,
            )
            
            # Combine with real examples if provided
            all_examples = synthetic_examples
            if real_examples:
                # Augment real examples
                augmented = self.synthetic_generator.generate_augmented(
                    real_examples,
                    augmentation_factor=5
                )
                all_examples.extend(augmented)
            
            n_training = len(all_examples)
            logger.info(f"Total training examples: {n_training}")
            
            # Step 3: Train Random Forest classifier
            report_progress("Training Random Forest", 0.4)
            
            rf_stats = self.classifier.train(all_examples, validation_split=0.2)
            
            logger.info(f"RF train accuracy: {rf_stats['train_accuracy']:.3f}")
            logger.info(f"RF validation accuracy: {rf_stats['validation_accuracy']:.3f}")
            
            # Step 4: Run Genetic Algorithm for rule discovery
            report_progress("Running Genetic Algorithm", 0.6)
            
            def ga_callback(gen: int, stats: Dict):
                progress = 0.6 + 0.3 * (gen / self.config.ga_max_generations)
                report_progress(f"GA generation {gen}", progress)
            
            ga_rules = self.ga_discovery.evolve(all_examples, callback=ga_callback)
            
            logger.info(f"GA discovered {len(ga_rules)} rules")
            
            # Step 5: Save models
            report_progress("Saving models", 0.95)
            
            output_prefix = self._get_output_prefix(year, make, model, system)
            
            # Save RF model
            rf_model_path = os.path.join(
                self.config.model_output_dir,
                f"{output_prefix}_rf_model.pkl"
            )
            self.classifier.save(rf_model_path)
            
            # Save GA rules
            ga_rules_path = os.path.join(
                self.config.model_output_dir,
                f"{output_prefix}_ga_rules.json"
            )
            self.ga_discovery.save(ga_rules_path)
            
            # Save fault tree
            fault_tree_path = os.path.join(
                self.config.model_output_dir,
                f"{output_prefix}_fault_tree.json"
            )
            with open(fault_tree_path, 'w') as f:
                f.write(fault_tree.to_json())
            
            # Build result
            training_time = (datetime.now() - start_time).total_seconds()
            
            report_progress("Complete", 1.0)
            
            return TrainingResult(
                success=True,
                vehicle=vehicle_str,
                system=system,
                training_time_seconds=training_time,
                n_fault_nodes=n_fault_nodes,
                n_training_examples=n_training,
                n_validation_examples=int(n_training * 0.2),
                rf_train_accuracy=rf_stats['train_accuracy'],
                rf_validation_accuracy=rf_stats['validation_accuracy'],
                rf_top_features=rf_stats['top_features'][:5],
                ga_n_rules_discovered=len(ga_rules),
                ga_best_fitness=max((r.fitness for r in ga_rules.values()), default=0.0),
                rf_model_path=rf_model_path,
                ga_rules_path=ga_rules_path,
                fault_tree_path=fault_tree_path,
            )
            
        except Exception as e:
            logger.error(f"Training failed: {e}", exc_info=True)
            training_time = (datetime.now() - start_time).total_seconds()
            
            return TrainingResult(
                success=False,
                vehicle=vehicle_str,
                system=system,
                training_time_seconds=training_time,
                error_message=str(e),
            )
    
    def train_from_fault_tree(
        self,
        fault_tree: FaultTree,
        real_examples: List[TrainingExample] = None,
        progress_callback: Callable[[str, float], None] = None,
    ) -> TrainingResult:
        """
        Train from an existing fault tree (skip Mitchell extraction).
        
        Useful for testing or when fault tree is already generated.
        """
        # Extract vehicle info from fault tree
        return self.train(
            year=fault_tree.vehicle_year,
            make=fault_tree.vehicle_make,
            model=fault_tree.vehicle_model,
            system=fault_tree.system,
            components=[],  # Empty - fault tree already generated
            tsbs=[],
            engine=fault_tree.vehicle_engine,
            real_examples=real_examples,
            progress_callback=progress_callback,
        )


class ModelManager:
    """
    Manages trained models for runtime inference.
    
    Loads pre-trained models and provides unified prediction interface.
    """
    
    def __init__(self, model_dir: str = "/tmp/predictive_diagnostics/models"):
        """
        Initialize the model manager.
        
        Args:
            model_dir: Directory containing trained models
        """
        self.model_dir = model_dir
        self.loaded_models: Dict[str, Dict] = {}  # key -> {classifier, ga, fault_tree}
    
    def _get_model_key(self, year: int, make: str, model: str, system: str) -> str:
        """Generate model lookup key."""
        safe_make = make.lower().replace(" ", "_")
        safe_model = model.lower().replace(" ", "_")
        safe_system = system.lower().replace(" ", "_")
        return f"{year}_{safe_make}_{safe_model}_{safe_system}"
    
    def load_model(
        self,
        year: int,
        make: str,
        model: str,
        system: str
    ) -> bool:
        """
        Load a trained model for a vehicle/system.
        
        Returns:
            True if model loaded successfully
        """
        key = self._get_model_key(year, make, model, system)
        
        # Check if already loaded
        if key in self.loaded_models:
            return True
        
        # Try to load from disk
        rf_path = os.path.join(self.model_dir, f"{key}_rf_model.pkl")
        ga_path = os.path.join(self.model_dir, f"{key}_ga_rules.json")
        ft_path = os.path.join(self.model_dir, f"{key}_fault_tree.json")
        
        if not os.path.exists(rf_path):
            logger.warning(f"Model not found for {key}")
            return False
        
        try:
            # Load RF classifier
            classifier = DiagnosticClassifier()
            classifier.load(rf_path)
            
            # Load GA rules
            ga = GeneticRuleDiscovery()
            if os.path.exists(ga_path):
                ga.load(ga_path)
            
            # Load fault tree
            fault_tree = None
            if os.path.exists(ft_path):
                with open(ft_path, 'r') as f:
                    fault_tree = FaultTree.from_dict(json.load(f))
            
            self.loaded_models[key] = {
                "classifier": classifier,
                "ga": ga,
                "fault_tree": fault_tree,
            }
            
            logger.info(f"Loaded model for {key}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to load model {key}: {e}")
            return False
    
    def predict(
        self,
        year: int,
        make: str,
        model: str,
        system: str,
        pid_values: Dict[str, float],
        dtc_codes: List[str] = None,
        top_k: int = 5
    ) -> Dict[str, Any]:
        """
        Get diagnosis prediction for scanner data.
        
        Args:
            year, make, model: Vehicle identification
            system: System name
            pid_values: PID readings
            dtc_codes: Active DTCs
            top_k: Number of predictions to return
            
        Returns:
            Dictionary with predictions, explanations, and recommended tests
        """
        key = self._get_model_key(year, make, model, system)
        
        # Load model if not loaded
        if key not in self.loaded_models:
            if not self.load_model(year, make, model, system):
                return {
                    "error": f"No trained model found for {year} {make} {model} - {system}",
                    "predictions": [],
                }
        
        model_data = self.loaded_models[key]
        classifier = model_data["classifier"]
        ga = model_data["ga"]
        fault_tree = model_data["fault_tree"]
        
        # Get RF predictions
        rf_predictions = classifier.predict(pid_values, dtc_codes, top_k=top_k)
        rf_explanation = classifier.explain_prediction(pid_values, dtc_codes)
        
        # Get GA rule matches
        ga_predictions = ga.predict(pid_values, dtc_codes) if ga.best_rules else []
        
        # Combine predictions
        combined = {}
        for fault_id, prob in rf_predictions:
            combined[fault_id] = {"rf_prob": prob, "ga_prob": 0.0}
        for fault_id, prob in ga_predictions:
            if fault_id in combined:
                combined[fault_id]["ga_prob"] = prob
            else:
                combined[fault_id] = {"rf_prob": 0.0, "ga_prob": prob}
        
        # Weight RF higher (0.7) than GA (0.3)
        for fault_id in combined:
            combined[fault_id]["combined_prob"] = (
                0.7 * combined[fault_id]["rf_prob"] +
                0.3 * combined[fault_id]["ga_prob"]
            )
        
        # Sort by combined probability
        sorted_predictions = sorted(
            combined.items(),
            key=lambda x: x[1]["combined_prob"],
            reverse=True
        )[:top_k]
        
        # Get fault details from fault tree
        predictions = []
        for fault_id, probs in sorted_predictions:
            fault_node = fault_tree.fault_nodes.get(fault_id) if fault_tree else None
            
            pred = {
                "fault_id": fault_id,
                "probability": probs["combined_prob"],
                "rf_probability": probs["rf_prob"],
                "ga_probability": probs["ga_prob"],
            }
            
            if fault_node:
                pred.update({
                    "component": fault_node.component.name,
                    "failure_mode": fault_node.failure_mode.name,
                    "diagnostic_test": fault_node.diagnostic_test,
                    "repair_action": fault_node.repair_action,
                    "tsb_reference": fault_node.tsb_reference,
                })
            
            predictions.append(pred)
        
        return {
            "vehicle": f"{year} {make} {model}",
            "system": system,
            "predictions": predictions,
            "top_prediction": predictions[0] if predictions else None,
            "contributing_features": rf_explanation.get("contributing_features", []),
            "ga_rules_matched": len(ga_predictions),
        }
    
    def list_available_models(self) -> List[Dict[str, str]]:
        """List all trained models available."""
        models = []
        
        if not os.path.exists(self.model_dir):
            return models
        
        for filename in os.listdir(self.model_dir):
            if filename.endswith("_rf_model.pkl"):
                # Parse filename
                key = filename.replace("_rf_model.pkl", "")
                parts = key.split("_")
                if len(parts) >= 4:
                    year = parts[0]
                    make = parts[1]
                    model_name = "_".join(parts[2:-1])
                    system = parts[-1]
                    
                    models.append({
                        "key": key,
                        "year": year,
                        "make": make,
                        "model": model_name,
                        "system": system,
                    })
        
        return models
