"""Transactional usage accounting. Token totals must originate with a provider response."""
import calendar, time, uuid, json, secrets
from datetime import datetime, timezone
from sqlalchemy import text
from open_webui.internal.db import engine

DEFAULT_TIERS = [("free", "Free", 100, 20, 0, None, {"mini": True, "standard": True, "pro": False}), ("plus", "Plus", 1000, None, 0, 499, {"mini": True, "standard": True, "pro": True, "code": True, "design": True}), ("pro", "Pro", 5000, None, 1000, 999, {"mini": True, "standard": True, "pro": True, "agents": True, "api_pass": True})]

def now(): return int(time.time())
def month_key(ts=None):
    d=datetime.fromtimestamp(ts or now(), timezone.utc); return f"{d.year}-{d.month:02d}"
def next_reset(ts=None):
    d=datetime.fromtimestamp(ts or now(), timezone.utc); y,m=(d.year+1,1) if d.month==12 else (d.year,d.month+1); return calendar.timegm(datetime(y,m,1,tzinfo=timezone.utc).timetuple())
def month_start(ts=None):
    d=datetime.fromtimestamp(ts or now(), timezone.utc)
    return calendar.timegm(datetime(d.year, d.month, 1, tzinfo=timezone.utc).timetuple())

def bootstrap():
    with engine.begin() as c:
        for ident, name, credits, daily, agents, price, rules in DEFAULT_TIERS:
            c.execute(text("INSERT INTO subscription_tier (id,name,monthly_credits,daily_limit,agent_credits,price_cents,currency,planned_price,features,model_rules,active,created_at,updated_at) SELECT :id,:name,:credits,:daily,:agents,:price,'EUR',1,:features,:rules,1,:n,:n WHERE NOT EXISTS (SELECT 1 FROM subscription_tier WHERE id=:id)"), {"id":ident,"name":name,"credits":credits,"daily":daily,"agents":agents,"price":price,"features":"{}","rules":__import__('json').dumps(rules),"n":now()})
        for name, rate, fair in (("ThatAI Mini",0,True),("ThatAI Standard",1,False),("ThatAI Pro",4,False)):
            c.execute(text("INSERT INTO model_credit_rate (model_id,credits_per_50k,fair_use,enabled,stream_usage_supported,updated_at) SELECT id,:r,:f,1,0,:n FROM model WHERE name=:name AND NOT EXISTS (SELECT 1 FROM model_credit_rate WHERE model_id=model.id)"), {"name":name,"r":rate,"f":fair,"n":now()})

def ensure_personal_invite(c, user_id, max_uses=3):
    """Return the owner's durable personal code; safe to call at signup and reads."""
    existing = c.execute(text("SELECT * FROM invite_code WHERE creator_id=:u AND is_referral=1 ORDER BY created_at LIMIT 1"), {"u": user_id}).mappings().first()
    if existing: return dict(existing)
    for _ in range(12):
        code = "THATAI-" + secrets.token_hex(5).upper()
        try:
            c.execute(text("INSERT INTO invite_code (id,code,creator_id,max_uses,uses,revoked,is_referral,created_at) VALUES (:id,:code,:u,:max,0,0,1,:n)"), {"id":str(uuid.uuid4()), "code":code, "u":user_id, "max":max_uses, "n":now()})
            return dict(c.execute(text("SELECT * FROM invite_code WHERE code=:code"), {"code":code}).mappings().one())
        except Exception:
            existing = c.execute(text("SELECT * FROM invite_code WHERE creator_id=:u AND is_referral=1"), {"u":user_id}).mappings().first()
            if existing: return dict(existing)
    raise RuntimeError("Unable to allocate a personal invitation code")

def release_invitation_for_deleted_user(user_id):
    """Return a consumed invitation slot when its registered account is deleted.

    The redemption is removed in the same transaction as the counter update, so
    repeated cleanup is harmless and cannot decrement the counter twice.
    """
    with engine.begin() as c:
        redemption=c.execute(text("SELECT invite_id FROM invite_redemption WHERE user_id=:u"), {"u":user_id}).mappings().first()
        if not redemption:
            return False
        c.execute(text("DELETE FROM invite_redemption WHERE user_id=:u"), {"u":user_id})
        c.execute(text("UPDATE invite_code SET uses=CASE WHEN uses>0 THEN uses-1 ELSE 0 END WHERE id=:id"), {"id":redemption['invite_id']})
        return True

