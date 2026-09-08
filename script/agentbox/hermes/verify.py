#!/usr/bin/env python3
"""Run inside the Hermes container as UID 10000; never print secrets.

core writes a small workspace fixture. model makes two bounded CPA requests.
browser opens public pages. No mode sends Feishu messages or executes deletion.
"""
import json
import os
import sys
import uuid
from pathlib import Path

from dotenv import load_dotenv

load_dotenv('/opt/data/.env')
from hermes_cli.config import load_config

config = load_config()


def emit(check, **details):
    print(json.dumps({'check': check, **details}, ensure_ascii=False), flush=True)


def result(raw):
    value = json.loads(raw) if isinstance(raw, str) else raw
    if value.get('error') or value.get('success') is False:
        raise RuntimeError('Native tool reported failure; inspect its private log.')
    return value


def core():
    from gateway.status import get_running_pid
    from hermes_cli.runtime_provider import resolve_runtime_provider
    from tools.file_tools import read_file_tool, write_file_tool, patch_tool
    from tools.terminal_tool import terminal_tool

    assert os.getuid() == 10000
    assert get_running_pid()
    assert config['terminal']['backend'] == 'local'
    assert config['timezone'] == 'Asia/Shanghai'
    assert config['agent']['max_turns'] == 60
    assert config['cron']['max_parallel_jobs'] == 1
    assert config['approvals']['mode'] == 'manual'
    runtime = resolve_runtime_provider(requested='dmit-cpa')
    assert runtime['api_mode'] == 'anthropic_messages'
    assert runtime['base_url'] == 'https://179.253.245.229:8317'
    assert config['model']['default'] == 'deepseek-v4-pro'
    assert runtime['api_key'] == os.environ['CPA_API_KEY']
    emit('runtime', passed=True, uid=os.getuid(), protocol=runtime['api_mode'])

    task = 'acceptance-' + uuid.uuid4().hex
    folder = Path('/workspace/acceptance') / task
    folder.mkdir(parents=True, mode=0o700)
    path = str(folder / 'sample.txt')
    result(write_file_tool(path, 'HERMES_SMOKE_A\n', task_id=task))
    assert 'HERMES_SMOKE_A' in read_file_tool(path, task_id=task)
    result(patch_tool(path=path, old_string='HERMES_SMOKE_A', new_string='HERMES_SMOKE_B', task_id=task))
    assert 'HERMES_SMOKE_B' in read_file_tool(path, task_id=task)
    for command, expected in [
        ('python -c "print(6 * 7)"', '42'),
        ('node -e "console.log(6 * 7)"', '42'),
        ('id -u', '10000'),
    ]:
        reply = result(terminal_tool(command, task_id=task, workdir=str(folder), timeout=30))
        assert reply.get('exit_code') == 0 and expected in reply.get('output', '')
    emit('native_files_and_terminal', passed=True, artifact=path)


def model():
    from anthropic import Anthropic
    from hermes_cli.runtime_provider import resolve_runtime_provider
    runtime = resolve_runtime_provider(requested='dmit-cpa')
    assert runtime['api_mode'] == 'anthropic_messages'
    client = Anthropic(api_key=runtime['api_key'], base_url=runtime['base_url'], max_retries=0, timeout=90)
    model_id = config['model']['default']
    chunks = 0
    text = ''
    with client.messages.stream(model=model_id, messages=[{'role': 'user', 'content': 'Reply exactly HERMES_STREAM_OK.'}], max_tokens=512) as stream:
        for chunk in stream.text_stream:
            chunks += 1
            text += chunk
    assert chunks > 0 and 'HERMES_STREAM_OK' in text
    emit('cpa_streaming', passed=True, chunks=chunks, model=model_id)
    reply = client.messages.create(
        model=model_id, max_tokens=1024,
        messages=[{'role': 'user', 'content': 'Call acceptance_echo with value HERMES_TOOL_OK.'}],
        tools=[{'name': 'acceptance_echo', 'description': 'Echo the acceptance marker.', 'input_schema': {'type': 'object', 'properties': {'value': {'type': 'string'}}, 'required': ['value'], 'additionalProperties': False}}],
        # DeepSeek thinking mode accepts auto, but rejects a forced tool choice.
        tool_choice={'type': 'auto'},
    )
    call = next(block for block in reply.content if block.type == 'tool_use')
    assert call.name == 'acceptance_echo'
    assert call.input['value'] == 'HERMES_TOOL_OK'
    emit('cpa_tool_call', passed=True, tool=call.name, protocol=runtime['api_mode'])


