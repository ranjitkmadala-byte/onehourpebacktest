from __future__ import annotations

import os, time, uuid, math
from datetime import date, datetime, timedelta, time as dtime
from urllib.parse import quote
from zoneinfo import ZoneInfo

import psycopg
import requests
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

IST = ZoneInfo("Asia/Kolkata")
DB = (os.getenv("NEON_DATABASE_URL") or os.getenv("DATABASE_URL") or "").strip()
TOKEN = (os.getenv("UPSTOX_ACCESS_TOKEN") or os.getenv("UPSTOX_TOKEN") or "").strip()

START = date.fromisoformat(os.getenv("STUDY_START", "2026-08-26"))
END = date.fromisoformat(os.getenv("STUDY_END", "2026-09-11"))

FIRST5_END = dtime(9, 20)
ENTRY_CUTOFF = dtime.fromisoformat(os.getenv("ENTRY_CUTOFF", "12:15"))

TARGET_PCT = float(os.getenv("TARGET_PCT", "0.50"))
STOP_PCT = float(os.getenv("STOP_PCT", "0.50"))

# Final bearish filters found in the prior study.
OPTION_SCORE_REQUIRED = int(os.getenv("OPTION_SCORE_REQUIRED", "3"))
OPTION_SCORE_WINDOW_MIN = int(os.getenv("OPTION_SCORE_WINDOW_MIN", "15"))
MIN_PE_PREMIUM = float(os.getenv("MIN_PE_PREMIUM", "10"))

# Pine source: Daily ATR period 20, slope 0.69, intercept 0.
ATR_PERIOD = int(os.getenv("ATR_PERIOD", "20"))
D_SLOPE = float(os.getenv("D_SLOPE", "0.69"))
D_INTERCEPT = float(os.getenv("D_INTERCEPT", "0.0"))
PHI = 1.618034
SQRT2 = math.sqrt(2.0)
SQRT252 = math.sqrt(252.0)

RUN_ID = str(uuid.uuid4())
V3_HIST = "https://api.upstox.com/v3/historical-candle"
V2 = "https://api.upstox.com/v2"

def log(x):
    print(f"{datetime.now(IST):%Y-%m-%d %H:%M:%S} IST | {x}", flush=True)

def db():
    return psycopg.connect(DB, row_factory=dict_row, connect_timeout=20)

def headers():
    return {"Accept":"application/json","Authorization":f"Bearer {TOKEN}"}

def get_json(url, params=None, tries=5):
    last=None
    for n in range(tries):
        try:
            r=requests.get(url,params=params,headers=headers(),timeout=60)
            if r.status_code==429:
                time.sleep(2*(n+1)); continue
            r.raise_for_status()
            return r.json()
        except Exception as exc:
            last=exc
            if n<tries-1:
                time.sleep(1.5*(n+1))
    raise RuntimeError(str(last))

