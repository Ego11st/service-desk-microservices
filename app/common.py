import os
import asyncio
from pathlib import Path

import psycopg
from psycopg.rows import dict_row
import nats

STREAM = "TICKETS"
SUBJECT = "tickets.created"


def db_host():
    path = Path(os.getenv("DB_HOST_FILE", "/runtime/db-host"))
    return path.read_text().strip() if path.exists() else os.getenv("DB_HOST", "db")


def db():
    return psycopg.connect(
        host=db_host(), port=int(os.getenv("DB_PORT", "5432")),
        dbname=os.getenv("DB_NAME", "desk"), user=os.getenv("DB_USER", "app"),
        password=os.environ["DB_PASSWORD"], connect_timeout=3,
        options="-c statement_timeout=5000", row_factory=dict_row,
    )


async def broker():
    return await asyncio.wait_for(nats.connect(
        servers=os.getenv("NATS_SERVERS", "nats://nats1:4222,nats://nats2:4222,nats://nats3:4222").split(","),
        token=os.environ["NATS_TOKEN"], connect_timeout=2,
        reconnect_time_wait=1, max_reconnect_attempts=-1,
        name=os.getenv("SERVICE_NAME", "desk"),
    ), timeout=8)


def json_safe(value):
    import json
    return json.loads(json.dumps(value, default=str))
