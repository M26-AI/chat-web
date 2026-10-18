"""Usage, subscription, coupon and closed-beta invitation API."""
import secrets, time, uuid
import json
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import text
from open_webui.internal.db import engine
from open_webui.utils.auth import get_admin_user, get_verified_user
from open_webui.services import usage
from open_webui.models.groups import Groups

router=APIRouter()
def fail(message): raise HTTPException(400,detail=message)
def n(): return int(time.time())

class TierForm(BaseModel):
    id: str; name: str; monthly_credits: float = Field(ge=0); daily_limit: Optional[float] = Field(None,ge=0); agent_credits: float=0; price_cents: Optional[int]=None; currency: str='EUR'; planned_price: bool=True; features: dict={}; model_rules: dict={}; active: bool=True
class AssignForm(BaseModel): user_id:str; tier_id:str; starts_at:Optional[int]=None; ends_at:Optional[int]=None; promotional:bool=False
class AdjustmentForm(BaseModel): user_id:str; amount:float; bucket:str='bonus'; reason:str
class RateForm(BaseModel): credits_per_50k:float=Field(ge=0); input_credits_per_50k:Optional[float]=Field(None,ge=0); output_credits_per_50k:Optional[float]=Field(None,ge=0); fair_use:bool=False; enabled:bool=True; stream_usage_supported:bool=False
class CouponForm(BaseModel): code:str; tier_id:Optional[str]=None; free_days:int=0; percent_off:Optional[float]=None; amount_off_cents:Optional[int]=None; bonus_credits:float=0; starts_at:Optional[int]=None; expires_at:Optional[int]=None; max_redemptions:Optional[int]=None; max_per_user:int=1; eligible_groups:list[str]=[]; combinable:bool=False; apply_after_current:bool=True; active:bool=True
class CodeForm(BaseModel): code:str
class InviteForm(BaseModel): max_uses:int=1; creator_id:Optional[str]=None
class SettingForm(BaseModel): value: object
class InviteUpdateForm(BaseModel): max_uses:Optional[int]=Field(None,ge=0); revoked:Optional[bool]=None; regenerate:bool=False

@router.get('/dashboard')
def dashboard(user=Depends(get_verified_user)): return usage.dashboard(user.id)

@router.get('/invites/preview')
def preview_invite(code: str):
    """Public, non-consuming check used by the pre-registration invite step."""
    with engine.begin() as c:
        invite=c.execute(text("SELECT i.code,i.max_uses,i.uses,i.revoked,u.name creator_name FROM invite_code i LEFT JOIN user u ON u.id=i.creator_id WHERE i.code=:code"), {'code':code.strip().upper()}).mappings().first()
        if not invite or invite['revoked']:
            raise HTTPException(404, detail='Invitation code is invalid')
        remaining=max(0, int(invite['max_uses'])-int(invite['uses']))
        return {'valid':remaining>0, 'creator_name':invite['creator_name'] or 'ThatAI Chat', 'remaining':remaining, 'max_uses':invite['max_uses'], 'uses':invite['uses']}

@router.get('/tiers')
def public_tiers(user=Depends(get_verified_user)):
    usage.bootstrap()
    with engine.begin() as c: return [dict(x) for x in c.execute(text("SELECT id,name,monthly_credits,daily_limit,agent_credits,price_cents,currency,planned_price,features,model_rules FROM subscription_tier WHERE active=1 ORDER BY monthly_credits")).mappings()]

@router.get('/admin/tiers')
def list_tiers(user=Depends(get_admin_user)):
    with engine.begin() as c: return [dict(x) for x in c.execute(text('SELECT * FROM subscription_tier ORDER BY monthly_credits')).mappings()]
@router.get('/admin/model-candidates')
async def model_candidates(request: Request, user=Depends(get_admin_user)):
    """Actual gateway IDs for configuring credit rates; names are display-only."""
    with engine.begin() as c:
        rates={r['model_id']:dict(r) for r in c.execute(text('SELECT * FROM model_credit_rate')).mappings()}
    return [{"id": model_id, "name": model.get("name", model_id), "rate":rates.get(model_id)} for model_id, model in request.app.state.MODELS.items()]