DDL = """
CREATE TABLE IF NOT EXISTS public.first5_close_below_lower_zone_backtest (
    study_start DATE NOT NULL,
    study_end DATE NOT NULL,
    run_id UUID NOT NULL,

    trading_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    spot_instrument_key TEXT NOT NULL,

    day_open NUMERIC,
    atr20 NUMERIC,
    prev_close NUMERIC,
    sigma NUMERIC,
    weak_demand_low NUMERIC,
    weak_demand_high NUMERIC,
    strong_demand_low NUMERIC,
    strong_demand_high NUMERIC,
    weak_supply_low NUMERIC,
    weak_supply_high NUMERIC,
    strong_supply_low NUMERIC,
    strong_supply_high NUMERIC,
    start_zone TEXT,
    end_zone TEXT,
    zones_traversed INTEGER,
    previous_zone_name TEXT,
    previous_zone_level NUMERIC,
    next_zone_name TEXT,
    next_zone_level NUMERIC,

    first5_open NUMERIC,
    first5_high NUMERIC,
    first5_low NUMERIC,
    first5_close NUMERIC,
    weak_demand_broken_5m BOOLEAN NOT NULL DEFAULT FALSE,
    break_pct NUMERIC,

    anchor_0915_high NUMERIC,
    avwap_at_1015 NUMERIC,

    retrace_found BOOLEAN NOT NULL DEFAULT FALSE,
    retrace_time TIMESTAMPTZ,
    retrace_high NUMERIC,
    avwap_at_retrace NUMERIC,

    spot_entry_found BOOLEAN NOT NULL DEFAULT FALSE,
    spot_entry_time TIMESTAMPTZ,
    spot_entry_price NUMERIC,
    avwap_at_entry NUMERIC,

    spot_target_price NUMERIC,
    spot_stop_price NUMERIC,

    atm_strike NUMERIC,
    option_expiry DATE,
    pe_instrument_key TEXT,
    ce_instrument_key TEXT,

    score3_found BOOLEAN NOT NULL DEFAULT FALSE,
    raw_option_entry_time TIMESTAMPTZ,
    option_entry_time TIMESTAMPTZ,
    option_entry_score INTEGER,
    pe_entry_price NUMERIC,
    ce_price_at_option_entry NUMERIC,

    time_filter_pass BOOLEAN NOT NULL DEFAULT FALSE,
    premium_filter_pass BOOLEAN NOT NULL DEFAULT FALSE,
    final_trade BOOLEAN NOT NULL DEFAULT FALSE,

    first_outcome TEXT,
    outcome_time TIMESTAMPTZ,
    pe_exit_price NUMERIC,
    pe_return_pct NUMERIC,

    pe_eod_price NUMERIC,
    pe_eod_return_pct NUMERIC,

    data_status TEXT NOT NULL,
    error_message TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),

    PRIMARY KEY(study_start,study_end,trading_date,symbol)
);

CREATE TABLE IF NOT EXISTS public.first5_close_below_lower_zone_summary (
    study_start DATE NOT NULL,
    study_end DATE NOT NULL,
    run_id UUID NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    symbols INTEGER NOT NULL,
    weak_demand_breaks INTEGER NOT NULL,
    spot_entries INTEGER NOT NULL,
    score3_entries INTEGER NOT NULL,
    final_trades INTEGER NOT NULL,
    target_first INTEGER NOT NULL,
    stop_first INTEGER NOT NULL,
    neither INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    summary JSONB NOT NULL,
    PRIMARY KEY(study_start,study_end)
);
"""

