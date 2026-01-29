# Rollback Procedure

This project uses tagged savepoints during automated changes.

## Available Savepoints
- aop-savepoint-1 (after task 3)
- aop-savepoint-2 (after task 6)

## Rollback Steps
1. Inspect history:
   - git log --oneline --decorate -10
2. Reset to a savepoint:
   - git checkout aop-savepoint-2
   - (or) git checkout aop-savepoint-1
3. If you need to move the branch back:
   - git checkout master
   - git reset --hard aop-savepoint-2

## Notes
- Savepoints are lightweight tags; they do not delete newer commits.
- Use with care if you have uncommitted changes.
