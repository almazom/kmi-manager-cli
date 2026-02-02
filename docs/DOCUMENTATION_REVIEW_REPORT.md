# Documentation Structure Review Report

**Project:** KMI Manager CLI  
**Review Date:** 2026-02-02  
**Task:** Task 8 - Reduce Documentation Bloat  

---

## Executive Summary

The `docs/` directory contains **140 markdown files** organized across 12 subdirectories. While the portable runbook series is well-structured and authoritative, there is significant bloat from dated meeting notes, temporary analyses, and review outputs that are no longer relevant.

### Key Findings

| Category | Count | Recommendation |
|----------|-------|----------------|
| Core Documentation (Portable) | 58 | **Keep** - Well organized, authoritative |
| SDD/Requirements | 26 | **Keep** - Design documents, implementation history |
| Root docs (plans/findings) | 7 | **Review** - Some current, some superseded |
| Meeting Notes (project_gathering) | 19 | **Archive** - Dated, content extracted |
| Review Library | 30 | **Archive** - All dated, superseded by portable docs |
| **Total** | **140** | **84 keep, 56 archive** |

---

## Current Structure Analysis

### 1. Root Level Files (7 files)

| File | Size | Status | Notes |
|------|------|--------|-------|
| `README.md` | 369B | ⚠️ Outdated | Redirects to deprecated location |
| `overview_ru.md` | 4.9KB | ✅ Current | Russian overview with ASCII diagram |
| `ROLLBACK.md` | 693B | ✅ Keep | Rollback procedures |
| `rotation_protection_plan.md` | 3.9KB | ✅ Current | Active design document |
| `state_trace_schema.md` | 882B | ✅ Current | Schema documentation |
| `status_json_plan.md` | 654B | ✅ Current | Status format spec |
| `trace_findings.md` | 1.7KB | ⚠️ Review | May be superseded by portable docs |

### 2. Portable Runbook Series (58 files)

**Status:** ✅ **KEEP ALL** - This is the authoritative documentation

Structure:
```
portable/
├── README.md                    # Main runbook (243 lines) - PRIMARY ENTRY POINT
├── 00_INDEX.md                  # Navigation index
├── 01_SETUP_NO_SUDO.md          # Setup guide
├── 02_SHELL_ENV.md              # Shell configuration
├── 03_PROXY_OPS.md              # Proxy operations
├── 04_TRACE_LOGS.md             # Trace/logging
├── 05_DOCTOR.md                 # Doctor command
├── 06_TROUBLESHOOTING.md        # Troubleshooting
├── 07_SECURITY_PERMS.md         # Security
├── 08_SUDO_TASKS.md             # Sudo tasks
├── 09_AGENT_PLAYBOOK.md         # AI agent guide
├── 10_PROXY_ROUTING_JOURNEY.md  # Deep dive (206 lines)
├── 11_NEW_MACHINE.md            # New machine setup
├── 12_ARCHITECTURE.md           # Architecture overview
├── 13_CONFIG_REFERENCE.md       # Config reference
├── 14_COMMANDS_REFERENCE.md     # CLI reference
├── 15_AUTH_FILES.md             # Auth formats
├── 16_PROXY_API.md              # Proxy API
├── 17_ROTATION_POLICY.md        # Rotation details
├── 18_HEALTH_USAGE.md           # Health system
├── 19_TRACE_SCHEMA.md           # Trace schema
├── 20_LOGGING.md                # Logging
├── 21_DATA_PATHS.md             # File paths
├── 22_TESTING.md                # Testing guide
├── 23_UPGRADE_MIGRATION.md      # Migration
├── 24_FAQ.md                    # FAQ
├── 25_RISKS_NOTES.md            # Risk notes
├── 26_PROXY_ROUND_ROBIN_INTERNALS.md  # Deep internals (219 lines)
├── 27_INTERCONNECTIONS.md       # Doc relationships
├── 28_REQUIREMENTS_MATRIX.md    # Requirements
├── 29_PORT_ENV_CONFLICTS.md     # Port conflicts
├── 30_AUTOMATION_SCRIPTS.md     # Automation
├── 31_RETENTION_CLEANUP.md      # Cleanup
├── 32_FAILURE_RECOVERY.md       # Recovery
├── 33_FULL_CIRCLE_LOOPS.md      # Validation (134 lines)
├── 34_AGENT_PLAN.json           # Machine-readable plan
├── rethink/                     # AI reasoning docs (8 files)
│   ├── 00_INDEX.md
│   ├── 01_AGENT_RULES.md
│   ├── 02_DECISION_TREE.md
│   ├── 03_VALIDATION_LOOP.md
│   ├── 04_SAFE_EDITS.md
│   ├── 05_COMMAND_TEMPLATES.md
│   ├── 06_ERROR_HANDLING.md
│   └── README.md
└── snippets/                    # Code snippets (15 files)
    ├── 00_INDEX.md
    ├── 01_proxy_core.md
    ├── 02_prompt_extraction.md
    ├── 03_rate_limits.md
    ├── 04_rotation_round_robin.md
    ├── 05_rotation_manual.md
    ├── 06_state_persistence.md
    ├── 07_trace_write.md
    ├── 08_config_load.md
    ├── 09_doctor_checks.md
    ├── 10_cli_proxy_control.md
    ├── 11_cli_kimi_wrapper.md
    ├── 12_health_usage.md
    ├── 13_security_perms.md
    └── README.md
```