@router.put('/admin/tiers/{tier_id}')
def save_tier(tier_id:str, form:TierForm, user=Depends(get_admin_user)):
    if tier_id != form.id: fail('Tier id cannot be changed')
    with engine.begin() as c:
        exists=c.execute(text('SELECT 1 FROM subscription_tier WHERE id=:id'),{'id':tier_id}).first()
        params={**form.model_dump(), 'features':json.dumps(form.features), 'model_rules':json.dumps(form.model_rules), 'n':n()}
        if exists: c.execute(text("UPDATE subscription_tier SET name=:name,monthly_credits=:monthly_credits,daily_limit=:daily_limit,agent_credits=:agent_credits,price_cents=:price_cents,currency=:currency,planned_price=:planned_price,features=:features,model_rules=:model_rules,active=:active,updated_at=:n WHERE id=:id"),params)
        else: c.execute(text("INSERT INTO subscription_tier (id,name,monthly_credits,daily_limit,agent_credits,price_cents,currency,planned_price,features,model_rules,active,created_at,updated_at) VALUES (:id,:name,:monthly_credits,:daily_limit,:agent_credits,:price_cents,:currency,:planned_price,:features,:model_rules,:active,:n,:n)"),params)
    return {'ok':True}
@router.post('/admin/assign')
def assign(form:AssignForm,user=Depends(get_admin_user)):
    with engine.begin() as c:
        if not c.execute(text('SELECT 1 FROM subscription_tier WHERE id=:id'),{'id':form.tier_id}).first(): fail('Unknown tier')
        start=form.starts_at or n(); sid=str(uuid.uuid4()); status='promotional' if form.promotional else ('scheduled' if start>n() else 'active')
        c.execute(text("INSERT INTO user_subscription (id,user_id,tier_id,status,access_status,billing_status,starts_at,ends_at,created_at,updated_at) VALUES (:id,:u,:t,:s,:a,'manual',:start,:end,:now,:now)"),{'id':sid,'u':form.user_id,'t':form.tier_id,'s':status,'a':'scheduled' if status=='scheduled' else 'active','start':start,'end':form.ends_at,'now':n()})
    return {'id':sid}
@router.post('/admin/adjustments')
def adjust(form:AdjustmentForm,user=Depends(get_admin_user)):
    if form.bucket not in ('monthly','bonus','agent'): fail('Invalid balance bucket')
    with engine.begin() as c:
        before=usage.balance(c,form.user_id,form.bucket); after=before+form.amount
        if after < 0: fail('Adjustment would make the balance negative')
        c.execute(text("INSERT INTO credit_ledger (id,user_id,kind,bucket,amount,balance_after,metadata,created_at) VALUES (:id,:u,'admin_adjustment',:b,:a,:after,:m,:n)"),{'id':str(uuid.uuid4()),'u':form.user_id,'b':form.bucket,'a':form.amount,'after':after,'m':'{"reason":"'+form.reason.replace('"','')+'"}','n':n()})
    return {'ok':True}
@router.put('/admin/rates/{model_id}')
def set_rate(model_id:str,form:RateForm,user=Depends(get_admin_user)):
    with engine.begin() as c: c.execute(text("INSERT INTO model_credit_rate (model_id,credits_per_50k,input_credits_per_50k,output_credits_per_50k,fair_use,enabled,stream_usage_supported,updated_at) VALUES (:m,:r,:i,:o,:f,:e,:s,:n) ON CONFLICT(model_id) DO UPDATE SET credits_per_50k=:r,input_credits_per_50k=:i,output_credits_per_50k=:o,fair_use=:f,enabled=:e,stream_usage_supported=:s,updated_at=:n"),{'m':model_id, 'r':form.credits_per_50k,'i':form.input_credits_per_50k,'o':form.output_credits_per_50k,'f':form.fair_use,'e':form.enabled,'s':form.stream_usage_supported,'n':n()})
    return {'ok':True}
