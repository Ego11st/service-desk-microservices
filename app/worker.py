import asyncio
import json
import logging

from nats.js.api import ConsumerConfig, AckPolicy
from common import db, broker, STREAM, SUBJECT

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("desk-worker")


def consume(event):
    with db() as conn:
        inserted = conn.execute("INSERT INTO processed_events(event_id) VALUES (%s) ON CONFLICT DO NOTHING RETURNING event_id",
                                (event["event_id"],)).fetchone()
        if inserted:
            conn.execute("INSERT INTO notifications(event_id,ticket_id,message) VALUES (%s,%s,%s)",
                         (event["event_id"], event["ticket_id"], "Заявка принята в обработку: " + event["title"]))
    # Both writes commit before the broker ACK. A repeated delivery is harmless.


async def main():
    while True:
        nc = None
        try:
            nc = await broker()
            js = nc.jetstream(timeout=4)
            await js.stream_info(STREAM)
            sub = await js.pull_subscribe(SUBJECT, durable="notifications-worker", stream=STREAM,
                config=ConsumerConfig(durable_name="notifications-worker", ack_policy=AckPolicy.EXPLICIT,
                                      ack_wait=30, max_ack_pending=20))
            while True:
                try:
                    messages = await sub.fetch(10, timeout=2)
                except asyncio.TimeoutError:
                    continue
                for msg in messages:
                    event = json.loads(msg.data)
                    await asyncio.to_thread(consume, event)
                    await msg.ack_sync(timeout=3)
                    log.info("processed event=%s ticket=%s", event["event_id"], event["ticket_id"])
        except Exception as exc:
            log.warning("worker retry: %s", exc)
            await asyncio.sleep(2)
        finally:
            if nc:
                await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
