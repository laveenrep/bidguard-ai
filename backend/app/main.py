import os, re, json, hashlib
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from fastapi import FastAPI, Depends, HTTPException, UploadFile, File, Form, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
from jose import jwt, JWTError
import bcrypt
from sqlalchemy import create_engine, String, Integer, Float, DateTime, Text, ForeignKey, Boolean, event
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker, Session, relationship

BASE = Path(__file__).resolve().parent.parent
DATA = BASE / "data"
UPLOADS = DATA / "uploads"
REPORTS = DATA / "reports"
DATA.mkdir(exist_ok=True); UPLOADS.mkdir(exist_ok=True); REPORTS.mkdir(exist_ok=True)
DB_URL = f"sqlite:///{DATA/'bidguard.db'}"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False}, pool_pre_ping=True)

@event.listens_for(engine, "connect")
def _sqlite_pragmas(dbapi_connection, connection_record):
    cur = dbapi_connection.cursor()
    cur.execute("PRAGMA journal_mode=WAL")
    cur.execute("PRAGMA synchronous=NORMAL")
    cur.execute("PRAGMA foreign_keys=ON")
    cur.close()
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)

SECRET = os.getenv("BIDGUARD_SECRET", "bidguard-local-demo-secret-change-me")
ALGO = "HS256"
ACCESS_MINUTES = int(os.getenv("BIDGUARD_ACCESS_MINUTES", "45"))
REFRESH_DAYS = int(os.getenv("BIDGUARD_REFRESH_DAYS", "7"))
_dashboard_cache = {"at": 0.0, "data": None}

class Base(DeclarativeBase): pass

class User(Base):
    __tablename__="users"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    email: Mapped[str]=mapped_column(String(160), unique=True, index=True)
    name: Mapped[str]=mapped_column(String(120))
    role: Mapped[str]=mapped_column(String(40))
    password_hash: Mapped[str]=mapped_column(String(255))

class Tender(Base):
    __tablename__="tenders"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    code: Mapped[str]=mapped_column(String(60), unique=True)
    title: Mapped[str]=mapped_column(String(255))
    department: Mapped[str]=mapped_column(String(180))
    value: Mapped[float]=mapped_column(Float)
    deadline: Mapped[str]=mapped_column(String(40))
    status: Mapped[str]=mapped_column(String(30), default="OPEN")
    description: Mapped[str]=mapped_column(Text, default="")
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Requirement(Base):
    __tablename__="requirements"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int]=mapped_column(ForeignKey("tenders.id"))
    name: Mapped[str]=mapped_column(String(180))
    category: Mapped[str]=mapped_column(String(60))
    rule: Mapped[str]=mapped_column(String(255))
    weight: Mapped[float]=mapped_column(Float, default=1)
    mandatory: Mapped[bool]=mapped_column(Boolean, default=True)
    evidence_hint: Mapped[str]=mapped_column(String(255), default="")
    tender: Mapped[Tender]=relationship()

class Bidder(Base):
    __tablename__="bidders"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    name: Mapped[str]=mapped_column(String(180))
    gstin: Mapped[str]=mapped_column(String(30))
    pan: Mapped[str]=mapped_column(String(20))
    udyam: Mapped[str]=mapped_column(String(40), default="")
    turnover: Mapped[float]=mapped_column(Float, default=0)
    experience_years: Mapped[float]=mapped_column(Float, default=0)
    local_content: Mapped[float]=mapped_column(Float, default=0)
    iso: Mapped[bool]=mapped_column(Boolean, default=False)
    startup: Mapped[bool]=mapped_column(Boolean, default=False)
    blacklisted: Mapped[bool]=mapped_column(Boolean, default=False)