@router.get('/admin/usage')
def platform_usage(user=Depends(get_admin_user)):
    with engine.begin() as c: return [dict(x) for x in c.execute(text("SELECT user_id,model_id,SUM(input_tokens) input_tokens,SUM(output_tokens) output_tokens,SUM(credits) credits FROM usage_record GROUP BY user_id,model_id ORDER BY credits DESC")).mappings()]
@router.get('/admin/overview')
def overview(user=Depends(get_admin_user)):
    with engine.begin() as c:
        return dict(c.execute(text("SELECT (SELECT COUNT(*) FROM user) users,(SELECT COUNT(*) FROM user WHERE last_active_at>=:week) active_users,(SELECT COALESCE(SUM(credits),0) FROM usage_record WHERE created_at>=:month) monthly_credits,(SELECT COALESCE(SUM(input_tokens+output_tokens),0) FROM usage_record WHERE created_at>=:month) tokens,(SELECT COUNT(*) FROM coupon WHERE active=1) active_coupons,(SELECT COUNT(*) FROM invite_redemption) successful_invitations"),{'week':n()-604800,'month':usage.month_start()}).mappings().one())
@router.get('/admin/users')
def admin_users(q:str='', user=Depends(get_admin_user)):
    with engine.begin() as c:
        return [dict(r) for r in c.execute(text("SELECT u.id,u.name,u.email,u.role,s.tier_id,s.ends_at,s.access_status FROM user u LEFT JOIN user_subscription s ON s.id=(SELECT id FROM user_subscription x WHERE x.user_id=u.id AND x.access_status='active' ORDER BY x.starts_at DESC LIMIT 1) WHERE lower(u.name) LIKE :q OR lower(u.email) LIKE :q ORDER BY u.created_at DESC LIMIT 100"),{'q':f'%{q.lower()}%'}).mappings()]
@router.get('/admin/settings/{key}')
def get_setting(key:str,user=Depends(get_admin_user)):
    with engine.begin() as c:
        value=c.execute(text('SELECT value FROM usage_setting WHERE key=:k'),{'k':key}).scalar()
    return {'key':key,'value':json.loads(value) if value else None}
@router.put('/admin/settings/{key}')
def put_setting(key:str,form:SettingForm,user=Depends(get_admin_user)):
    # Supports documented keys such as fair_use, monthly_reset_policy,
    # referral_rewards_enabled and referral_reward_days without code changes.
    if key not in {'fair_use','monthly_reset_policy','referral_rewards_enabled','referral_reward_days','invitation_only','usage_warning_thresholds'}: fail('Unsupported setting')
    with engine.begin() as c: c.execute(text("INSERT INTO usage_setting (key,value,updated_at) VALUES (:k,:v,:n) ON CONFLICT(key) DO UPDATE SET value=:v,updated_at=:n"),{'k':key,'v':json.dumps(form.value),'n':n()})
    return {'key':key,'value':form.value}

@router.post('/admin/coupons')
def create_coupon(form:CouponForm,user=Depends(get_admin_user)):
    code=form.code.strip().upper()
    if not code or form.free_days < 0 or form.max_per_user < 1 or (form.starts_at and form.expires_at and form.expires_at <= form.starts_at): fail('Invalid coupon')
    with engine.begin() as c:
        if form.tier_id and not c.execute(text('SELECT 1 FROM subscription_tier WHERE id=:id'), {'id':form.tier_id}).first(): fail('Unknown subscription tier')
        try: c.execute(text("INSERT INTO coupon (id,code,tier_id,free_days,percent_off,amount_off_cents,bonus_credits,starts_at,expires_at,max_redemptions,max_per_user,eligible_groups,combinable,apply_after_current,active,created_at) VALUES (:id,:code,:tier_id,:free_days,:percent_off,:amount_off_cents,:bonus_credits,:starts_at,:expires_at,:max_redemptions,:max_per_user,:eligible_groups,:combinable,:apply_after_current,:active,:n)"),{**form.model_dump(),'eligible_groups':json.dumps(form.eligible_groups),'id':str(uuid.uuid4()),'code':code,'n':n()})
        except Exception: fail('Coupon code already exists')
    return {'ok':True}
