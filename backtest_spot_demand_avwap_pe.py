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
ENTRY_CUTOFF = dtime(12, 15)
TARGET_PCT = float(os.getenv("TARGET_PCT", "0.50"))
STOP_PCT = float(os.getenv("STOP_PCT", "0.50"))
OPTION_SCORE_MIN = int(os.getenv("OPTION_SCORE_MIN", "3"))
OPTION_SCORE_WINDOW_MIN = int(os.getenv("OPTION_SCORE_WINDOW_MIN", "15"))

SQRT252 = math.sqrt(252.0)
D_SLOPE = 0.69
D_INTERCEPT = 0.0
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
            if n<tries-1: time.sleep(1.5*(n+1))
    raise RuntimeError(str(last))

DDL = """
CREATE TABLE IF NOT EXISTS public.spot_demand_1015_avwap_pe_backtest (
    study_start DATE NOT NULL,
    study_end DATE NOT NULL,
    run_id UUID NOT NULL,

    trading_date DATE NOT NULL,
    symbol TEXT NOT NULL,
    spot_instrument_key TEXT NOT NULL,

    day_open NUMERIC,
    atr14 NUMERIC,
    prev_close NUMERIC,
    strong_demand_low NUMERIC,
    strong_demand_high NUMERIC,

    breakdown_1015 BOOLEAN NOT NULL DEFAULT FALSE,
    breakdown_close NUMERIC,
    breakdown_pct NUMERIC,

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

    option_entry_found BOOLEAN NOT NULL DEFAULT FALSE,
    option_entry_time TIMESTAMPTZ,
    option_entry_score INTEGER,
    pe_entry_price NUMERIC,
    ce_price_at_option_entry NUMERIC,

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

CREATE TABLE IF NOT EXISTS public.spot_demand_1015_avwap_pe_summary (
    study_start DATE NOT NULL,
    study_end DATE NOT NULL,
    run_id UUID NOT NULL,
    generated_at TIMESTAMPTZ DEFAULT NOW(),
    symbols INTEGER NOT NULL,
    breakdowns INTEGER NOT NULL,
    spot_entries INTEGER NOT NULL,
    option_entries INTEGER NOT NULL,
    target_first INTEGER NOT NULL,
    stop_first INTEGER NOT NULL,
    neither INTEGER NOT NULL,
    failed INTEGER NOT NULL,
    summary JSONB NOT NULL,
    PRIMARY KEY(study_start,study_end)
);
"""

