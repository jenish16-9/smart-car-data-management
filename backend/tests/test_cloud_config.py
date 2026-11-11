"""Cloud-style connection strings (placeholders only; nothing here connects anywhere)."""

from urllib.parse import quote

import pytest
from pymongo.uri_parser import parse_uri
from sqlalchemy.engine import make_url

from app.core.config import normalize_postgres_url, redact_url
from app.db.postgres import engine_options

SPECIAL = "p@ss:w/rd#?%&=+ ü"


def test_postgres_scheme_is_converted_to_asyncpg() -> None:
    for scheme in ("postgres", "postgresql"):
        url = normalize_postgres_url(f"{scheme}://dev_user:CHANGE_ME@host.example.com/smart_car_dev")
        assert make_url(url).drivername == "postgresql+asyncpg"


def test_encoded_password_round_trips() -> None:
    raw = f"postgresql+asyncpg://dev_user:{quote(SPECIAL, safe='')}@host.example.com/smart_car_dev"
    parsed = make_url(normalize_postgres_url(raw))
    assert parsed.password == SPECIAL
    assert parsed.username == "dev_user"
    assert parsed.host == "host.example.com"


def test_libpq_ssl_options_are_translated_for_asyncpg() -> None:
    url = normalize_postgres_url("postgresql://u:CHANGE_ME@h.example.com/db?sslmode=require&channel_binding=require")
    assert dict(make_url(url).query) == {"ssl": "require"}


def test_non_asyncpg_urls_are_left_alone() -> None:
    assert normalize_postgres_url("sqlite+aiosqlite://") == "sqlite+aiosqlite://"


def test_pooler_hosts_disable_prepared_statement_cache() -> None:
    pooled = engine_options("postgresql+asyncpg://u:x@ep-1-pooler.region.aws.neon.tech/db")
    direct = engine_options("postgresql+asyncpg://u:x@ep-1.region.aws.neon.tech/db")
    assert pooled["connect_args"] == {"statement_cache_size": 0}
    assert "connect_args" not in direct


def test_redact_hides_password() -> None:
    shown = redact_url("postgresql+asyncpg://dev_user:SuperSecret@host.example.com/db")
    assert "SuperSecret" not in shown
    assert "dev_user" in shown


@pytest.mark.parametrize("uri_host", ["your-cluster.mongodb.net"])
def test_atlas_srv_url_with_encoded_password_parses_offline(uri_host: str) -> None:
    # parse_uri on an SRV URI would need DNS; validate the non-DNS parts with a seed-list URI instead.
    uri = f"mongodb://dev_user:{quote(SPECIAL, safe='')}@shard-00-00.{uri_host}:27017/?tls=true&authSource=admin"
    parsed = parse_uri(uri)
    assert parsed["username"] == "dev_user"
    assert parsed["password"] == SPECIAL
    assert parsed["options"]["tls"] is True


def test_dnspython_is_installed_for_srv_urls() -> None:
    import dns.resolver  # noqa: F401
