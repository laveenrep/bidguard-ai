import React, {useCallback, useEffect, useMemo, useRef, useState} from "react";
import {createRoot} from "react-dom/client";
import {
  Activity, AlertTriangle, CheckCircle2, ClipboardList, Download, FileText,
  Landmark, LayoutDashboard, LogOut, RefreshCw, Search, ShieldCheck, Upload,
  Users, XCircle, Clock3, LockKeyhole, BarChart3
} from "lucide-react";
import "./style.css";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api";
const TOKEN_KEY = "bg_access_token";
const REFRESH_KEY = "bg_refresh_token";
const USER_KEY = "bg_user";

const readUser = () => {
  try { return JSON.parse(localStorage.getItem(USER_KEY) || "null"); } catch { return null; }
};
const saveSession = (data) => {
  localStorage.setItem(TOKEN_KEY, data.access_token);
  localStorage.setItem(REFRESH_KEY, data.refresh_token);
  localStorage.setItem(USER_KEY, JSON.stringify(data.user));
};
const clearSession = () => {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
};

async function rawFetch(path, options = {}, token = null) {
  const headers = {...(options.body instanceof FormData ? {} : {"Content-Type":"application/json"}), ...(options.headers || {})};
  if (token) headers.Authorization = `Bearer ${token}`;
  return fetch(API + path, {...options, headers});
}

let refreshPromise = null;
async function refreshAccessToken() {
  if (!localStorage.getItem(REFRESH_KEY)) return null;
  if (refreshPromise) return refreshPromise;
  refreshPromise = rawFetch("/auth/refresh", {
    method:"POST",
    body: JSON.stringify({refresh_token: localStorage.getItem(REFRESH_KEY)})
  }).then(async r => {
    if (!r.ok) throw new Error("Session expired");
    const d = await r.json();
    localStorage.setItem(TOKEN_KEY, d.access_token);
    return d.access_token;
  }).catch(() => null).finally(() => { refreshPromise = null; });
  return refreshPromise;
}

async function api(path, options = {}, retry = true) {
  const token = localStorage.getItem(TOKEN_KEY);
  const r = await rawFetch(path, options, token);
  if (r.status === 401 && retry) {
    const fresh = await refreshAccessToken();
    if (fresh) return api(path, options, false);
    clearSession();
    window.dispatchEvent(new Event("bidguard-session-expired"));
    throw new Error("Your session expired. Please sign in again.");
  }
  const type = r.headers.get("content-type") || "";
  if (!r.ok) {
    const body = await r.json().catch(() => ({detail:r.statusText}));
    throw new Error(body.detail || "Request failed");
  }
  return type.includes("application/pdf") ? r.blob() : r.json();
}

function useAsyncLoad(loader, deps = []) {
  const [state, setState] = useState({loading:true, data:null, error:""});
  const run = useCallback(async () => {
    let active = true;
    setState(s => ({...s, loading:true, error:""}));
    try { const data = await loader(); if (active) setState({loading:false,data,error:""}); }
    catch (e) { if (active) setState({loading:false,data:null,error:e.message}); }
    return () => { active = false; };
  }, deps);
  useEffect(() => { let alive = true; loader().then(data => alive && setState({loading:false,data,error:""})).catch(e => alive && setState({loading:false,data:null,error:e.message})); return () => { alive = false; }; }, deps);
  return {...state, reload:run};
}

function Login({onLogin}) {
  const [email,setEmail] = useState("officer@bidguard.demo");
  const [password,setPassword] = useState("Officer@123");
  const [err,setErr] = useState("");
  const [busy,setBusy] = useState(false);
  async function submit(e) {
    e.preventDefault(); setBusy(true); setErr("");
    try {
      const r = await rawFetch("/auth/login", {method:"POST", body:JSON.stringify({email,password})});
      const d = await r.json(); if (!r.ok) throw new Error(d.detail || "Invalid email or password");
      saveSession(d); onLogin(d.user);
    } catch(e) { setErr(e.message); } finally { setBusy(false); }
  }
  return <div className="login"><div className="login-card">
    <div className="brand"><div className="logo">BG</div><div><h1>BidGuard AI</h1><span>Procurement Intelligence Platform · 4.0</span></div></div>
    <h2>Secure sign in</h2><p className="muted">Real-time local application · protected session</p>
    <form onSubmit={submit}>
      <label>Email<input value={email} onChange={e=>setEmail(e.target.value)} autoComplete="username"/></label>
      <label>Password<input type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete="current-password"/></label>
      {err && <div className="error">{err}</div>}
      <button className="primary wide" disabled={busy}>{busy?<><RefreshCw className="spin" size={16}/> Signing in…</>:<><LockKeyhole size={16}/> Sign in</>}</button>
    </form>
    <div className="demo"><b>Demo accounts</b><br/>Officer: officer@bidguard.demo / Officer@123<br/>Admin: admin@bidguard.demo / Admin@123<br/>Auditor: auditor@bidguard.demo / Auditor@123</div>
  </div></div>;
}

