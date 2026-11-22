"""Screen stream, console copy, --first subset, and small-subset bulk skip."""
import json
import time

from invoice_closer.bulk import SMALL_SUBSET, BulkGateway, lookup_gateway, take_first
from invoice_closer.inputs import Target
from invoice_closer.reporting import RunLog, screen_line


def test_runlog_streams_timestamped_lines_and_keeps_console_copy(tmp_path, capsys):
    log = RunLog(tmp_path)
    log("outcome", invoice="123", outcome="HELD", reason="no fund", record={"big": "x" * 5000})
    log("run_context", argv=["x"])          # file only
    log.echo("final report")
    log.close()
    out = capsys.readouterr().out.splitlines()
    assert out[0][:4].isdigit() and " outcome " in out[0] and "invoice=123" in out[0]
    assert "record=" not in out[0]          # bulky fields stay in the file only
    assert not any("run_context" in l for l in out)
    assert out[-1] == "final report"
    assert (tmp_path / "console.txt").read_text(encoding="utf-8").splitlines() == out
    recs = [json.loads(l) for l in (tmp_path / "log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert recs[0]["record"]["big"] == "x" * 5000 and "." in recs[0]["t"]   # ms timestamps


def test_quiet_shows_progress_only(tmp_path, capsys):
    log = RunLog(tmp_path, stream=False)
    log("outcome", invoice="1")
    log("progress", stage="s", done=1, total=2)
    log.close()
    out = capsys.readouterr().out
    assert "outcome" not in out and "progress" in out


def test_screen_line_cuts_long_values():
    line = screen_line({"t": "2026-11-22T09:00:00.000", "event": "e", "reason": "y" * 500})
    assert len(line) < 250 and line.startswith("2026-11-22 09:00:00.000")


def test_take_first_keeps_first_n():
    ts = [Target("invoice_number", str(i), f"f row {i}") for i in range(10)]
    logged = []
    assert [t.value for t in take_first(ts, 3, lambda *a, **k: logged.append(k))] == ["0", "1", "2"]
    assert logged[0]["of"] == 10
    assert take_first(ts, None, print) is ts and take_first(ts, 99, print) is ts


def test_small_subset_skips_bulk_unless_fresh_cache(tmp_path):
    gw, cache = object(), tmp_path / "c.json"
    assert lookup_gateway(gw, "RIALTO", lambda *a, **k: None, cache, 60, SMALL_SUBSET) is gw
    assert lookup_gateway(gw, None, lambda *a, **k: None, cache, 60, None) is gw
    cache.write_text(json.dumps({"vendor": "RIALTO", "invoices": [], "lines": {}, "pols": {}}))
    got = lookup_gateway(gw, "RIALTO", lambda *a, **k: None, cache, 60, 5)
    assert isinstance(got, BulkGateway)
