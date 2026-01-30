# Manual E2E Test Checklist

> Status: READY | Last updated: 2026-01-29 11:14:26 MSK

**Prerequisites:**
- [ ] `kmi` installed globally and executable in PATH
- [ ] `.env` configured with required variables
- [ ] `_auths/` contains at least 3 keys
- [ ] Proxy can bind to `127.0.0.1:54123`

**Test Environment:**
- Dry-run mode: enabled
- Test data: sample prompts

## Test Cases

### Test 1: Manual Rotation

Steps:
1. [ ] Run: `kmi --rotate`
2. [ ] Verify: dashboard shows active key changed **or** rotation skipped with a reason
3. [ ] Verify: key list shows health status for each key
4. [ ] Run: `kmi --rotate` again
5. [ ] Verify: active key advances to most resourceful **or** rotation skipped if current ranks best

Expected result: ✅ rotation selects best key (or skips with reason) and dashboard updates

### Test 1b: Manual Rotation Skip (current best)

Steps:
1. [ ] Ensure current key has the highest remaining quota (or equal to others in dry-run)
2. [ ] Run: `kmi --rotate`
3. [ ] Verify: output says `Rotation skipped`
4. [ ] Verify: output shows a `Reason:` line

Expected result: ✅ rotation skipped with reasoning when current key is best

### Test 2: Auto Rotation + Trace

Steps:
1. [ ] Run: `kmi --auto_rotate`
2. [ ] Start a workload (send 10 requests through proxy)
3. [ ] Run: `kmi --trace`
4. [ ] Verify: trace shows alternating keys
5. [ ] Verify: confidence >= 95% after 200 requests

Expected result: ✅ round-robin and confidence metric valid

### Test 3: Blocked Key

Steps:
1. [ ] Mark a key invalid (401)
2. [ ] Trigger a request through proxy
3. [ ] Verify: key is marked blocked
4. [ ] Verify: next key is selected

Expected result: ✅ blocked key skipped

### Test 4: Exhausted Key Cooldown

Steps:
1. [ ] Force 429 on a key (rate limit)
2. [ ] Trigger a request through proxy
3. [ ] Verify: key marked exhausted and skipped
4. [ ] Wait for cooldown period
5. [ ] Verify: key becomes eligible again

Expected result: ✅ cooldown enforced and key re-enabled

## Regression Tests

- [ ] Kimi CLI still works with `KIMI_BASE_URL` overridden
- [ ] Kimi CLI can still list models and usage

## Sample Outputs

### Rotate

```
Rotation complete
Active key: alpha

Key Dashboard
Label   Status   Last Used             Key
alpha   healthy  2026-01-29T11:00:00Z   sk-1***7890
bravo   warn     2026-01-29T10:58:00Z   sk-2***abcd
```

### Rotate (skipped)

```
Rotation skipped
Reason: Current key ties for best remaining quota (100%). Keeping current over bravo.
Active key: alpha
```

### Trace

```
KMI TRACE | window=200 | confidence=97.5%
ts_msk               req_id    key   endpoint            status  latency_ms
2026-01-29 11:02:01  a1b2c3d4  alpha /chat/completions  200     143
```