UPSERT = """
INSERT INTO public.spot_demand_1015_avwap_pe_backtest (
 study_start,study_end,run_id,trading_date,symbol,spot_instrument_key,
 day_open,atr14,prev_close,strong_demand_low,strong_demand_high,
 breakdown_1015,breakdown_close,breakdown_pct,
 anchor_0915_high,avwap_at_1015,
 retrace_found,retrace_time,retrace_high,avwap_at_retrace,
 spot_entry_found,spot_entry_time,spot_entry_price,avwap_at_entry,
 spot_target_price,spot_stop_price,
 atm_strike,option_expiry,pe_instrument_key,ce_instrument_key,
 option_entry_found,option_entry_time,option_entry_score,pe_entry_price,ce_price_at_option_entry,
 first_outcome,outcome_time,pe_exit_price,pe_return_pct,pe_eod_price,pe_eod_return_pct,
 data_status,error_message
) VALUES (
 %(study_start)s,%(study_end)s,%(run_id)s,%(trading_date)s,%(symbol)s,%(spot_instrument_key)s,
 %(day_open)s,%(atr14)s,%(prev_close)s,%(strong_demand_low)s,%(strong_demand_high)s,
 %(breakdown_1015)s,%(breakdown_close)s,%(breakdown_pct)s,
 %(anchor_0915_high)s,%(avwap_at_1015)s,
 %(retrace_found)s,%(retrace_time)s,%(retrace_high)s,%(avwap_at_retrace)s,
 %(spot_entry_found)s,%(spot_entry_time)s,%(spot_entry_price)s,%(avwap_at_entry)s,
 %(spot_target_price)s,%(spot_stop_price)s,
 %(atm_strike)s,%(option_expiry)s,%(pe_instrument_key)s,%(ce_instrument_key)s,
 %(option_entry_found)s,%(option_entry_time)s,%(option_entry_score)s,%(pe_entry_price)s,%(ce_price_at_option_entry)s,
 %(first_outcome)s,%(outcome_time)s,%(pe_exit_price)s,%(pe_return_pct)s,%(pe_eod_price)s,%(pe_eod_return_pct)s,
 %(data_status)s,%(error_message)s
)
ON CONFLICT(study_start,study_end,trading_date,symbol) DO UPDATE SET
 run_id=EXCLUDED.run_id,day_open=EXCLUDED.day_open,atr14=EXCLUDED.atr14,prev_close=EXCLUDED.prev_close,
 strong_demand_low=EXCLUDED.strong_demand_low,strong_demand_high=EXCLUDED.strong_demand_high,
 breakdown_1015=EXCLUDED.breakdown_1015,breakdown_close=EXCLUDED.breakdown_close,breakdown_pct=EXCLUDED.breakdown_pct,
 anchor_0915_high=EXCLUDED.anchor_0915_high,avwap_at_1015=EXCLUDED.avwap_at_1015,
 retrace_found=EXCLUDED.retrace_found,retrace_time=EXCLUDED.retrace_time,retrace_high=EXCLUDED.retrace_high,
 avwap_at_retrace=EXCLUDED.avwap_at_retrace,spot_entry_found=EXCLUDED.spot_entry_found,
 spot_entry_time=EXCLUDED.spot_entry_time,spot_entry_price=EXCLUDED.spot_entry_price,avwap_at_entry=EXCLUDED.avwap_at_entry,
 spot_target_price=EXCLUDED.spot_target_price,spot_stop_price=EXCLUDED.spot_stop_price,
 atm_strike=EXCLUDED.atm_strike,option_expiry=EXCLUDED.option_expiry,
 pe_instrument_key=EXCLUDED.pe_instrument_key,ce_instrument_key=EXCLUDED.ce_instrument_key,
 option_entry_found=EXCLUDED.option_entry_found,option_entry_time=EXCLUDED.option_entry_time,
 option_entry_score=EXCLUDED.option_entry_score,pe_entry_price=EXCLUDED.pe_entry_price,
 ce_price_at_option_entry=EXCLUDED.ce_price_at_option_entry,first_outcome=EXCLUDED.first_outcome,
 outcome_time=EXCLUDED.outcome_time,pe_exit_price=EXCLUDED.pe_exit_price,pe_return_pct=EXCLUDED.pe_return_pct,
 pe_eod_price=EXCLUDED.pe_eod_price,pe_eod_return_pct=EXCLUDED.pe_eod_return_pct,
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

def fetch_daily(key, to_day, days=40):
    # V3 days/1 endpoint over a broad lookback.
    from_day = to_day - timedelta(days=90)
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

def wilder_atr(daily, period=14):
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

def demand_zone(day_open, atr, prev_close):
    ann=atr/prev_close*SQRT252*100
    ev=D_SLOPE*ann + D_INTERCEPT
    p=round(day_open)
    sigma=p*ev/(100*SQRT252)
    ws=round(sigma/4)
    low=round(p-sigma-ws/2)
    high=round(p-sigma+ws/2)
    return low,high

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
    return dict(study_start=START,study_end=END,run_id=RUN_ID,trading_date=day,symbol=sym,
      spot_instrument_key=key,day_open=None,atr14=None,prev_close=None,strong_demand_low=None,strong_demand_high=None,
      breakdown_1015=False,breakdown_close=None,breakdown_pct=None,anchor_0915_high=None,avwap_at_1015=None,
      retrace_found=False,retrace_time=None,retrace_high=None,avwap_at_retrace=None,
      spot_entry_found=False,spot_entry_time=None,spot_entry_price=None,avwap_at_entry=None,
      spot_target_price=None,spot_stop_price=None,atm_strike=None,option_expiry=None,pe_instrument_key=None,ce_instrument_key=None,
      option_entry_found=False,option_entry_time=None,option_entry_score=None,pe_entry_price=None,ce_price_at_option_entry=None,
      first_outcome=None,outcome_time=None,pe_exit_price=None,pe_return_pct=None,pe_eod_price=None,pe_eod_return_pct=None,
      data_status="OK",error_message=None)

def process(sym,key,day):
    z=blank(sym,key,day)
    spot=fetch_1m(key,day)
    market=[r for r in spot if dtime(9,15)<=r["ts"].time().replace(tzinfo=None)<dtime(15,30)]
    if not market: raise ValueError("no spot 1m history")

    daily=fetch_daily(key,day-timedelta(days=1))
    prev=[r for r in daily if r["day"]<day]
    if len(prev)<15: raise ValueError("insufficient daily history")
    atr=wilder_atr(prev)
    prev_close=prev[-1]["close"]
    day_open=market[0]["open"]
    dl,dh=demand_zone(day_open,atr,prev_close)
    z.update(day_open=day_open,atr14=atr,prev_close=prev_close,strong_demand_low=dl,strong_demand_high=dh)

    first_hour=[r for r in market if dtime(9,15)<=r["ts"].time().replace(tzinfo=None)<dtime(10,15)]
    if not first_hour: return z
    close1015=first_hour[-1]["close"]
    z["breakdown_close"]=close1015
    z["breakdown_1015"]=close1015<dl
    z["breakdown_pct"]=(close1015/dl-1)*100 if dl else None
    if not z["breakdown_1015"]: return z

    bars=calc_avwap(build_3m(market))
    if not bars: return z
    z["anchor_0915_high"]=bars[0]["high"]
    av1015=[b for b in bars if b["end"]<=datetime.combine(day,dtime(10,15),IST)]
    if av1015: z["avwap_at_1015"]=av1015[-1]["avwap"]

    retrace=None; entry=None
    ten15=datetime.combine(day,dtime(10,15),IST)
    cutoff=datetime.combine(day,ENTRY_CUTOFF,IST)
    for b in bars:
        if b["end"]<=ten15: continue
        if b["end"]>cutoff: break
        if retrace is None and b["high"]>=b["avwap"]:
            retrace=b
            z.update(retrace_found=True,retrace_time=b["end"],retrace_high=b["high"],avwap_at_retrace=b["avwap"])
            continue
        if retrace is not None and b["end"]>retrace["end"] and b["close"]<b["avwap"]:
            entry=b; break
    if entry is None: return z

    spot_entry_time=entry["end"]; spot_entry_price=entry["close"]
    target=spot_entry_price*(1-TARGET_PCT/100)
    stop=spot_entry_price*(1+STOP_PCT/100)
    z.update(spot_entry_found=True,spot_entry_time=spot_entry_time,spot_entry_price=spot_entry_price,
             avwap_at_entry=entry["avwap"],spot_target_price=target,spot_stop_price=stop)

    expiry,pair=pick_atm_pair(key,day,spot_entry_price)
    ce=option_1m(pair["CE"],day); pe=option_1m(pair["PE"],day)
    z.update(atm_strike=pair["PE"]["strike"],option_expiry=expiry,pe_instrument_key=pair["PE"]["key"],ce_instrument_key=pair["CE"]["key"])
    ce_post=[r for r in ce if r["ts"]>=spot_entry_time]
    pe_post=[r for r in pe if r["ts"]>=spot_entry_time]
    if not ce_post or not pe_post: raise ValueError("option history missing after spot entry")

    ce0,pe0=ce_post[0],pe_post[0]
    option_entry=None
    for minute in range(0,OPTION_SCORE_WINDOW_MIN+1):
        t=spot_entry_time+timedelta(minutes=minute)
        cr=nearest_row([r for r in ce_post if r["ts"]<=t],t)
        pr=nearest_row([r for r in pe_post if r["ts"]<=t],t)
        if not cr or not pr: continue
        score=sum([
            pr["close"]>pe0["close"],       # PE premium up
            pr["oi"]<pe0["oi"],             # PE OI down
            cr["close"]<ce0["close"],       # CE premium down
            cr["oi"]>ce0["oi"],             # CE OI up
        ])
        if score>=OPTION_SCORE_MIN:
            option_entry=(max(cr["ts"],pr["ts"]),score,cr,pr)
            break
    if option_entry is None: return z

    ot,score,cr,pr=option_entry
    pe_entry=pr["close"]
    z.update(option_entry_found=True,option_entry_time=ot,option_entry_score=score,
             pe_entry_price=pe_entry,ce_price_at_option_entry=cr["close"])

    # Executable outcome only AFTER option entry; levels remain anchored to original spot entry.
    post=[r for r in market if r["ts"]>=ot]
    outcome="NEITHER"; outcome_time=None
    for r in post:
        hit_t=r["low"]<=target
        hit_s=r["high"]>=stop
        if hit_t and hit_s:
            outcome="AMBIGUOUS_SAME_1M_BAR"; outcome_time=r["ts"]+timedelta(minutes=1); break
        if hit_t:
            outcome="TARGET_FIRST"; outcome_time=r["ts"]+timedelta(minutes=1); break
        if hit_s:
            outcome="STOP_FIRST"; outcome_time=r["ts"]+timedelta(minutes=1); break

    pe_eod=pe_post[-1]["close"]
    z["pe_eod_price"]=pe_eod
    z["pe_eod_return_pct"]=(pe_eod/pe_entry-1)*100 if pe_entry else None
    z["first_outcome"]=outcome
    z["outcome_time"]=outcome_time

    if outcome_time:
        px=nearest_row(pe_post,outcome_time)
        if px:
            z["pe_exit_price"]=px["close"]
            z["pe_return_pct"]=(px["close"]/pe_entry-1)*100 if pe_entry else None
    else:
        z["pe_exit_price"]=pe_eod
        z["pe_return_pct"]=z["pe_eod_return_pct"]
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
            if i%25==0: time.sleep(.15)

    if rows:
        with db() as c:
            with c.cursor() as x: x.executemany(UPSERT,rows)
            c.commit()

    qcount="""
    SELECT
      COUNT(DISTINCT symbol) symbols,
      COUNT(*) FILTER(WHERE breakdown_1015) breakdowns,
      COUNT(*) FILTER(WHERE spot_entry_found) spot_entries,
      COUNT(*) FILTER(WHERE option_entry_found) option_entries,
      COUNT(*) FILTER(WHERE option_entry_found AND first_outcome='TARGET_FIRST') target_first,
      COUNT(*) FILTER(WHERE option_entry_found AND first_outcome='STOP_FIRST') stop_first,
      COUNT(*) FILTER(WHERE option_entry_found AND first_outcome='NEITHER') neither,
      ROUND(SUM(pe_return_pct) FILTER(WHERE option_entry_found),2) cumulative_pct_points,
      ROUND(AVG(pe_return_pct) FILTER(WHERE option_entry_found),2) avg_pe_return_pct,
      ROUND(PERCENTILE_CONT(.5) WITHIN GROUP(ORDER BY pe_return_pct)
            FILTER(WHERE option_entry_found)::numeric,2) median_pe_return_pct
    FROM public.spot_demand_1015_avwap_pe_backtest
    WHERE study_start=%s AND study_end=%s
    """
    with db() as c:
        with c.cursor() as x:
            x.execute(qcount,(START,END)); s=dict(x.fetchone())

    summary={**s,"failed":failed,
      "mirror_rule":{
        "breakdown":"09:15-10:15 spot close below Strong Demand Low",
        "avwap_anchor_context":"09:15 3-minute HIGH; AVWAP accumulated from 09:15",
        "retrace":"later 3m high touches/crosses AVWAP",
        "spot_entry":"first later completed 3m close below AVWAP by 12:15",
        "option_score":"PE premium up + PE OI down + CE premium down + CE OI up",
        "option_entry":"first score >=3 within 15m",
        "target":"spot -0.5% from spot entry",
        "stop":"spot +0.5% from spot entry",
        "exit":"100% ATM PE when target or stop occurs first; neither -> EOD"
      }}
    qs="""INSERT INTO public.spot_demand_1015_avwap_pe_summary
    (study_start,study_end,run_id,symbols,breakdowns,spot_entries,option_entries,target_first,stop_first,neither,failed,summary)
    VALUES(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
    ON CONFLICT(study_start,study_end) DO UPDATE SET
      run_id=EXCLUDED.run_id,generated_at=NOW(),symbols=EXCLUDED.symbols,breakdowns=EXCLUDED.breakdowns,
      spot_entries=EXCLUDED.spot_entries,option_entries=EXCLUDED.option_entries,target_first=EXCLUDED.target_first,
      stop_first=EXCLUDED.stop_first,neither=EXCLUDED.neither,failed=EXCLUDED.failed,summary=EXCLUDED.summary"""
    with db() as c:
        with c.cursor() as x:
            x.execute(qs,(START,END,RUN_ID,s["symbols"],s["breakdowns"],s["spot_entries"],s["option_entries"],
                          s["target_first"],s["stop_first"],s["neither"],failed,Jsonb(summary)))
        c.commit()
    log("COMPLETE")
    log(str(summary))

if __name__=="__main__":
    main()
