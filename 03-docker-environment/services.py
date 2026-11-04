"""Deployment adapters around the unchanged SVEC core. Public technical fixtures only.

Administrative routes are trusted harness endpoints on an isolated test network.
They are not proposed production authorization or durable recovery mechanisms.
"""
from pathlib import Path
import os,sys,json,time,base64,secrets,shutil,hmac,argparse,urllib.request
from types import SimpleNamespace
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'01-source-code'))
from svec_setup import *
from cryptography.hazmat.primitives.serialization import PrivateFormat,NoEncryption
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey,Ed25519PublicKey
def write(p,obj):p=Path(p);p.parent.mkdir(parents=True,exist_ok=True);p.write_text(json.dumps(obj,indent=2))
def priv(k):return k.private_bytes(Encoding.Raw,PrivateFormat.Raw,NoEncryption()).hex()
def key(s):return Ed25519PrivateKey.from_private_bytes(bytes.fromhex(s))
def request(url,obj=None,token=None):
 headers={'Content-Type':'application/json'}
 if token:headers['X-Admin-Token']=token
 req=urllib.request.Request(url,None if obj is None else canon(obj),headers)
 with urllib.request.urlopen(req,timeout=10) as r:return json.load(r)
def bootstrap(root):
 root=Path(root);path=root/'fixture/registered.json'
 deadline=time.monotonic()+120
 while not path.exists():
  if time.monotonic()>deadline:raise TimeoutError('Registry bootstrap')
  time.sleep(.2)
 metadata=json.loads(path.read_text())
 for r in metadata['records']:r['anchor']['rpcUrl']=os.environ.get('REGISTRY_URL','http://ganache:19880')
 write(path,metadata);state=setup(path.parent);authority=PolicyAuthority();token=secrets.token_hex(32);gates=[];policies=[];sources=[]
 urls=dict(authority=os.environ.get('AUTHORITY_URL','http://authority:19881'),signed=os.environ.get('SIGNED_URL','http://signed:19882'),gate=os.environ.get('GATE_URL','http://gate:19883'))
 for kind in ['ledger','signed']:
  spec=state['metadata']['context'] if kind=='ledger' else dict(kind='signed',registration_key=rawkey(state['registration_key'].public_key()),immutable_reference=True)
  for strategy in ['full','coarse','selective']:
   cell=f'{kind}/{strategy}';ctx=make_context(authority,spec,cell);gk=Ed25519PrivateKey.generate();ref=state['byname'][kind]['toy_data_0']
   gates.append(dict(cell=cell,kind=kind,strategy=strategy,ctx=ctx,key=priv(gk),spec=spec,ref=ref))
   policies.append(dict(ctx=ctx,ref=ref,gate_public=rawkey(gk.public_key())))
 for i,((mh,sh),(mb,sb)) in enumerate(state['sources'].items()):
  folder=root/'gate/artifacts';folder.mkdir(parents=True,exist_ok=True);(folder/f'{i}.joblib').write_bytes(mb);(folder/f'{i}.json').write_bytes(sb);sources.append(dict(mh=mh,sh=sh,model=f'artifacts/{i}.joblib',schema=f'artifacts/{i}.json'))
 write(root/'authority/config.json',dict(key=priv(authority.key),policies=policies,token=token))
 write(root/'signed/config.json',dict(entries=state['entries']))
 write(root/'gate/config.json',dict(cells=gates,authority_public=rawkey(authority.pub),catalogs=state['catalogs'],sources=sources,urls=urls,registration_public=rawkey(state['registration_key'].public_key()),token=token,fixture=base64.b64encode(state['data']['toy_data_0']).decode()))
 write(root/'tester/config.json',dict(urls=urls,token=token,cells=[g['cell'] for g in gates]))
 print('Role-separated runtime configuration generated; no key is stored in the image.',flush=True)
