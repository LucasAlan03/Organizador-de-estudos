from datetime import date, datetime, time, timedelta

from app.alerts import apply_action, get_day, mark_alert_sent, should_alert

ALERT = time(18, 30)
DAY = date(2026, 11, 6)


def at(h, m=0, day=DAY):
    return datetime(day.year, day.month, day.day, h, m)


def test_no_alert_before_alert_time():
    assert should_alert("pendente", at(18, 29), ALERT, None, None) is False


def test_alert_at_alert_time_when_pendente():
    assert should_alert("pendente", at(18, 30), ALERT, None, None) is True


def test_catch_up_sends_once_after_alert_time():
    assert should_alert("pendente", at(19, 40), ALERT, None, None) is True
    assert should_alert("pendente", at(19, 41), ALERT, None, at(19, 40)) is False


def test_no_alert_after_2200():
    assert should_alert("pendente", at(21, 59), ALERT, None, None) is True
    assert should_alert("pendente", at(22, 0), ALERT, None, None) is False


def test_no_alert_when_estudou_pulou_or_vai_estudar():
    for status in ("estudou", "pulou", "vai_estudar"):
        assert should_alert(status, at(19), ALERT, None, None) is False


def test_snooze_blocks_until_due():
    snooze = at(19, 0)
    last = at(18, 30)
    assert should_alert("pendente", at(18, 59), ALERT, snooze, last) is False
    assert should_alert("pendente", at(19, 0), ALERT, snooze, last) is True


def test_snooze_past_2200_never_fires():
    assert should_alert("pendente", at(22, 5), ALERT, at(22, 0), at(21, 30)) is False


def test_last_alert_from_yesterday_does_not_block_today():
    yesterday = at(18, 30, DAY - timedelta(days=1))
    assert should_alert("pendente", at(18, 30), ALERT, None, yesterday) is True


def test_get_day_creates_pendente(conn):
    row = get_day(conn, DAY)
    assert row["status"] == "pendente"
    assert row["alert_count"] == 0


def test_apply_action_agora_sets_vai_estudar(conn):
    get_day(conn, DAY)
    text = apply_action(conn, "agora", at(18, 31), 30)
    assert get_day(conn, DAY)["status"] == "vai_estudar"
    assert text


def test_apply_action_hoje_nao_sets_pulou(conn):
    get_day(conn, DAY)
    apply_action(conn, "hoje_nao", at(18, 31), 30)
    assert get_day(conn, DAY)["status"] == "pulou"


def test_apply_action_adiar_sets_snooze_until_now_plus_30(conn):
    get_day(conn, DAY)
    apply_action(conn, "adiar", at(18, 31), 30)
    row = get_day(conn, DAY)
    assert row["status"] == "pendente"
    assert row["snooze_until"] == at(19, 1).isoformat()


def test_apply_action_after_estudou_keeps_estudou(conn):
    get_day(conn, DAY)
    conn.execute("UPDATE days SET status = 'estudou' WHERE day = ?", (DAY.isoformat(),))
    conn.commit()
    for action in ("agora", "adiar", "hoje_nao"):
        apply_action(conn, action, at(20), 30)
    row = get_day(conn, DAY)
    assert row["status"] == "estudou"
    assert row["snooze_until"] is None


def test_mark_alert_sent_clears_snooze_and_counts(conn):
    get_day(conn, DAY)
    apply_action(conn, "adiar", at(18, 31), 30)
    mark_alert_sent(conn, at(19, 1))
    row = get_day(conn, DAY)
    assert row["snooze_until"] is None
    assert row["alert_count"] == 1
    assert row["last_alert_at"] == at(19, 1).isoformat()
