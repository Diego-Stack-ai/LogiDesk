"""Laboratorio HTTP loopback: elabora PDF e salva solo staging locale privato."""
from __future__ import annotations
import argparse, base64, io, json, re, sys, uuid
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from pypdf import PdfReader
from urllib.request import Request, urlopen

ROOT=Path(__file__).resolve().parents[1]; sys.path.insert(0,str(ROOT/'functions')); sys.path.insert(0,str(ROOT/'tools'))
from services.document_ingestion import extract_ddt  # noqa:E402
from services.route_sheet_ingestion import extract_route_sheet  # noqa:E402
from compare_ingestion_pipelines import _ai_bundle  # noqa:E402

HTML=ROOT/'tools'/'local-ingestion-lab.html'; DEST=ROOT/'test-data'/'ingestion-private'/'derived'/'lab-sessions'; MAX=25*1024*1024
SESSION_RE=re.compile(r'^\d{8}-\d{6}-[0-9a-f]{6}$')
def reply(handler,status,payload,content_type='application/json'):
    body=payload if isinstance(payload,bytes) else json.dumps(payload,ensure_ascii=False).encode(); handler.send_response(status); handler.send_header('Content-Type',content_type); handler.send_header('Content-Length',str(len(body))); handler.end_headers(); handler.wfile.write(body)
def analyze_unknown_pdf(pages,tenant,file_name):
    schema={'document_type':'route_sheet|ddt_collection|planning_report|unknown','route_count':0,'observed_route_codes':[],'page_roles':[{'page':1,'role':'string'}],'field_mapping':[{'source_label':'string','logidesk_field':'string','confidence':0.0,'reason':'string'}],'fields_detected':[],'new_fields':[],'ambiguities':[],'review_required':True,'writes_performed':0}
    page_text='\n\n'.join(f'=== PAGINA {number} ===\n{text}' for number,text in pages)
    prompt=('Sei il classificatore documentale locale di LogiDesk. Non trascrivere tutte le fermate: classifica soltanto struttura e campi per costruire un parser deterministico. '
            'Cliente intestatario e destinazione possono avere codici distinti: segnalalo nella mappatura e non fonderli. Non inventare valori. '
            'Restituisci esclusivamente JSON conforme a questa struttura: '+json.dumps(schema,ensure_ascii=False)+
            f'. Committente non certificato: {tenant}. File: {file_name}. Confidenza fra 0 e 1. Non proporre scritture e mantieni writes_performed=0.\n\n'+page_text[:18000])
    body=json.dumps({'model':'qwen3.5:9b','prompt':prompt,'stream':False,'think':False,'format':'json','keep_alive':'5m','options':{'temperature':0.0,'num_ctx':8192,'num_predict':1400}}).encode('utf-8')
    with urlopen(Request('http://127.0.0.1:11434/api/generate',data=body,headers={'Content-Type':'application/json'},method='POST'),timeout=240) as response: envelope=json.loads(response.read().decode('utf-8'))
    proposal=json.loads(envelope.get('response') or '{}')
    if not isinstance(proposal.get('field_mapping'),list) or proposal.get('writes_performed')!=0: raise ValueError('Proposta AI generale non valida')
    proposal.update(producer='LOCAL_AI',model=envelope.get('model','qwen3.5:9b'),elapsed_seconds=round(envelope.get('total_duration',0)/1_000_000_000,2),tenant_id=tenant,source_file=file_name,review_required=True,writes_performed=0)
    return proposal
