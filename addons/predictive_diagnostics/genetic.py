"""
Genetic Algorithm for Diagnostic Rule Discovery

This module implements a Genetic Algorithm (GA) that automatically discovers
diagnostic rules from data patterns. Unlike the Random Forest which learns
a fixed model, the GA evolves human-readable IF-THEN rules.

Example evolved rule:
    IF coolant_temp > 110°C AND engine_rpm > 1500 AND fan_current < 0.5A
    THEN diagnose: cooling_fan_motor_failure (confidence: 0.87)

Key features:
- Discovers rules humans might not think of
- Rules are interpretable and auditable
- Can find rare failure mode patterns
- Evolves increasingly sophisticated rules over generations

GA Components:
- Chromosome: A diagnostic rule (conditions + diagnosis)
- Population: Collection of candidate rules
- Fitness: Precision * Recall * Simplicity
- Selection: Tournament selection
- Crossover: Rule combination
- Mutation: Threshold/operator changes
"""

import random
import logging
from typing import Dict, List, Optional, Tuple, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from copy import deepcopy
import json

from .classifier import TrainingExample, COMMON_PID_FEATURES, PIDFeature

logger = logging.getLogger(__name__)


class Operator:
    """Comparison operators for rule conditions."""
    LESS_THAN = "<"
    LESS_EQUAL = "<="
    GREATER_THAN = ">"
    GREATER_EQUAL = ">="
    EQUAL = "=="
    NOT_EQUAL = "!="
    IN_RANGE = "in_range"
    OUT_OF_RANGE = "out_of_range"
    
    ALL = [LESS_THAN, LESS_EQUAL, GREATER_THAN, GREATER_EQUAL, EQUAL, NOT_EQUAL]
    RANGE_OPS = [IN_RANGE, OUT_OF_RANGE]