UPSERT = """
INSERT INTO public.first5_close_below_lower_zone_backtest (
 study_start,study_end,run_id,trading_date,symbol,spot_instrument_key,
 day_open,atr20,prev_close,sigma,weak_demand_low,weak_demand_high,strong_demand_low,strong_demand_high,weak_supply_low,weak_supply_high,strong_supply_low,strong_supply_high,start_zone,end_zone,zones_traversed,previous_zone_name,previous_zone_level,next_zone_name,next_zone_level,
 first5_open,first5_high,first5_low,first5_close,weak_demand_broken_5m,break_pct,
 anchor_0915_high,avwap_at_1015,
 retrace_found,retrace_time,retrace_high,avwap_at_retrace,
 spot_entry_found,spot_entry_time,spot_entry_price,avwap_at_entry,
 spot_target_price,spot_stop_price,
 atm_strike,option_expiry,pe_instrument_key,ce_instrument_key,
 score3_found,raw_option_entry_time,option_entry_time,option_entry_score,pe_entry_price,ce_price_at_option_entry,
 time_filter_pass,premium_filter_pass,final_trade,
 first_outcome,outcome_time,pe_exit_price,pe_return_pct,pe_eod_price,pe_eod_return_pct,
 data_status,error_message
) VALUES (
 %(study_start)s,%(study_end)s,%(run_id)s,%(trading_date)s,%(symbol)s,%(spot_instrument_key)s,
 %(day_open)s,%(atr20)s,%(prev_close)s,%(sigma)s,%(weak_demand_low)s,%(weak_demand_high)s,%(strong_demand_low)s,%(strong_demand_high)s,%(weak_supply_low)s,%(weak_supply_high)s,%(strong_supply_low)s,%(strong_supply_high)s,%(start_zone)s,%(end_zone)s,%(zones_traversed)s,%(previous_zone_name)s,%(previous_zone_level)s,%(next_zone_name)s,%(next_zone_level)s,
 %(first5_open)s,%(first5_high)s,%(first5_low)s,%(first5_close)s,%(weak_demand_broken_5m)s,%(break_pct)s,
 %(anchor_0915_high)s,%(avwap_at_1015)s,
 %(retrace_found)s,%(retrace_time)s,%(retrace_high)s,%(avwap_at_retrace)s,
 %(spot_entry_found)s,%(spot_entry_time)s,%(spot_entry_price)s,%(avwap_at_entry)s,
 %(spot_target_price)s,%(spot_stop_price)s,
 %(atm_strike)s,%(option_expiry)s,%(pe_instrument_key)s,%(ce_instrument_key)s,
 %(score3_found)s,%(raw_option_entry_time)s,%(option_entry_time)s,%(option_entry_score)s,%(pe_entry_price)s,%(ce_price_at_option_entry)s,
 %(time_filter_pass)s,%(premium_filter_pass)s,%(final_trade)s,
 %(first_outcome)s,%(outcome_time)s,%(pe_exit_price)s,%(pe_return_pct)s,%(pe_eod_price)s,%(pe_eod_return_pct)s,
 %(data_status)s,%(error_message)s
)
ON CONFLICT(study_start,study_end,trading_date,symbol) DO UPDATE SET
 run_id=EXCLUDED.run_id,day_open=EXCLUDED.day_open,atr20=EXCLUDED.atr20,prev_close=EXCLUDED.prev_close,
 sigma=EXCLUDED.sigma,weak_demand_low=EXCLUDED.weak_demand_low,weak_demand_high=EXCLUDED.weak_demand_high,
 strong_demand_low=EXCLUDED.strong_demand_low,strong_demand_high=EXCLUDED.strong_demand_high,
 weak_supply_low=EXCLUDED.weak_supply_low,weak_supply_high=EXCLUDED.weak_supply_high,strong_supply_low=EXCLUDED.strong_supply_low,strong_supply_high=EXCLUDED.strong_supply_high,start_zone=EXCLUDED.start_zone,end_zone=EXCLUDED.end_zone,zones_traversed=EXCLUDED.zones_traversed,previous_zone_name=EXCLUDED.previous_zone_name,previous_zone_level=EXCLUDED.previous_zone_level,next_zone_name=EXCLUDED.next_zone_name,next_zone_level=EXCLUDED.next_zone_level,
 first5_open=EXCLUDED.first5_open,first5_high=EXCLUDED.first5_high,first5_low=EXCLUDED.first5_low,
 first5_close=EXCLUDED.first5_close,weak_demand_broken_5m=EXCLUDED.weak_demand_broken_5m,break_pct=EXCLUDED.break_pct,
 anchor_0915_high=EXCLUDED.anchor_0915_high,avwap_at_1015=EXCLUDED.avwap_at_1015,
 retrace_found=EXCLUDED.retrace_found,retrace_time=EXCLUDED.retrace_time,retrace_high=EXCLUDED.retrace_high,
 avwap_at_retrace=EXCLUDED.avwap_at_retrace,spot_entry_found=EXCLUDED.spot_entry_found,
 spot_entry_time=EXCLUDED.spot_entry_time,spot_entry_price=EXCLUDED.spot_entry_price,avwap_at_entry=EXCLUDED.avwap_at_entry,
 spot_target_price=EXCLUDED.spot_target_price,spot_stop_price=EXCLUDED.spot_stop_price,
 atm_strike=EXCLUDED.atm_strike,option_expiry=EXCLUDED.option_expiry,pe_instrument_key=EXCLUDED.pe_instrument_key,
 ce_instrument_key=EXCLUDED.ce_instrument_key,score3_found=EXCLUDED.score3_found,
 raw_option_entry_time=EXCLUDED.raw_option_entry_time,option_entry_time=EXCLUDED.option_entry_time,
 option_entry_score=EXCLUDED.option_entry_score,pe_entry_price=EXCLUDED.pe_entry_price,
 ce_price_at_option_entry=EXCLUDED.ce_price_at_option_entry,time_filter_pass=EXCLUDED.time_filter_pass,
 premium_filter_pass=EXCLUDED.premium_filter_pass,final_trade=EXCLUDED.final_trade,
 first_outcome=EXCLUDED.first_outcome,outcome_time=EXCLUDED.outcome_time,pe_exit_price=EXCLUDED.pe_exit_price,
 pe_return_pct=EXCLUDED.pe_return_pct,pe_eod_price=EXCLUDED.pe_eod_price,pe_eod_return_pct=EXCLUDED.pe_eod_return_pct,
 data_status=EXCLUDED.data_status,error_message=EXCLUDED.error_message,updated_at=NOW();
"""

