"""
Training Data Collector for Automotive AI Fine-Tuning

Collects diagnostic conversations in a format ready for fine-tuning:
- User query (with vehicle context) → AI response
- Mitchell lookups → structured data
- Scan tool data → diagnosis

Output format: JSONL files ready for fine-tuning with Llama, Mistral, etc.
"""

import json
import os
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from dataclasses import dataclass, asdict
from enum import Enum
import logging

logger = logging.getLogger(__name__)

# Default storage location
DATA_DIR = Path(os.environ.get("TRAINING_DATA_DIR", "/home/drawson/autotech_ai/training_data"))


class DataCategory(str, Enum):
    """Categories for training data"""
    DTC_DIAGNOSIS = "dtc_diagnosis"          # DTC code → causes, tests, fixes
    SYMPTOM_DIAGNOSIS = "symptom_diagnosis"  # Symptom description → diagnostic path
    SCAN_DATA_ANALYSIS = "scan_data_analysis"  # PID data → interpretation
    SPEC_LOOKUP = "spec_lookup"              # Vehicle spec queries
    PROCEDURE = "procedure"                  # How-to procedures
    TSB_LOOKUP = "tsb_lookup"                # TSB queries
    WIRING = "wiring"                        # Wiring diagram queries
    GENERAL = "general"                      # General automotive Q&A


@dataclass
class VehicleContext:
    """Vehicle information for training context"""
    year: Optional[int] = None
    make: Optional[str] = None
    model: Optional[str] = None
    engine: Optional[str] = None
    vin: Optional[str] = None  # Will be hashed for privacy
    mileage: Optional[int] = None
    
    def to_string(self) -> str:
        """Convert to natural language string"""
        parts = []
        if self.year:
            parts.append(str(self.year))
        if self.make:
            parts.append(self.make)
        if self.model:
            parts.append(self.model)
        if self.engine:
            parts.append(self.engine)
        return " ".join(parts) if parts else "Unknown vehicle"


@dataclass
class ScanToolData:
    """OBD2 scan data for training"""
    dtcs: List[Dict[str, str]] = None  # [{"code": "P0171", "status": "current"}]
    pids: Dict[str, Any] = None  # {"stft1": 14.5, "ltft1": 8.2, ...}
    freeze_frame: Dict[str, Any] = None
    
    def __post_init__(self):
        self.dtcs = self.dtcs or []
        self.pids = self.pids or {}
        self.freeze_frame = self.freeze_frame or {}


@dataclass
class TrainingExample:
    """A single training example for fine-tuning"""
    id: str
    timestamp: str
    category: str
    
    # The actual training pair
    input_text: str      # User query + context
    output_text: str     # AI response
    
    # Metadata (not used in training, but useful for filtering/analysis)
    vehicle: Optional[Dict] = None
    scan_data: Optional[Dict] = None
    mitchell_data: Optional[Dict] = None  # Any Mitchell lookup results
    source: str = "user_chat"  # user_chat, mitchell_tool, scan_tool, synthetic
    quality_score: Optional[float] = None  # For filtering low-quality examples
    
    def to_fine_tune_format(self, style: str = "alpaca") -> Dict:
        """Convert to various fine-tuning formats"""
        
        if style == "alpaca":
            # Alpaca/Stanford format
            return {
                "instruction": self.input_text,
                "input": "",  # Could include vehicle context here
                "output": self.output_text
            }
        
        elif style == "sharegpt":
            # ShareGPT conversation format
            return {
                "conversations": [
                    {"from": "human", "value": self.input_text},
                    {"from": "gpt", "value": self.output_text}
                ]
            }
        
        elif style == "openai":
            # OpenAI fine-tuning format
            return {
                "messages": [
                    {"role": "system", "content": "You are an expert automotive diagnostic technician."},
                    {"role": "user", "content": self.input_text},
                    {"role": "assistant", "content": self.output_text}
                ]
            }
        
        else:  # simple
            return {
                "input": self.input_text,
                "output": self.output_text
            }


