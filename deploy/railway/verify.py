#!/usr/bin/env python3
"""One-version private MCP round trip and a subsequent restart durability check."""
import json, os, pathlib, subprocess, time, urllib.request, urllib.error, urllib.parse, uuid

home = pathlib.Path(os.environ.get('GBRAIN_HOME', '/data')) / '.gbrain'
receipt = home / 'runtime-verification.json'
handoff = home / 'runtime-verifier.json'
base = 'http://127.0.0.1:' + os.environ.get('PORT', '3131')
version = '0.60.243.0'

def save(value):
    temp = receipt.with_suffix('.tmp')
    temp.write_text(json.dumps(value, indent=2) + '\n')
    temp.chmod(0o600)
    temp.replace(receipt)

def verify():
    previous = json.loads(receipt.read_text()) if receipt.exists() else {}
    if previous.get('version') == version and previous.get('restart_verified'):
        print('[runtime-verify] prior MCP and restart verification retained', flush=True)
        return
    for _ in range(120):
        try:
            with urllib.request.urlopen(base + '/health', timeout=3) as response:
                if response.status == 200:
                    break
        except (urllib.error.URLError, TimeoutError):
            pass
        time.sleep(1)
    else:
        raise RuntimeError('health readiness timeout')
    if not handoff.exists():
        run = subprocess.run(['gbrain', 'mcp', 'grant', 'runtime-verifier', '--harness', 'codex',
            '--profile', 'memory-writer', '--skills', 'memory-only', '--source', 'default',
            '--url', base + '/mcp', '--budget-usd-per-day', '0', '--credentials-out', str(handoff), '--json'],
            capture_output=True, text=True, timeout=60)
        if run.returncode:
            raise RuntimeError('private MCP client provisioning failed: ' + run.stdout[:800])
    credentials = json.loads(handoff.read_text())
    form = urllib.parse.urlencode({'grant_type': 'client_credentials', 'client_id': credentials['client_id'],
        'client_secret': credentials['client_secret']}).encode()
    with urllib.request.urlopen(urllib.request.Request(base + '/token', data=form,
            headers={'Content-Type': 'application/x-www-form-urlencoded'}), timeout=20) as response:
        token = json.load(response)['access_token']
    counter = 0
    def rpc(method, params):
        nonlocal counter
        counter += 1
        body = json.dumps({'jsonrpc': '2.0', 'id': counter, 'method': method, 'params': params}).encode()
        headers = {'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream',
            'Authorization': 'Bearer ' + token, 'MCP-Protocol-Version': '2025-03-26'}
        with urllib.request.urlopen(urllib.request.Request(base + '/mcp', data=body, headers=headers), timeout=45) as response:
            raw = response.read().decode()
        messages = [json.loads(line[5:].strip()) for line in raw.splitlines() if line.startswith('data:')]
        result = next((item for item in messages if item.get('id') == counter), None) if messages else json.loads(raw)
        if 'error' in result:
            raise RuntimeError('MCP error ' + json.dumps(result['error'])[:800])
        return result['result']
    def call(name, params):
        out = rpc('tools/call', {'name': name, 'arguments': params})
        if out.get('isError'):
            raise RuntimeError(name + ' refused: ' + json.dumps(out)[:1200])
        data = out.get('structuredContent')
        if data is None:
            data = json.loads(next(block['text'] for block in out['content'] if block['type'] == 'text'))
        if data.get('state') in ('pending', 'accepted') or data.get('status') == 'write_pending':
            raise RuntimeError('write not yet committed')
        return data
    rpc('initialize', {'protocolVersion': '2025-03-26', 'capabilities': {},
        'clientInfo': {'name': 'private-runtime-verifier', 'version': '1'}})
    tools = {item['name'] for item in rpc('tools/list', {})['tools']}
    assert {'remember', 'recall', 'forget'} <= tools, 'memory tools absent'
    try:
        urllib.request.urlopen(urllib.request.Request(base + '/mcp', data=b'{}',
            headers={'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream'}), timeout=10)
        raise AssertionError('unauthenticated MCP unexpectedly accessible')
    except urllib.error.HTTPError as error:
        assert error.code == 401, 'unexpected unauthenticated response'
    if previous.get('version') == version and previous.get('pending_fact_id'):
        facts = call('recall', {'entity': previous['entity']})['facts']
        assert any(str(item.get('fact_id', item.get('id'))) == previous['pending_fact_id'] for item in facts), 'restart lost fact'
        call('forget', {'id': previous['pending_fact_id'], 'reason': 'restart verification complete'})
        save({'version': version, 'mcp_roundtrip': True, 'unauthenticated_denied': True,
            'restart_verified': True, 'verified_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime())})
        print('[runtime-verify] PASS: MCP auth, memory round trip, correction, withdrawal, restart durability', flush=True)
        return
    entity = 'runtime-verification-' + uuid.uuid4().hex[:10]
    initial = call('remember', {'fact': 'Install verification value alpha', 'entity': entity,
        'provenance': 'automated installation check', 'content_origin': 'tool_output'})
    fact_id = str(initial['id'])
    assert fact_id in json.dumps(call('recall', {'entity': entity})), 'saved fact not recalled'
    revised = call('remember', {'fact': 'Install verification value beta', 'entity': entity,
        'provenance': 'automated correction check', 'content_origin': 'tool_output', 'replaces': fact_id})
    assert revised['status'] == 'superseded', 'correction did not supersede original'
    revised_id = str(revised['id'])
    facts = call('recall', {'entity': entity})['facts']
    assert any(str(item.get('fact_id', item.get('id'))) == revised_id for item in facts), 'corrected fact missing'
    assert not any(str(item.get('fact_id', item.get('id'))) == fact_id for item in facts), 'old fact still active'
    call('forget', {'id': revised_id, 'reason': 'installation check cleanup'})
    assert not call('recall', {'entity': entity})['facts'], 'withdrawn fact still active'
    durable = call('remember', {'fact': 'Temporary restart durability probe', 'entity': entity,
        'provenance': 'automated installation check', 'content_origin': 'tool_output'})
    save({'version': version, 'mcp_roundtrip': True, 'unauthenticated_denied': True,
        'restart_verified': False, 'pending_fact_id': str(durable['id']), 'entity': entity})
    print('[runtime-verify] PASS: MCP auth, remember, recall, correction, withdrawal; restart check pending', flush=True)

try:
    verify()
except Exception as error:
    print('[runtime-verify] FAIL: ' + str(error), flush=True)
    raise