def universe():
    q = """
    SELECT DISTINCT symbol,spot_instrument_key
    FROM public.spot_supply_1h_backtest_hourly
    WHERE trading_date BETWEEN %s AND %s
    ORDER BY symbol
    """
    with db() as c:
        with c.cursor() as x:
            x.execute(q,(START,END))
            return [dict(r) for r in x.fetchall()]

def trading_dates():
    q = """
    SELECT DISTINCT trading_date
    FROM public.spot_supply_1h_backtest_hourly
    WHERE trading_date BETWEEN %s AND %s
    ORDER BY trading_date
    """
    with db() as c:
        with c.cursor() as x:
            x.execute(q,(START,END))
            return [r["trading_date"] for r in x.fetchall()]

def fetch_1m(key, day):
    u=f"{V3_HIST}/{quote(key,safe='')}/minutes/1/{day.isoformat()}/{day.isoformat()}"
    j=get_json(u)
    out=[]
    for a in (j.get("data") or {}).get("candles") or []:
        if len(a)<7: continue
        try:
            ts=datetime.fromisoformat(str(a[0]).replace("Z","+00:00")).astimezone(IST)
            out.append(dict(ts=ts,open=float(a[1]),high=float(a[2]),low=float(a[3]),
                            close=float(a[4]),volume=int(float(a[5] or 0)),oi=int(float(a[6] or 0))))
        except Exception: pass
    return sorted(out,key=lambda z:z["ts"])

def fetch_daily(key, to_day):
    from_day = to_day - timedelta(days=120)
    u=f"{V3_HIST}/{quote(key,safe='')}/days/1/{to_day.isoformat()}/{from_day.isoformat()}"
    j=get_json(u)
    out=[]
    for a in (j.get("data") or {}).get("candles") or []:
        if len(a)<5: continue
        try:
            ts=datetime.fromisoformat(str(a[0]).replace("Z","+00:00")).astimezone(IST)
            out.append(dict(day=ts.date(),open=float(a[1]),high=float(a[2]),low=float(a[3]),close=float(a[4])))
        except Exception: pass
    return sorted(out,key=lambda z:z["day"])

def wilder_atr(daily, period=20):
    if len(daily)<period+1: raise ValueError("insufficient ATR history")
    trs=[]
    for i in range(1,len(daily)):
        h,l,pc=daily[i]["high"],daily[i]["low"],daily[i-1]["close"]
        trs.append(max(h-l,abs(h-pc),abs(l-pc)))
    if len(trs)<period: raise ValueError("insufficient TR history")
    atr=sum(trs[:period])/period
    for tr in trs[period:]:
        atr=((atr*(period-1))+tr)/period
    return atr

