"""Run the audit using a disposable database and a read-only Mongo role."""

import csv
from datetime import UTC, datetime
from urllib.parse import urlencode, urlsplit, urlunsplit
from uuid import uuid4

from pymongo import MongoClient, monitoring

from app.jobs.rainfall_audit import main
from tests.integration.test_authenticated_workflow import _local_test_uri
from tests.test_rainfall_audit import write_inputs


class AuditCommands(monitoring.CommandListener):
    def __init__(self, database):
        self.database = database
        self.commands = []

    def started(self, event):
        if event.database_name == self.database and event.command_name != "saslContinue":
            self.commands.append((event.command_name, event.command))

    def succeeded(self, event):
        pass

    def failed(self, event):
        pass


def test_cli_reads_only_bounded_rainfall_and_writes_reports(tmp_path, monkeypatch, capsys):
    uri = _local_test_uri()
    key = uuid4().hex
    database_name = f"novayield_audit_test_{key}"
    username = f"audit_{key}"
    password = uuid4().hex
    commands = AuditCommands(database_name)
    import app.jobs.rainfall_audit as audit

    client_type = audit.AsyncMongoClient
    monkeypatch.setattr(
        audit,
        "AsyncMongoClient",
        lambda *args, **kwargs: client_type(*args, event_listeners=[commands], **kwargs),
    )
    with MongoClient(uri) as client:
        db = client[database_name]
        try:
            db.command(
                "createUser", username, pwd=password, roles=[{"role": "read", "db": db.name}]
            )
            db.supported_locations.insert_many(
                [
                    {
                        "location_key": "ejura",
                        "nasa_cell_key": "private-cell",
                        "coordinates": "hidden",
                    },
                    {"location_key": "outside", "nasa_cell_key": "out-of-scope"},
                ]
            )
            db.climate_daily.insert_many(
                [
                    {
                        "cell_key": "private-cell",
                        "day": datetime.fromisoformat(day).replace(tzinfo=UTC),
                        "rain_mm": rain,
                        "source_products": ["MERRA2", "undisclosed-source"],
                    }
                    for day, rain in (
                        ("2022-12-31", 100),
                        ("2024-02-29", 0),
                        ("2024-03-01", 2),
                        ("2024-03-02", None),
                        ("2025-01-01", 100),
                    )
                ]
            )
            parsed = urlsplit(uri)
            audit_uri = urlunsplit(
                (
                    parsed.scheme,
                    f"{username}:{password}@{parsed.netloc}",
                    "/",
                    urlencode({"authSource": db.name}),
                    "",
                )
            )
            monkeypatch.setenv("NOVAYIELD_AUDIT_MONGODB_URI", audit_uri)
            monkeypatch.setenv("NOVAYIELD_AUDIT_MONGODB_DATABASE", db.name)
            csv_path, manifest = write_inputs(
                tmp_path, "ejura,2024-02-29,0\nejura,2024-03-01,3\nejura,2024-03-02,5\n"
            )
            output_dir = tmp_path / "reports"
            assert (
                main(
                    [
                        "--imerg-csv",
                        str(csv_path),
                        "--manifest",
                        str(manifest),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
                == 0
            )
            assert [name for name, _ in commands.commands] == ["find", "find"]
            assert commands.commands[0][1]["projection"] == {
                "_id": 0,
                "location_key": 1,
                "nasa_cell_key": 1,
            }
            assert commands.commands[1][1]["filter"]["day"] == {
                "$gte": datetime(2023, 1, 1, tzinfo=UTC),
                "$lte": datetime(2024, 12, 31, tzinfo=UTC),
            }
            with (output_dir / "rainfall-audit.csv").open(encoding="utf-8") as stream:
                rows = list(csv.DictReader(stream))
            assert len(rows) == 84
            assert {row["location_key"] for row in rows} == {"ejura", "anyinasu", "kintampo"}
            assert (
                sum(int(row["paired_days"]) for row in rows if row["window_type"] == "month") == 2
            )
            march = next(row for row in rows if row["start_date"] == "2024-03-01")
            assert march["mean_daily_difference_mm"] == "1.0"
            report = (output_dir / "rainfall-audit.md").read_text(encoding="utf-8")
            assert "FIXTURE" in report and "MERRA2" in report
            visible = report + capsys.readouterr().out
            for private in (password, "coordinates", "private-cell", "undisclosed-source"):
                assert private not in visible
        finally:
            db.command("dropUser", username)
            client.drop_database(database_name)
