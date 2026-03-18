"""Tests for monitor.py — live terminal dashboard."""

import json
import sys
import pytest
from pathlib import Path

SCRIPTS = Path(__file__).parent.parent / 'skills' / 'pickle-rick' / 'scripts'
sys.path.insert(0, str(SCRIPTS))

from monitor import (
    format_time, status_symbol, collect_tickets,
    latest_iteration_log, render,
)


class TestFormatTime:
    def test_seconds(self):
        assert format_time(45) == '0m45s'

    def test_minutes(self):
        assert format_time(125) == '2m05s'

    def test_hours(self):
        assert format_time(3661) == '1h01m01s'

    def test_zero(self):
        assert format_time(0) == '0m00s'


class TestStatusSymbol:
    def test_done(self):
        assert status_symbol('Done') == '[x]'

    def test_in_progress(self):
        assert status_symbol('In Progress') == '[>]'

    def test_todo(self):
        assert status_symbol('Todo') == '[ ]'

    def test_skipped(self):
        assert status_symbol('Skipped') == '[!]'

    def test_unknown(self):
        assert status_symbol('SomethingElse') == '[?]'

    def test_case_insensitive(self):
        assert status_symbol('done') == '[x]'
        assert status_symbol('TODO') == '[ ]'


class TestCollectTickets:
    def test_empty(self, tmp_session):
        tickets = collect_tickets(tmp_session)
        assert tickets == []

    def test_collects_tickets(self, tmp_session):
        ticket_dir = tmp_session / 'tickets' / 'abc123'
        ticket_dir.mkdir(parents=True)
        (ticket_dir / 'ticket.md').write_text(
            '---\nid: abc123\ntitle: First ticket\nstatus: Todo\norder: 10\n---\n')
        
        ticket_dir2 = tmp_session / 'tickets' / 'def456'
        ticket_dir2.mkdir(parents=True)
        (ticket_dir2 / 'ticket.md').write_text(
            '---\nid: def456\ntitle: Second ticket\nstatus: Done\norder: 20\n---\n')
        
        tickets = collect_tickets(tmp_session)
        assert len(tickets) == 2
        assert tickets[0]['order'] == 10
        assert tickets[1]['order'] == 20

    def test_sort_by_order(self, tmp_session):
        for i, (tid, order) in enumerate([('b', 30), ('a', 10), ('c', 20)]):
            d = tmp_session / 'tickets' / tid
            d.mkdir(parents=True)
            (d / 'ticket.md').write_text(f'---\nid: {tid}\ntitle: T{tid}\nstatus: Todo\norder: {order}\n---\n')
        
        tickets = collect_tickets(tmp_session)
        assert [t['id'] for t in tickets] == ['a', 'c', 'b']

    def test_no_tickets_dir(self, tmp_path):
        tickets = collect_tickets(tmp_path)
        assert tickets == []


class TestLatestIterationLog:
    def test_finds_log(self, tmp_session):
        (tmp_session / 'iteration_0.log').write_text('log 0')
        (tmp_session / 'iteration_1.log').write_text('log 1')
        log = latest_iteration_log(tmp_session)
        assert log is not None
        assert 'iteration_1' in str(log)

    def test_finds_microverse_log(self, tmp_session):
        (tmp_session / 'microverse_iter_0.log').write_text('mv log')
        log = latest_iteration_log(tmp_session)
        assert log is not None
        assert 'microverse' in str(log)

    def test_no_logs(self, tmp_session):
        log = latest_iteration_log(tmp_session)
        assert log is None


class TestRender:
    def test_render_active(self, tmp_session, capsys):
        result = render(tmp_session)
        assert result is True
        captured = capsys.readouterr()
        assert 'PICKLE RICK' in captured.out
        assert 'ONLINE' in captured.out

    def test_render_inactive(self, tmp_session, capsys):
        state = json.loads((tmp_session / 'state.json').read_text())
        state['active'] = False
        (tmp_session / 'state.json').write_text(json.dumps(state))
        result = render(tmp_session)
        assert result is False
        captured = capsys.readouterr()
        assert 'OFFLINE' in captured.out

    def test_render_missing_dir(self, tmp_path):
        result = render(tmp_path / 'nonexistent')
        assert result is False

    def test_render_with_tickets(self, tmp_session, capsys):
        ticket_dir = tmp_session / 'tickets' / 'abc'
        ticket_dir.mkdir(parents=True)
        (ticket_dir / 'ticket.md').write_text(
            '---\nid: abc\ntitle: My Ticket\nstatus: Todo\norder: 10\n---\n')
        render(tmp_session)
        captured = capsys.readouterr()
        assert 'My Ticket' in captured.out

    def test_render_with_circuit_breaker(self, tmp_session, capsys):
        (tmp_session / 'circuit_breaker.json').write_text(json.dumps({
            'state': 'HALF_OPEN', 'reason': 'no progress'}))
        render(tmp_session)
        captured = capsys.readouterr()
        assert 'HALF_OPEN' in captured.out
