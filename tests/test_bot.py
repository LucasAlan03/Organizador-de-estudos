from datetime import date, datetime, timedelta

from app.alerts import get_day
from app.bot import Bot
from app.db import get_setting, set_setting

DAY = date(2026, 11, 6)
PATH = r"D:\Users\lucas\Desktop\Projetos\AP -ORG MMA"
CHAT = 555


class Clock:
    def __init__(self, h, m=0, day=DAY):
        self.t = datetime(day.year, day.month, day.day, h, m)

    def __call__(self):
        return self.t

    def advance(self, minutes):
        self.t += timedelta(minutes=minutes)


def make(conn, tg, clock, bound=True, sleep=None):
    if bound:
        set_setting(conn, "telegram_chat_id", str(CHAT))
    return Bot(conn, tg, clock, PATH, sleep=sleep)


def start_update(chat=CHAT):
    return {"update_id": 1, "message": {"chat": {"id": chat}, "text": "/start"}}


def press(data, chat=CHAT, cid="cb1", mid=100):
    return {
        "update_id": 2,
        "callback_query": {
            "id": cid,
            "data": data,
            "message": {"chat": {"id": chat}, "message_id": mid},
        },
    }


def test_tick_sends_alert_with_three_buttons_at_alert_time(conn, tg):
    bot = make(conn, tg, Clock(18, 30))
    assert bot.tick() is True
    msg = tg.sent[0]
    assert msg["chat_id"] == CHAT
    assert f"Pasta: {PATH}" in msg["text"]
    assert [d for _, d in msg["buttons"][0]] == ["agora", "adiar", "hoje_nao"]
    assert [t for t, _ in msg["buttons"][0]] == ["Consigo agora", "Daqui 30 min", "Hoje não"]


def test_tick_does_not_resend_after_alert_sent(conn, tg):
    clock = Clock(18, 30)
    bot = make(conn, tg, clock)
    bot.tick()
    clock.advance(1)
    assert bot.tick() is False
    assert len(tg.sent) == 1


def test_tick_before_alert_time_sends_nothing(conn, tg):
    assert make(conn, tg, Clock(18, 0)).tick() is False


def test_tick_without_chat_id_sends_nothing(conn, tg):
    assert make(conn, tg, Clock(18, 30), bound=False).tick() is False
    assert tg.sent == []


def test_start_binds_chat_id_and_replies(conn, tg):
    bot = make(conn, tg, Clock(10), bound=False)
    bot.handle_update(start_update())
    assert get_setting(conn, "telegram_chat_id") == str(CHAT)
    assert tg.sent[0]["chat_id"] == CHAT


def test_start_from_other_chat_is_ignored(conn, tg):
    bot = make(conn, tg, Clock(10))
    bot.handle_update(start_update(chat=999))
    assert get_setting(conn, "telegram_chat_id") == str(CHAT)
    assert tg.sent == []


def test_callback_agora_marks_vai_estudar_and_edits_message(conn, tg):
    clock = Clock(18, 31)
    bot = make(conn, tg, clock)
    bot.handle_update(press("agora"))
    assert get_day(conn, DAY)["status"] == "vai_estudar"
    assert tg.answered == ["cb1"]
    assert tg.edited[0]["message_id"] == 100


def test_callback_agora_message_has_folder_path_and_site_url(conn, tg):
    bot = make(conn, tg, Clock(18, 31))
    bot.handle_update(press("agora"))
    text = tg.edited[0]["text"]
    assert f"Pasta: {PATH}" in text
    assert "http://127.0.0.1:8765" in text


def test_callback_adiar_resends_after_snooze(conn, tg):
    clock = Clock(18, 30)
    bot = make(conn, tg, clock)
    bot.tick()
    clock.advance(1)
    bot.handle_update(press("adiar"))
    clock.advance(29)
    assert bot.tick() is False
    clock.advance(1)
    assert bot.tick() is True
    assert len(tg.sent) == 2


def test_callback_hoje_nao_stops_alerts(conn, tg):
    clock = Clock(18, 31)
    bot = make(conn, tg, clock)
    bot.handle_update(press("hoje_nao"))
    clock.advance(120)
    assert get_day(conn, DAY)["status"] == "pulou"
    assert bot.tick() is False


def test_callback_from_other_chat_ignored(conn, tg):
    bot = make(conn, tg, Clock(18, 31))
    bot.handle_update(press("hoje_nao", chat=999))
    assert get_day(conn, DAY)["status"] == "pendente"
    assert tg.answered == [] and tg.edited == []


def test_double_press_is_harmless(conn, tg):
    bot = make(conn, tg, Clock(18, 31))
    bot.handle_update(press("agora"))
    bot.handle_update(press("agora", cid="cb2"))
    assert get_day(conn, DAY)["status"] == "vai_estudar"
    assert tg.answered == ["cb1", "cb2"]


def test_new_day_alerts_again_once(conn, tg):
    clock = Clock(18, 30)
    bot = make(conn, tg, clock)
    assert bot.tick() is True
    clock.t = datetime(2026, 11, 7, 18, 30)
    assert bot.tick() is True
    assert bot.tick() is False
    assert len(tg.sent) == 2


def test_alert_time_change_applies_without_restart(conn, tg):
    bot = make(conn, tg, Clock(18, 40))
    set_setting(conn, "alert_time", "19:00")
    assert bot.tick() is False
    set_setting(conn, "alert_time", "18:30")
    assert bot.tick() is True


def test_alert_failure_does_not_mark_sent(conn, tg):
    bot = make(conn, tg, Clock(18, 30))
    tg.fail_send = True
    assert bot.tick() is False
    assert get_day(conn, DAY)["last_alert_at"] is None
    tg.fail_send = False
    assert bot.tick() is True


def test_alert_text_shows_minutes_studied_today(conn, tg):
    conn.execute(
        "INSERT INTO topics(id,title,position,pdf_title,pdf_pages,list_title) "
        "VALUES ('t','T',1,'p',1,'l')"
    )
    conn.execute(
        "INSERT INTO items(key,kind,topic_id,page,label,position) VALUES ('t:p1','page','t',1,'p1',1)"
    )
    conn.execute("INSERT INTO logs(item_id, minutes, day) VALUES (1, 25, ?)", (DAY.isoformat(),))
    conn.commit()
    make(conn, tg, Clock(18, 30)).tick()
    assert "25" in tg.sent[0]["text"] and "90" in tg.sent[0]["text"]


def test_run_backs_off_on_telegram_error_and_recovers(conn, tg):
    import threading

    stop = threading.Event()
    waits = []
    tg.fail_get_updates = 2
    tg.on_get_updates = lambda n: stop.set() if n >= 4 else None
    bot = make(conn, tg, Clock(10), sleep=waits.append)
    bot.run(stop)
    assert waits == [5, 10]
    assert tg.get_updates_calls == 4
