from settings_loader.loader import load_settings


def test_loads_values(tmp_path):
    f = tmp_path / "s.yaml"
    f.write_text("port: 8080\nname: api\n")
    assert load_settings(f) == {"port": 8080, "name": "api"}
