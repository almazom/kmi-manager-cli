# Rollback Procedure

This project uses tagged savepoints during automated changes.

## Available Savepoints
- aop-savepoint-8 (after Phase 4 docs + CI updates)
- aop-savepoint-7 (after Phase 4 core fixes)
- aop-savepoint-6 (previous run)

## Rollback Steps
1. Inspect history:
   - git log --oneline --decorate -10
2. Reset to a savepoint:
   - git checkout aop-savepoint-8
   - (or) git checkout aop-savepoint-7
3. If you need to move the branch back:
   - git checkout master
   - git reset --hard aop-savepoint-2

## Notes
- Savepoints are lightweight tags; they do not delete newer commits.
- Use with care if you have uncommitted changes.
