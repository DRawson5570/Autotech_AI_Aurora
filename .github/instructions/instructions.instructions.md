---
applyTo: '**'
---

## CRITICAL RULES
- **Approval required** before making code changes
- **Investigate first** - never guess, always gather evidence
- **Conda env**: `open-webui` (use `chrono_test` only for PyChrono simulation)
- **No CI references** - local development only

---

## 🎯 PROJECT: Predictive Diagnostics

**Goal:** Cut 1-2 hour diagnostic to 5 minutes with AI-powered root cause analysis.

### Documentation
- **Progress Tracker:** `addons/predictive_diagnostics/PROGRESS.md` ← **READ THIS FIRST**
- **Full Spec:** `addons/predictive_diagnostics/SPEC.md`

### Current Sprint (Jan 2026)
Training ML models from PyChrono-simulated vehicle data:
1. ✅ PyChrono simulation working (fault injection)
2. ⏳ Generating 10,000 training samples
3. ✅ Training scripts ready (`train_hierarchical_from_chrono.py`)
4. 🔜 Train final models when data generation completes

### Key Commands
```bash
# Check data generation progress
ls addons/predictive_diagnostics/training_data/chrono_synthetic/*.json | wc -l

# Train models (after generation completes)
cd addons/predictive_diagnostics
conda run -n open-webui python chrono_simulator/train_hierarchical_from_chrono.py --epochs 150
```

---

## Environment
- **Development:** localhost
- **Production:** poweredge1 (automotive.aurora-sentient.net)
- **Sync:** `./sync_to_servers.sh`

---

## Mitchell Agent
- **NEVER kill Chrome** or start the remote agent without permission
- **ALWAYS logout** before disconnecting (session limits!)
- Config: `addons/mitchell_agent/.env`
- Logs: `/tmp/mitchell_agent.log`