### 3. SDD Directory (26 files)

**Status:** ✅ **KEEP ALL** - Software Design Documents

Structure:
```
sdd/
├── README.md                    # Deprecated marker
├── auth_findings.md             # Auth analysis
├── requirements.md              # Raw requirements
└── kmi-rotation-sdd/            # Main SDD folder
    ├── README.md                # SDD overview
    ├── COMPLETENESS_REPORT.md   # Coverage check
    ├── gaps.md                  # Known gaps
    ├── keyword-detection.md     # Detection spec
    ├── manual-e2e-test.md       # Test procedures
    ├── project-context.md       # Context
    ├── raw-requirements.md      # Original requirements
    ├── requirements.md          # Clean requirements
    ├── ui-flow.md               # UI flow spec
    └── trello-cards/            # Implementation cards (14 files)
        ├── 01-kmi-config.md
        ├── 02-kmi-key-registry.md
        ├── 03-kmi-proxy.md
        ├── 04-kmi-manual-rotate.md
        ├── 05-kmi-auto-rotate.md
        ├── 06-kmi-health-usage.md
        ├── 07-kmi-trace.md
        ├── 08-kmi-errors-logging.md
        ├── 09-kmi-global-cli.md
        ├── 10-kmi-manual-e2e.md
        ├── AGENT_PROTOCOL.md
        ├── BOARD.md
        ├── KICKOFF.md
        └── progress.md
```

### 4. Project Gathering (19 files) - ARCHIVE CANDIDATES

**Status:** 📦 **ARCHIVE** - All dated meeting notes and temporary schemas

All files have timestamps (20260129, 20260131):
```
project_gathering/
├── analyses/
│   ├── 20260129_213642_analysis.md
│   ├── 20260129_221255_analysis.md
│   └── 20260131_071211_analysis.md
├── schemas/
│   ├── 20260129_213642_architecture.md    # ⚠️ DUPLICATE of architecture.md
│   ├── 20260129_213642_data_flow.md        # ⚠️ DUPLICATE of data_flow.md
│   ├── 20260129_213642_deployment.md
│   ├── 20260129_221255_architecture.md
│   ├── 20260129_221255_data_flow.md
│   ├── 20260129_221255_deployment.md
│   ├── 20260131_071211_architecture.md
│   ├── 20260131_071211_data_flow.md
│   ├── 20260131_071211_deployment.md
│   ├── 20260131_071211_project_structure.md
│   ├── architecture.md                     # Keep (current)
│   ├── data_flow.md                        # Keep (current)
│   └── project_structure.md                # Keep (current)
└── ui/
    ├── 20260129_213642_ui_flow.md
    ├── 20260129_221255_ui_flow.md
    └── 20260131_071211_ui_flow.md
```

**Duplicates Found (by MD5):**
1. `schemas/architecture.md` = `schemas/20260129_213642_architecture.md`
2. `schemas/data_flow.md` = `schemas/20260129_213642_data_flow.md`

