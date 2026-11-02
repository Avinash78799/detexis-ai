"""Recoverable processing: the database is the source of pending events."""
from datetime import datetime, timedelta, timezone
from statistics import mean, pstdev

from rq import Queue
from sqlalchemy import select, literal, bindparam

from detexis_shield.features import extract_features
from .db import SessionLocal
from .models import Alert, Event, HourBucket, Incident, Site, IncidentAction
from .redis_store import get_redis
from .rules import LOGIN_PATHS, evaluate

WINDOW = """
redis.call('ZADD', KEYS[1], 'NX', ARGV[1], ARGV[2])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', ARGV[1] - 60)
redis.call('EXPIRE', KEYS[1], 120)
return redis.call('ZCOUNT', KEYS[1], ARGV[1] - 60, ARGV[1])
"""
SEVERITY = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def utc(value):
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


def enqueue_batch(site_id, event_ids, redis=None):
    return Queue("shield", connection=redis if redis is not None else get_redis()).enqueue(
        "app.worker.process_batch", site_id, event_ids, job_timeout=120, result_ttl=0, failure_ttl=86400)


def baseline_threshold(db, site, hour):
    if utc(site.created_at) > hour - timedelta(days=7):
        return None
    history = {utc(row.hour): row.count for row in db.scalars(select(HourBucket).where(
        HourBucket.site_id == site.id, HourBucket.hour >= hour - timedelta(days=7), HourBucket.hour < hour))}
    # Compare with the same UTC hour on the previous seven days, not unrelated hours.
    expected = [hour - timedelta(days=day) for day in range(1, 8)]
    if any(previous not in history for previous in expected):
        return None  # Missing telemetry is not evidence of zero normal traffic.
    samples = [history[previous] for previous in expected]
    return max(100, mean(samples) + 3 * pstdev(samples))


def save_event_results(db, updates):
    if not updates:
        return
    events = Event.__table__
    site = bindparam("batch_site_id", type_=events.c.site_id.type)
    if db.bind.dialect.name == "postgresql":
        site = select(site).offset(0).scalar_subquery()
    statement = events.update().where(events.c.site_id == site,
        events.c.event_id == bindparam("batch_event_id")).values(
            features=bindparam("result_features"), findings=bindparam("result_findings"),
            processed_at=bindparam("result_processed_at"))
    # Keep event writes in the same transaction as incident and baseline changes.
    # A core executemany avoids ORM literal-site UPDATEs picking a broad index
    # for every event in a newly growing tenant (see PROCESSING-LATENCY.md).
    db.execute(statement, updates)