def model_allowed(sub, model_id):
    rules=json.loads(sub['model_rules'] or '{}') if isinstance(sub.get('model_rules'), str) else (sub.get('model_rules') or {})
    return bool(rules.get(model_id, rules.get(model_id.replace('ThatAI ', '').lower(), False)))

def active_subscription(c, user_id, timestamp=None):
    timestamp=timestamp or now()
    return c.execute(text("SELECT s.*, t.name,t.monthly_credits,t.daily_limit,t.model_rules FROM user_subscription s JOIN subscription_tier t ON t.id=s.tier_id WHERE s.user_id=:u AND s.access_status='active' AND s.starts_at<=:n AND (s.ends_at IS NULL OR s.ends_at>:n) ORDER BY s.starts_at DESC LIMIT 1"), {"u":user_id,"n":timestamp}).mappings().first()

def promotional_start(c, user_id, timestamp=None):
    """Append promotions after all already scheduled entitlement, never overlap it."""
    timestamp = timestamp or now()
    latest = c.execute(text("SELECT MAX(ends_at) FROM user_subscription WHERE user_id=:u AND ends_at>:n"), {"u":user_id,"n":timestamp}).scalar()
    return max(timestamp, int(latest)) if latest else timestamp

def ensure_entitlement(c, user_id):
    # Lifecycle transitions are idempotent and transactionally applied on every
    # entitlement check. This makes restarts safe without a background worker.
    timestamp=now()
    c.execute(text("UPDATE user_subscription SET status='expired',access_status='expired',updated_at=:n WHERE user_id=:u AND ends_at IS NOT NULL AND ends_at<=:n AND access_status IN ('active','scheduled')"), {"u":user_id,"n":timestamp})
    c.execute(text("UPDATE user_subscription SET status=CASE WHEN status='scheduled' THEN 'active' ELSE status END,access_status='active',updated_at=:n WHERE user_id=:u AND starts_at<=:n AND access_status='scheduled' AND (ends_at IS NULL OR ends_at>:n)"), {"u":user_id,"n":timestamp})
    sub=active_subscription(c,user_id)
    if sub: return sub
    tier=c.execute(text("SELECT * FROM subscription_tier WHERE id='free' AND active=1")).mappings().first()
    sid=str(uuid.uuid4()); n=now()
    c.execute(text("INSERT INTO user_subscription (id,user_id,tier_id,status,access_status,billing_status,starts_at,ends_at,created_at,updated_at) VALUES (:id,:u,'free','free','active','none',:n,NULL,:n,:n)"),{"id":sid,"u":user_id,"n":n})
    return {**dict(tier), "id":sid, "tier_id":"free"}

def balance(c,user_id,bucket):
    # Monthly credits intentionally do not roll over. Bonus and agent balances
    # are persistent until explicitly adjusted or spent.
    query="SELECT COALESCE(SUM(amount),0) FROM credit_ledger WHERE user_id=:u AND bucket=:b"
    params={"u":user_id,"b":bucket}
    if bucket == "monthly":
        query += " AND created_at>=:period_start"
        params["period_start"]=month_start()
    return float(c.execute(text(query),params).scalar() or 0)

def grant_monthly(c,user_id,sub):
    key=month_key(); marker=f"monthly:{key}:{sub['tier_id']}"
    exists=c.execute(text("SELECT 1 FROM credit_ledger WHERE user_id=:u AND request_id=:r"),{"u":user_id,"r":marker}).first()
    if not exists:
        before=balance(c,user_id,"monthly"); amount=float(sub["monthly_credits"])
        c.execute(text("INSERT INTO credit_ledger (id,user_id,kind,bucket,amount,balance_after,request_id,metadata,created_at) VALUES (:id,:u,'monthly_grant','monthly',:a,:b,:r,:m,:n)"),{"id":str(uuid.uuid4()),"u":user_id,"a":amount,"b":before+amount,"r":marker,"m":'{"period":"'+key+'"}',"n":now()})