@router.get('/admin/coupons')
def list_coupons(user=Depends(get_admin_user)):
    with engine.begin() as c: return [dict(x) for x in c.execute(text("SELECT c.*,COUNT(r.id) redemptions FROM coupon c LEFT JOIN coupon_redemption r ON r.coupon_id=c.id GROUP BY c.id ORDER BY c.created_at DESC")).mappings()]
@router.put('/admin/coupons/{coupon_id}')
def update_coupon(coupon_id:str,form:CouponForm,user=Depends(get_admin_user)):
    code=form.code.strip().upper()
    if not code or form.free_days<0 or form.max_per_user<1: fail('Invalid coupon')
    with engine.begin() as c:
        result=c.execute(text("UPDATE coupon SET code=:code,tier_id=:tier_id,free_days=:free_days,percent_off=:percent_off,amount_off_cents=:amount_off_cents,bonus_credits=:bonus_credits,starts_at=:starts_at,expires_at=:expires_at,max_redemptions=:max_redemptions,max_per_user=:max_per_user,eligible_groups=:eligible_groups,combinable=:combinable,apply_after_current=:apply_after_current,active=:active WHERE id=:id"),{**form.model_dump(),'code':code,'eligible_groups':json.dumps(form.eligible_groups),'id':coupon_id})
        if not result.rowcount: fail('Coupon not found')
    return {'ok':True}
@router.post('/coupons/redeem')
def redeem_coupon(form:CodeForm,user=Depends(get_verified_user)):
    # Immediate transaction makes max-use checks and redemption insertion atomic.
    with engine.connect() as c:
        if engine.dialect.name=='sqlite': c.exec_driver_sql('BEGIN IMMEDIATE')
        else: c.begin()
        try:
            coupon=c.execute(text("SELECT * FROM coupon WHERE code=:code AND active=1"),{'code':form.code.strip().upper()}).mappings().first(); now=n()
            if not coupon or (coupon['starts_at'] and coupon['starts_at']>now) or (coupon['expires_at'] and coupon['expires_at']<=now): fail('Coupon is unavailable')
            eligible = json.loads(coupon['eligible_groups'] or '[]')
            if eligible and not any(user.id in (Groups.get_group_user_ids_by_id(group_id) or []) for group_id in eligible): fail('Coupon is not available to this account')
            total=c.execute(text('SELECT COUNT(*) FROM coupon_redemption WHERE coupon_id=:id'),{'id':coupon['id']}).scalar(); mine=c.execute(text('SELECT COUNT(*) FROM coupon_redemption WHERE coupon_id=:id AND user_id=:u'),{'id':coupon['id'],'u':user.id}).scalar()
            if (coupon['max_redemptions'] is not None and total>=coupon['max_redemptions']) or mine>=coupon['max_per_user']: fail('Coupon redemption limit reached')
            if not coupon['combinable'] and c.execute(text("SELECT 1 FROM user_subscription WHERE user_id=:u AND status='promotional' AND (ends_at IS NULL OR ends_at>:n)"), {'u':user.id,'n':now}).first(): fail('This coupon cannot be combined with an existing promotion')
            start=usage.promotional_start(c,user.id,now) if coupon['apply_after_current'] else now
            sid=None
            if coupon['tier_id'] and coupon['free_days']:
                sid=str(uuid.uuid4()); end=start+coupon['free_days']*86400; c.execute(text("INSERT INTO user_subscription (id,user_id,tier_id,status,access_status,billing_status,starts_at,ends_at,created_at,updated_at) VALUES (:id,:u,:t,'promotional',:a,'none',:s,:e,:n,:n)"),{'id':sid,'u':user.id,'t':coupon['tier_id'],'a':'active' if start<=now else 'scheduled','s':start,'e':end,'n':now})
            if coupon['bonus_credits']:
                b=usage.balance(c,user.id,'bonus'); c.execute(text("INSERT INTO credit_ledger (id,user_id,kind,bucket,amount,balance_after,metadata,created_at) VALUES (:id,:u,'coupon','bonus',:a,:b,:m,:n)"),{'id':str(uuid.uuid4()),'u':user.id,'a':coupon['bonus_credits'],'b':b+coupon['bonus_credits'],'m':'{"coupon":"'+coupon['code']+'"}','n':now})
            c.execute(text('INSERT INTO coupon_redemption (id,coupon_id,user_id,subscription_id,created_at) VALUES (:id,:c,:u,:s,:n)'),{'id':str(uuid.uuid4()),'c':coupon['id'],'u':user.id,'s':sid,'n':now}); c.commit(); return {'ok':True,'scheduled_at':start,'payment_note':'Discounts are recorded only; Closed Beta never charges payment methods.'}
        except HTTPException: c.rollback(); raise
        except Exception: c.rollback(); raise