function App() {
  const [user,setUser] = useState(readUser);
  const [page,setPage] = useState("dashboard");
  useEffect(() => { const h=()=>setUser(null); window.addEventListener("bidguard-session-expired",h); return ()=>window.removeEventListener("bidguard-session-expired",h); },[]);
  useEffect(() => {
    if (!localStorage.getItem(TOKEN_KEY) || !user) return;
    let alive=true;
    api("/auth/me").then(me=>alive && setUser(me)).catch(()=>{});
    return ()=>{alive=false};
  },[]);
  if (!user || !localStorage.getItem(TOKEN_KEY)) return <Login onLogin={setUser}/>;
  return <Shell user={user} page={page} setPage={setPage} onLogout={()=>{clearSession();setUser(null)}}/>;
}

const nav = [
  ["dashboard","Overview",LayoutDashboard], ["tenders","Tenders",FileText], ["bidders","Bidders",Users],
  ["compliance","Compliance",ShieldCheck], ["risk","Risk Analysis",Activity], ["government","Government Verification",Landmark],
  ["audit","Audit Trail",ClipboardList]
];

function Shell({user,page,setPage,onLogout}) {
  return <div className="app"><aside>
    <div className="brand small"><div className="logo">BG</div><div><b>BidGuard AI</b><small>4.0 · LIVE</small></div></div>
    <div className="nav">{nav.map(([id,name,I])=><button key={id} className={page===id?"active":""} onClick={()=>setPage(id)}><I size={18}/><span>{name}</span></button>)}</div>
    <div className="side-bottom"><div className="user"><div className="avatar">{user.name?.[0] || "U"}</div><div><b>{user.name}</b><small>{user.role}</small></div></div><button onClick={onLogout}><LogOut size={17}/> Sign out</button></div>
  </aside><main><header><div><h2>{nav.find(x=>x[0]===page)?.[1] || "Overview"}</h2><span className="muted">Evidence-first procurement workflow</span></div><div className="header-right"><span className="live"><i/> LIVE DATABASE</span><button className="iconbtn" title="Refresh current page" onClick={()=>window.dispatchEvent(new Event("bidguard-refresh"))}><RefreshCw size={18}/></button></div></header><section className="content"><Page page={page} user={user}/></section></main></div>;
}

function Page({page,user}) {
  if(page==="dashboard") return <Dashboard/>;
  if(page==="tenders") return <Tenders user={user}/>;
  if(page==="bidders") return <Bidders/>;
  if(page==="compliance") return <Compliance user={user}/>;
  if(page==="risk") return <Risk/>;
  if(page==="government") return <Government/>;
  return <Audit/>;
}

function ErrorBox({message}) { return message ? <div className="error"><AlertTriangle size={15}/>{message}</div> : null; }
function Loading(){return <div className="loading"><RefreshCw className="spin"/> Loading live data…</div>}
function Badge({text,bad=false}){return <span className={`badge ${bad?"bad":""}`}>{text}</span>}
function Panel({title,children,action}){return <div className="panel"><div className="panel-head"><h3>{title}</h3>{action}</div>{children}</div>}
function Card({title,value,icon,sub}){return <div className="card"><div className="card-icon">{icon}</div><span>{title}</span><strong>{value}</strong>{sub&&<small>{sub}</small>}</div>}

