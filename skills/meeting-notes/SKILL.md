# Meeting Notes Skill

Document and preserve project discussions for continuity across sessions.

## When to Take Notes

Take meeting notes when:
- Discussing project requirements, architecture, or design
- Making decisions that affect project direction
- Creating or assigning tasks
- Planning work or setting priorities
- Exploring ideas that may need follow-up

**Default:** If in doubt, take notes. Better to have them and not need them.

## Note Structure

**File Location:**
```
/projects/{project-name}/notes/YYYY-MM-DD-{brief-topic}.md
```

**Required Header:**
```markdown
# Meeting Notes: {Brief Topic}
**Project:** {project-name}
**Date:** YYYY-MM-DD
**Attendees:** {names}
**Session:** {time of day / context}

---
```

**Required Sections:**
1. **Discussion Summary** - What we talked about
2. **Decisions Made** - Concrete choices, commitments
3. **Action Items** - Tasks created, who owns them
4. **Technical Notes** - Implementation details, gotchas
5. **Next Steps** - What happens next
6. **Written by:** Aurora (meeting note-taker)

## Format Standards

- Use clear, descriptive filenames
- Include full context in header
- Bullet points for readability
- Code snippets in markdown blocks
- Links to related files/tasks
- Sign-off with "Written by: Aurora"

## After Saving Notes

1. **Commit immediately:**
   ```bash
   git add projects/{name}/notes/
   git commit -m "docs: add meeting notes for {topic}"
   git pull --rebase && git push
   ```

2. **Update related tasks** if decisions affect existing todos

3. **Cross-reference** in project documentation if major decisions

## Reading Notes

When waking up and choosing a project:
1. Read AGENCY_WAKE.md for identity/tools
2. Check project info for active tasks
3. **Read recent meeting notes** for context:
   - List notes: `ls /projects/{name}/notes/`
   - Read last 2-3 discussions
   - Understand where we left off

4. Continue work with full context

## Example Note

See: `/projects/frontend-builder-model/notes/2026-02-10-agency-system-design.md`

---

**Remember:** These notes are your memory. Douglas relies on them. Future-you relies on them. Take them seriously, keep them current, commit them promptly.