def begin_request(user_id, model_id, request_id):
    """Authorize a metered model and acquire a short-lived per-user spend lock."""
    bootstrap(); timestamp=now()
    with engine.begin() as c:
        rate=c.execute(text("SELECT * FROM model_credit_rate WHERE model_id=:m AND enabled=1"), {"m":model_id}).mappings().first()
        # A model cannot silently escape the product limits just because an
        # administrator has not configured it yet.
        if not rate: raise ValueError("This model has not been configured for usage accounting")
        sub=ensure_entitlement(c,user_id); grant_monthly(c,user_id,sub)
        if not model_allowed(sub, model_id): raise ValueError("Your subscription does not include this model")
        if not rate['fair_use'] and balance(c,user_id,'monthly') + balance(c,user_id,'bonus') <= 0: raise ValueError("Monthly credit limit reached")
        if sub['daily_limit'] is not None:
            spent=float(c.execute(text("SELECT COALESCE(SUM(credits),0) FROM usage_record WHERE user_id=:u AND created_at>=:d"),{'u':user_id,'d':timestamp-(timestamp%86400)}).scalar() or 0)
            if spent >= float(sub['daily_limit']): raise ValueError("Daily credit limit reached")
        c.execute(text("DELETE FROM credit_reservation WHERE expires_at<=:n"), {'n':timestamp})
        try:
            c.execute(text("INSERT INTO credit_reservation (user_id,request_id,expires_at) VALUES (:u,:r,:e)"), {'u':user_id,'r':request_id,'e':timestamp+900})
        except Exception as exc:
            raise ValueError("A metered request is already in progress") from exc
        return dict(rate)

def release_request(user_id, request_id):
    with engine.begin() as c:
        c.execute(text("DELETE FROM credit_reservation WHERE user_id=:u AND request_id=:r"), {'u':user_id,'r':request_id})

async def verified_metered_stream(iterator, user_id, model_id, request_id):
    """Fail closed: buffer a metered stream until factual usage is charged.

    This deliberately trades streaming latency for correctness. A provider that
    does not emit final usage produces no assistant output and is marked as an
    unsupported metered stream instead of granting a free completion.
    """
    chunks = []
    async for chunk in iterator:
        chunks.append(chunk)
    wire = b"".join(chunk if isinstance(chunk, bytes) else str(chunk).encode() for chunk in chunks).decode("utf-8", errors="replace")
    provider_usage = None
    for line in wire.splitlines():
        candidate = line[5:].strip() if line.startswith("data:") else line.strip()
        if not candidate or candidate == "[DONE]":
            continue
        try:
            event = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(event, dict):
            if event.get("usage"):
                provider_usage = event["usage"]
            elif event.get("prompt_eval_count") is not None and event.get("eval_count") is not None:
                provider_usage = {"input_tokens": event["prompt_eval_count"], "output_tokens": event["eval_count"]}
    if not provider_usage:
        release_request(user_id, request_id)
        raise RuntimeError("Provider did not return final token usage; metered streaming is unsupported")
    charge(user_id, model_id, provider_usage.get("prompt_tokens", provider_usage.get("input_tokens")), provider_usage.get("completion_tokens", provider_usage.get("output_tokens")), request_id)
    for chunk in chunks:
        yield chunk

def dashboard(user_id):
    bootstrap()
    with engine.begin() as c:
        sub=ensure_entitlement(c,user_id); grant_monthly(c,user_id,sub)
        monthly=balance(c,user_id,"monthly"); bonus=balance(c,user_id,"bonus")
        rows=c.execute(text("SELECT model_id,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(credits) credits FROM usage_record WHERE user_id=:u GROUP BY model_id"),{"u":user_id}).mappings().all()
        daily=c.execute(text("SELECT date(created_at,'unixepoch') day,SUM(input_tokens+output_tokens) tokens,SUM(credits) credits FROM usage_record WHERE user_id=:u GROUP BY day ORDER BY day DESC LIMIT 30"),{"u":user_id}).mappings().all()
        ledger=c.execute(text("SELECT * FROM credit_ledger WHERE user_id=:u ORDER BY created_at DESC LIMIT 100"),{"u":user_id}).mappings().all()
        return {"tier":dict(sub),"monthly_remaining":monthly,"bonus_remaining":bonus,"monthly_total":float(sub['monthly_credits']),"consumed":max(0,float(sub['monthly_credits'])-monthly),"next_reset":next_reset(),"by_model":[dict(r) for r in rows],"daily":[dict(r) for r in daily],"transactions":[dict(r) for r in ledger]}