@router.post('/admin/invites')
def create_invite(form:InviteForm,user=Depends(get_admin_user)):
    if form.max_uses<1: fail('max_uses must be positive')
    code=secrets.token_urlsafe(9).upper();
    with engine.begin() as c: c.execute(text("INSERT INTO invite_code (id,code,creator_id,max_uses,uses,revoked,is_referral,created_at) VALUES (:id,:code,:creator,:max,0,0,0,:n)"),{'id':str(uuid.uuid4()),'code':code,'creator':form.creator_id,'max':form.max_uses,'n':n()})
    return {'code':code}
@router.post('/admin/invitations/enabled')
def set_invitation_only(enabled: bool, user=Depends(get_admin_user)):
    with engine.begin() as c: c.execute(text("INSERT INTO usage_setting (key,value,updated_at) VALUES ('invitation_only',:v,:n) ON CONFLICT(key) DO UPDATE SET value=:v,updated_at=:n"), {'v':json.dumps(enabled),'n':n()})
    return {'invitation_only':enabled}
@router.get('/invites')
def my_invites(user=Depends(get_verified_user)):
    with engine.begin() as c:
        code=usage.ensure_personal_invite(c,user.id)
        successful=c.execute(text('SELECT COUNT(*) FROM invite_redemption WHERE invite_id=:i'),{'i':code['id']}).scalar()
        return {'code':code['code'],'max_uses':code['max_uses'],'uses':code['uses'],'remaining':max(0,code['max_uses']-code['uses']),'revoked':code['revoked'],'successful':successful,'share_path':'/auth?invite='+code['code']}
@router.get('/admin/invites')
def admin_invites(user=Depends(get_admin_user)):
    with engine.begin() as c: return [dict(x) for x in c.execute(text("SELECT i.*,u.name creator_name,COUNT(r.id) redemptions FROM invite_code i LEFT JOIN user u ON u.id=i.creator_id LEFT JOIN invite_redemption r ON r.invite_id=i.id GROUP BY i.id ORDER BY i.created_at DESC")).mappings()]
@router.put('/admin/invites/{invite_id}')
def update_invite(invite_id:str,form:InviteUpdateForm,user=Depends(get_admin_user)):
    with engine.begin() as c:
        invite=c.execute(text('SELECT * FROM invite_code WHERE id=:id'),{'id':invite_id}).mappings().first()
        if not invite: fail('Invitation code not found')
        values={'id':invite_id,'max':form.max_uses if form.max_uses is not None else invite['max_uses'],'revoked':form.revoked if form.revoked is not None else invite['revoked']}
        if form.regenerate:
            values['code']='THATAI-'+secrets.token_hex(5).upper()
            c.execute(text('UPDATE invite_code SET code=:code,max_uses=:max,revoked=:revoked,uses=0 WHERE id=:id'),values)
        else: c.execute(text('UPDATE invite_code SET max_uses=:max,revoked=:revoked WHERE id=:id'),values)
    return {'ok':True}