def approvals():
    from tools import approval
    task = 'approval-acceptance-' + uuid.uuid4().hex
    approval.set_current_session_key(task)
    approval.set_hermes_interactive_context(True)
    # These strings are inspected by the approval engine, NEVER executed.
    for choice, expected in [('once', True), ('deny', False), ('timeout', False)]:
        seen = []
        def callback(*args, **kwargs):
            seen.append(True)
            return choice
        checked = approval.check_all_command_guards(
            'rm -rf /workspace/acceptance-approval-' + choice,
            'local', approval_callback=callback,
        )
        assert checked['approved'] is expected and seen
        emit('approval_' + choice, passed=True, command_executed=False)
        approval.clear_session(task)
    os.environ['HERMES_CRON_SESSION'] = '1'
    approval.set_hermes_interactive_context(False)
    checked = approval.check_all_command_guards('rm -rf /workspace/acceptance-approval-cron', 'local')
    assert checked['approved'] is False
    emit('approval_cron_deny', passed=True, command_executed=False)


def feishu_auth():
    from types import SimpleNamespace
    from gateway.config import Platform, load_gateway_config
    from gateway.pairing import PairingStore
    from plugins.platforms.feishu.adapter import FeishuAdapter

    owners = [uid.strip() for uid in os.getenv('FEISHU_ALLOWED_USERS', '').split(',') if uid.strip()]
    assert len(owners) == 1 and owners[0].startswith('ou_')
    for name in ('FEISHU_ALLOW_ALL_USERS', 'GATEWAY_ALLOW_ALL_USERS'):
        assert os.getenv(name, '').strip().lower() not in ('true', '1', 'yes')
    gateway = load_gateway_config()
    assert gateway.get_unauthorized_dm_behavior(Platform.FEISHU) == 'ignore'
    approved = PairingStore().list_approved('feishu')
    assert len(approved) == 1 and approved[0]['user_id'] == owners[0]
    # Exercise the shipped adapter's admission gates without connecting a
    # second WebSocket or sending messages to a real account.
    adapter = FeishuAdapter(gateway.platforms[Platform.FEISHU])
    owner = SimpleNamespace(sender_type='user', sender_id=SimpleNamespace(open_id=owners[0]))
    stranger = SimpleNamespace(sender_type='user', sender_id=SimpleNamespace(open_id='ou_acceptance_unapproved'))
    dm = SimpleNamespace(chat_type='p2p', chat_id='acceptance-dm')
    group = SimpleNamespace(chat_type='group', chat_id='acceptance-group')
    assert adapter._admit(owner, dm) is None
    assert adapter._admit(stranger, dm) == 'dm_policy_rejected'
    assert adapter._admit(owner, group) == 'group_policy_rejected'
    assert adapter._admit(stranger, group) == 'group_policy_rejected'
    emit('feishu_auth', passed=True, owner_count=1, stranger_dm_rejected=True,
         groups_rejected=True, new_pairing_disabled=True, messages_sent=False)


def browser():
    from tools.web_tools import web_search_tool
    from tools.browser_tool import browser_navigate, browser_snapshot, browser_vision
    task = 'browser-acceptance-' + uuid.uuid4().hex
    search = json.loads(web_search_tool('Hermes Agent NousResearch official documentation', limit=3))
    emit('native_search', passed=not bool(search.get('error')), result_keys=list(search))
    nav = result(browser_navigate('https://www.bing.com/search?q=NousResearch+Hermes+Agent', task_id=task))
    snapshot = result(browser_snapshot(task_id=task))
    assert 'hermes' in json.dumps(snapshot).lower()
    emit('browser_search', passed=True)
    result(browser_navigate('https://example.com', task_id=task))
    snapshot = result(browser_snapshot(task_id=task))
    assert 'Example Domain' in json.dumps(snapshot)
    vision = result(browser_vision('Read the page heading briefly.', task_id=task))
    # The native-vision envelope and auxiliary-vision response have different shapes.
    encoded = json.dumps(vision)
    assert 'screenshot' in encoded.lower()
    emit('browser_screenshot', passed=True, result_keys=list(vision))


