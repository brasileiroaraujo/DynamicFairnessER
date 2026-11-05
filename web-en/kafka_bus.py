"""Micro-batch transport: Kafka when a broker is reachable, in-memory otherwise.

The producer publishes one message per increment, paced by the time budget
(tau). The consumer receives them in order. Both sides expose the same tiny
interface so the worker does not care which transport is active.
"""
import json
import queue
import threading
import time

BOOTSTRAP = "localhost:9092"  # see kafka/docker-compose.yaml


def kafka_available(bootstrap=BOOTSTRAP, timeout=3.0):
    """Return (ok, detail). Never raises."""
    try:
        from confluent_kafka.admin import AdminClient
    except Exception as e:  # library missing
        return False, "confluent-kafka unavailable (%s)" % e
    try:
        md = AdminClient({"bootstrap.servers": bootstrap}).list_topics(timeout=timeout)
        return True, "broker %s (%d topics)" % (bootstrap, len(md.topics))
    except Exception as e:
        return False, "broker %s unreachable" % bootstrap


class MemoryBus:
    name = "memory"

    def __init__(self):
        self._q = queue.Queue()

    def send(self, payload):
        self._q.put(json.dumps(payload))

    def poll(self, timeout):
        try:
            return json.loads(self._q.get(timeout=timeout))
        except queue.Empty:
            return None

    def close(self):
        pass


class KafkaBus:
    name = "kafka"

    def __init__(self, topic, bootstrap=BOOTSTRAP):
        from confluent_kafka import Producer, Consumer
        from confluent_kafka.admin import AdminClient, NewTopic
        self.topic = topic
        self.bootstrap = bootstrap
        admin = AdminClient({"bootstrap.servers": bootstrap})
        for fut in admin.create_topics([NewTopic(topic, num_partitions=1, replication_factor=1)]).values():
            try:
                fut.result(timeout=10)
            except Exception:
                pass  # already exists / auto-created
        self._producer = Producer({"bootstrap.servers": bootstrap})
        self._consumer = Consumer({
            "bootstrap.servers": bootstrap,
            "group.id": topic + "-consumer",
            "auto.offset.reset": "earliest",
            "enable.auto.commit": True,
        })
        self._consumer.subscribe([topic])
        self._admin = admin

    def send(self, payload):
        self._producer.produce(self.topic, json.dumps(payload).encode("utf-8"))
        self._producer.flush(10)

    def poll(self, timeout):
        msg = self._consumer.poll(timeout)
        if msg is None or msg.error():
            return None
        return json.loads(msg.value().decode("utf-8"))

    def close(self):
        try:
            self._consumer.close()
        except Exception:
            pass
        try:
            self._admin.delete_topics([self.topic])
        except Exception:
            pass


def open_bus(run_id, prefer_kafka=True):
    """Return (bus, note)."""
    if prefer_kafka:
        ok, detail = kafka_available()
        if ok:
            try:
                return KafkaBus("xtreats-" + run_id), detail
            except Exception as e:
                return MemoryBus(), "Kafka failed (%s); using in-memory queue" % e
        return MemoryBus(), detail + "; using in-memory queue"
    return MemoryBus(), "in-memory queue"


class Producer(threading.Thread):
    """Publishes micro-batches paced by tau seconds (a real clock, not a sleep after processing)."""

    def __init__(self, bus, batches, tau, stop_event):
        super().__init__(daemon=True)
        self.bus, self.batches, self.tau, self.stop_event = bus, batches, tau, stop_event

    def run(self):
        start = time.time()
        for i, batch in enumerate(self.batches):
            due = start + i * self.tau
            while not self.stop_event.is_set() and time.time() < due:
                time.sleep(min(0.2, max(0.0, due - time.time())))
            if self.stop_event.is_set():
                return
            batch = dict(batch, index=i + 1, sent_at=time.time())
            self.bus.send(batch)
        self.bus.send({"eof": True, "sent_at": time.time()})