@dataclass
class Condition:
    """A single condition in a diagnostic rule."""
    feature: str           # PID name or DTC
    operator: str          # Comparison operator
    threshold: float       # Value to compare against
    threshold_high: Optional[float] = None  # For range operators
    
    def evaluate(self, example: TrainingExample) -> bool:
        """Evaluate this condition against an example."""
        # Handle DTC conditions
        if self.feature.startswith("DTC_"):
            dtc = self.feature[4:]
            has_dtc = dtc in example.dtc_codes
            if self.operator == Operator.EQUAL:
                return has_dtc
            elif self.operator == Operator.NOT_EQUAL:
                return not has_dtc
            return False
        
        # Handle PID conditions
        if self.feature not in example.pid_values:
            return False  # Missing data = condition fails
        
        value = example.pid_values[self.feature]
        
        if self.operator == Operator.LESS_THAN:
            return value < self.threshold
        elif self.operator == Operator.LESS_EQUAL:
            return value <= self.threshold
        elif self.operator == Operator.GREATER_THAN:
            return value > self.threshold
        elif self.operator == Operator.GREATER_EQUAL:
            return value >= self.threshold
        elif self.operator == Operator.EQUAL:
            return abs(value - self.threshold) < 0.001
        elif self.operator == Operator.NOT_EQUAL:
            return abs(value - self.threshold) >= 0.001
        elif self.operator == Operator.IN_RANGE:
            return self.threshold <= value <= (self.threshold_high or self.threshold)
        elif self.operator == Operator.OUT_OF_RANGE:
            return value < self.threshold or value > (self.threshold_high or self.threshold)
        
        return False
    
    def to_string(self) -> str:
        """Human-readable condition string."""
        if self.operator == Operator.IN_RANGE:
            return f"{self.feature} IN [{self.threshold}, {self.threshold_high}]"
        elif self.operator == Operator.OUT_OF_RANGE:
            return f"{self.feature} NOT IN [{self.threshold}, {self.threshold_high}]"
        else:
            return f"{self.feature} {self.operator} {self.threshold:.2f}"
    
    def to_dict(self) -> Dict:
        return {
            "feature": self.feature,
            "operator": self.operator,
            "threshold": self.threshold,
            "threshold_high": self.threshold_high,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "Condition":
        return cls(
            feature=data["feature"],
            operator=data["operator"],
            threshold=data["threshold"],
            threshold_high=data.get("threshold_high"),
        )


@dataclass
class DiagnosticRule:
    """
    A diagnostic rule (chromosome in GA terms).
    
    IF condition1 AND condition2 AND ... THEN diagnosis
    """
    rule_id: str
    conditions: List[Condition]
    diagnosis: str                # Fault node ID to predict
    
    # Fitness metrics (computed during evaluation)
    fitness: float = 0.0
    precision: float = 0.0        # When rule fires, how often is it correct?
    recall: float = 0.0           # Of all cases with this diagnosis, how many does rule catch?
    coverage: float = 0.0         # What fraction of data does this rule fire on?
    true_positives: int = 0
    false_positives: int = 0
    false_negatives: int = 0
    
    generation: int = 0           # Which generation this rule was created
    parent_ids: List[str] = field(default_factory=list)
    
    def evaluate(self, example: TrainingExample) -> bool:
        """Check if this rule fires for an example."""
        # All conditions must be true (AND logic)
        return all(cond.evaluate(example) for cond in self.conditions)
    
    def compute_fitness(
        self,
        examples: List[TrainingExample],
        precision_weight: float = 0.4,
        recall_weight: float = 0.3,
        simplicity_weight: float = 0.2,
        coverage_weight: float = 0.1
    ) -> float:
        """
        Compute fitness score for this rule.
        
        Fitness = weighted combination of:
        - Precision: When rule fires, is it correct?
        - Recall: Does rule catch most cases of this diagnosis?
        - Simplicity: Fewer conditions = better (prevents overfitting)
        - Coverage: Rules that apply to more cases are preferred
        """
        # Count predictions
        self.true_positives = 0
        self.false_positives = 0
        self.false_negatives = 0
        total_positive = 0  # Examples with this diagnosis
        total_fires = 0     # Times rule fires
        
        for ex in examples:
            is_positive = (ex.fault_label == self.diagnosis)
            fires = self.evaluate(ex)
            
            if is_positive:
                total_positive += 1
                if fires:
                    self.true_positives += 1
                else:
                    self.false_negatives += 1
            else:
                if fires:
                    self.false_positives += 1
            
            if fires:
                total_fires += 1
        
        # Calculate metrics
        if self.true_positives + self.false_positives > 0:
            self.precision = self.true_positives / (self.true_positives + self.false_positives)
        else:
            self.precision = 0.0
        
        if total_positive > 0:
            self.recall = self.true_positives / total_positive
        else:
            self.recall = 0.0
        
        self.coverage = total_fires / len(examples) if examples else 0.0
        
        # Simplicity: Prefer fewer conditions (max 10 conditions)
        simplicity = 1.0 - (len(self.conditions) / 10.0)
        simplicity = max(0.0, simplicity)
        
        # Compute weighted fitness
        self.fitness = (
            precision_weight * self.precision +
            recall_weight * self.recall +
            simplicity_weight * simplicity +
            coverage_weight * self.coverage
        )
        
        # Penalty for rules that never fire or fire on everything
        if total_fires == 0 or total_fires == len(examples):
            self.fitness *= 0.1
        
        return self.fitness
    
    def to_string(self) -> str:
        """Human-readable rule string."""
        conditions_str = " AND ".join(c.to_string() for c in self.conditions)
        return f"IF {conditions_str} THEN {self.diagnosis}"
    
    def to_dict(self) -> Dict:
        return {
            "rule_id": self.rule_id,
            "conditions": [c.to_dict() for c in self.conditions],
            "diagnosis": self.diagnosis,
            "fitness": self.fitness,
            "precision": self.precision,
            "recall": self.recall,
            "coverage": self.coverage,
            "generation": self.generation,
            "parent_ids": self.parent_ids,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> "DiagnosticRule":
        rule = cls(
            rule_id=data["rule_id"],
            conditions=[Condition.from_dict(c) for c in data["conditions"]],
            diagnosis=data["diagnosis"],
            generation=data.get("generation", 0),
            parent_ids=data.get("parent_ids", []),
        )
        rule.fitness = data.get("fitness", 0.0)
        rule.precision = data.get("precision", 0.0)
        rule.recall = data.get("recall", 0.0)
        rule.coverage = data.get("coverage", 0.0)
        return rule


class GeneticRuleDiscovery:
    """
    Genetic Algorithm for discovering diagnostic rules.
    
    Evolves a population of rules over multiple generations,
    selecting the fittest rules and combining them to find
    better diagnostic patterns.
    """
    
    def __init__(
        self,
        population_size: int = 100,
        max_generations: int = 50,
        elite_size: int = 10,
        crossover_rate: float = 0.7,
        mutation_rate: float = 0.3,
        tournament_size: int = 5,
        min_precision: float = 0.6,    # Minimum precision to keep rule
        min_recall: float = 0.1,       # Minimum recall to keep rule
        max_conditions: int = 6,       # Maximum conditions per rule
    ):
        """
        Initialize the GA.
        
        Args:
            population_size: Number of rules in each generation
            max_generations: Maximum evolution generations
            elite_size: Number of top rules to preserve each generation
            crossover_rate: Probability of crossover vs copy
            mutation_rate: Probability of mutating a rule
            tournament_size: Selection tournament size
            min_precision: Minimum precision threshold
            min_recall: Minimum recall threshold
            max_conditions: Maximum conditions per rule
        """
        self.population_size = population_size
        self.max_generations = max_generations
        self.elite_size = elite_size
        self.crossover_rate = crossover_rate
        self.mutation_rate = mutation_rate
        self.tournament_size = tournament_size
        self.min_precision = min_precision
        self.min_recall = min_recall
        self.max_conditions = max_conditions
        
        self.population: List[DiagnosticRule] = []
        self.best_rules: Dict[str, DiagnosticRule] = {}  # diagnosis -> best rule
        self.generation_history: List[Dict] = []
        
        self.available_features: List[str] = []
        self.feature_ranges: Dict[str, Tuple[float, float]] = {}
        self.available_diagnoses: List[str] = []
        
        self._rule_counter = 0
    
    def _generate_rule_id(self) -> str:
        """Generate unique rule ID."""
        self._rule_counter += 1
        return f"rule_{self._rule_counter:04d}"
    
    def _analyze_data(self, examples: List[TrainingExample]) -> None:
        """Analyze training data to understand feature ranges and diagnoses."""
        self.available_features = []
        self.feature_ranges = {}
        self.available_diagnoses = list(set(ex.fault_label for ex in examples))
        
        # Collect all PIDs and their ranges
        all_pids = set()
        pid_values: Dict[str, List[float]] = {}
        
        for ex in examples:
            for pid, value in ex.pid_values.items():
                all_pids.add(pid)
                if pid not in pid_values:
                    pid_values[pid] = []
                pid_values[pid].append(value)
            
            # DTCs as binary features
            for dtc in ex.dtc_codes:
                all_pids.add(f"DTC_{dtc}")
        
        self.available_features = list(all_pids)
        
        # Compute ranges
        for pid, values in pid_values.items():
            if values:
                self.feature_ranges[pid] = (min(values), max(values))
    
    def _random_condition(self) -> Condition:
        """Generate a random condition."""
        feature = random.choice(self.available_features)
        
        if feature.startswith("DTC_"):
            # DTC condition
            operator = random.choice([Operator.EQUAL, Operator.NOT_EQUAL])
            return Condition(feature=feature, operator=operator, threshold=1.0)
        
        # PID condition
        operator = random.choice(Operator.ALL)
        
        # Get range for this feature
        min_val, max_val = self.feature_ranges.get(feature, (0, 100))
        range_size = max_val - min_val
        
        # Random threshold within range (with some margin)
        threshold = min_val + random.random() * range_size
        
        return Condition(feature=feature, operator=operator, threshold=threshold)
    
    def _random_rule(self, diagnosis: Optional[str] = None) -> DiagnosticRule:
        """Generate a random rule."""
        n_conditions = random.randint(1, self.max_conditions)
        conditions = [self._random_condition() for _ in range(n_conditions)]
        
        if diagnosis is None:
            diagnosis = random.choice(self.available_diagnoses)
        
        return DiagnosticRule(
            rule_id=self._generate_rule_id(),
            conditions=conditions,
            diagnosis=diagnosis,
            generation=0,
        )
    
    def _initialize_population(self, examples: List[TrainingExample]) -> None:
        """Initialize population with random rules."""
        self._analyze_data(examples)
        
        self.population = []
        
        # Create rules for each diagnosis
        rules_per_diagnosis = self.population_size // len(self.available_diagnoses)
        
        for diagnosis in self.available_diagnoses:
            for _ in range(rules_per_diagnosis):
                rule = self._random_rule(diagnosis)
                self.population.append(rule)
        
        # Fill remaining with random diagnoses
        while len(self.population) < self.population_size:
            self.population.append(self._random_rule())
        
        logger.info(f"Initialized population with {len(self.population)} rules")
    
    def _tournament_select(self) -> DiagnosticRule:
        """Select a rule using tournament selection."""
        tournament = random.sample(self.population, self.tournament_size)
        return max(tournament, key=lambda r: r.fitness)
    
    def _crossover(self, parent1: DiagnosticRule, parent2: DiagnosticRule) -> DiagnosticRule:
        """Create child rule by combining two parents."""
        # Must have same diagnosis
        if parent1.diagnosis != parent2.diagnosis:
            # Return copy of better parent
            return deepcopy(parent1) if parent1.fitness > parent2.fitness else deepcopy(parent2)
        
        # Combine conditions from both parents
        all_conditions = parent1.conditions + parent2.conditions
        
        # Select random subset
        n_conditions = random.randint(1, min(self.max_conditions, len(all_conditions)))
        conditions = random.sample(all_conditions, n_conditions)
        
        child = DiagnosticRule(
            rule_id=self._generate_rule_id(),
            conditions=[deepcopy(c) for c in conditions],
            diagnosis=parent1.diagnosis,
            generation=max(parent1.generation, parent2.generation) + 1,
            parent_ids=[parent1.rule_id, parent2.rule_id],
        )
        
        return child
    
    def _mutate(self, rule: DiagnosticRule) -> DiagnosticRule:
        """Mutate a rule."""
        rule = deepcopy(rule)
        rule.rule_id = self._generate_rule_id()
        
        mutation_type = random.choice([
            "threshold", "operator", "add_condition", "remove_condition", "replace_condition"
        ])
        
        if mutation_type == "threshold" and rule.conditions:
            # Mutate a threshold
            cond = random.choice(rule.conditions)
            if not cond.feature.startswith("DTC_"):
                min_val, max_val = self.feature_ranges.get(cond.feature, (0, 100))
                range_size = max_val - min_val
                # Gaussian mutation
                cond.threshold += random.gauss(0, range_size * 0.1)
                cond.threshold = max(min_val, min(max_val, cond.threshold))
        
        elif mutation_type == "operator" and rule.conditions:
            # Change an operator
            cond = random.choice(rule.conditions)
            if cond.feature.startswith("DTC_"):
                cond.operator = random.choice([Operator.EQUAL, Operator.NOT_EQUAL])
            else:
                cond.operator = random.choice(Operator.ALL)
        
        elif mutation_type == "add_condition" and len(rule.conditions) < self.max_conditions:
            # Add a new condition
            rule.conditions.append(self._random_condition())
        
        elif mutation_type == "remove_condition" and len(rule.conditions) > 1:
            # Remove a random condition
            rule.conditions.remove(random.choice(rule.conditions))
        
        elif mutation_type == "replace_condition" and rule.conditions:
            # Replace a condition
            idx = random.randint(0, len(rule.conditions) - 1)
            rule.conditions[idx] = self._random_condition()
        
        return rule
    
    def _evaluate_population(self, examples: List[TrainingExample]) -> None:
        """Evaluate fitness of all rules in population."""
        for rule in self.population:
            rule.compute_fitness(examples)
    
    def _evolve_generation(self, examples: List[TrainingExample]) -> None:
        """Evolve one generation."""
        # Evaluate current population
        self._evaluate_population(examples)
        
        # Sort by fitness
        self.population.sort(key=lambda r: r.fitness, reverse=True)
        
        # Keep elite
        new_population = self.population[:self.elite_size]
        
        # Track best rule per diagnosis
        for rule in self.population:
            if rule.precision >= self.min_precision and rule.recall >= self.min_recall:
                if rule.diagnosis not in self.best_rules or \
                   rule.fitness > self.best_rules[rule.diagnosis].fitness:
                    self.best_rules[rule.diagnosis] = deepcopy(rule)
        
        # Generate rest of population
        while len(new_population) < self.population_size:
            if random.random() < self.crossover_rate:
                # Crossover
                parent1 = self._tournament_select()
                parent2 = self._tournament_select()
                child = self._crossover(parent1, parent2)
            else:
                # Copy with possible mutation
                child = deepcopy(self._tournament_select())
            
            # Mutate
            if random.random() < self.mutation_rate:
                child = self._mutate(child)
            
            new_population.append(child)
        
        self.population = new_population
    
    def evolve(
        self, 
        examples: List[TrainingExample],
        callback: Optional[Callable[[int, Dict], None]] = None
    ) -> Dict[str, DiagnosticRule]:
        """
        Run the genetic algorithm to discover diagnostic rules.
        
        Args:
            examples: Training examples
            callback: Optional callback(generation, stats) for progress
            
        Returns:
            Dictionary of diagnosis -> best rule
        """
        logger.info(f"Starting GA evolution with {len(examples)} examples")
        
        # Initialize
        self._initialize_population(examples)
        self.best_rules = {}
        self.generation_history = []
        
        # Evolve
        for gen in range(self.max_generations):
            self._evolve_generation(examples)
            
            # Compute generation statistics
            fitnesses = [r.fitness for r in self.population]
            stats = {
                "generation": gen,
                "best_fitness": max(fitnesses),
                "avg_fitness": sum(fitnesses) / len(fitnesses),
                "n_good_rules": len(self.best_rules),
                "best_rules": {
                    d: {"fitness": r.fitness, "precision": r.precision, "recall": r.recall}
                    for d, r in self.best_rules.items()
                },
            }
            self.generation_history.append(stats)
            
            if callback:
                callback(gen, stats)
            
            logger.info(
                f"Gen {gen}: best={stats['best_fitness']:.3f}, "
                f"avg={stats['avg_fitness']:.3f}, good_rules={stats['n_good_rules']}"
            )
            
            # Early stopping if no improvement
            if gen > 10:
                recent_best = [h["best_fitness"] for h in self.generation_history[-10:]]
                if max(recent_best) - min(recent_best) < 0.001:
                    logger.info(f"Early stopping at generation {gen} (no improvement)")
                    break
        
        logger.info(f"Evolution complete. Found {len(self.best_rules)} good rules.")
        return self.best_rules
    
    def predict(
        self,
        pid_values: Dict[str, float],
        dtc_codes: List[str] = None
    ) -> List[Tuple[str, float]]:
        """
        Predict using evolved rules.
        
        Args:
            pid_values: PID readings
            dtc_codes: Active DTCs
            
        Returns:
            List of (diagnosis, confidence) sorted by confidence
        """
        # Create temporary example
        example = TrainingExample(
            example_id="predict",
            vehicle_year=0,
            vehicle_make="",
            vehicle_model="",
            pid_values=pid_values,
            dtc_codes=dtc_codes or [],
            fault_label="",
        )
        
        # Check each rule
        predictions = []
        for diagnosis, rule in self.best_rules.items():
            if rule.evaluate(example):
                predictions.append((diagnosis, rule.precision))
        
        # Sort by confidence
        predictions.sort(key=lambda x: x[1], reverse=True)
        
        return predictions
    
    def get_rules_as_text(self) -> str:
        """Get all discovered rules as human-readable text."""
        lines = ["Discovered Diagnostic Rules", "=" * 50, ""]
        
        for diagnosis in sorted(self.best_rules.keys()):
            rule = self.best_rules[diagnosis]
            lines.append(rule.to_string())
            lines.append(f"  Precision: {rule.precision:.2%}")
            lines.append(f"  Recall: {rule.recall:.2%}")
            lines.append(f"  Fitness: {rule.fitness:.3f}")
            lines.append("")
        
        return "\n".join(lines)
    
    def save(self, path: str) -> None:
        """Save discovered rules to file."""
        data = {
            "rules": {d: r.to_dict() for d, r in self.best_rules.items()},
            "history": self.generation_history,
            "params": {
                "population_size": self.population_size,
                "max_generations": self.max_generations,
                "min_precision": self.min_precision,
                "min_recall": self.min_recall,
            }
        }
        with open(path, 'w') as f:
            json.dump(data, f, indent=2)
        logger.info(f"Rules saved to {path}")
    
    def load(self, path: str) -> None:
        """Load rules from file."""
        with open(path, 'r') as f:
            data = json.load(f)
        
        self.best_rules = {
            d: DiagnosticRule.from_dict(r)
            for d, r in data.get("rules", {}).items()
        }
        self.generation_history = data.get("history", [])
        
        params = data.get("params", {})
        self.population_size = params.get("population_size", self.population_size)
        self.max_generations = params.get("max_generations", self.max_generations)
        
        logger.info(f"Loaded {len(self.best_rules)} rules from {path}")