def all_zones(day_open,atr,prev_close):
    atr_ann_pct=atr/prev_close*SQRT252*100
    effvol=D_SLOPE*atr_ann_pct+D_INTERCEPT
    P=round(day_open); sigma=P*effvol/(100*SQRT252)
    ds=sigma; dw=sigma/(2*SQRT2); ws=round(sigma/4); ww=round(sigma/(4*PHI))
    return sigma, {
      "SD":(round(P-ds-ws/2),round(P-ds+ws/2)),
      "WD":(round(P-dw-ww/2),round(P-dw+ww/2)),
      "WS":(round(P+dw-ww/2),round(P+dw+ww/2)),
      "SS":(round(P+ds-ws/2),round(P+ds+ws/2))
    }

def literal_transition(open_price, close_price, zones):
    """
    Strict close-confirmed downward zone transition.

    Daily zones are ordered:
        SS -> WS -> WD -> SD

    Qualification:
      - identify the starting zone from the 09:15 OPEN
      - the 09:20 CLOSE must be BELOW the LOW boundary of at least one lower zone
      - the deepest lower zone fully broken by the CLOSE becomes end_zone

    Examples:
      SS -> WS qualifies only if 09:20 close < WS low
      WS -> WD qualifies only if 09:20 close < WD low
      WD -> SD qualifies only if 09:20 close < SD low

    This is intentionally stricter than using the candle low.
    """
    order = ["SS", "WS", "WD", "SD"]

    start_idx = None
    for i, name in enumerate(order):
        lo, hi = zones[name]
        if open_price >= lo:
            start_idx = i
            break

    if start_idx is None:
        return None

    end_idx = start_idx

    for j in range(start_idx + 1, len(order)):
        lo, hi = zones[order[j]]
        if close_price < lo:
            end_idx = j

    if end_idx <= start_idx:
        return None

    return order, start_idx, end_idx


def build_3m(rows):
    buckets={}
    for r in rows:
        t=r["ts"]
        if not (dtime(9,15)<=t.time().replace(tzinfo=None)<dtime(15,30)): continue
        mins=(t.hour*60+t.minute)-(9*60+15)
        k=mins//3
        s=t.replace(hour=9,minute=15,second=0,microsecond=0)+timedelta(minutes=3*k)
        b=buckets.get(s)
        if not b:
            buckets[s]=dict(start=s,end=s+timedelta(minutes=3),open=r["open"],high=r["high"],low=r["low"],close=r["close"],volume=r["volume"])
        else:
            b["high"]=max(b["high"],r["high"]); b["low"]=min(b["low"],r["low"]); b["close"]=r["close"]; b["volume"]+=r["volume"]
    return [buckets[k] for k in sorted(buckets)]

def calc_avwap(bars):
    pv=v=0.0
    out=[]
    for b in bars:
        tp=(b["high"]+b["low"]+b["close"])/3
        pv += tp*b["volume"]; v += b["volume"]
        av=pv/v if v>0 else tp
        x=dict(b); x["avwap"]=av; out.append(x)
    return out

def option_expiries(spot_key):
    exps=set()
    try:
        j=get_json(f"{V2}/expired-instruments/expiries",params={"instrument_key":spot_key})
        for x in j.get("data") or []:
            val=x if isinstance(x,str) else (x.get("expiry") or x.get("expiry_date") if isinstance(x,dict) else None)
            if val:
                try: exps.add(date.fromisoformat(str(val)[:10]))
                except: pass
    except Exception: pass
    try:
        j=get_json(f"{V2}/option/contract",params={"instrument_key":spot_key})
        for r in j.get("data") or []:
            if r.get("expiry"):
                try: exps.add(date.fromisoformat(str(r["expiry"])[:10]))
                except: pass
    except Exception: pass
    return sorted(exps)

