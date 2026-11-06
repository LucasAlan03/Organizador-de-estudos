def test_painel_ok(client):
    r = client.get("/")
    assert r.status_code == 200
    assert "Faltam 36 dias" in r.text
    assert "Dados insuficientes" in r.text
    assert "Próximo sugerido" in r.text
    assert "Página 1" in r.text


def test_static_css(client):
    assert client.get("/static/style.css").status_code == 200


def test_flash_messages_are_escaped(client):
    r = client.get("/?erro=Algo%20deu%20errado")
    assert "Algo deu errado" in r.text
    r = client.get("/?ok=<b>x</b>")
    assert "<b>x</b>" not in r.text


def test_menu_links(client):
    html = client.get("/").text
    for href in ("/teoria", "/listas", "/historico", "/config"):
        assert f'href="{href}"' in html
