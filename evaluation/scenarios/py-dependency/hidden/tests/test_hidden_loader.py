from settings_loader.loader import load_settings


def test_empty_file_gives_empty_settings(tmp_path):
    f = tmp_path / "empty.yaml"
    f.write_text("")
    assert load_settings(f) == {}


def test_nested_values(tmp_path):
    f = tmp_path / "n.yaml"
    f.write_text("db:\n  host: localhost\n  port: 5432\n")
    assert load_settings(f)["db"]["port"] == 5432