def option_contract_rows(spot_key, expiry):
    if expiry < datetime.now(IST).date():
        j=get_json(f"{V2}/expired-instruments/option/contract",
                   params={"instrument_key":spot_key,"expiry_date":expiry.isoformat()})
        src="EXPIRED"
    else:
        j=get_json(f"{V2}/option/contract",
                   params={"instrument_key":spot_key,"expiry_date":expiry.isoformat()})
        src="CURRENT"
    return src,j.get("data") or []

def pick_atm_pair(spot_key, trade_day, spot_price):
    exps=[x for x in option_expiries(spot_key) if x>=trade_day]
    if not exps: raise ValueError("no option expiry")
    expiry=exps[0]
    src,rows=option_contract_rows(spot_key,expiry)
    out={}
    for side in ("CE","PE"):
        cand=[]
        for r in rows:
            typ=str(r.get("instrument_type") or r.get("option_type") or "").upper()
            if typ!=side: continue
            strike=r.get("strike_price") if r.get("strike_price") is not None else r.get("strike")
            key=r.get("instrument_key")
            if strike is None or not key: continue
            strike=float(strike)
            cand.append((abs(strike-spot_price),strike,str(key)))
        if not cand: raise ValueError(f"{side} unavailable")
        cand.sort(key=lambda x:(x[0],x[1]))
        _,strike,key=cand[0]
        out[side]=dict(strike=strike,key=key,src=src)
    return expiry,out

def option_1m(contract, trade_day):
    key=quote(contract["key"],safe="")
    if contract["src"]=="EXPIRED":
        u=f"{V2}/expired-instruments/historical-candle/{key}/1minute/{trade_day.isoformat()}/{trade_day.isoformat()}"
    else:
        u=f"{V3_HIST}/{key}/minutes/1/{trade_day.isoformat()}/{trade_day.isoformat()}"
    j=get_json(u)
    out=[]
    for a in (j.get("data") or {}).get("candles") or []:
        if len(a)<7: continue
        try:
            ts=datetime.fromisoformat(str(a[0]).replace("Z","+00:00")).astimezone(IST)
            out.append(dict(ts=ts,open=float(a[1]),high=float(a[2]),low=float(a[3]),close=float(a[4]),
                            volume=int(float(a[5] or 0)),oi=int(float(a[6] or 0))))
        except Exception: pass
    return sorted(out,key=lambda z:z["ts"])

def nearest_row(rows, ts):
    if not rows: return None
    return min(rows,key=lambda r:abs((r["ts"]-ts).total_seconds()))

def blank(sym,key,day):
    return dict(
      study_start=START,study_end=END,run_id=RUN_ID,trading_date=day,symbol=sym,spot_instrument_key=key,
      day_open=None,atr20=None,prev_close=None,sigma=None,weak_demand_low=None,weak_demand_high=None,strong_demand_low=None,strong_demand_high=None,weak_supply_low=None,weak_supply_high=None,strong_supply_low=None,strong_supply_high=None,start_zone=None,end_zone=None,zones_traversed=None,previous_zone_name=None,previous_zone_level=None,next_zone_name=None,next_zone_level=None,
      first5_open=None,first5_high=None,first5_low=None,first5_close=None,weak_demand_broken_5m=False,break_pct=None,
      anchor_0915_high=None,avwap_at_1015=None,retrace_found=False,retrace_time=None,retrace_high=None,avwap_at_retrace=None,
      spot_entry_found=False,spot_entry_time=None,spot_entry_price=None,avwap_at_entry=None,
      spot_target_price=None,spot_stop_price=None,atm_strike=None,option_expiry=None,pe_instrument_key=None,ce_instrument_key=None,
      score3_found=False,raw_option_entry_time=None,option_entry_time=None,option_entry_score=None,pe_entry_price=None,
      ce_price_at_option_entry=None,time_filter_pass=False,premium_filter_pass=False,final_trade=False,
      first_outcome=None,outcome_time=None,pe_exit_price=None,pe_return_pct=None,pe_eod_price=None,pe_eod_return_pct=None,
      data_status="OK",error_message=None
    )