def process_batch(site_id, event_ids, redis=None):
    redis = redis if redis is not None else get_redis()
    with SessionLocal() as db:
        # FOR NO KEY UPDATE serializes workers without blocking the KEY SHARE
        # lock taken by new event inserts' site foreign-key checks. The worker
        # never changes the site's key. SQLAlchemy calls this key_share=True.
        site = db.scalar(select(Site).where(Site.id == site_id).with_for_update(key_share=True))
        if site is None:
            return 0
        # New sites can grow faster than PostgreSQL's column statistics refresh.
        # A scalar init-plan uses average site selectivity instead of a stale
        # "one row" estimate that scanned the site's whole history for each job.
        identity = (select(literal(site_id)).offset(0).scalar_subquery()
                    if db.bind.dialect.name == "postgresql" else site_id)
        rows = db.scalars(select(Event).where(Event.site_id == identity, Event.event_id.in_(event_ids),
                                              Event.processed_at.is_(None)).order_by(Event.received_at)).all()
        # Pipeline Redis round trips while retaining event order and atomic Lua windows.
        pipeline = redis.pipeline(transaction=False)
        login_events = []
        for event in rows:
            stamp = utc(event.received_at)
            key = f"dxs:window:{{{site_id}}}:{event.ip_hash}"
            pipeline.eval(WINDOW, 1, key, stamp.timestamp(), event.event_id)
            login = event.path.lower().rstrip("/") in LOGIN_PATHS and event.status in {401, 403}
            login_events.append(login)
            if login:
                pipeline.eval(WINDOW, 1, key + ":login", stamp.timestamp(), event.event_id)
        counts = iter(pipeline.execute())
        buckets, thresholds, incidents, alerted = {}, {}, {}, set()
        updates = []
        for event, login in zip(rows, login_events):
            stamp = utc(event.received_at)
            count = next(counts)
            failed = next(counts) if login else 0
            settings = site.settings or {}
            hits = [f.json() for f in evaluate(event.path, event.query_redacted, event.ua, event.status,
                honeytokens=site.honeytokens, request_count=count, failed_logins=failed,
                login_threshold=max(3, int(settings.get("login_threshold", 10))),
                flood_threshold=max(20, int(settings.get("flood_threshold", 300))))]
            features = extract_features(event.path, event.query_redacted)  # Never trust client features.
            hour = stamp.replace(minute=0, second=0, microsecond=0)
            if hour not in buckets:
                # Persist a prior hour before using it as baseline history.
                if buckets:
                    db.flush()
                bucket = db.get(HourBucket, (site_id, hour))
                if bucket is None:
                    bucket = HourBucket(site_id=site_id, hour=hour, count=0)
                    db.add(bucket)
                buckets[hour] = bucket
                thresholds[hour] = baseline_threshold(db, site, hour)
            bucket = buckets[hour]
            bucket.count += 1
            threshold = thresholds[hour]
            if threshold is not None and bucket.count > threshold:
                hits.append({"rule_id": "volume_anomaly", "severity": "medium", "cwe": "CWE-400",
                             "owasp": "A06:2025", "reason": "Current hour exceeds the seven-day same-hour mean + 3σ"})
            # ML failures fall back to the existing rule findings.
            from .ml_runtime import classify
            prediction = classify(features)
            if prediction is not None:
                features = {**features, "ml": prediction}
                if prediction["alert"]:
                    hits.append({"rule_id": "ml_request", "severity": "medium", "cwe": "CWE-20",
                                 "owasp": "A05:2025", "reason": "Classifier probability exceeded the validated threshold"})
            if hits:
                group = int(stamp.timestamp()) // 300
                group_key = (event.ip_hash, group)
                if group_key not in incidents:
                    incidents[group_key] = db.scalar(select(Incident).where(Incident.site_id == site_id, Incident.ip_hash == event.ip_hash, Incident.bucket == group))
                incident = incidents[group_key]
                severity = max((h["severity"] for h in hits), key=SEVERITY.get)
                if incident is None:
                    incident = Incident(site_id=site_id, ip_hash=event.ip_hash, bucket=group,
                                        severity=severity, rules=[], correlations=[], event_count=0,
                                        first_seen=stamp, last_seen=stamp)
                    db.add(incident)
                    db.flush()
                    incidents[group_key] = incident
                incident.severity = max(incident.severity, severity, key=SEVERITY.get)
                if incident.status == "resolved":
                    incident.status = "open"
                    db.add(IncidentAction(incident_id=incident.id, previous_status="resolved", status="open",
                                          note="Reopened automatically when another matching event was processed"))
                existing = set(incident.rules)
                current = {h["rule_id"] for h in hits}
                correlations = set(incident.correlations)
                if existing & {"sensitive_path", "scanner_ua", "honeytoken"} and current & {"sqli_boolean", "sqli_union", "sqli_time", "xss", "command_injection"}:
                    correlations.add("recon_to_exploit")
                if "login_brute_force" in current:
                    correlations.add("repeated_login_failures")  # Credentials are not collected; stuffing is not proven.
                if "request_flood" in current:
                    correlations.add("flood")
                incident.rules = sorted(existing | current)
                incident.correlations = sorted(correlations)
                incident.last_seen = max(utc(incident.last_seen), stamp)
                incident.event_count += 1
                if SEVERITY[incident.severity] >= 2 and incident.id not in alerted:
                    if not db.scalar(select(Alert).where(Alert.incident_id == incident.id)):
                        db.add(Alert(site_id=site_id, incident_id=incident.id))
                    alerted.add(incident.id)
            updates.append({"batch_site_id": site_id, "batch_event_id": event.event_id,
                            "result_features": features, "result_findings": hits,
                            "result_processed_at": datetime.now(timezone.utc)})
        save_event_results(db, updates)
        db.commit()
        return len(rows)


def recover_pending(limit=1000, redis=None):
    redis = redis if redis is not None else get_redis()
    with SessionLocal() as db:
        rows = db.execute(select(Event.site_id, Event.event_id).where(Event.processed_at.is_(None))
                          .order_by(Event.received_at).limit(limit)).all()
    groups = {}
    for site_id, event_id in rows:
        groups.setdefault(site_id, []).append(event_id)
    for site_id, ids in groups.items():
        for start in range(0, len(ids), 100):
            enqueue_batch(site_id, ids[start:start + 100], redis)
    return len(rows)