def extract(payload):
    tenant=str(payload.get('tenant_id') or '').strip(); channel=str(payload.get('channel') or '').upper(); raw=base64.b64decode(payload.get('file_base64') or '',validate=True)
    if not tenant: raise ValueError('Committente obbligatorio');
    if channel not in {'LATTE','FRUTTA'}: raise ValueError('Canale non valido')
    if len(raw)>MAX: raise ValueError('File oltre il limite di 25 MB')
    reader=PdfReader(io.BytesIO(raw)); points={}; notes=[]; articles=[]; ai_result=None; pages=[]
    for page_no,page in enumerate(reader.pages,1):
        text=page.extract_text() or ''; pages.append((page_no,text)); data=extract_ddt(text); code=data.get('codice_punto_committente'); source={'file':payload.get('file_name'),'page':page_no,'numero_ddt':data.get('numero_ddt')}
        if code and code.upper() not in points: points[code.upper()]={'tenant_id':tenant,**{k:data.get(k) for k in ('codice_punto_committente','denominazione_punto','indirizzo','cap','localita','provincia','telefono','referente')},'source':source,'review_status':'PENDING'}
        if data.get('orario_operativo_raw'): notes.append({'tenant_id':tenant,'codice_punto_committente':code,'codice_zona_originale':data.get('codice_zona_originale'),'codice_zona_logistica':data.get('codice_zona_logistica'),'orario_operativo_raw':data.get('orario_operativo_raw'),'orario_operativo_proposto':data.get('orario_operativo_proposto'),'master_update_allowed':False,'source':source,'review_status':'PENDING'})
        for article in data.get('articoli',[]): articles.append({'tenant_id':tenant,**article,'source':source,'review_status':'PENDING'})
        if payload.get('ai_ddt') and str(payload['ai_ddt']).upper()==str(data.get('numero_ddt')).upper(): ai_result=_ai_bundle(text,tenant,'qwen3.5:9b')
    if not points:
        route_candidate=extract_route_sheet(pages)
        for stop in route_candidate.get('stops',[]):
            code=stop.get('delivery_point_code') or stop.get('customer_code')
            if not code: continue
            identity=f"{stop.get('customer_code')}:{code}"
            points[identity.upper()]={'tenant_id':tenant,'identita_candidata':identity,'codice_punto_committente':code,'codice_punto_da_confermare':stop.get('delivery_point_code_requires_confirmation'),'codice_cliente':stop.get('customer_code'),'codice_servizio_documento':stop.get('document_or_service_code'),'denominazione_punto':stop.get('denomination'),'indirizzo':stop.get('address'),'cap':None,'localita':stop.get('city'),'provincia':stop.get('province'),'telefono':stop.get('phone'),'referente':None,'sequenza_giro':stop.get('sequence'),'peso_lordo':stop.get('gross_weight'),'finestre_consegna':stop.get('delivery_windows'),'tipi_servizio':stop.get('service_flags'),'source':{'file':payload.get('file_name'),'page':stop.get('source_page'),'route_code':route_candidate.get('route_code')},'producer':'DETERMINISTIC_CANDIDATE','review_status':'PENDING'}
        if route_candidate.get('stops'):
            notes=[{'tenant_id':tenant,'codice_punto_committente':stop.get('delivery_point_code') or stop.get('customer_code'),'codice_punto_da_confermare':stop.get('delivery_point_code_requires_confirmation'),'route_code':route_candidate.get('route_code'),'departure_date':route_candidate.get('departure_date'),'start_time':route_candidate.get('start_time'),'sequence':stop.get('sequence'),'gross_weight':stop.get('gross_weight'),'delivery_windows':stop.get('delivery_windows'),'master_update_allowed':False,'source':{'file':payload.get('file_name'),'page':stop.get('source_page')},'review_status':'PENDING'} for stop in route_candidate['stops']]
    if not any(row.get('producer')!='DETERMINISTIC_CANDIDATE' for row in points.values()) and payload.get('ai_unknown',True):
        ai_result=analyze_unknown_pdf(pages,tenant,payload.get('file_name'))
        for route in ai_result.get('routes',[]):
            for stop in route.get('stops',[]):
                code=stop.get('delivery_point_code') or stop.get('customer_code')
                if not code: continue
                key=str(code).upper()
                if key not in points: points[key]={'tenant_id':tenant,'codice_punto_committente':code,'denominazione_punto':stop.get('denomination'),'indirizzo':stop.get('address'),'cap':stop.get('postal_code'),'localita':stop.get('city'),'provincia':stop.get('province'),'telefono':stop.get('phone'),'referente':None,'ai_confidence':stop.get('confidence'),'source':{'file':payload.get('file_name'),'page':stop.get('source_page'),'route_code':route.get('route_code')},'producer':'LOCAL_AI_PROPOSAL','review_status':'PENDING'}
    return {'mode':'LOCAL_LAB_NO_REMOTE_ACCESS','tenant_id':tenant,'channel':channel,'file_name':payload.get('file_name'),'delivery_points':list(points.values()),'travel_notes':notes,'articles':articles,'ai_result':ai_result,'firebase_reads':0,'firebase_writes':0,'storage_writes':0}
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path in {'/','/index.html'}: return reply(self,200,HTML.read_bytes(),'text/html; charset=utf-8')
        if self.path=='/api/status': return reply(self,200,{'status':'ok','bind':'127.0.0.1','firebase_enabled':False})
        if self.path=='/api/latest-session':
            sessions=sorted((p for p in DEST.glob('*') if p.is_dir() and SESSION_RE.fullmatch(p.name)),reverse=True)
            if not sessions: return reply(self,404,{'error':'Nessuna sessione locale salvata'})
            folder=sessions[0]
            manifest=json.loads((folder/'manifest.json').read_text(encoding='utf-8'))
            result={'mode':'LOCAL_LAB_NO_REMOTE_ACCESS','tenant_id':manifest.get('tenant_id'),'file_name':manifest.get('source_file'),'channel':manifest.get('channel')}
            for group in ('delivery_points','travel_notes','articles'):
                result[group]=json.loads((folder/f'{group}.json').read_text(encoding='utf-8'))
            ai=folder/'ai_result.json'; result['ai_result']=json.loads(ai.read_text(encoding='utf-8')) if ai.exists() else None
            result.update(firebase_reads=0,firebase_writes=0,storage_writes=0)
            return reply(self,200,{'session_id':folder.name,'result':result})
        reply(self,404,{'error':'Not found'})
    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0')); payload=json.loads(self.rfile.read(length))
            if self.path=='/api/process': return reply(self,200,extract(payload))
            if self.path=='/api/save':
                result=payload.get('result'); approvals=payload.get('approvals') or {}
                if not isinstance(result,dict) or result.get('mode')!='LOCAL_LAB_NO_REMOTE_ACCESS': raise ValueError('Risultato laboratorio non valido')
                session=f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-{uuid.uuid4().hex[:6]}"; folder=DEST/session; folder.mkdir(parents=True)
                for group in ('delivery_points','travel_notes','articles'):
                    rows=[]
                    for i,row in enumerate(result.get(group,[])): rows.append({**row,'operator_review_status':'APPROVED_FOR_LOCAL_STAGING' if approvals.get(f'{group}:{i}') else 'PENDING'})
                    (folder/f'{group}.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')
                manifest={'session_id':session,'created_at':datetime.now(timezone.utc).isoformat(),'source_file':result.get('file_name'),'tenant_id':result.get('tenant_id'),'channel':result.get('channel'),'firebase_reads':0,'firebase_writes':0,'storage_writes':0}; (folder/'manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
                if result.get('ai_result') is not None: (folder/'ai_result.json').write_text(json.dumps(result['ai_result'],ensure_ascii=False,indent=2),encoding='utf-8')
                return reply(self,200,{'session_id':session,'folder':str(folder),'firebase_writes':0,'storage_writes':0})
            if self.path=='/api/save-comparison':
                session=str(payload.get('session_id') or '')
                if not SESSION_RE.fullmatch(session): raise ValueError('Identificativo sessione non valido')
                folder=(DEST/session).resolve()
                if folder.parent!=DEST.resolve() or not folder.is_dir(): raise ValueError('Sessione locale non trovata')
                remote=payload.get('remote_snapshot'); comparison=payload.get('comparison')
                if not isinstance(remote,list) or not isinstance(comparison,list): raise ValueError('Confronto non valido')
                (folder/'firestore_readonly_snapshot.json').write_text(json.dumps(remote,ensure_ascii=False,indent=2),encoding='utf-8')
                (folder/'visual_comparison.json').write_text(json.dumps(comparison,ensure_ascii=False,indent=2),encoding='utf-8')
                return reply(self,200,{'folder':str(folder),'firebase_reads':len(remote),'firebase_writes':0,'storage_writes':0})
            reply(self,404,{'error':'Not found'})
        except Exception as exc: reply(self,400,{'error':str(exc)})
    def log_message(self,fmt,*args): print('[local-lab]',fmt%args)
def main():
    parser=argparse.ArgumentParser(); parser.add_argument('--port',type=int,default=8765); args=parser.parse_args(); server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler); print(f'Laboratorio: http://127.0.0.1:{args.port}'); server.serve_forever()
if __name__=='__main__': main()