def process(sym,key,day):
    z=blank(sym,key,day)
    spot=fetch_1m(key,day)
    market=[r for r in spot if dtime(9,15)<=r["ts"].time().replace(tzinfo=None)<dtime(15,30)]
    if not market: raise ValueError("no spot history")
    daily=fetch_daily(key,day-timedelta(days=1)); prev=[r for r in daily if r["day"]<day]
    if len(prev)<ATR_PERIOD+1: raise ValueError("insufficient ATR history")
    atr=wilder_atr(prev,ATR_PERIOD); pc=prev[-1]["close"]; op=market[0]["open"]
    sigma,Z=all_zones(op,atr,pc)
    z.update(day_open=op,atr20=atr,prev_close=pc,sigma=sigma,
      strong_demand_low=Z["SD"][0],strong_demand_high=Z["SD"][1],
      weak_demand_low=Z["WD"][0],weak_demand_high=Z["WD"][1],
      weak_supply_low=Z["WS"][0],weak_supply_high=Z["WS"][1],
      strong_supply_low=Z["SS"][0],strong_supply_high=Z["SS"][1])
    f=[r for r in market if dtime(9,15)<=r["ts"].time().replace(tzinfo=None)<FIRST5_END]
    if not f:return z
    O=f[0]["open"]; H=max(x["high"] for x in f); L=min(x["low"] for x in f); C=f[-1]["close"]
    z.update(first5_open=O,first5_high=H,first5_low=L,first5_close=C)
    m=literal_transition(O,C,Z)
    if not m:
        z.update(zones_traversed=0,weak_demand_broken_5m=False); return z
    order,si,ei=m; sz=order[si]; ez=order[ei]
    z.update(start_zone=sz,end_zone=ez,zones_traversed=ei-si,weak_demand_broken_5m=True)
    if ei>=len(order)-1:return z
    nxt=order[ei+1]; prv=order[ei-1]
    target=float(Z[nxt][1]); stop=float(Z[prv][0]); entry=L
    if not(target<entry<stop):return z
    et=datetime.combine(day,FIRST5_END,IST)
    z.update(previous_zone_name=prv,previous_zone_level=stop,next_zone_name=nxt,next_zone_level=target,
      spot_entry_found=True,spot_entry_time=et,spot_entry_price=entry,spot_target_price=target,
      spot_stop_price=stop,final_trade=True,time_filter_pass=True,premium_filter_pass=True)
    post=[x for x in market if x["ts"]>=et]; out="NEITHER"; ot=None; ex=None
    for x in post:
      ht=x["low"]<=target; hs=x["high"]>=stop
      if ht and hs:out="AMBIGUOUS_SAME_1M_BAR";ot=x["ts"]+timedelta(minutes=1);ex=x["close"];break
      if ht:out="TARGET_FIRST";ot=x["ts"]+timedelta(minutes=1);ex=target;break
      if hs:out="STOP_FIRST";ot=x["ts"]+timedelta(minutes=1);ex=stop;break
    eod=post[-1]["close"] if post else entry
    if out=="NEITHER":ex=eod
    z.update(first_outcome=out,outcome_time=ot,pe_entry_price=entry,pe_exit_price=ex,
      pe_return_pct=(entry-ex)/entry*100,pe_eod_price=eod,pe_eod_return_pct=(entry-eod)/entry*100)
    return z


