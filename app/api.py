import asyncio
import contextlib
import json
import logging
import os
import uuid
from contextlib import asynccontextmanager

import psycopg
import redis
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Literal

from common import db, db_host, broker, json_safe, STREAM, SUBJECT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("desk-api")
cache = redis.Redis(host=os.getenv("REDIS_HOST", "redis"), port=int(os.getenv("REDIS_PORT", "6379")),
                    password=os.environ["REDIS_PASSWORD"], decode_responses=True,
                    socket_connect_timeout=2, socket_timeout=2)


def next_events():
    with db() as conn:
        return conn.execute("SELECT id, payload FROM outbox WHERE published_at IS NULL ORDER BY created_at LIMIT 20").fetchall()


def mark_published(event_id):
    with db() as conn:
        conn.execute("UPDATE outbox SET published_at=now() WHERE id=%s", (event_id,))


async def publisher():
    # The SQL transaction commits before publication. A crash before marking the
    # outbox row may resend an event; the consumer deduplicates it by event ID.
    from nats.js.api import StreamConfig, StorageType
    while True:
        nc = None
        try:
            nc = await broker()
            js = nc.jetstream(timeout=4)
            try:
                await js.stream_info(STREAM)
            except Exception:
                await js.add_stream(config=StreamConfig(name=STREAM, subjects=[SUBJECT],
                    storage=StorageType.FILE, num_replicas=int(os.getenv("NATS_REPLICAS", "3")),
                    max_age=86400))
            while True:
                for event in await asyncio.to_thread(next_events):
                    await js.publish(SUBJECT, json.dumps(event["payload"]).encode(),
                                     headers={"Nats-Msg-Id": str(event["id"])})
                    await asyncio.to_thread(mark_published, event["id"])
                    log.info("published event=%s", event["id"])
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            log.warning("outbox retry: %s", str(exc))
            await asyncio.sleep(2)
        finally:
            if nc is not None:
                await nc.close()


@asynccontextmanager
async def lifespan(app):
    task = asyncio.create_task(publisher())
    yield
    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task


app = FastAPI(title="Service Desk API", version="1.0", lifespan=lifespan)


@app.exception_handler(psycopg.Error)
async def database_error(request, exc):
    log.warning("database unavailable: %s", exc)
    return JSONResponse(status_code=503, content={"detail": "Database unavailable"})


class TicketInput(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    status: Literal["open", "closed"] = "open"


def invalidate():
    try:
        cache.incr("tickets:version")
    except redis.RedisError:
        pass


@app.get("/api/hello")
def hello():
    return {"message": "Hello from the ticket microservice"}


@app.get("/api/live")
def live():
    return {"status": "alive"}


@app.get("/api/tickets")
def tickets(response: Response):
    # Versioned keys avoid a stale writer repopulating the active cache key
    # after a concurrent mutation. Cache errors fall back to PostgreSQL.
    version = "0"
    try:
        version = cache.get("tickets:version") or "0"
        cached = cache.get("tickets:list:" + version)
        if cached is not None:
            response.headers["X-Cache"] = "HIT"
            return json.loads(cached)
    except redis.RedisError:
        pass
    with db() as conn:
        rows = json_safe(conn.execute("SELECT id,title,status,created_at FROM tickets ORDER BY id DESC").fetchall())
    try:
        cache.setex("tickets:list:" + version, 30, json.dumps(rows))
        response.headers["X-Cache"] = "MISS"
    except redis.RedisError:
        response.headers["X-Cache"] = "BYPASS"
    return rows


@app.post("/api/tickets", status_code=201)
def create_ticket(body: TicketInput):
    title = body.title.strip()
    if not title:
        raise HTTPException(422, "Title must contain text")
    event_id = str(uuid.uuid4())
    with db() as conn:
        row = conn.execute("INSERT INTO tickets(title,status) VALUES (%s,%s) RETURNING id,title,status,created_at",
                           (title, body.status)).fetchone()
        payload = {"event_id": event_id, "ticket_id": row["id"], "title": title}
        conn.execute("INSERT INTO outbox(id,payload) VALUES (%s,%s::jsonb)", (event_id, json.dumps(payload)))
    invalidate()
    return json_safe(row)


@app.put("/api/tickets/{ticket_id}")
def update_ticket(ticket_id: int, body: TicketInput):
    title = body.title.strip()
    if not title:
        raise HTTPException(422, "Title must contain text")
    with db() as conn:
        row = conn.execute("UPDATE tickets SET title=%s,status=%s WHERE id=%s RETURNING id,title,status,created_at",
                           (title,body.status,ticket_id)).fetchone()
    if row is None:
        raise HTTPException(404, "Ticket not found")
    invalidate()
    return json_safe(row)


@app.delete("/api/tickets/{ticket_id}", status_code=204)
def delete_ticket(ticket_id: int):
    with db() as conn:
        row = conn.execute("DELETE FROM tickets WHERE id=%s RETURNING id", (ticket_id,)).fetchone()
    if row is None:
        raise HTTPException(404, "Ticket not found")
    invalidate()
    return Response(status_code=204)


@app.get("/api/notifications")
def notifications():
    with db() as conn:
        return json_safe(conn.execute("SELECT id,event_id,ticket_id,message,created_at FROM notifications ORDER BY id DESC LIMIT 30").fetchall())


@app.get("/api/diagnostics")
async def diagnostics():
    result = {"database": {"host": db_host()}, "cache": {}, "broker": {}}
    try:
        def inspect_db():
            with db() as conn:
                meta = conn.execute("SELECT pg_is_in_recovery() AS standby, inet_server_addr()::text AS address").fetchone()
                counts = conn.execute("SELECT (SELECT count(*) FROM tickets) AS tickets, (SELECT count(*) FROM outbox WHERE published_at IS NULL) AS pending_events, (SELECT count(*) FROM notifications) AS notifications").fetchone()
                return {**meta, **counts, "status": "ok"}
        result["database"].update(await asyncio.to_thread(inspect_db))
    except Exception:
        result["database"]["status"] = "unavailable"
    try:
        await asyncio.to_thread(cache.ping)
        result["cache"] = {"status": "ok", "ttl_seconds": 30}
    except redis.RedisError:
        result["cache"] = {"status": "unavailable"}
    nc = None
    try:
        nc = await broker()
        js = nc.jetstream(timeout=3)
        info = await js.stream_info(STREAM)
        result["broker"] = {"status": "ok", "stream": STREAM,
            "replicas": info.config.num_replicas,
            "leader": info.cluster.leader if info.cluster else "standalone",
            "messages": info.state.messages,
            "replica_nodes": [{"name": r.name, "current": r.current, "offline": r.offline}
                              for r in (info.cluster.replicas or [])] if info.cluster else []}
    except Exception:
        result["broker"] = {"status": "unavailable"}
    finally:
        if nc:
            await nc.close()
    return result