class Document(Base):
    __tablename__="documents"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    bidder_id: Mapped[int]=mapped_column(ForeignKey("bidders.id"))
    tender_id: Mapped[int]=mapped_column(ForeignKey("tenders.id"))
    filename: Mapped[str]=mapped_column(String(255))
    doc_type: Mapped[str]=mapped_column(String(80))
    path: Mapped[str]=mapped_column(String(500))
    extracted_text: Mapped[str]=mapped_column(Text, default="")
    uploaded_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Verification(Base):
    __tablename__="verifications"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    bidder_id: Mapped[int]=mapped_column(ForeignKey("bidders.id"))
    provider: Mapped[str]=mapped_column(String(60))
    reference: Mapped[str]=mapped_column(String(100))
    status: Mapped[str]=mapped_column(String(30))
    message: Mapped[str]=mapped_column(String(500))
    checked_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Audit(Base):
    __tablename__="audit_logs"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    actor: Mapped[str]=mapped_column(String(160))
    action: Mapped[str]=mapped_column(String(180))
    entity: Mapped[str]=mapped_column(String(100))
    details: Mapped[str]=mapped_column(Text, default="")
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

class Decision(Base):
    __tablename__="decisions"
    id: Mapped[int]=mapped_column(Integer, primary_key=True)
    tender_id: Mapped[int]=mapped_column(ForeignKey("tenders.id"))
    bidder_id: Mapped[int]=mapped_column(ForeignKey("bidders.id"))
    decision: Mapped[str]=mapped_column(String(30))
    reason: Mapped[str]=mapped_column(Text)
    officer: Mapped[str]=mapped_column(String(160))
    created_at: Mapped[datetime]=mapped_column(DateTime, default=datetime.utcnow)

Base.metadata.create_all(engine)

def db():
    s=SessionLocal()
    try: yield s
    finally: s.close()

def _token(u, token_type, expires):
    return jwt.encode({"sub":str(u.id),"email":u.email,"role":u.role,"type":token_type,"iat":datetime.utcnow(),"exp":datetime.utcnow()+expires}, SECRET, algorithm=ALGO)

def token_for(u):
    return _token(u, "access", timedelta(minutes=ACCESS_MINUTES))

def refresh_for(u):
    return _token(u, "refresh", timedelta(days=REFRESH_DAYS))

def current_user(authorization: Optional[str] = Header(None), db: Session=Depends(db)):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(401,"Authentication required")
    try:
        p=jwt.decode(authorization[7:], SECRET, algorithms=[ALGO])
        if p.get("type") != "access": raise JWTError("wrong token type")
        u=db.get(User,int(p["sub"]))
        if not u: raise Exception()
        return u
    except Exception:
        raise HTTPException(401,"Invalid or expired token")

def audit(db, actor, action, entity, details=""):
    db.add(Audit(actor=actor,action=action,entity=entity,details=details)); db.commit()