function Dashboard() {
  const [d,setD]=useState(null),[error,setError]=useState(""),[loading,setLoading]=useState(true);
  const load=useCallback(async()=>{setLoading(true);try{setD(await api("/dashboard"));setError("")}catch(e){setError(e.message)}finally{setLoading(false)}},[]);
  useEffect(()=>{load();const h=()=>load();window.addEventListener("bidguard-refresh",h);return()=>window.removeEventListener("bidguard-refresh",h)},[load]);
  if(loading&&!d)return <Loading/>;
  if(error&&!d)return <ErrorBox message={error}/>;
  return <>
    <ErrorBox message={error}/>
    <div className="cards">
      <Card title="Active Tenders" value={d.tenders} icon={<FileText/>} sub="Open procurement records"/>
      <Card title="Registered Bidders" value={d.bidders} icon={<Users/>} sub="Verified bidder master"/>
      <Card title="Compliance Rate" value={`${d.compliance_rate}%`} icon={<ShieldCheck/>} sub={`${d.passing_bids} passing assessments`}/>
      <Card title="High Risk Bids" value={d.high_risk} icon={<AlertTriangle/>} sub="Risk score ≥ 60"/>
    </div>
    <div className="metric-strip"><div><Clock3/><span>Last refresh</span><b>{new Date(d.last_updated).toLocaleTimeString()}</b></div><div><BarChart3/><span>Assessments</span><b>{d.total_assessments}</b></div><div><CheckCircle2/><span>Passed</span><b>{d.passing_bids}</b></div><div><XCircle/><span>Failed</span><b>{d.failed_bids}</b></div></div>
    <div className="grid2">
      <Panel title="Operational status"><div className="statusbox"><CheckCircle2/><div><b>All core services operational</b><p>FastAPI, SQLite WAL database, compliance engine, audit logging and report generation are connected.</p></div></div><div className="mini-grid"><div><span>API</span><b>ONLINE</b></div><div><span>Database</span><b>SQLITE WAL</b></div><div><span>Auth</span><b>JWT + REFRESH</b></div><div><span>Mode</span><b>LIVE LOCAL</b></div></div></Panel>
      <Panel title="Workflow"><ol className="steps"><li><b>1</b>Select tender and inspect requirements</li><li><b>2</b>Select bidder and upload evidence</li><li><b>3</b>Run compliance and risk assessment</li><li><b>4</b>Verify GST/PAN/Udyam/blacklist references</li><li><b>5</b>Record decision and generate PDF evidence report</li></ol></Panel>
    </div>
  </>;
}

function Tenders({user}) {
  const [ts,setTs]=useState([]),[q,setQ]=useState(""),[sel,setSel]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState("");
  const load=useCallback(async()=>{setLoading(true);try{setTs(await api("/tenders"));setError("")}catch(e){setError(e.message)}finally{setLoading(false)}},[]);
  useEffect(()=>{load();const h=()=>load();window.addEventListener("bidguard-refresh",h);return()=>window.removeEventListener("bidguard-refresh",h)},[load]);
  const filtered=useMemo(()=>ts.filter(t=>(`${t.title} ${t.code} ${t.department}`).toLowerCase().includes(q.toLowerCase())),[ts,q]);
  return <div className="grid-main"><ErrorBox message={error}/><Panel title="Tender register" action={<button onClick={load}><RefreshCw size={15}/> Refresh</button>}>
    <div className="toolbar"><div className="search"><Search size={16}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search tender, code or department…"/></div><span className="muted">{filtered.length} of {ts.length} tenders</span></div>
    {loading?<Loading/>:<div className="tablewrap"><table><thead><tr><th>Reference</th><th>Tender</th><th>Department</th><th>Value</th><th>Deadline</th><th>Status</th></tr></thead><tbody>{filtered.map(t=><tr onClick={()=>setSel(t.id)} className="click" key={t.id}><td><b>{t.code}</b></td><td>{t.title}</td><td>{t.department}</td><td>₹{Number(t.value).toLocaleString("en-IN")}</td><td>{t.deadline}</td><td><Badge text={t.status}/></td></tr>)}</tbody></table></div>}
  </Panel>{sel&&<TenderDetail id={sel} user={user} close={()=>setSel(null)}/>}</div>;
}

function TenderDetail({id,user,close}) {
  const [t,setT]=useState(null),[msg,setMsg]=useState(""),[err,setErr]=useState("");
  useEffect(()=>{let alive=true;api(`/tenders/${id}`).then(x=>alive&&setT(x)).catch(e=>alive&&setErr(e.message));return()=>{alive=false}},[id]);
  if(err)return <Panel title="Tender details"><ErrorBox message={err}/></Panel>;
  if(!t)return <Panel title="Tender details"><Loading/></Panel>;
  async function extract(){try{const x=await api(`/tenders/${id}/extract`,{method:"POST"});setMsg(x.message)}catch(e){setErr(e.message)}}
  return <Panel title={t.title} action={<button onClick={close}>Close</button>}><div className="detail-head"><div><b>{t.code}</b><span>{t.department}</span></div><Badge text={t.status}/></div><p>{t.description}</p><div className="toolbar"><b>{t.requirements.length} requirements</b><button className="primary" onClick={extract}><ShieldCheck size={16}/> Normalize requirements</button></div>{msg&&<div className="success">{msg}</div>}<ErrorBox message={err}/><div className="reqgrid">{t.requirements.map(r=><div className="req" key={r.id}><span>{r.category}</span><b>{r.name}</b><small>Weight {r.weight} · {r.mandatory?"Mandatory":"Optional"} · Evidence: {r.evidence_hint}</small></div>)}</div></Panel>;
}

