/* Identidades durables de UI, doble clic y respuesta perdida, sin red. */
const assert = require('node:assert/strict');
const { test } = require('node:test');
const fs = require('node:fs');
const vm = require('node:vm');
const { randomUUID } = require('node:crypto');
const source = fs.readFileSync('src/noesis/web/static/app.js','utf8').split('/* Icono de papelera')[0];
function browser(storage, fetch, tabStorage = new Map()) {
  const context = vm.createContext({window:{NOESIS_BIZ:1,NOESIS_SESSION:'1:0',NOESIS_FINANCIAL_CORE:true},
    localStorage:{getItem:k=>storage.get(k)||null,setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
    sessionStorage:{getItem:k=>tabStorage.get(k)||null,setItem:(k,v)=>tabStorage.set(k,v),removeItem:k=>tabStorage.delete(k)},
    crypto:{randomUUID},confirm:()=>true,fetch,location:{},console});
  vm.runInContext(source+'\nglobalThis.post=apiPost;',context);
  return context;
}
function server(revision = null) {
  let committed=false, fail=false, effects=0;
  const calls=[];
  const fetch=async (url,opts)=> {
    const body=JSON.parse(opts.body);calls.push({url,body});
    if (url.endsWith('/chat')) {
      if (fail) {fail=false;throw Error('timeout');}
      return {ok:true,json:async()=>({reply:'Propuesta'})};
    }
    const result={operation_uuid:'op',request_hash:'hash',revision,
      confirmation_required:!committed,reply:'Registrar gasto\n12.10 €',result:committed?{source_id:1}:null};
    if (url.endsWith('/confirm')) {
      if (!committed) effects++;
      committed=true;result.confirmation_required=false;result.result={source_id:1};
      if (fail) {fail=false;throw Error('timeout después del commit');}
    }
    return {ok:true,json:async()=>result};
  };
  return {fetch,calls,effects:()=>effects,fail:()=>{fail=true;}};
}
test('doble submit conserva acción y una sola aprobación',async()=>{
  const storage=new Map(), backend=server(), ui=browser(storage,backend.fetch);
  const body={concept:'Material',amount:'12.10'};
  await Promise.all([ui.post('/expenses',body),ui.post('/expenses',body)]);
  assert.equal(backend.calls.length,2);assert.equal(backend.effects(),1);assert.equal(storage.size,0);
  assert.equal(backend.calls[0].body.intent.fields.amount,'12.10');
});

test('cada pestaña confirma la propuesta que mostró, no la de otra pestaña',async()=>{
  const calls=[],storage=new Map();
  const fetch=async(url,opts)=>{
    const body=JSON.parse(opts.body);calls.push(body);
    return {ok:true,json:async()=>body.message==='sí'?{reply:'Resultado'}:{confirmation_required:true,operation_uuid:body.message,request_hash:'hash-'+body.message,revision:1}};
  };
  const a=browser(storage,fetch),b=browser(storage,fetch);
  await a.post('/chat',{message:'A'});await b.post('/chat',{message:'B'});
  await a.post('/chat',{message:'sí'});await b.post('/chat',{message:'sí'});
  assert.equal(calls[2].proposal_ref.operation_uuid,'A');
  assert.equal(calls[3].proposal_ref.operation_uuid,'B');
});
test('cerrar/reabrir navegador tras timeout conserva confirmación',async()=>{
  const storage=new Map(), backend=server(), body={concept:'Material',amount:'12.10'};
  backend.fail();await assert.rejects(browser(storage,backend.fetch).post('/expenses',body));
  await browser(storage,backend.fetch).post('/expenses',body);
  const confirmations=backend.calls.filter(c=>c.url.endsWith('/confirm'));
  assert.equal(confirmations[0].body.action_uuid,confirmations[1].body.action_uuid);
  assert.equal(backend.effects(),1);assert.equal(storage.size,0);
});
test('float monetario no cruza el bridge',async()=>{
  const backend=server();await assert.rejects(browser(new Map(),backend.fetch).post('/expenses',{concept:'M',amount:12.1}));
  assert.equal(backend.calls.length,0);
});
test('revisión superior a 2^53 conserva cada dígito al confirmar',async()=>{
  const revision='1152921504606846975',backend=server(revision);
  await browser(new Map(),backend.fetch).post('/expenses',{concept:'M',amount:'12.10'});
  const body=backend.calls.find(c=>c.url.endsWith('/confirm')).body;
  assert.equal(body.revision,revision);assert.equal(typeof body.revision,'string');
});
test('chat retry mantiene UUID, nuevo mensaje legítimo tiene otro',async()=>{
  const storage=new Map(),backend=server();backend.fail();
  await assert.rejects(browser(storage,backend.fetch).post('/chat',{message:'gasto 12 €'}));
  await browser(storage,backend.fetch).post('/chat',{message:'gasto 12 €'});
  await browser(storage,backend.fetch).post('/chat',{message:'gasto 12 €'});
  assert.equal(backend.calls[0].body.message_uuid,backend.calls[1].body.message_uuid);
  assert.notEqual(backend.calls[1].body.message_uuid,backend.calls[2].body.message_uuid);
});