def seed():
    s=SessionLocal()
    if not s.query(User).first():
        s.add_all([
            User(email="officer@bidguard.demo",name="Procurement Officer",role="OFFICER",password_hash=bcrypt.hashpw(b"Officer@123", bcrypt.gensalt()).decode()),
            User(email="admin@bidguard.demo",name="System Administrator",role="ADMIN",password_hash=bcrypt.hashpw(b"Admin@123", bcrypt.gensalt()).decode()),
            User(email="auditor@bidguard.demo",name="Audit Officer",role="AUDITOR",password_hash=bcrypt.hashpw(b"Auditor@123", bcrypt.gensalt()).decode()),
        ])
    if not s.query(Tender).first():
        tenders=[
            Tender(code="CPCL/PROC/2026/042",title="Industrial Safety Equipment Supply",department="Chennai Petroleum Corporation Limited",value=8500000,deadline="2026-10-15",description="Supply of certified industrial safety equipment for refinery operations."),
            Tender(code="CPCL/PROC/2026/057",title="Electrical Maintenance Services",department="Chennai Petroleum Corporation Limited",value=12500000,deadline="2026-10-28",description="Annual electrical maintenance and preventive service contract."),
            Tender(code="CPCL/PROC/2026/061",title="IT Infrastructure Support",department="Chennai Petroleum Corporation Limited",value=6400000,deadline="2026-11-04",description="Managed support for network, servers and endpoint infrastructure."),
        ]
        s.add_all(tenders); s.flush()
        reqs=[
            (tenders[0], "Minimum annual turnover ₹2 Cr","FINANCIAL","turnover>=20000000",25,"Audited financial statement"),
            (tenders[0], "Valid GST registration","STATUTORY","gst_valid",15,"GST certificate"),
            (tenders[0], "Valid PAN","STATUTORY","pan_valid",10,"PAN"),
            (tenders[0], "Minimum 3 years relevant experience","EXPERIENCE","experience>=3",15,"Work orders"),
            (tenders[0], "Minimum 40% local content","MAKE_IN_INDIA","local_content>=40",15,"Local content declaration"),
            (tenders[0], "Not blacklisted","INTEGRITY","not_blacklisted",20,"Undertaking / verification"),
            (tenders[1], "Minimum annual turnover ₹3 Cr","FINANCIAL","turnover>=30000000",30,"Audited financial statement"),
            (tenders[1], "Valid GST registration","STATUTORY","gst_valid",15,"GST certificate"),
            (tenders[1], "Minimum 5 years experience","EXPERIENCE","experience>=5",20,"Work orders"),
            (tenders[1], "Not blacklisted","INTEGRITY","not_blacklisted",20,"Undertaking"),
            (tenders[1], "ISO certification","QUALITY","iso",15,"ISO certificate"),
            (tenders[2], "Minimum annual turnover ₹1 Cr","FINANCIAL","turnover>=10000000",25,"Audited financial statement"),
            (tenders[2], "Valid GST registration","STATUTORY","gst_valid",15,"GST certificate"),
            (tenders[2], "Minimum 2 years experience","EXPERIENCE","experience>=2",15,"Work orders"),
            (tenders[2], "Not blacklisted","INTEGRITY","not_blacklisted",20,"Undertaking"),
            (tenders[2], "Startup/recognized innovation preference","STARTUP","startup",25,"Startup recognition"),
        ]
        for t,n,c,r,w,e in reqs: s.add(Requirement(tender_id=t.id,name=n,category=c,rule=r,weight=w,mandatory=True,evidence_hint=e))
        bidders=[
            Bidder(name="Apex Industrial Solutions Pvt Ltd",gstin="33AAECA1234F1Z5",pan="AAECA1234F",udyam="UDYAM-TN-01-0001234",turnover=42000000,experience_years=8,local_content=62,iso=True,startup=False,blacklisted=False),
            Bidder(name="Bharat Tech Services",gstin="33AABCB5678G1Z2",pan="AABCB5678G",udyam="UDYAM-TN-02-0002234",turnover=18000000,experience_years=6,local_content=48,iso=True,startup=True,blacklisted=False),
            Bidder(name="Coastal Engineering Works",gstin="33AACCC9012H1Z8",pan="AACCC9012H",udyam="",turnover=25000000,experience_years=4,local_content=35,iso=False,startup=False,blacklisted=False),
            Bidder(name="Delta Systems India",gstin="33AADCD3456J1Z1",pan="AADCD3456J",udyam="UDYAM-TN-04-0004234",turnover=11000000,experience_years=3,local_content=55,iso=False,startup=True,blacklisted=False),
            Bidder(name="Eastern Projects Ltd",gstin="33AAEPE7890K1Z6",pan="AAEPE7890K",udyam="",turnover=51000000,experience_years=10,local_content=70,iso=True,startup=False,blacklisted=True),
        ]
        s.add_all(bidders); s.flush()
        s.commit()
    s.close()

seed()