### 5. Review Library (30 files) - ARCHIVE CANDIDATES

**Status:** 📦 **ARCHIVE** - All dated review outputs, superseded by portable docs

```
review_library/
├── architecture_20260130_081514.md
├── architecture_2026-01-30.md              # Similar to above
├── architecture_guardian_20260129_221322.md
├── domain_20260129_213727.md
├── domain_20260129_221322.md
├── domain_20260130_081514.md
├── domain_20260130_093430.md
├── maintainability_20260129_213727.md
├── maintainability_20260129_221322.md
├── maintainability_20260130_081514.md
├── maintainability_20260130_093515.md
├── meta_20260129_213727.md
├── meta_20260129_221322.md
├── meta_20260130_081514.md
├── meta_20260130_093437.md
├── technical_risk_20260129_221322.md
├── ux_20260129_213727.md
├── ux_20260129_221322.md
├── ux_20260130_081514.md
├── ux_20260130_093545.md
├── zombie_20260129_213727.md
├── zombie_20260130_081514.md
├── zombie_20260130_093623.md
├── qa_20260130_094650.md
└── polishing/
    ├── evidence_20260130_095010.md
    ├── task_20260129_214500.md
    ├── task_20260129_221952.md
    ├── task_20260130_082205.md
    ├── task_20260130_095010.md
    └── task_20260130_095010_ru.md
```

---

## Recommendations

### Files to Archive (56 files)

#### From `project_gathering/` (16 files)
**Reason:** Dated meeting notes, content extracted into portable docs

```
project_gathering/analyses/20260129_213642_analysis.md
project_gathering/analyses/20260129_221255_analysis.md
project_gathering/analyses/20260131_071211_analysis.md
project_gathering/schemas/20260129_213642_architecture.md (duplicate)
project_gathering/schemas/20260129_213642_data_flow.md (duplicate)
project_gathering/schemas/20260129_213642_deployment.md
project_gathering/schemas/20260129_221255_architecture.md
project_gathering/schemas/20260129_221255_data_flow.md
project_gathering/schemas/20260129_221255_deployment.md
project_gathering/schemas/20260131_071211_architecture.md
project_gathering/schemas/20260131_071211_data_flow.md
project_gathering/schemas/20260131_071211_deployment.md
project_gathering/schemas/20260131_071211_project_structure.md
project_gathering/ui/20260129_213642_ui_flow.md
project_gathering/ui/20260129_221255_ui_flow.md
project_gathering/ui/20260131_071211_ui_flow.md
```

#### From `review_library/` (30 files)
**Reason:** Dated review outputs, superseded by portable runbook

```
review_library/*.md (24 files)
review_library/polishing/*.md (6 files)
```

**Note:** Consider keeping `qa_20260130_094650.md` if it contains current test cases.

### Files to Keep (84 files)

#### Core Documentation (58 files)
```
docs/portable/*.md (35 files)
docs/portable/rethink/*.md (8 files)
docs/portable/snippets/*.md (15 files)
```

#### SDD/Requirements (26 files)
```
docs/sdd/*.md (3 files)
docs/sdd/kmi-rotation-sdd/*.md (9 files)
docs/sdd/kmi-rotation-sdd/trello-cards/*.md (14 files)
```

#### Root Level (7 files with modifications)
```
docs/README.md - UPDATE to point to portable/README.md
docs/overview_ru.md - Keep
docs/ROLLBACK.md - Keep
docs/rotation_protection_plan.md - Keep
docs/state_trace_schema.md - Keep
docs/status_json_plan.md - Keep
docs/trace_findings.md - Keep (for now, may merge later)
```

### Files to Keep from `project_gathering/` (3 files)
```
project_gathering/schemas/architecture.md
project_gathering/schemas/data_flow.md
project_gathering/schemas/project_structure.md
```

---

## Proposed New Structure