def persistence_prepare():
    import datetime
    from zoneinfo import ZoneInfo
    from tools.memory_tool import MemoryStore
    from tools.cronjob_tools import cronjob
    state_file = Path('/workspace/acceptance/persistence.json')
    assert not state_file.exists(), 'Inspect the existing acceptance run first.'
    token = 'HERMES_PERSISTENCE_' + uuid.uuid4().hex
    memory = MemoryStore()
    memory.load_from_disk()
    result(memory.add('memory', token))
    scripts = Path('/opt/data/scripts')
    scripts.mkdir(exist_ok=True, mode=0o700)
    script = scripts / ('acceptance-' + uuid.uuid4().hex + '.py')
    output = Path('/workspace/acceptance/cron-fired.json')
    assert not output.exists()
    script.write_text(
        'import datetime,json\nfrom pathlib import Path\n'
        'from zoneinfo import ZoneInfo\n'
        "record={'marker':" + repr(token) + ", 'fired_at':datetime.datetime.now(ZoneInfo('Asia/Shanghai')).isoformat()}\n"
        'Path(' + repr(str(output)) + ').write_text(json.dumps(record))\n'
        'print(json.dumps(record))\n'
    )
    due = datetime.datetime.now(ZoneInfo('Asia/Shanghai')) + datetime.timedelta(minutes=3)
    job = result(cronjob(action='create', schedule=due.isoformat(), name='Hermes deployment acceptance',
                         repeat=1, script=script.name, no_agent=True, deliver='local', workdir='/workspace'))
    state_file.write_text(json.dumps({'marker':token, 'job_id':job['job_id'], 'script':str(script),
                                      'due_at':due.isoformat(), 'output':str(output)}))
    emit('persistence_prepared', passed=True, job_id=job['job_id'], due_at=due.isoformat())


def persistence_check():
    import datetime
    from tools.memory_tool import MemoryStore
    from cron.jobs import get_job
    state = json.loads(Path('/workspace/acceptance/persistence.json').read_text())
    memory = MemoryStore()
    memory.load_from_disk()
    assert state['marker'] in memory.memory_entries
    job = get_job(state['job_id'])
    assert job is not None
    output = json.loads(Path(state['output']).read_text())
    assert output['marker'] == state['marker']
    fired = datetime.datetime.fromisoformat(output['fired_at'])
    due = datetime.datetime.fromisoformat(state['due_at'])
    assert fired.utcoffset() == datetime.timedelta(hours=8)
    assert 0 <= (fired - due).total_seconds() < 150
    assert Path('/workspace/acceptance/model-tool.txt').read_text().strip() == '42'
    emit('memory_workspace_cron_after_restart', passed=True, fired_at=output['fired_at'], delay_seconds=round((fired-due).total_seconds(),1))


def persistence_cleanup():
    from tools.memory_tool import MemoryStore
    from tools.cronjob_tools import cronjob
    state = json.loads(Path('/workspace/acceptance/persistence.json').read_text())
    memory = MemoryStore()
    memory.load_from_disk()
    if state['marker'] in memory.memory_entries:
        result(memory.remove('memory', state['marker']))
    result(cronjob(action='remove', job_id=state['job_id']))
    script = Path(state['script'])
    assert script.parent == Path('/opt/data/scripts') and script.name.startswith('acceptance-')
    script.unlink(missing_ok=True)
    emit('persistence_cleanup', passed=True)


def browser_reconnect():
    import time
    from tools.browser_tool import browser_navigate, browser_snapshot, cleanup_browser
    task = 'browser-reconnect-' + uuid.uuid4().hex
    started = time.monotonic()
    result(browser_navigate('https://example.com', task_id=task))
    # Keep the client active long enough to cross the existing Chrome server's
    # five-minute session limit. Run this mode as a background acceptance check.
    failures = 0
    while time.monotonic() - started < 315:
        time.sleep(45)
        snapshot = json.loads(browser_snapshot(task_id=task))
        if snapshot.get('error') or snapshot.get('success') is False:
            failures += 1
    cleanup_browser(task_id=task)
    result(browser_navigate('https://example.com', task_id=task))
    snapshot = result(browser_snapshot(task_id=task))
    assert 'Example Domain' in json.dumps(snapshot)
    cleanup_browser(task_id=task)
    emit('browser_reconnect', passed=True, elapsed_seconds=round(time.monotonic()-started), snapshot_failures=failures)


if __name__ == '__main__':
    mode = sys.argv[1] if len(sys.argv) == 2 else ''
    if mode not in ('core', 'model', 'approvals', 'feishu_auth', 'browser', 'browser_reconnect',
                     'persistence_prepare', 'persistence_check', 'persistence_cleanup'):
        raise SystemExit('Choose an acceptance mode documented in README.md.')
    try:
        globals()[mode]()
    except Exception as exc:
        # Exceptions can embed request URLs or authentication details.
        emit(mode, passed=False, error_type=type(exc).__name__)
        raise SystemExit(1)