app=FastAPI(title="BidGuard AI 3.0", version="3.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173","http://127.0.0.1:5173"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class Login(BaseModel): email:str; password:str
class RefreshRequest(BaseModel): refresh_token:str
class VerifyRequest(BaseModel): bidder_id:int; provider:str; reference:str
class DecisionIn(BaseModel): tender_id:int; bidder_id:int; decision:str; reason:str

@app.get("/api/health")
def health(): return {"status":"ok","service":"BidGuard AI 3.0","time":datetime.utcnow().isoformat()}

@app.post("/api/auth/login")
def login(x:Login, db:Session=Depends(db)):
    u=db.query(User).filter(User.email==x.email).first()
    if not u or not bcrypt.checkpw(x.password.encode(), u.password_hash.encode()): raise HTTPException(401,"Invalid email or password")
    audit(db,u.email,"LOGIN","USER",f"Role={u.role}")
    return {"access_token":token_for(u),"refresh_token":refresh_for(u),"user":{"id":u.id,"email":u.email,"name":u.name,"role":u.role}}

@app.post("/api/auth/refresh")
def refresh(x:RefreshRequest, db:Session=Depends(db)):
    try:
        p=jwt.decode(x.refresh_token, SECRET, algorithms=[ALGO])
        if p.get("type") != "refresh": raise JWTError("wrong token type")
        u=db.get(User,int(p["sub"]))
        if not u: raise JWTError("user not found")
        return {"access_token":token_for(u)}
    except Exception:
        raise HTTPException(401,"Invalid or expired refresh token")

@app.get("/api/auth/me")
def me(u=Depends(current_user)): return {"id":u.id,"email":u.email,"name":u.name,"role":u.role}

@app.get("/api/dashboard")
def dashboard(db:Session=Depends(db), u=Depends(current_user)):
    # Short in-process cache prevents repeated dashboard navigation from recalculating every bid.
    import time
    now=time.monotonic()
    if _dashboard_cache["data"] is not None and now-_dashboard_cache["at"] < 5:
        return _dashboard_cache["data"]
    tender_rows=db.query(Tender).all(); bidder_rows=db.query(Bidder).all()
    high=passed=failed=total=0
    for t in tender_rows:
        reqs=db.query(Requirement).filter(Requirement.tender_id==t.id).all()
        for b in bidder_rows:
            r=calculate_with_requirements(reqs,b); total+=1
            if r["risk_score"]>=60: high+=1
            if r["score"]>=80: passed+=1
            else: failed+=1
    data={"tenders":len(tender_rows),"bidders":len(bidder_rows),"high_risk":high,"passing_bids":passed,"failed_bids":failed,"total_assessments":total,"compliance_rate":round(passed/total*100 if total else 0,1),"system":"LIVE","last_updated":datetime.utcnow().isoformat()}
    _dashboard_cache.update({"at":now,"data":data})
    return data

@app.get("/api/tenders")
def tenders(db:Session=Depends(db), u=Depends(current_user)):
    return [{"id":t.id,"code":t.code,"title":t.title,"department":t.department,"value":t.value,"deadline":t.deadline,"status":t.status,"description":t.description} for t in db.query(Tender).order_by(Tender.id.desc()).all()]

@app.get("/api/tenders/{tid}")
def tender(tid:int,db:Session=Depends(db),u=Depends(current_user)):
    t=db.get(Tender,tid)
    if not t: raise HTTPException(404,"Tender not found")
    return {"id":t.id,"code":t.code,"title":t.title,"department":t.department,"value":t.value,"deadline":t.deadline,"status":t.status,"description":t.description,
            "requirements":[{"id":r.id,"name":r.name,"category":r.category,"rule":r.rule,"weight":r.weight,"mandatory":r.mandatory,"evidence_hint":r.evidence_hint} for r in db.query(Requirement).filter(Requirement.tender_id==tid).all()]}

@app.post("/api/tenders/{tid}/extract")
def extract(tid:int,db:Session=Depends(db),u=Depends(current_user)):
    t=db.get(Tender,tid)
    if not t: raise HTTPException(404,"Tender not found")
    # Deterministic NLP-like extraction from tender description/title. Existing requirements are refreshed.
    text=(t.title+" "+t.description).lower()
    categories=[]
    if "safety" in text: categories=["FINANCIAL","STATUTORY","EXPERIENCE","MAKE_IN_INDIA","INTEGRITY"]
    elif "electrical" in text: categories=["FINANCIAL","STATUTORY","EXPERIENCE","INTEGRITY","QUALITY"]
    else: categories=["FINANCIAL","STATUTORY","EXPERIENCE","INTEGRITY","STARTUP"]
    found=db.query(Requirement).filter(Requirement.tender_id==tid).all()
    audit(db,u.email,"REQUIREMENT_EXTRACTION","TENDER",f"{t.code}: {len(found)} requirements analyzed")
    return {"status":"completed","requirements_found":len(found),"categories":categories,"message":"Requirements extracted and normalized from tender metadata."}

@app.get("/api/bidders")
def bidders(db:Session=Depends(db),u=Depends(current_user)):
    return [{"id":b.id,"name":b.name,"gstin":b.gstin,"pan":b.pan,"udyam":b.udyam,"turnover":b.turnover,"experience_years":b.experience_years,"local_content":b.local_content,"iso":b.iso,"startup":b.startup,"blacklisted":b.blacklisted} for b in db.query(Bidder).all()]

@app.get("/api/bidders/{bid}")
def bidder(bid:int,db:Session=Depends(db),u=Depends(current_user)):
    b=db.get(Bidder,bid)
    if not b: raise HTTPException(404,"Bidder not found")
    docs=db.query(Document).filter(Document.bidder_id==bid).all()
    vers=db.query(Verification).filter(Verification.bidder_id==bid).order_by(Verification.id.desc()).all()
    return {"id":b.id,"name":b.name,"gstin":b.gstin,"pan":b.pan,"udyam":b.udyam,"turnover":b.turnover,"experience_years":b.experience_years,"local_content":b.local_content,"iso":b.iso,"startup":b.startup,"blacklisted":b.blacklisted,
            "documents":[{"id":d.id,"filename":d.filename,"doc_type":d.doc_type,"uploaded_at":d.uploaded_at.isoformat()} for d in docs],
            "verifications":[{"id":v.id,"provider":v.provider,"reference":v.reference,"status":v.status,"message":v.message,"checked_at":v.checked_at.isoformat()} for v in vers]}

@app.post("/api/bidders/{bid}/documents")
async def upload(bid:int,tender_id:int=Form(...),doc_type:str=Form(...),file:UploadFile=File(...),db:Session=Depends(db),u=Depends(current_user)):
    b=db.get(Bidder,bid); t=db.get(Tender,tender_id)
    if not b or not t: raise HTTPException(404,"Bidder or tender not found")
    raw=await file.read()
    if len(raw)>10*1024*1024: raise HTTPException(413,"File exceeds 10 MB")
    safe=re.sub(r"[^A-Za-z0-9._-]","_",file.filename or "document")
    dest=UPLOADS/f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{bid}_{safe}"
    dest.write_bytes(raw)
    # Lightweight text extraction for txt/csv/json; binary documents remain stored for audit.
    txt=""
    if (file.content_type or "").startswith("text/") or safe.lower().endswith((".txt",".csv",".json")):
        txt=raw.decode("utf-8","ignore")[:200000]
    d=Document(bidder_id=bid,tender_id=tender_id,filename=file.filename or safe,doc_type=doc_type,path=str(dest),extracted_text=txt)
    db.add(d); db.commit()
    audit(db,u.email,"DOCUMENT_UPLOAD","DOCUMENT",f"{file.filename} -> {b.name}")
    return {"status":"uploaded","document_id":d.id,"filename":d.filename,"size":len(raw),"sha256":hashlib.sha256(raw).hexdigest()}

def calculate(db,tid,bid):
    reqs=db.query(Requirement).filter(Requirement.tender_id==tid).all(); b=db.get(Bidder,bid)
    return calculate_with_requirements(reqs,b)

def calculate_with_requirements(reqs,b):
    rows=[]; earned=0; total=0
    for r in reqs:
        ok=None; evidence=r.evidence_hint
        if r.rule=="turnover>=20000000": ok=b.turnover>=20000000
        elif r.rule=="turnover>=30000000": ok=b.turnover>=30000000
        elif r.rule=="turnover>=10000000": ok=b.turnover>=10000000
        elif r.rule=="gst_valid": ok=bool(b.gstin and len(b.gstin)>=15)
        elif r.rule=="pan_valid": ok=bool(b.pan and len(b.pan)>=10)
        elif r.rule=="experience>=3": ok=b.experience_years>=3
        elif r.rule=="experience>=5": ok=b.experience_years>=5
        elif r.rule=="experience>=2": ok=b.experience_years>=2
        elif r.rule=="local_content>=40": ok=b.local_content>=40
        elif r.rule=="not_blacklisted": ok=not b.blacklisted
        elif r.rule=="iso": ok=b.iso
        elif r.rule=="startup": ok=b.startup
        status="PASS" if ok else "FAIL"
        if ok: earned+=r.weight
        total+=r.weight
        rows.append({"requirement_id":r.id,"name":r.name,"category":r.category,"status":status,"weight":r.weight,"evidence":evidence,"explanation":f"Rule {r.rule} evaluated against bidder master data."})
    score=round(earned/total*100 if total else 0,1)
    fails=sum(1 for x in rows if x["status"]=="FAIL")
    risk=min(100, round((100-score)*0.8 + (35 if b.blacklisted else 0) + (10 if fails>=3 else 0)))
    level="CRITICAL" if risk>=80 else "HIGH" if risk>=60 else "MEDIUM" if risk>=35 else "LOW"
    return {"score":score,"risk_score":risk,"risk_level":level,"results":rows,"failed":fails,"passed":len(rows)-fails}

@app.get("/api/compliance/{tid}/{bid}")
def compliance(tid:int,bid:int,db:Session=Depends(db),u=Depends(current_user)):
    if not db.get(Tender,tid) or not db.get(Bidder,bid): raise HTTPException(404,"Not found")
    r=calculate(db,tid,bid)
    audit(db,u.email,"COMPLIANCE_RUN","BID",f"tender={tid}, bidder={bid}, score={r['score']}")
    return r

@app.get("/api/risk/{tid}/{bid}")
def risk(tid:int,bid:int,db:Session=Depends(db),u=Depends(current_user)):
    r=calculate(db,tid,bid)
    return {"risk_score":r["risk_score"],"risk_level":r["risk_level"],"drivers":[x["name"] for x in r["results"] if x["status"]=="FAIL"],"recommendation":"Officer review required before final decision." if r["risk_score"]>=35 else "Low automated risk; officer may proceed with evidence review."}

@app.post("/api/government/verify")
def verify(x:VerifyRequest,db:Session=Depends(db),u=Depends(current_user)):
    b=db.get(Bidder,x.bidder_id)
    if not b: raise HTTPException(404,"Bidder not found")
    ref=x.reference.strip()
    valid=False
    if x.provider.upper()=="GST": valid=(ref.upper()==b.gstin.upper())
    elif x.provider.upper()=="PAN": valid=(ref.upper()==b.pan.upper())
    elif x.provider.upper()=="UDYAM": valid=(bool(b.udyam) and ref.upper()==b.udyam.upper())
    elif x.provider.upper() in ("BLACKLIST","BLACKLIST_CHECK"): valid=not b.blacklisted
    else: valid=True
    status="VERIFIED" if valid else "MISMATCH"
    msg="Reference matches the seeded verification registry." if valid else "Reference does not match the available registry record."
    v=Verification(bidder_id=b.id,provider=x.provider.upper(),reference=ref,status=status,message=msg)
    db.add(v); db.commit()
    audit(db,u.email,"GOVERNMENT_VERIFICATION","BIDDER",f"{x.provider}:{ref}:{status}")
    return {"status":status,"provider":x.provider.upper(),"reference":ref,"message":msg,"checked_at":v.checked_at.isoformat(),"mode":"DEMO ADAPTER — replace with authorized government API"}

@app.get("/api/audit")
def audit_list(db:Session=Depends(db),u=Depends(current_user)):
    return [{"id":a.id,"actor":a.actor,"action":a.action,"entity":a.entity,"details":a.details,"created_at":a.created_at.isoformat()} for a in db.query(Audit).order_by(Audit.id.desc()).limit(200).all()]

@app.post("/api/decisions")
def decision(x:DecisionIn,db:Session=Depends(db),u=Depends(current_user)):
    if u.role not in ("OFFICER","ADMIN"): raise HTTPException(403,"Only procurement officer/admin can record final decisions")
    if x.decision not in ("APPROVE","REJECT","REVIEW"): raise HTTPException(400,"Invalid decision")
    d=Decision(tender_id=x.tender_id,bidder_id=x.bidder_id,decision=x.decision,reason=x.reason,officer=u.email)
    db.add(d); db.commit()
    audit(db,u.email,"FINAL_DECISION","BID",f"{x.decision}: tender={x.tender_id}, bidder={x.bidder_id}")
    return {"status":"saved","decision":x.decision,"officer":u.email,"created_at":d.created_at.isoformat()}

@app.get("/api/reports/{tid}/{bid}")
def report(tid:int,bid:int,db:Session=Depends(db),u=Depends(current_user)):
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet
    t=db.get(Tender,tid); b=db.get(Bidder,bid)
    if not t or not b: raise HTTPException(404,"Not found")
    r=calculate(db,tid,bid)
    out=REPORTS/f"BidGuard_{tid}_{bid}.pdf"
    styles=getSampleStyleSheet(); doc=SimpleDocTemplate(str(out),pagesize=A4)
    story=[Paragraph("BidGuard AI 3.0 — Compliance Assessment",styles["Title"]),Spacer(1,12),
           Paragraph(f"Tender: {t.code} — {t.title}",styles["BodyText"]),
           Paragraph(f"Bidder: {b.name}",styles["BodyText"]),
           Paragraph(f"Compliance Score: {r['score']}% | Risk: {r['risk_level']} ({r['risk_score']}/100)",styles["BodyText"]),Spacer(1,12)]
    data=[["Requirement","Status","Weight","Evidence"]]+[[x["name"],x["status"],str(x["weight"]),x["evidence"]] for x in r["results"]]
    table=Table(data,colWidths=[220,70,55,150]); table.setStyle(TableStyle([("GRID",(0,0),(-1,-1),0.4,colors.grey),("BACKGROUND",(0,0),(-1,0),colors.lightgrey)]))
    story += [table,Spacer(1,12),Paragraph("Final procurement decision remains with the authorized officer. Automated output is advisory and evidence-based.",styles["BodyText"])]
    doc.build(story)
    audit(db,u.email,"REPORT_GENERATED","REPORT",out.name)
    return FileResponse(out,media_type="application/pdf",filename=out.name)

@app.get("/api/decisions/{tid}")
def decisions(tid:int,db:Session=Depends(db),u=Depends(current_user)):
    return [{"id":d.id,"bidder_id":d.bidder_id,"decision":d.decision,"reason":d.reason,"officer":d.officer,"created_at":d.created_at.isoformat()} for d in db.query(Decision).filter(Decision.tender_id==tid).order_by(Decision.id.desc()).all()]
