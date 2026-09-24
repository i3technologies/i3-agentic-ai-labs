import re, sys

checks = [
    'platform/admissions/admissions_agent.py',
    'platform/pmaas/agents/campaign_agent.py',
    'onboarding-agent/src/orchestrator/planner.ts',
    'onboarding-agent/src/orchestrator/subagents/base-scan.ts',
    'onboarding-agent/src/orchestrator/decisionLog.ts',
    'platform/agent-registry/manifests/admissions-agent-v1.yaml',
    'platform/agent-registry/manifests/pmaas-campaign-agent-v1.yaml',
    'platform/agent-registry/manifests/onboarding-planner-v1.yaml',
    'platform/agent-registry/main.py',
]
bad = re.compile(r'autonomy_tier.*["\x27](L2|L3)')
for fpath in checks:
    content = open(fpath, encoding='utf-8').read()
    m = bad.search(content)
    if m:
        sys.exit('HC-3 VIOLATION in %s: %s' % (fpath, m.group()))
    print('  %s: no L2/L3 -> PASS' % fpath)
print('HC-3 check: PASS -- no autonomy_tier > L1 in any file')
