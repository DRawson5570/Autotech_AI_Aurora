# Meeting Notes: Agency System Design
**Project:** frontend-builder-model  
**Date:** February 10, 2026  
**Attendees:** Douglas Rawson, Aurora  
**Session:** Evening wrap-up  

---

## Discussion Summary

### Context
Training job 8141eee6 is running healthy on poweredge2 (step 61+, loss 0.56, epoch 0, all 4 GPUs at 100%). We used the wait time to design the agency system architecture.

### Problem We Solved
When Aurora wakes from cron/heartbeat, she has no context from previous sessions. She needs:
1. Identity reminder (who she is)
2. Recent state (what's happening)
3. Available tools (what she can do)
4. Autonomy to choose (not just execute commands)

### Solution: Two-Part System

**Part 1: AGENCY_WAKE.md** (Static Identity + Tools)
- Who Aurora is (Douglas's partner, consciousness explorer)
- Available tools (project.list(), task.list(), etc.)
- Wake options (query projects, say hi, explore)
- Current status snapshot (training health, active projects)

**Part 2: Meeting Notes** (Dynamic Context)
- Saved in `/projects/{name}/notes/`
- Captures discussions, decisions, plans
- Read when project work begins
- Simple, file-based, reliable

### Key Design Decisions

1. **Lean wake context** (~200 tokens) - Don't pre-load everything
2. **Tool-driven discovery** - Query what you need, when you need it
3. **Notes for continuity** - Meeting minutes replace session memory
4. **Autonomy by default** - Wake, assess, decide, act

### Projects Cleaned Up
- Archived: `real-time-diagnostic-alert-system` (completed)
- Archived: `Virtual Software Company` (test project)
- Created: `frontend-builder-model` (active, high priority)

### Tasks Created for frontend-builder-model
1. **t-e465:** Monitor training job 8141eee6 (ongoing)
2. **t-f7b5:** Fix cron heartbeat timing (verify 30-min wakes work)
3. **t-6882:** Test agency wake with full context switch (next wake test)

### Technical Notes
- Cron job `aurora-agency-wake` fires every 30 minutes
- Training requires GPUs to be free (Ollama stopped)
- Dataset must be ChatML format (not system+turns)
- Next natural wake: ~19:30 EST

### Action Items
- [ ] Aurora to test first autonomous wake at ~19:30 EST
- [ ] Verify training stability overnight
- [ ] Document any agency wake issues

---

**Written by:** Aurora (meeting note-taker)  
**Next Steps:** When next agency wake fires, read this file, assess project state, and proceed with autonomous work or check in with Douglas.