def charge(user_id, model_id, input_tokens, output_tokens, request_id):
    """Idempotent factual debit. SQLite BEGIN IMMEDIATE serializes competing spenders."""
    if input_tokens is None or output_tokens is None: raise ValueError("Provider did not return token usage; this accounting path is rejected")
    bootstrap(); n=now()
    with engine.connect() as c:
        if engine.dialect.name == "sqlite": c.exec_driver_sql("BEGIN IMMEDIATE")
        else: c.begin()
        try:
            sub=ensure_entitlement(c,user_id); grant_monthly(c,user_id,sub)
            if c.execute(text("SELECT 1 FROM usage_record WHERE request_id=:r"),{"r":request_id}).first():
                c.execute(text("DELETE FROM credit_reservation WHERE user_id=:u AND request_id=:r"), {'u':user_id,'r':request_id})
                c.commit(); return 0
            rate=c.execute(text("SELECT * FROM model_credit_rate WHERE model_id=:m AND enabled=1"),{"m":model_id}).mappings().first()
            if not rate: raise ValueError("This model has not been configured for usage accounting")
            if rate['fair_use']: credits=0.0
            else:
                input_rate=rate['input_credits_per_50k'] if 'input_credits_per_50k' in rate else None
                output_rate=rate['output_credits_per_50k'] if 'output_credits_per_50k' in rate else None
                credits=(int(input_tokens)*float(input_rate if input_rate is not None else rate['credits_per_50k']) + int(output_tokens)*float(output_rate if output_rate is not None else rate['credits_per_50k']))/50000.0
            if not model_allowed(sub, model_id): raise ValueError("Your subscription does not include this model")
            daily=sub['daily_limit']
            if daily is not None and credits:
                spent=float(c.execute(text("SELECT COALESCE(SUM(credits),0) FROM usage_record WHERE user_id=:u AND created_at>=:d"),{"u":user_id,"d":n-(n%86400)}).scalar() or 0)
                if spent+credits > float(daily): raise ValueError("Daily credit limit reached")
            available=balance(c,user_id,'monthly')+balance(c,user_id,'bonus')
            if credits > available + 1e-9: raise ValueError("Monthly credit limit reached")
            c.execute(text("INSERT INTO usage_record (id,user_id,model_id,input_tokens,output_tokens,credits,request_id,created_at) VALUES (:id,:u,:m,:i,:o,:cr,:r,:n)"),{"id":str(uuid.uuid4()),"u":user_id,"m":model_id,"i":input_tokens,"o":output_tokens,"cr":credits,"r":request_id,"n":n})
            remaining=credits
            for bucket in ('monthly','bonus'):
                b=balance(c,user_id,bucket); debit=min(b,remaining)
                if debit: c.execute(text("INSERT INTO credit_ledger (id,user_id,kind,bucket,amount,balance_after,request_id,model_id,input_tokens,output_tokens,created_at) VALUES (:id,:u,'usage',:b,:a,:after,:r,:m,:i,:o,:n)"),{"id":str(uuid.uuid4()),"u":user_id,"b":bucket,"a":-debit,"after":b-debit,"r":request_id+':'+bucket,"m":model_id,"i":input_tokens,"o":output_tokens,"n":n}); remaining-=debit
            c.execute(text("DELETE FROM credit_reservation WHERE user_id=:u AND request_id=:r"), {'u':user_id,'r':request_id})
            c.commit(); return credits
        except Exception:
            c.rollback()
            release_request(user_id, request_id)
            raise
