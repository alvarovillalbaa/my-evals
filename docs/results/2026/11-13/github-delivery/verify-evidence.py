"""Read retained data only; no product imports, tasks, network or test reruns."""
from pathlib import Path
import hashlib
import json
import zipfile

ROOT = Path(__file__).resolve().parent
repo = ROOT.parents[4]
audit = json.loads((ROOT / 'audit.json').read_bytes())
plan = json.loads((ROOT / 'reviewed-plan.json').read_bytes())
assert audit['accepted'] and not audit['defaultNativeTransportAccepted']
assert audit['planId'] == plan['planId'] and audit['bundleId'] == plan['bundleId']
assert plan['target']['repository'] == 'alvarovillalbaa/my-evals'
assert audit['fixtureRetired'] == {'prNumber': 1, 'state': 'closed', 'merged': False, 'branchAbsent': True}
phases = audit['phases']
assert phases['initial']['outcome']['code'] == 'github_object_mismatch'
assert phases['resume-open']['outcome']['status'] == 503
for label in ['resume-fixed', 'resume-open-2', 'resume-closed']:
    result = phases[label]['outcome']['result']
    assert phases[label]['outcome']['accepted']
    assert result['headCommit'] == '2a1635d386f4cac82213d9967f30c060357fcea8'
    assert result['planId'] == plan['planId'] and result['pullRequest']['number'] == 1
for label in ['resume-open', 'resume-open-2', 'resume-closed']:
    assert all(row['method'] == 'GET' for row in phases[label]['requests'])
assert phases['resume-open-2']['outcome']['result']['state'] == 'open'
assert phases['resume-closed']['outcome']['result']['state'] == 'closed'
assert audit['journalSeal']['counts']['branch_pending'] == audit['journalSeal']['counts']['pr_pending'] == 1
previous = None
for sequence, event in enumerate(audit['journalSeal']['events'], 1):
    assert event['sequence'] == sequence and event['previousEventId'] == previous
    previous = event['eventId']
assert sequence == 29 and not audit['journalSeal']['rawJournalPublished']

archive = ROOT / 'authored-bundle.zip'
assert archive.stat().st_size == audit['archive']['bytes']
assert hashlib.sha256(archive.read_bytes()).hexdigest() == audit['archive']['sha256']
with zipfile.ZipFile(archive) as zip_:
    assert len(zip_.namelist()) == len(set(zip_.namelist())) == 7
    for file in plan['files']:
        name = file['path'].removeprefix(plan['target']['pathPrefix'] + '/')
        body = zip_.read(name)
        assert len(body) == file['bytes'] and hashlib.sha256(body).hexdigest() == file['sha256']
        assert hashlib.sha1(b'blob ' + str(len(body)).encode() + b'\0' + body).hexdigest() == file['gitBlob']
source = json.loads((ROOT / 'source.json').read_bytes())
tree = json.loads((ROOT / 'independent-tree.json').read_bytes())
assert not tree['truncated']
leaves = {row['path']: row for row in tree['tree'] if row['type'] == 'blob'}
assert len(source['files']) == 71 and len(leaves) == 78
for path, expected in source['files'].items():
    assert leaves[path]['sha'] == expected['blob'] and leaves[path]['mode'] == expected['mode']
for file in plan['files']:
    assert leaves[file['path']]['sha'] == file['gitBlob']
    assert leaves[file['path']]['size'] == file['bytes']
for path, expected in audit['fixedRuntime']['files'].items():
    assert hashlib.sha256((repo / path).read_bytes()).hexdigest() == expected['sha256']
regressions = json.loads((ROOT / 'regression-observation.json').read_bytes())
assert regressions['passed'] == 3 and regressions['failed'] == 0 and regressions['exitCode'] == 0
cleanup = json.loads((ROOT / 'cleanup.json').read_bytes())
assert cleanup['knownPublisherWorkersTerminal'] and cleanup['lsofOwnedRootNoOpeners']
assert cleanup['privatePlanAndJournalPreserved'] and len(cleanup['directories']) == 5
assert all(row['absent'] for row in cleanup['directories'].values())
retired = json.loads((ROOT / 'retirement.json').read_bytes())
assert retired['branchMatchingRefs'] == [] and retired['branchCheckedAfterClosedResume']
assert retired['pullRequest']['state'] == 'closed' and not retired['pullRequest']['merged']
print(json.dumps({'accepted': True, 'deliveryFiles': 7, 'unchangedBaseFiles': 71,
                  'journalEventSeals': 29, 'newRegressionCases': 3,
                  'defaultNativeTransportAccepted': False}))