function Bidders() {
  const [bs,setBs]=useState([]),[q,setQ]=useState(""),[sel,setSel]=useState(null),[loading,setLoading]=useState(true),[error,setError]=useState("");
  const load=useCallback(async()=>{setLoading(true);try{setBs(await api("/bidders"));setError("")}catch(e){setError(e.message)}finally{setLoading(false)}},[]);
  useEffect(()=>{load();return()=>{}},[load]);
  const filtered=useMemo(()=>bs.filter(b=>`${b.name} ${b.gstin} ${b.pan}`.toLowerCase().includes(q.toLowerCase())),[bs,q]);
  return <div className="grid-main"><ErrorBox message={error}/><Panel title="Bidder registry" action={<button onClick={load}><RefreshCw size={15}/> Refresh</button>}><div className="toolbar"><div className="search"><Search size={16}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search bidder, GSTIN or PAN…"/></div><span className="muted">{filtered.length} bidders</span></div>{loading?<Loading/>:<div className="tablewrap"><table><thead><tr><th>Bidder</th><th>GSTIN</th><th>Turnover</th><th>Experience</th><th>Local content</th><th>Flags</th></tr></thead><tbody>{filtered.map(b=><tr className="click" onClick={()=>setSel(b.id)} key={b.id}><td><b>{b.name}</b><small>{b.pan}</small></td><td>{b.gstin}</td><td>₹{Number(b.turnover).toLocaleString("en-IN")}</td><td>{b.experience_years} yrs</td><td>{b.local_content}%</td><td>{b.blacklisted?<Badge text="BLACKLIST FLAG" bad/>:<Badge text="CLEAR"/>}</td></tr>)}</tbody></table></div>}</Panel>{sel&&<BidderDetail id={sel} close={()=>setSel(null)}/>}</div>;
}

function BidderDetail({id,close}) {
  const [b,setB]=useState(null),[tenders,setTenders]=useState([]),[tid,setTid]=useState(""),[file,setFile]=useState(null),[msg,setMsg]=useState(""),[err,setErr]=useState(""),[busy,setBusy]=useState(false);
  const load=useCallback(async()=>{try{const [bd,ts]=await Promise.all([api(`/bidders/${id}`),api("/tenders")]);setB(bd);setTenders(ts);if(!tid&&ts[0])setTid(String(ts[0].id))}catch(e){setErr(e.message)}},[id,tid]);
  useEffect(()=>{load()},[id]);
  if(!b)return <Panel title="Bidder details"><ErrorBox message={err}/><Loading/></Panel>;
  async function upload(){if(!file||!tid)return;setBusy(true);try{const f=new FormData();f.append("file",file);f.append("tender_id",tid);f.append("doc_type","Tender Evidence");const x=await api(`/bidders/${id}/documents`,{method:"POST",body:f});setMsg(`Uploaded ${x.filename}. SHA-256 ${x.sha256.slice(0,24)}…`);setFile(null);setB(await api(`/bidders/${id}`))}catch(e){setErr(e.message)}finally{setBusy(false)}}
  return <Panel title={b.name} action={<button onClick={close}>Close</button>}><div className="detail-head"><div><b>GSTIN {b.gstin}</b><span>PAN {b.pan || "—"} · Udyam {b.udyam || "—"}</span></div>{b.blacklisted?<Badge text="BLACKLIST FLAG" bad/>:<Badge text="CLEAR"/>}</div><div className="facts"><div><span>Turnover</span><b>₹{Number(b.turnover).toLocaleString("en-IN")}</b></div><div><span>Experience</span><b>{b.experience_years} yrs</b></div><div><span>Local content</span><b>{b.local_content}%</b></div><div><span>ISO</span><b>{b.iso?"Yes":"No"}</b></div><div><span>Startup</span><b>{b.startup?"Yes":"No"}</b></div><div><span>Documents</span><b>{b.documents.length}</b></div></div><div className="upload"><select value={tid} onChange={e=>setTid(e.target.value)}>{tenders.map(t=><option key={t.id} value={t.id}>{t.code}</option>)}</select><input type="file" onChange={e=>setFile(e.target.files?.[0]||null)}/><button className="primary" onClick={upload} disabled={!file||busy}><Upload size={15}/>{busy?"Uploading…":"Upload evidence"}</button></div><ErrorBox message={err}/>{msg&&<div className="success">{msg}</div>}<h4>Evidence register</h4><div className="doclist">{b.documents.length?b.documents.map(d=><div key={d.id}><FileText size={15}/><b>{d.filename}</b><small>{d.doc_type} · {new Date(d.uploaded_at).toLocaleString()}</small></div>):<span className="muted">No evidence uploaded yet.</span>}</div></Panel>;
}

