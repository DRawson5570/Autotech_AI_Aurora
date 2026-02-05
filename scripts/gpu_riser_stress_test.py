#!/usr/bin/env python3
"""
GPU Riser Cable Stress Test
============================

Tests PCIe riser cable stability under sustained heavy load.
Designed to detect signal integrity issues that cause GPU to "drop off the bus".

Tests performed:
1. Sustained compute (matrix multiplications)
2. PCIe bus stress (host<->device memory transfers)
3. Memory stress (allocate/deallocate large buffers)
4. Mixed workload (compute + transfer simultaneously)

Run: python gpu_riser_stress_test.py --duration 3600  # 1 hour test

Requirements:
    pip install torch numpy

For Tesla M40 (Maxwell architecture):
    - 24GB GDDR5 memory
    - PCIe 3.0 x16
    - No tensor cores (uses CUDA cores)
"""

import argparse
import subprocess
import sys
import time
import threading
import signal
from datetime import datetime, timedelta
from typing import Optional, Tuple, Dict, Any
import os

# Check for required packages
try:
    import torch
    import numpy as np
except ImportError:
    print("Installing required packages...")
    subprocess.check_call([sys.executable, "-m", "pip", "install", "torch", "numpy"])
    import torch
    import numpy as np


class GPUMonitor:
    """Monitor GPU health via nvidia-smi."""
    
    def __init__(self, gpu_id: int = 0):
        self.gpu_id = gpu_id
        self.baseline_stats: Optional[Dict] = None
        self.error_count = 0
        self.warning_count = 0
        self.max_temp = 0
        self.max_power = 0
        self.last_check_ok = True
        
    def get_gpu_stats(self) -> Optional[Dict[str, Any]]:
        """Query GPU stats via nvidia-smi."""
        try:
            result = subprocess.run(
                [
                    "nvidia-smi",
                    f"--id={self.gpu_id}",
                    "--query-gpu=name,temperature.gpu,power.draw,memory.used,memory.total,pcie.link.gen.current,pcie.link.width.current,ecc.errors.corrected.volatile.total,ecc.errors.uncorrected.volatile.total",
                    "--format=csv,noheader,nounits"
                ],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return None
                
            parts = result.stdout.strip().split(", ")
            if len(parts) < 7:
                return None
                
            stats = {
                "name": parts[0],
                "temp": int(parts[1]) if parts[1].isdigit() else 0,
                "power": float(parts[2]) if parts[2].replace(".", "").isdigit() else 0,
                "mem_used": int(parts[3]) if parts[3].isdigit() else 0,
                "mem_total": int(parts[4]) if parts[4].isdigit() else 0,
                "pcie_gen": parts[5].strip(),
                "pcie_width": parts[6].strip(),
                "ecc_corrected": int(parts[7]) if len(parts) > 7 and parts[7].strip().isdigit() else 0,
                "ecc_uncorrected": int(parts[8]) if len(parts) > 8 and parts[8].strip().isdigit() else 0,
            }
            
            self.last_check_ok = True
            return stats
            
        except subprocess.TimeoutExpired:
            self.last_check_ok = False
            return None
        except Exception as e:
            self.last_check_ok = False
            return None
    
    def check_gpu_present(self) -> bool:
        """Quick check if GPU is still on the bus."""
        try:
            result = subprocess.run(
                ["nvidia-smi", f"--id={self.gpu_id}", "-L"],
                capture_output=True,
                timeout=5
            )
            return result.returncode == 0
        except:
            return False
    
    def set_baseline(self):
        """Record baseline stats at start."""
        self.baseline_stats = self.get_gpu_stats()
        if self.baseline_stats:
            print(f"  GPU: {self.baseline_stats['name']}")
            print(f"  Memory: {self.baseline_stats['mem_total']} MB")
            print(f"  PCIe: Gen {self.baseline_stats['pcie_gen']} x{self.baseline_stats['pcie_width']}")
            print(f"  Initial temp: {self.baseline_stats['temp']}°C")
    
    def check_for_issues(self, stats: Dict) -> list:
        """Check stats for warning signs."""
        issues = []
        
        # Track maximums
        if stats["temp"] > self.max_temp:
            self.max_temp = stats["temp"]
        if stats["power"] > self.max_power:
            self.max_power = stats["power"]
        
        # Temperature warnings
        if stats["temp"] > 95:
            issues.append(f"CRITICAL: GPU temp {stats['temp']}°C (throttling likely)")
            self.error_count += 1
        elif stats["temp"] > 85:
            issues.append(f"WARNING: GPU temp {stats['temp']}°C (high)")
            self.warning_count += 1
        
        # PCIe link degradation (sign of riser issues!)
        if self.baseline_stats:
            if stats["pcie_gen"] != self.baseline_stats["pcie_gen"]:
                issues.append(f"CRITICAL: PCIe gen dropped! {self.baseline_stats['pcie_gen']} -> {stats['pcie_gen']}")
                self.error_count += 1
            if stats["pcie_width"] != self.baseline_stats["pcie_width"]:
                issues.append(f"CRITICAL: PCIe width dropped! x{self.baseline_stats['pcie_width']} -> x{stats['pcie_width']}")
                self.error_count += 1
        
        # ECC errors (memory issues)
        if stats["ecc_uncorrected"] > 0:
            issues.append(f"CRITICAL: {stats['ecc_uncorrected']} uncorrected ECC errors!")
            self.error_count += 1
        if stats["ecc_corrected"] > 10:
            issues.append(f"WARNING: {stats['ecc_corrected']} corrected ECC errors")
            self.warning_count += 1
        
        return issues


class StressTest:
    """GPU stress test suite."""
    
    def __init__(self, gpu_id: int = 0, matrix_size: int = 16384):
        self.gpu_id = gpu_id
        self.matrix_size = matrix_size  # 16384x16384 = 1GB per matrix, ~4GB working set
        self.device = torch.device(f"cuda:{gpu_id}")
        self.monitor = GPUMonitor(gpu_id)
        self.running = True
        self.total_ops = 0
        self.total_transfers_gb = 0.0
        self.errors: list = []
        self.start_time: Optional[datetime] = None
        
        # Handle Ctrl+C gracefully
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def _signal_handler(self, signum, frame):
        print("\n\n⚠️  Interrupt received, stopping gracefully...")
        self.running = False
    
    def _log(self, msg: str, level: str = "INFO"):
        """Log with timestamp."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        elapsed = ""
        if self.start_time:
            delta = datetime.now() - self.start_time
            elapsed = f"[{str(delta).split('.')[0]}] "
        print(f"[{timestamp}] {elapsed}{level}: {msg}")
    
    def verify_gpu(self) -> bool:
        """Verify GPU is available and working."""
        print("\n" + "="*60)
        print("GPU RISER CABLE STRESS TEST")
        print("="*60)
        
        if not torch.cuda.is_available():
            print("ERROR: CUDA not available!")
            return False
        
        gpu_count = torch.cuda.device_count()
        print(f"\nFound {gpu_count} CUDA device(s)")
        
        if self.gpu_id >= gpu_count:
            print(f"ERROR: GPU {self.gpu_id} not found!")
            return False
        
        print(f"\nTarget GPU {self.gpu_id}:")
        self.monitor.set_baseline()
        
        # Quick CUDA test
        try:
            test_tensor = torch.randn(1000, 1000, device=self.device)
            result = torch.mm(test_tensor, test_tensor)
            del test_tensor, result
            torch.cuda.synchronize(self.device)
            print("  CUDA test: OK")
        except Exception as e:
            print(f"  CUDA test: FAILED - {e}")
            return False
        
        return True
    
    def stress_compute(self, duration_sec: float) -> Tuple[int, list]:
        """
        Sustained compute stress - matrix multiplications.
        This maxes out the CUDA cores.
        """
        errors = []
        ops = 0
        
        try:
            # Pre-allocate MULTIPLE large matrices to keep GPU fully loaded
            # 16384x16384 float32 = 1GB each, use 4 matrices = 4GB + results
            matrices = []
            for i in range(4):
                matrices.append(torch.randn(self.matrix_size, self.matrix_size, 
                                           device=self.device, dtype=torch.float32))
            
            # Pre-allocate result buffers to avoid allocation overhead
            results = [torch.empty_like(matrices[0]) for _ in range(2)]
            
            end_time = time.time() + duration_sec
            
            while time.time() < end_time and self.running:
                # Chain multiple matmuls without sync to keep GPU saturated
                # A @ B -> C, C @ D -> E, etc.
                torch.mm(matrices[0], matrices[1], out=results[0])
                torch.mm(results[0], matrices[2], out=results[1])
                torch.mm(results[1], matrices[3], out=results[0])
                torch.mm(results[0], matrices[1], out=results[1])
                
                # Only sync every 10 iterations to keep pipeline full
                ops += 4
                if ops % 40 == 0:
                    torch.cuda.synchronize(self.device)
                    
                    # Verify result isn't garbage (NaN/Inf = memory corruption)
                    if torch.isnan(results[0]).any() or torch.isinf(results[0]).any():
                        errors.append("Compute produced NaN/Inf - possible memory corruption!")
            
            # Final sync
            torch.cuda.synchronize(self.device)
            
            del matrices, results
            
        except RuntimeError as e:
            errors.append(f"Compute error: {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
        
        return ops, errors
    
    def stress_pcie_transfer(self, duration_sec: float) -> Tuple[float, list]:
        """
        PCIe bus stress - heavy host<->device transfers.
        This is the key test for riser cable integrity!
        """
        errors = []
        total_gb = 0.0
        
        # Use LARGE buffers for maximum bus stress - 2GB chunks
        buffer_size = 2 * 1024 * 1024 * 1024  # 2 GB
        buffer_elements = buffer_size // 4  # float32 = 4 bytes
        
        try:
            # Multiple host buffers (pinned memory for faster DMA)
            host_srcs = [torch.randn(buffer_elements, dtype=torch.float32).pin_memory() for _ in range(2)]
            host_dsts = [torch.empty(buffer_elements, dtype=torch.float32).pin_memory() for _ in range(2)]
            
            # Multiple device buffers for overlapping transfers
            device_bufs = [torch.empty(buffer_elements, dtype=torch.float32, device=self.device) for _ in range(2)]
            
            # Create CUDA streams for concurrent transfers
            streams = [torch.cuda.Stream(device=self.device) for _ in range(2)]
            
            end_time = time.time() + duration_sec
            transfer_count = 0
            
            while time.time() < end_time and self.running:
                # Overlap transfers using multiple streams
                for i in range(2):
                    with torch.cuda.stream(streams[i]):
                        # Host -> Device (upload)
                        device_bufs[i].copy_(host_srcs[i], non_blocking=True)
                        # Device -> Host (download) 
                        host_dsts[i].copy_(device_bufs[i], non_blocking=True)
                
                # Sync all streams
                for stream in streams:
                    stream.synchronize()
                
                total_gb += (buffer_size * 4) / (1024**3)  # 2 buffers x 2 directions
                transfer_count += 1
                
                # Verify data integrity every 5 transfers
                if transfer_count % 5 == 0:
                    if not torch.allclose(host_srcs[0][:1000], host_dsts[0][:1000], rtol=1e-5, atol=1e-5):
                        errors.append("Data corruption detected in PCIe transfer!")
            
            del host_srcs, host_dsts, device_bufs
            
        except RuntimeError as e:
            errors.append(f"Transfer error: {e}")
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
        
        return total_gb, errors
    
    def stress_memory(self, duration_sec: float) -> Tuple[int, list]:
        """
        Memory stress - allocate/deallocate, fill with patterns.
        Tests VRAM stability.
        """
        errors = []
        cycles = 0
        
        try:
            # Get available memory
            torch.cuda.empty_cache()
            free_mem = torch.cuda.get_device_properties(self.device).total_memory
            free_mem = int(free_mem * 0.8)  # Use 80% to leave headroom
            
            end_time = time.time() + duration_sec
            
            while time.time() < end_time and self.running:
                # Allocate large buffer
                elements = free_mem // 4  # float32
                try:
                    buf = torch.empty(elements, dtype=torch.float32, device=self.device)
                    
                    # Fill with pattern
                    buf.fill_(cycles % 256)
                    torch.cuda.synchronize(self.device)
                    
                    # Verify pattern
                    expected = float(cycles % 256)
                    sample = buf[:1000].cpu()
                    if not torch.allclose(sample, torch.full_like(sample, expected)):
                        errors.append(f"Memory pattern verification failed at cycle {cycles}")
                    
                    del buf
                    torch.cuda.empty_cache()
                    cycles += 1
                    
                except RuntimeError as e:
                    if "out of memory" in str(e).lower():
                        # OOM is ok, just reduce size
                        free_mem = int(free_mem * 0.8)
                        torch.cuda.empty_cache()
                    else:
                        errors.append(f"Memory error: {e}")
                        break
            
        except Exception as e:
            errors.append(f"Unexpected error: {e}")
        
        return cycles, errors
    
    def run_mixed_stress(self, duration_sec: float):
        """
        Mixed workload - compute and transfer simultaneously.
        This is the ultimate riser stress test!
        """
        self._log("Starting mixed stress (compute + PCIe transfers)...")
        
        compute_ops = 0
        transfer_gb = 0.0
        all_errors = []
        
        # Run compute and transfer in parallel threads
        compute_result = [0, []]
        transfer_result = [0.0, []]
        
        def compute_worker():
            ops, errs = self.stress_compute(duration_sec)
            compute_result[0] = ops
            compute_result[1] = errs
        
        def transfer_worker():
            gb, errs = self.stress_pcie_transfer(duration_sec)
            transfer_result[0] = gb
            transfer_result[1] = errs
        
        t1 = threading.Thread(target=compute_worker)
        t2 = threading.Thread(target=transfer_worker)
        
        t1.start()
        t2.start()
        
        t1.join()
        t2.join()
        
        return compute_result[0], transfer_result[0], compute_result[1] + transfer_result[1]
    
    def run_full_test(self, duration_minutes: int = 60, phase_duration: int = 300):
        """
        Run the complete stress test suite.
        
        Args:
            duration_minutes: Total test duration in minutes
            phase_duration: Duration of each test phase in seconds
        """
        if not self.verify_gpu():
            return False
        
        self.start_time = datetime.now()
        end_time = self.start_time + timedelta(minutes=duration_minutes)
        
        print(f"\n{'='*60}")
        print(f"Starting stress test")
        print(f"Duration: {duration_minutes} minutes")
        print(f"Phase duration: {phase_duration} seconds")
        print(f"Matrix size: {self.matrix_size}x{self.matrix_size}")
        print(f"Expected end: {end_time.strftime('%H:%M:%S')}")
        print(f"{'='*60}\n")
        
        phase = 0
        
        try:
            while datetime.now() < end_time and self.running:
                phase += 1
                
                # Check GPU health before each phase
                stats = self.monitor.get_gpu_stats()
                if stats is None:
                    self._log("GPU NOT RESPONDING - may have dropped off bus!", "CRITICAL")
                    self.errors.append("GPU became unresponsive")
                    break
                
                issues = self.monitor.check_for_issues(stats)
                for issue in issues:
                    self._log(issue)
                    self.errors.append(issue)
                
                # Status update
                self._log(f"Phase {phase} | Temp: {stats['temp']}°C | Power: {stats['power']:.0f}W | "
                         f"PCIe: Gen{stats['pcie_gen']} x{stats['pcie_width']} | "
                         f"Mem: {stats['mem_used']}/{stats['mem_total']}MB")
                
                # Rotate through test types
                test_type = phase % 4
                
                if test_type == 0:
                    # Compute stress
                    self._log("Running: Compute stress (matrix multiply)...")
                    ops, errs = self.stress_compute(phase_duration)
                    self.total_ops += ops
                    self.errors.extend(errs)
                    self._log(f"  Completed {ops} matrix operations")
                    
                elif test_type == 1:
                    # PCIe stress
                    self._log("Running: PCIe bus stress (host<->device transfers)...")
                    gb, errs = self.stress_pcie_transfer(phase_duration)
                    self.total_transfers_gb += gb
                    self.errors.extend(errs)
                    self._log(f"  Transferred {gb:.1f} GB")
                    
                elif test_type == 2:
                    # Memory stress
                    self._log("Running: Memory stress (alloc/dealloc)...")
                    cycles, errs = self.stress_memory(phase_duration)
                    self.errors.extend(errs)
                    self._log(f"  Completed {cycles} memory cycles")
                    
                else:
                    # Mixed stress (hardest on riser)
                    self._log("Running: MIXED stress (compute + PCIe simultaneous)...")
                    ops, gb, errs = self.run_mixed_stress(phase_duration)
                    self.total_ops += ops
                    self.total_transfers_gb += gb
                    self.errors.extend(errs)
                    self._log(f"  Compute: {ops} ops, Transfer: {gb:.1f} GB")
                
                # Minimal cooldown between phases (just clear cache, no sleep)
                if self.running:
                    torch.cuda.empty_cache()
        
        except Exception as e:
            self._log(f"Test aborted: {e}", "ERROR")
            self.errors.append(f"Test aborted: {e}")
        
        # Final report
        self._print_report()
        
        return len([e for e in self.errors if "CRITICAL" in e]) == 0
    
    def _print_report(self):
        """Print final test report."""
        duration = datetime.now() - self.start_time if self.start_time else timedelta(0)
        
        print(f"\n{'='*60}")
        print("STRESS TEST COMPLETE")
        print(f"{'='*60}")
        print(f"Duration: {str(duration).split('.')[0]}")
        print(f"Total compute ops: {self.total_ops:,}")
        print(f"Total PCIe transfers: {self.total_transfers_gb:.1f} GB")
        print(f"Peak temperature: {self.monitor.max_temp}°C")
        print(f"Peak power: {self.monitor.max_power:.0f}W")
        print(f"Warnings: {self.monitor.warning_count}")
        print(f"Errors: {self.monitor.error_count}")
        
        # Final GPU check
        if self.monitor.check_gpu_present():
            final_stats = self.monitor.get_gpu_stats()
            if final_stats:
                print(f"\nFinal GPU status:")
                print(f"  Temperature: {final_stats['temp']}°C")
                print(f"  PCIe: Gen {final_stats['pcie_gen']} x{final_stats['pcie_width']}")
                print(f"  ECC corrected: {final_stats['ecc_corrected']}")
                print(f"  ECC uncorrected: {final_stats['ecc_uncorrected']}")
        else:
            print("\n⚠️  GPU NOT RESPONDING - likely dropped off bus!")
        
        if self.errors:
            print(f"\nIssues encountered:")
            for err in self.errors[:20]:  # Limit output
                print(f"  - {err}")
            if len(self.errors) > 20:
                print(f"  ... and {len(self.errors) - 20} more")
        
        # Verdict
        print(f"\n{'='*60}")
        critical_errors = [e for e in self.errors if "CRITICAL" in e]
        if critical_errors:
            print("❌ RISER CABLE TEST: FAILED")
            print("   Critical issues detected - riser may be unreliable!")
        elif self.monitor.warning_count > 10:
            print("⚠️  RISER CABLE TEST: MARGINAL")
            print("   Many warnings - monitor closely in production")
        else:
            print("✅ RISER CABLE TEST: PASSED")
            print("   No critical issues detected")
        print(f"{'='*60}\n")


def main():
    parser = argparse.ArgumentParser(
        description="GPU Riser Cable Stress Test",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  Quick test (5 min):    python gpu_riser_stress_test.py --duration 5
  Standard test (1 hr):  python gpu_riser_stress_test.py --duration 60
  Overnight test:        python gpu_riser_stress_test.py --duration 480
  Specific GPU:          python gpu_riser_stress_test.py --gpu 1 --duration 60
  Smaller matrices:      python gpu_riser_stress_test.py --matrix-size 8192 --duration 60
        """
    )
    parser.add_argument("--gpu", type=int, default=0, help="GPU ID to test (default: 0)")
    parser.add_argument("--duration", type=int, default=60, help="Test duration in minutes (default: 60)")
    parser.add_argument("--phase", type=int, default=300, help="Phase duration in seconds (default: 300)")
    parser.add_argument("--matrix-size", type=int, default=16384, help="Matrix size for compute test (default: 16384)")
    
    args = parser.parse_args()
    
    test = StressTest(gpu_id=args.gpu, matrix_size=args.matrix_size)
    success = test.run_full_test(duration_minutes=args.duration, phase_duration=args.phase)
    
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
