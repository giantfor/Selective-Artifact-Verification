"""Controlled local faults; production SVEC code is unchanged."""
from pathlib import Path
import sys,subprocess,json,time,threading,socket,urllib.request,argparse
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
B=Path(__file__).resolve().parents[1];sys.path.insert(0,str(B/'01-source-code'))
from svec_setup import *
from chain_runtime import with_chain
def write(p,v):Path(p).write_text(json.dumps(v,indent=2))
def free_closed_url():
 s=socket.socket();s.bind(('127.0.0.1',0));p=s.getsockname()[1];s.close();return f'http://127.0.0.1:{p}'
def child(cfgpath,info):
 cfg=json.loads(Path(cfgpath).read_text());a=PolicyAuthority().start();a.register(cfg['ctx'],cfg['ref'],Ed25519PublicKey.from_public_bytes(bytes.fromhex(cfg['gate_public'])))
 write(info,dict(url=a.url,public=rawkey(a.pub)));threading.Event().wait()
def restart_checks(work):
 gk=Ed25519PrivateKey.generate();cfg=work/'restart_public_bootstrap.json';write(cfg,dict(ctx='restart-test',ref='immutable-ref',gate_public=rawkey(gk.public_key())))
 def start(n):
  f=work/f'restart_endpoint_{n}.json';p=subprocess.Popen([sys.executable,'-X','utf8',__file__,'--authority-child',str(cfg),'--info',str(f)],creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
  limit=time.monotonic()+30
  while True:
   try:return p,json.loads(f.read_text())
   except (OSError,json.JSONDecodeError):
    assert p.poll() is None
    if time.monotonic()>limit:p.kill();raise TimeoutError('Authority child')
    time.sleep(.05)
 def proxy(v):return SimpleNamespace(url=v['url'],pub=Ed25519PublicKey.from_public_bytes(bytes.fromhex(v['public'])))
 p,v=start(0);c=PolicyClient(proxy(v),'restart-test',gk);t=c.begin();p.terminate();p.wait(10)
 p,v2=start(1)
 try:
  cases=[];c.url=v2['url']
  for name,client,ticket,expected in [('old trust anchor after process restart',c,t,'SIGNATURE'),('explicitly adopted new anchor, old active ticket',PolicyClient(proxy(v2),'restart-test',gk),t,'TICKET_UNKNOWN')]:
   error=None
   try:client.commit(ticket,'0x'+'11'*32,'0x'+'22'*32)
   except ValueError as e:error=str(e)
   assert error==expected;cases.append(dict(adapter='authority-only',scenario=name,error=error,model_calls=None,released=None,validated_receipt=False,passed=True))
  nc=PolicyClient(proxy(v2),'restart-test',gk);nt=nc.begin();receipt=nc.commit(nt,'0x'+'11'*32,'0x'+'22'*32);assert receipt['ticket']==nt['ticket']
  cases.append(dict(adapter='authority-only',scenario='fresh Begin after explicit new-anchor adoption',error=None,model_calls=None,released=None,validated_receipt=True,passed=True))
  return cases
 finally:p.terminate();p.wait(10)
def faults(state):
 cases=[]
 def trial(kind,name,configure,expected,error,calls):
  g,a=build_gate(state,kind,'selective','toy_data_0');kwargs={};cleanup=[]
  try:
   configure(g,a,kwargs,cleanup);r=g.predict(state['data']['toy_data_0'],**kwargs)
   assert r['released']==expected and r['model_calls']==calls and (error is None or r.get('error')==error),(name,r)
   assert expected or ('score_hash' not in r and 'prediction_hash' not in r)
   cases.append(dict(adapter=kind,scenario=name,error=r.get('error'),model_calls=r['model_calls'],released=r['released'],total_ms=r['total_ms'],validated_receipt=r['released'],passed=True))
  finally:
   for f in cleanup:f()
   a.close()
 for kind in ['ledger','signed']:
  trial(kind,'authority unreachable before Begin',lambda g,a,k,c:setattr(g.client,'url',free_closed_url()),False,'POLICY_UNAVAILABLE',0)
  trial(kind,'authority unreachable before Commit',lambda g,a,k,c:k.update(before_commit=lambda t:setattr(g.client,'url',free_closed_url())),False,'POLICY_UNAVAILABLE',1)
  trial(kind,'epoch publication after computation',lambda g,a,k,c:k.update(before_commit=lambda t:a.publish(g.client.ctx)),False,'POLICY_CHANGED',1)
  trial(kind,'cold registration service unavailable',lambda g,a,k,c:setattr(g.reader,'offline',True),False,'REFERENCE_UNAVAILABLE',0)
  def warm_offline(g,a,k,c):assert g.predict(state['data']['toy_data_0'])['released'];g.reader.offline=True
  trial(kind,'warm immutable proof during registration outage',warm_offline,True,None,1)
  g,a=build_gate(state,kind,'selective','toy_data_0')
  try:
   assert g.predict(state['data']['toy_data_0'])['released'];before=g.counters();a.publish(g.client.ctx,ref=state['byname'][kind]['toy_data_1']);r=g.predict(state['data']['toy_data_1']);after=g.counters()
   assert r['released'] and after['reference_checks']-before['reference_checks']==1 and after['activation_misses']==before['activation_misses']
   cases.append(dict(adapter=kind,scenario='reference change: new proof, reused activation',error=None,model_calls=1,released=True,validated_receipt=True,proof_checks=1,activation_misses=0,passed=True))
   before=g.counters();a.publish(g.client.ctx,ref=state['byname'][kind]['toy_model_1']);r=g.predict(state['data']['toy_model_1']);after=g.counters()
   assert r['released'] and after['activation_misses']-before['activation_misses']==1
   cases.append(dict(adapter=kind,scenario='model/schema revision: new activation',error=None,model_calls=1,released=True,validated_receipt=True,activation_misses=1,passed=True))
  finally:a.close()
 # A real delayed TCP/HTTP proxy forwards every request to the EVM endpoint.
 g,a=build_gate(state,'ledger','selective','toy_data_0');ref=g.reader.catalog[state['byname']['ledger']['toy_data_0']];upstream=ref['anchor']['rpcUrl'];count=[]
 class Proxy(BaseHTTPRequestHandler):
  def do_POST(self):
   b=self.rfile.read(int(self.headers['Content-Length']));time.sleep(.03);count.append(1)
   req=urllib.request.Request(upstream,b,{'Content-Type':'application/json'})
   with urllib.request.urlopen(req,timeout=3) as r:answer=r.read()
   self.send_response(200);self.send_header('Content-Length',str(len(answer)));self.end_headers();self.wfile.write(answer)
  def log_message(self,*a):pass
 server=ThreadingHTTPServer(('127.0.0.1',0),Proxy);threading.Thread(target=server.serve_forever,daemon=True).start();ref['anchor']['rpcUrl']=f'http://127.0.0.1:{server.server_port}'
 try:
  r=g.predict(state['data']['toy_data_0']);assert r['released'] and len(count)==7 and r['total_ms']>=210
  cases.append(dict(adapter='ledger',scenario='30 ms injected delay per RPC read',error=None,model_calls=1,released=True,validated_receipt=True,forwarded_rpc_reads=7,configured_delay_ms=30,elapsed_ms=r['total_ms'],passed=True))
 finally:server.shutdown();server.server_close();a.close()
 return cases
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--authority-child');p.add_argument('--info');p.add_argument('--work',type=Path,default=B/'09-audit-reports/native_work');a=p.parse_args()
 if a.authority_child:child(a.authority_child,a.info)
 else:
  work=a.work.resolve();work.mkdir(parents=True,exist_ok=True);root=work/'fixture'
  assert not root.exists(),'Use fresh work directory'
  subprocess.run([sys.executable,'-X','utf8',str(B/'01-source-code/prepare_svec_fixture.py'),'--out',str(root)],check=True)
  cases=with_chain(root,19920,faults);cases+=restart_checks(work)
  report=dict(scope='Author-operated local technical fixture; controlled harness faults and real HTTP proxy/process restart, not clinical validation or durable recovery',cases=cases,passed=sum(c['passed'] for c in cases),total=len(cases),authority_restart_restores_ticket_state=False,core_algorithm_changed=False)
  write(B/'09-audit-reports/fault_checks.json',report);print('Fault/transition checks',report['passed'],'/',report['total'],flush=True)