function Selectors({onRun,loading}) {
  const [tenders,setTenders]=useState([]),[bidders,setBidders]=useState([]),[tid,setTid]=useState(""),[bid,setBid]=useState("");
  useEffect(()=>{Promise.all([api("/tenders"),api("/bidders")]).then(([t,b])=>{setTenders(t);setBidders(b);setTid(String(t[0]?.id||""));setBid(String(b[0]?.id||""))}).catch(()=>{})},[]);
  return <div className="selectors"><label>Tender<select value={tid} onChange={e=>setTid(e.target.value)}>{tenders.map(t=><option key={t.id} value={t.id}>{t.code} — {t.title}</option>)}</select></label><label>Bidder<select value={bid} onChange={e=>setBid(e.target.value)}>{bidders.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label><button className="primary run" disabled={!tid||!bid||loading} onClick={()=>onRun(Number(tid),Number(bid))}>{loading?<><RefreshCw size={15} className="spin"/> Running…</>:<><ShieldCheck size={15}/> Run assessment</>}</button></div>;
}

function Compliance({user}) {
  const [r,setR]=useState(null),[err,setErr]=useState(""),[busy,setBusy]=useState(false),[selection,setSelection]=useState(null);
  async function run(t,b){setBusy(true);setErr("");try{setSelection({t,b});setR(await api(`/compliance/${t}/${b}`))}catch(e){setErr(e.message)}finally{setBusy(false)}}
  async function decision(decision){if(!selection)return;const reason=window.prompt("Reason for final decision:","Reviewed automated compliance results and evidence.");if(reason===null)return;try{await api("/decisions",{method:"POST",body:JSON.stringify({tender_id:selection.t,bidder_id:selection.b,decision,reason})});alert("Decision saved.")}catch(e){setErr(e.message)}}
  async function report(){if(!selection)return;try{const blob=await api(`/reports/${selection.t}/${selection.b}`);const url=URL.createObjectURL(blob);const a=document.createElement("a");a.href=url;a.download=`BidGuard_${selection.t}_${selection.b}.pdf`;a.click();setTimeout(()=>URL.revokeObjectURL(url),1000)}catch(e){setErr(e.message)}}
  return <><Panel title="Compliance assessment"><Selectors onRun={run} loading={busy}/></Panel><ErrorBox message={err}/>{r&&<Panel title="Assessment result"><div className="scoreline"><div><span>Compliance</span><strong>{r.score}%</strong></div><div><span>Risk score</span><strong>{r.risk_score}/100</strong></div><div><span>Passed</span><strong>{r.passed}</strong></div><div><span>Failed</span><strong>{r.failed}</strong></div></div><div className="tablewrap"><table><thead><tr><th>Requirement</th><th>Category</th><th>Status</th><th>Weight</th><th>Evidence</th></tr></thead><tbody>{r.results.map(x=><tr key={x.requirement_id}><td><b>{x.name}</b><small>{x.explanation}</small></td><td>{x.category}</td><td>{x.status==="PASS"?<Badge text="PASS"/>:<Badge text="FAIL" bad/>}</td><td>{x.weight}</td><td>{x.evidence}</td></tr>)}</tbody></table></div>{(user.role==="OFFICER"||user.role==="ADMIN")&&<div className="decision"><div><h4>Officer decision</h4><p className="muted">Automated assessment is advisory; authorized staff remain responsible for the final procurement decision.</p></div><button onClick={()=>decision("APPROVE")} className="primary">Approve</button><button onClick={()=>decision("REVIEW")}>Review</button><button onClick={()=>decision("REJECT")}>Reject</button><button onClick={report}><Download size={15}/> PDF report</button></div>}</Panel>}</>;
}

function Risk(){const [r,setR]=useState(null),[err,setErr]=useState(""),[busy,setBusy]=useState(false);async function run(t,b){setBusy(true);try{setR(await api(`/risk/${t}/${b}`));setErr("")}catch(e){setErr(e.message)}finally{setBusy(false)}}return <><Panel title="Risk analysis"><Selectors onRun={run} loading={busy}/></Panel><ErrorBox message={err}/>{r&&<Panel title="Risk profile"><div className="riskbox"><div className={`riskcircle ${r.risk_level.toLowerCase()}`}>{r.risk_score}</div><div><h3>{r.risk_level} RISK</h3><p>{r.recommendation}</p><h4>Drivers</h4>{r.drivers.length?r.drivers.map(x=><div className="driver" key={x}><AlertTriangle size={14}/>{x}</div>):<span className="muted">No failed-rule drivers.</span>}</div></div></Panel>}</>}

function Government(){const [bidders,setBidders]=useState([]),[bid,setBid]=useState(""),[provider,setProvider]=useState("GST"),[ref,setRef]=useState(""),[result,setResult]=useState(null),[err,setErr]=useState(""),[busy,setBusy]=useState(false);useEffect(()=>{api("/bidders").then(x=>{setBidders(x);if(x[0]){setBid(String(x[0].id));setRef(x[0].gstin)}}).catch(e=>setErr(e.message))},[]);function syncRef(id,p){const b=bidders.find(x=>x.id===Number(id));if(!b)return;setBid(String(id));setRef(p==="GST"?b.gstin:p==="PAN"?b.pan:p==="UDYAM"?b.udyam:b.blacklisted?"BLACKLIST":"CLEAR")}async function verify(){setBusy(true);try{setResult(await api("/government/verify",{method:"POST",body:JSON.stringify({bidder_id:Number(bid),provider,reference:ref})}));setErr("")}catch(e){setErr(e.message)}finally{setBusy(false)}}return <><Panel title="Government verification"><div className="notice"><Landmark size={17}/><div>This build uses a local deterministic verification adapter. It demonstrates the live workflow but does not claim direct access to government databases.</div></div><div className="selectors"><label>Bidder<select value={bid} onChange={e=>syncRef(e.target.value,provider)}>{bidders.map(b=><option key={b.id} value={b.id}>{b.name}</option>)}</select></label><label>Provider<select value={provider} onChange={e=>{setProvider(e.target.value);syncRef(bid,e.target.value)}}><option>GST</option><option>PAN</option><option>UDYAM</option><option>BLACKLIST</option></select></label><label>Reference<input value={ref} onChange={e=>setRef(e.target.value)}/></label><button className="primary run" onClick={verify} disabled={busy}>{busy?<><RefreshCw className="spin" size={15}/> Checking…</>:"Verify"}</button></div><ErrorBox message={err}/>{result&&<div className={result.status==="VERIFIED"?"verify-ok":"verify-bad"}>{result.status==="VERIFIED"?<CheckCircle2/>:<XCircle/>}<div><b>{result.status}</b><p>{result.message}</p><small>{result.mode}</small></div></div>}</Panel></>}

function Audit(){const [rows,setRows]=useState([]),[q,setQ]=useState(""),[loading,setLoading]=useState(true),[err,setErr]=useState("");const load=useCallback(async()=>{setLoading(true);try{setRows(await api("/audit"));setErr("")}catch(e){setErr(e.message)}finally{setLoading(false)}},[]);useEffect(()=>{load()},[load]);const filtered=useMemo(()=>rows.filter(a=>`${a.actor} ${a.action} ${a.entity} ${a.details}`.toLowerCase().includes(q.toLowerCase())),[rows,q]);return <Panel title="Audit trail" action={<button onClick={load}><RefreshCw size={15}/> Refresh</button>}><div className="toolbar"><div className="search"><Search size={16}/><input value={q} onChange={e=>setQ(e.target.value)} placeholder="Search audit events…"/></div><span className="muted">Latest {filtered.length} events</span></div>{loading?<Loading/>:<div className="timeline">{filtered.map(a=><div key={a.id}><span className="dot"/><div><b>{a.action}</b><span>{a.actor} · {a.entity} · {new Date(a.created_at).toLocaleString()}</span><p>{a.details}</p></div></div>)}</div>}</Panel>}

createRoot(document.getElementById("root")).render(<App/>);