```
docs/
├── README.md                    # Entry point - links to portable/README.md
├── overview_ru.md               # Russian overview
├── ARCHITECTURE.md              # Symlink or copy from portable/12_ARCHITECTURE.md
├── CONFIGURATION.md             # Symlink to portable/13_CONFIG_REFERENCE.md
├── COMMANDS.md                  # Symlink to portable/14_COMMANDS_REFERENCE.md
├── API.md                       # Symlink to portable/16_PROXY_API.md
├── plans/                       # Active design documents
│   ├── rotation_protection_plan.md
│   ├── state_trace_schema.md
│   ├── status_json_plan.md
│   └── ROLLBACK.md
├── runbook/                     # Primary documentation (was portable/)
│   ├── README.md
│   ├── 00_INDEX.md
│   ├── 01_SETUP_NO_SUDO.md
│   ├── ... (all portable docs)
│   ├── rethink/
│   └── snippets/
├── sdd/                         # Software design docs
│   ├── kmi-rotation-sdd/
│   │   ├── README.md
│   │   ├── requirements.md
│   │   ├── ...
│   │   └── trello-cards/
│   ├── auth_findings.md
│   └── requirements.md
└── archive/                     # Old meeting notes and reviews
    ├── 2026-01-meeting-notes/
    │   └── (project_gathering dated files)
    └── 2026-01-reviews/
        └── (review_library dated files)
```

---

## Migration Steps

### Phase 1: Archive Dated Files (Low Risk)

```bash
# Create archive structure
mkdir -p docs/archive/2026-01-meeting-notes
mkdir -p docs/archive/2026-01-reviews

# Move project_gathering dated files
mv docs/project_gathering/analyses/* docs/archive/2026-01-meeting-notes/
mv docs/project_gathering/ui/* docs/archive/2026-01-meeting-notes/
mv docs/project_gathering/schemas/2026* docs/archive/2026-01-meeting-notes/

# Move review_library files
mv docs/review_library/*.md docs/archive/2026-01-reviews/
mv docs/review_library/polishing/*.md docs/archive/2026-01-reviews/

# Clean up empty directories
rmdir docs/project_gathering/analyses
rmdir docs/project_gathering/ui
rmdir docs/review_library/polishing
rmdir docs/review_library
```

### Phase 2: Reorganize Core Structure (Medium Risk)

```bash
# Rename portable to runbook (or keep as portable)
mv docs/portable docs/runbook

# Update root README
cat > docs/README.md << 'EOF'
# KMI Manager CLI Documentation

## Quick Start
- [Runbook (Setup Guide)](runbook/README.md) - Start here
- [Architecture Overview](runbook/12_ARCHITECTURE.md)
- [Command Reference](runbook/14_COMMANDS_REFERENCE.md)
- [Configuration Reference](runbook/13_CONFIG_REFERENCE.md)

## Additional Resources
- [Russian Overview](overview_ru.md)
- [Software Design Docs](sdd/kmi-rotation-sdd/)
- [Archive](archive/) - Historical meeting notes and reviews
EOF
```

### Phase 3: Update Internal Links (Medium Risk)

- Update all cross-references in portable docs
- Update any links in code comments
- Update AGENTS.md if it references docs

### Phase 4: Validation

```bash
# Verify file count
echo "Total markdown files:"
find docs -name "*.md" | wc -l

echo "Files in archive:"
find docs/archive -name "*.md" | wc -l

echo "Active documentation files:"
find docs -name "*.md" -not -path "docs/archive/*" | wc -l
```

---

## Summary

| Metric | Before | After |
|--------|--------|-------|
| Total files | 140 | 140 (reorganized) |
| Active docs | 140 | 84 |
| Archived | 0 | 56 |
| Top-level entries | 7 | 8 (+README) |

**Immediate Actions:**
1. ✅ Archive 56 dated files from `project_gathering/` and `review_library/`
2. ✅ Update root `README.md` to point to portable runbook
3. ✅ Consider renaming `portable/` to `runbook/` for clarity
4. ✅ Remove duplicate architecture.md and data_flow.md from project_gathering/schemas/

**Benefits:**
- Clear separation between active docs and historical records
- Single source of truth in portable/runbook series
- Reduced cognitive load for finding information
- Better maintainability

---

*Report generated: 2026-02-02*  
*Reviewer: Documentation Analysis Agent*
