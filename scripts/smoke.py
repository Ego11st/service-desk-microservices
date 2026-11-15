#!/usr/bin/env python3
"""Functional test against a real running application. Python stdlib only."""
import json
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path

BASE = sys.argv[1].rstrip('/') if len(sys.argv) > 1 else 'http://localhost:8080'
report = []


def req(path, method='GET', body=None):
    data = json.dumps(body).encode() if body is not None else None
    r = urllib.request.urlopen(urllib.request.Request(BASE + '/api/' + path, data=data, method=method,
        headers={'Content-Type': 'application/json'}), timeout=20)
    raw = r.read()
    return json.loads(raw) if raw else None, r.headers


def record(check, result):
    report.append({'check': check, 'result': result})
    print(check + ': ' + json.dumps(result, ensure_ascii=False), flush=True)


def main():
    record('hello', req('hello')[0])
    title = 'Демонстрационная заявка ' + str(int(time.time()))
    ticket, _ = req('tickets', 'POST', {'title': title, 'status': 'open'})
    ticket_id = ticket['id']
    record('INSERT', ticket)
    rows, headers = req('tickets')
    assert any(x['id'] == ticket_id and x['title'] == title for x in rows)
    record('SELECT and cache fill', {'X-Cache': headers.get('X-Cache')})
    _, headers = req('tickets')
    assert headers.get('X-Cache') == 'HIT', headers
    record('cache read', {'X-Cache': headers.get('X-Cache')})
    updated, _ = req('tickets/' + str(ticket_id), 'PUT', {'title': title + ' изменена', 'status': 'closed'})
    assert updated['status'] == 'closed'
    record('UPDATE', updated)
    rows, headers = req('tickets')
    assert any(x['id'] == ticket_id and x['status'] == 'closed' for x in rows)
    assert headers.get('X-Cache') != 'HIT', headers
    record('cache invalidation', {'X-Cache': headers.get('X-Cache')})
    deadline = time.monotonic() + 35
    while True:
        notifications, _ = req('notifications')
        found = [x for x in notifications if x['ticket_id'] == ticket_id]
        if found:
            assert len(found) == 1
            record('publish consume ACK', found[0])
            break
        if time.monotonic() > deadline:
            raise AssertionError('No notification from worker after 35 seconds')
        time.sleep(1)
    req('tickets/' + str(ticket_id), 'DELETE')
    rows, _ = req('tickets')
    assert all(x['id'] != ticket_id for x in rows)
    record('DELETE', {'deleted_id': ticket_id})
    record('diagnostics', req('diagnostics')[0])
    Path('evidence').mkdir(exist_ok=True)
    Path('evidence/functional.json').write_text(json.dumps(report, ensure_ascii=False, indent=2))
    print('PASS: CRUD, cache, invalidation and broker delivery')


if __name__ == '__main__':
    main()