class TrainingDataCollector:
    """Collects and stores training data for fine-tuning"""
    
    def __init__(self, data_dir: Path = DATA_DIR):
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        
        # Separate files by category for easier management
        self.files = {}
        for category in DataCategory:
            filepath = self.data_dir / f"{category.value}.jsonl"
            self.files[category] = filepath
    
    def _generate_id(self, input_text: str, output_text: str) -> str:
        """Generate unique ID for deduplication"""
        content = f"{input_text}|{output_text}"
        return hashlib.sha256(content.encode()).hexdigest()[:16]
    
    def _hash_vin(self, vin: str) -> str:
        """Hash VIN for privacy"""
        if not vin:
            return None
        return hashlib.sha256(vin.encode()).hexdigest()[:8]
    
    def collect(
        self,
        input_text: str,
        output_text: str,
        category: DataCategory = DataCategory.GENERAL,
        vehicle: Optional[VehicleContext] = None,
        scan_data: Optional[ScanToolData] = None,
        mitchell_data: Optional[Dict] = None,
        source: str = "user_chat",
        quality_score: Optional[float] = None
    ) -> TrainingExample:
        """
        Collect a training example.
        
        Args:
            input_text: The user's query/input
            output_text: The AI's response
            category: Type of diagnostic query
            vehicle: Vehicle context
            scan_data: OBD2 scan data if available
            mitchell_data: Any Mitchell lookup results
            source: Where this data came from
            quality_score: Optional quality rating (0-1)
        
        Returns:
            The created TrainingExample
        """
        
        # Hash VIN if present
        if vehicle and vehicle.vin:
            vehicle.vin = self._hash_vin(vehicle.vin)
        
        example = TrainingExample(
            id=self._generate_id(input_text, output_text),
            timestamp=datetime.utcnow().isoformat(),
            category=category.value,
            input_text=input_text,
            output_text=output_text,
            vehicle=asdict(vehicle) if vehicle else None,
            scan_data=asdict(scan_data) if scan_data else None,
            mitchell_data=mitchell_data,
            source=source,
            quality_score=quality_score
        )
        
        # Append to category-specific file
        filepath = self.files[category]
        with open(filepath, "a") as f:
            f.write(json.dumps(asdict(example)) + "\n")
        
        logger.info(f"Collected training example: {example.id} [{category.value}]")
        return example
    
    def collect_dtc_diagnosis(
        self,
        dtc_code: str,
        vehicle: VehicleContext,
        diagnosis: str,
        causes: List[str] = None,
        tests: List[str] = None,
        mitchell_data: Dict = None
    ) -> TrainingExample:
        """Convenience method for DTC diagnosis examples"""
        
        input_text = f"What causes {dtc_code} on a {vehicle.to_string()}?"
        
        # Format output nicely
        output_parts = [diagnosis]
        if causes:
            output_parts.append("\n\nCommon causes:\n" + "\n".join(f"- {c}" for c in causes))
        if tests:
            output_parts.append("\n\nDiagnostic tests:\n" + "\n".join(f"- {t}" for t in tests))
        
        output_text = "".join(output_parts)
        
        return self.collect(
            input_text=input_text,
            output_text=output_text,
            category=DataCategory.DTC_DIAGNOSIS,
            vehicle=vehicle,
            mitchell_data=mitchell_data,
            source="mitchell_tool" if mitchell_data else "user_chat"
        )
    
    def collect_scan_analysis(
        self,
        vehicle: VehicleContext,
        scan_data: ScanToolData,
        analysis: str
    ) -> TrainingExample:
        """Convenience method for scan data analysis examples"""
        
        # Build input from scan data
        input_parts = [f"Analyze this scan data for a {vehicle.to_string()}:"]
        
        if scan_data.dtcs:
            dtc_list = ", ".join(d["code"] for d in scan_data.dtcs)
            input_parts.append(f"DTCs: {dtc_list}")
        
        if scan_data.pids:
            pid_lines = []
            if "stft1" in scan_data.pids:
                pid_lines.append(f"STFT Bank 1: {scan_data.pids['stft1']}%")
            if "ltft1" in scan_data.pids:
                pid_lines.append(f"LTFT Bank 1: {scan_data.pids['ltft1']}%")
            if "stft2" in scan_data.pids:
                pid_lines.append(f"STFT Bank 2: {scan_data.pids['stft2']}%")
            if "ltft2" in scan_data.pids:
                pid_lines.append(f"LTFT Bank 2: {scan_data.pids['ltft2']}%")
            if "rpm" in scan_data.pids:
                pid_lines.append(f"RPM: {scan_data.pids['rpm']}")
            if "coolant_temp" in scan_data.pids:
                pid_lines.append(f"Coolant Temp: {scan_data.pids['coolant_temp']}°C")
            if pid_lines:
                input_parts.append("Live Data:\n" + "\n".join(f"  {p}" for p in pid_lines))
        
        input_text = "\n".join(input_parts)
        
        return self.collect(
            input_text=input_text,
            output_text=analysis,
            category=DataCategory.SCAN_DATA_ANALYSIS,
            vehicle=vehicle,
            scan_data=scan_data
        )
    
    def export(
        self,
        output_path: Path,
        categories: List[DataCategory] = None,
        format: str = "alpaca",
        min_quality: float = None
    ) -> int:
        """
        Export collected data to a single file for fine-tuning.
        
        Args:
            output_path: Where to write the export
            categories: Which categories to include (None = all)
            format: Output format (alpaca, sharegpt, openai, simple)
            min_quality: Minimum quality score to include
        
        Returns:
            Number of examples exported
        """
        categories = categories or list(DataCategory)
        examples = []
        
        for category in categories:
            filepath = self.files[category]
            if not filepath.exists():
                continue
            
            with open(filepath, "r") as f:
                for line in f:
                    if line.strip():
                        data = json.loads(line)
                        
                        # Filter by quality if specified
                        if min_quality and data.get("quality_score"):
                            if data["quality_score"] < min_quality:
                                continue
                        
                        example = TrainingExample(**data)
                        examples.append(example.to_fine_tune_format(format))
        
        # Write export file
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, "w") as f:
            for example in examples:
                f.write(json.dumps(example) + "\n")
        
        logger.info(f"Exported {len(examples)} examples to {output_path}")
        return len(examples)
    
    def stats(self) -> Dict[str, int]:
        """Get statistics on collected data"""
        stats = {}
        for category, filepath in self.files.items():
            if filepath.exists():
                with open(filepath, "r") as f:
                    count = sum(1 for line in f if line.strip())
                stats[category.value] = count
            else:
                stats[category.value] = 0
        stats["total"] = sum(stats.values())
        return stats


# Global collector instance
_collector = None

def get_collector() -> TrainingDataCollector:
    """Get the global collector instance"""
    global _collector
    if _collector is None:
        _collector = TrainingDataCollector()
    return _collector


# Convenience functions
def collect_training_example(
    input_text: str,
    output_text: str,
    category: DataCategory = DataCategory.GENERAL,
    **kwargs
) -> TrainingExample:
    """Collect a training example using the global collector"""
    return get_collector().collect(input_text, output_text, category, **kwargs)


def export_training_data(output_path: str, **kwargs) -> int:
    """Export training data using the global collector"""
    return get_collector().export(Path(output_path), **kwargs)