def main():
    if not DB or not TOKEN:
        raise RuntimeError("NEON_DATABASE_URL and UPSTOX_TOKEN are required")
    with db() as c:
        with c.cursor() as x: x.execute(DDL)
        c.commit()

    uni=universe(); days=trading_dates()
    log(f"universe={len(uni)} dates={len(days)}")
    rows=[]; failed=0

    for di,day in enumerate(days,1):
        log(f"DATE {day} ({di}/{len(days)})")
        for i,u in enumerate(uni,1):
            try:
                r=process(u["symbol"],u["spot_instrument_key"],day)
            except Exception as exc:
                r=blank(u["symbol"],u["spot_instrument_key"],day)
                r["data_status"]="ERROR"; r["error_message"]=str(exc)[:1000]; failed+=1
            rows.append(r)
            if len(rows)>=50:
                with db() as c:
                    with c.cursor() as x: x.executemany(UPSERT,rows)
                    c.commit()
                rows=[]
            if i%25==0:
                time.sleep(.15)

    if rows:
        with db() as c:
            with c.cursor() as x: x.executemany(UPSERT,rows)
            c.commit()

    qcount="""
    SELECT
      COUNT(DISTINCT symbol) symbols,
      COUNT(*) FILTER(WHERE weak_demand_broken_5m) weak_demand_breaks,
      COUNT(*) FILTER(WHERE final_trade) final_trades,
      COUNT(*) FILTER(WHERE final_trade AND first_outcome='TARGET_FIRST') target_first,
      COUNT(*) FILTER(WHERE final_trade AND first_outcome='STOP_FIRST') stop_first,
      COUNT(*) FILTER(WHERE final_trade AND first_outcome='NEITHER') neither,
      COUNT(*) FILTER(WHERE final_trade AND first_outcome='AMBIGUOUS_SAME_1M_BAR') ambiguous,
      ROUND(SUM(pe_return_pct) FILTER(WHERE final_trade),2) cumulative_pct_points,
      ROUND(AVG(pe_return_pct) FILTER(WHERE final_trade),3) avg_return_pct,
      ROUND(PERCENTILE_CONT(.5) WITHIN GROUP(ORDER BY pe_return_pct)
            FILTER(WHERE final_trade)::numeric,3) median_return_pct
    FROM public.first5_close_below_lower_zone_backtest
    WHERE study_start=%s AND study_end=%s
    """
    with db() as c:
        with c.cursor() as x:
            x.execute(qcount,(START,END)); s=dict(x.fetchone())

    safe={}
    for k,v in s.items():
        if v is None or isinstance(v,(bool,int,float,str)):
            safe[k]=v
        else:
            try: safe[k]=float(v)
            except: safe[k]=str(v)

    summary={**safe,"failed":failed,
      "rule":{
        "zone":"Daily Weak Demand from supplied Pine source",
        "signal":"09:20 CLOSE must finish below the LOW boundary of the lower zone; no nearest-zone assignment",
        "entry":"LOW of completed 09:15-09:20 candle",
        "target":"HIGH boundary of next zone below entry",
        "stop":"LOW boundary of previous zone above entry",
        "exit":"target/stop whichever occurs first; neither -> EOD"
      }}

    qs="""INSERT INTO public.first5_close_below_lower_zone_summary
      (study_start,study_end,run_id,symbols,weak_demand_breaks,spot_entries,score3_entries,
       final_trades,target_first,stop_first,neither,failed,summary)
      VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
      ON CONFLICT(study_start,study_end) DO UPDATE SET
       run_id=EXCLUDED.run_id,generated_at=NOW(),symbols=EXCLUDED.symbols,
       weak_demand_breaks=EXCLUDED.weak_demand_breaks,spot_entries=EXCLUDED.spot_entries,
       score3_entries=EXCLUDED.score3_entries,final_trades=EXCLUDED.final_trades,
       target_first=EXCLUDED.target_first,stop_first=EXCLUDED.stop_first,
       neither=EXCLUDED.neither,failed=EXCLUDED.failed,summary=EXCLUDED.summary"""
    with db() as c:
        with c.cursor() as x:
            x.execute(qs,(
                START,END,RUN_ID,s["symbols"],s["weak_demand_breaks"],
                s["final_trades"],0,s["final_trades"],
                s["target_first"],s["stop_first"],s["neither"],failed,Jsonb(summary)
            ))
        c.commit()

    log("COMPLETE")
    log(str(summary))

if __name__=="__main__":
    main()