class Server(ThreadingHTTPServer):request_queue_size=128;daemon_threads=True
def serve(role,root,port):
 root=Path(root);cfg=json.loads((root/'config.json').read_text());authority=None;gates={}
 if role=='authority':
  authority=PolicyAuthority();authority.key=key(cfg['key']);authority.pub=authority.key.public_key()
  for p in cfg['policies']:authority.register(p['ctx'],p['ref'],Ed25519PublicKey.from_public_bytes(bytes.fromhex(p['gate_public'])))
 if role=='gate':
  proxy=SimpleNamespace(url=cfg['urls']['authority'],pub=Ed25519PublicKey.from_public_bytes(bytes.fromhex(cfg['authority_public'])))
  sources={(r['mh'],r['sh']):((root/r['model']).read_bytes(),(root/r['schema']).read_bytes()) for r in cfg['sources']}
  for c in cfg['cells']:
   client=PolicyClient(proxy,c['ctx'],key(c['key']));reader=ReferenceReader(c['kind'],cfg['catalogs'][c['kind']],c['spec'],cfg['urls']['signed'],Ed25519PublicKey.from_public_bytes(bytes.fromhex(cfg['registration_public'])))
   gates[c['cell']]=SVEC(client,reader,sources,c['strategy'])
 class Handler(BaseHTTPRequestHandler):
  def reply(self,obj,status=200):
   b=canon(obj);self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(b)));self.end_headers();self.wfile.write(b)
  def admin(self):return hmac.compare_digest(self.headers.get('X-Admin-Token',''),cfg.get('token','NO-ADMIN'))
  def do_GET(self):
   if self.path=='/health':return self.reply(dict(role=role,ready=True))
   if role=='signed' and self.path.startswith('/reference/'):
    v=cfg['entries'].get(self.path.rsplit('/',1)[-1]);return self.reply(v,200 if v else 404)
   if role=='gate' and self.path=='/technical-fixture':return self.reply(dict(data=cfg['fixture'],fixture='independent simulated technical data, not patient data'))
   if self.path=='/admin/state' and self.admin():
    if role=='authority':return self.reply(dict(events=authority.events,policies=authority.policies,tickets=len(authority.tickets)))
    if role=='gate':return self.reply({k:v.counters() for k,v in gates.items()})
   return self.reply(dict(error='NOT_FOUND'),404)
  def do_POST(self):
   try:
    obj=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
    if role=='authority' and self.path=='/':
     try:r=authority.handle(obj)
     except Exception as e:r=seal(authority.key,dict(kind='error',error=str(e)))
     return self.reply(r)
    if role=='authority' and self.path=='/admin/publish' and self.admin():return self.reply(dict(epoch=authority.publish(obj['ctx'],ref=obj.get('ref'),allowed=obj.get('allowed'))))
    if role=='gate' and self.path=='/predict':
     if set(obj)!={'cell','data'}:raise ValueError('CONFIG_OVERRIDE')
     r=gates[obj['cell']].predict(base64.b64decode(obj['data'],validate=True));return self.reply(r)
    return self.reply(dict(error='NOT_FOUND'),404)
   except Exception as e:return self.reply(dict(error=str(e)),400)
  def log_message(self,*a):pass
 print(f'{role} listening on {port}',flush=True);Server(('0.0.0.0',port),Handler).serve_forever()
def smoke(root,out):
 cfg=json.loads((Path(root)/'config.json').read_text());urls=cfg['urls'];deadline=time.monotonic()+120
 for role in ['authority','signed','gate']:
  while True:
   try:assert request(urls[role]+'/health')['ready'];break
   except Exception:
    if time.monotonic()>deadline:raise
    time.sleep(.2)
 data=request(urls['gate']+'/technical-fixture')['data'];cases=[];pair=None
 for cell in cfg['cells']:
  r=request(urls['gate']+'/predict',dict(cell=cell,data=data));assert r['released'];p=(r['score_hash'],r['prediction_hash']);assert pair is None or p==pair;pair=p
  cases.append(dict(cell=cell,released=True,model_calls=r['model_calls'],epoch=r['epoch']))
 events=request(urls['authority']+'/admin/state',token=cfg['token'])['events'];assert len([e for e in events if e['kind']=='commit'])==6
 write(out,dict(scope='Author-operated role-separated containers on one Docker host; technical fixture only, not a multi-host benchmark or independent external replication',cases=cases,all_hashes_equal=True,authority_commit_events=len(events),passed=True))
 print('Six role-separated end-to-end cases passed.',flush=True)
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('role',choices=['bootstrap','authority','signed','gate','smoke']);p.add_argument('--root',default='/state');p.add_argument('--port',type=int);p.add_argument('--out',default='/reports/container_smoke.json');a=p.parse_args()
 if a.role=='bootstrap':bootstrap(a.root)
 elif a.role=='smoke':smoke(a.root,a.out)
 else:serve(a.role,a.root,a.port)
