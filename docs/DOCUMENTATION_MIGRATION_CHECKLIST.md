# Documentation Migration Checklist

## Phase 1: Create Archive Structure

```bash
# Create archive directories
mkdir -p docs/archive/2026-01-meeting-notes/analyses
mkdir -p docs/archive/2026-01-meeting-notes/ui
mkdir -p docs/archive/2026-01-meeting-notes/schemas
mkdir -p docs/archive/2026-01-reviews/polishing
```

## Phase 2: Archive Dated Files (56 files)

### Move project_gathering/analyses/ (3 files)
- [ ] `docs/project_gathering/analyses/20260129_213642_analysis.md`
- [ ] `docs/project_gathering/analyses/20260129_221255_analysis.md`
- [ ] `docs/project_gathering/analyses/20260131_071211_analysis.md`

### Move project_gathering/ui/ (3 files)
- [ ] `docs/project_gathering/ui/20260129_213642_ui_flow.md`
- [ ] `docs/project_gathering/ui/20260129_221255_ui_flow.md`
- [ ] `docs/project_gathering/ui/20260131_071211_ui_flow.md`

### Move project_gathering/schemas/ dated files (10 files)
- [ ] `docs/project_gathering/schemas/20260129_213642_architecture.md` (DUPLICATE)
- [ ] `docs/project_gathering/schemas/20260129_213642_data_flow.md` (DUPLICATE)
- [ ] `docs/project_gathering/schemas/20260129_213642_deployment.md`
- [ ] `docs/project_gathering/schemas/20260129_221255_architecture.md`
- [ ] `docs/project_gathering/schemas/20260129_221255_data_flow.md`
- [ ] `docs/project_gathering/schemas/20260129_221255_deployment.md`
- [ ] `docs/project_gathering/schemas/20260131_071211_architecture.md`
- [ ] `docs/project_gathering/schemas/20260131_071211_data_flow.md`
- [ ] `docs/project_gathering/schemas/20260131_071211_deployment.md`
- [ ] `docs/project_gathering/schemas/20260131_071211_project_structure.md`

### Move review_library/ root files (24 files)
- [ ] `docs/review_library/architecture_20260130_081514.md`
- [ ] `docs/review_library/architecture_2026-01-30.md`
- [ ] `docs/review_library/architecture_guardian_20260129_221322.md`
- [ ] `docs/review_library/domain_20260129_213727.md`
- [ ] `docs/review_library/domain_20260129_221322.md`
- [ ] `docs/review_library/domain_20260130_081514.md`
- [ ] `docs/review_library/domain_20260130_093430.md`
- [ ] `docs/review_library/maintainability_20260129_213727.md`
- [ ] `docs/review_library/maintainability_20260129_221322.md`
- [ ] `docs/review_library/maintainability_20260130_081514.md`
- [ ] `docs/review_library/maintainability_20260130_093515.md`
- [ ] `docs/review_library/meta_20260129_213727.md`
- [ ] `docs/review_library/meta_20260129_221322.md`
- [ ] `docs/review_library/meta_20260130_081514.md`
- [ ] `docs/review_library/meta_20260130_093437.md`
- [ ] `docs/review_library/qa_20260130_094650.md`
- [ ] `docs/review_library/technical_risk_20260129_221322.md`
- [ ] `docs/review_library/ux_20260129_213727.md`
- [ ] `docs/review_library/ux_20260129_221322.md`
- [ ] `docs/review_library/ux_20260130_081514.md`
- [ ] `docs/review_library/ux_20260130_093545.md`
- [ ] `docs/review_library/zombie_20260129_213727.md`
- [ ] `docs/review_library/zombie_20260130_081514.md`
- [ ] `docs/review_library/zombie_20260130_093623.md`

### Move review_library/polishing/ (6 files)
- [ ] `docs/review_library/polishing/evidence_20260130_095010.md`
- [ ] `docs/review_library/polishing/task_20260129_214500.md`
- [ ] `docs/review_library/polishing/task_20260129_221952.md`
- [ ] `docs/review_library/polishing/task_20260130_082205.md`
- [ ] `docs/review_library/polishing/task_20260130_095010.md`
- [ ] `docs/review_library/polishing/task_20260130_095010_ru.md`

## Phase 3: Clean Up Empty Directories

```bash
# After moving files, remove empty directories
rmdir docs/project_gathering/analyses 2>/dev/null || true
rmdir docs/project_gathering/ui 2>/dev/null || true
rmdir docs/review_library/polishing 2>/dev/null || true
rmdir docs/review_library 2>/dev/null || true
```

## Phase 4: Update Root Documentation

### Update docs/README.md
- [ ] Replace content with new navigation structure pointing to portable/

### Add docs/ARCHITECTURE.md (optional)
- [ ] Create symlink or copy from portable/12_ARCHITECTURE.md

## Phase 5: Verification

### File Count Checks
```bash
# Should show: 84 active, 56 archived
echo "=== Active Documentation ==="
find docs -name "*.md" -not -path "docs/archive/*" | wc -l

echo "=== Archived Documentation ==="
find docs/archive -name "*.md" 2>/dev/null | wc -l

echo "=== Total Documentation ==="
find docs -name "*.md" | wc -l
```

### Directory Structure Check
```bash
echo "=== New Structure ==="
tree -L 3 docs/ 2>/dev/null || find docs -type d | sort
```

## Files Retained (84 files)

### Root Level (7 files)
1. `docs/README.md` (updated)
2. `docs/overview_ru.md`
3. `docs/ROLLBACK.md`
4. `docs/rotation_protection_plan.md`
5. `docs/state_trace_schema.md`
6. `docs/status_json_plan.md`
7. `docs/trace_findings.md`

### project_gathering/schemas/ (3 files - current versions)
1. `docs/project_gathering/schemas/architecture.md`
2. `docs/project_gathering/schemas/data_flow.md`
3. `docs/project_gathering/schemas/project_structure.md`

### portable/ (58 files total)
- 35 files in portable/
- 8 files in portable/rethink/
- 15 files in portable/snippets/

### sdd/ (26 files)
- 3 files in sdd/
- 9 files in sdd/kmi-rotation-sdd/
- 14 files in sdd/kmi-rotation-sdd/trello-cards/

---

## Post-Migration Notes

- The `portable/` directory name may be renamed to `runbook/` for clarity
- Consider adding a note to archived files indicating they are historical
- Update any internal links that reference moved files
- Consider compressing archive/ directory to save space
