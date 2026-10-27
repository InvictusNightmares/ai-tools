import {test} from 'node:test';
import assert from 'node:assert/strict';
import vm from 'node:vm';
import {ALL_PATCHES,applyReplacementsToText} from '../lib/core.js';
const patch=ALL_PATCHES.find(p=>p.id===42);
// Native entry Config remains the only authoritative store on modern hosts.
const modern=`var SettingsForms = class extends Service {
\tconstructor(ownerContext) {
\t\tsuper(ownerContext, "settings");
\t\tthis.ownerContext = ownerContext;
\t}
\tdescribe(options) { return this.ownerContext.value; }
\tasync replace(ns, section, expectedRevision) { this.ownerContext.value=section; }
\tconfigure(presentation, owner = this.ctx.fiber) {
\t}
};`;
function legacyInject(s){for(const {pattern,replace} of patch.replacements){if(typeof pattern==='string')s=s.split(pattern).join(replace);}return s;}
test('modern settings never advertise legacy register, native config reads/writes survive repeated binding',async()=>{
 const out=applyReplacementsToText(modern,patch);assert.equal(out.changed,true);assert.doesNotMatch(out.text,/legacyRegistrations|settings-legacy.yaml|register\(ns/);
 const C=vm.runInNewContext(out.text+';SettingsForms',{Service:class{}});const ctx={value:{preset:'keep'}};const s=new C(ctx);
 for(let i=0;i<3;i++){assert.equal(typeof s.register,'undefined');assert.equal(s.describe().preset,'keep');}await s.replace('panel',{preset:'new'});assert.equal(ctx.value.preset,'new');assert.equal(applyReplacementsToText(out.text,patch).changed,false);
});
test('upgrade strips only the exact old shim and preserves unrelated edits',()=>{
 const old=legacyInject(modern)+'\n// another plugin';const migrated=applyReplacementsToText(old,patch);
 assert.equal(migrated.text,applyReplacementsToText(modern,patch).text+'\n// another plugin');
});
test('historical #42 shim generations migrate instead of failing',()=>{
 const expected=applyReplacementsToText(modern,patch).text;
 const canonical=legacyInject(modern);
 const resolved89='\t\tconst resolved = plainConfig(schema(mergeLayers(options?.base ?? {}, user ?? {}))); // [dsh-purge] #86 plainConfig before validate + #89 ?? {} 兜 over=undefined 丢 base';
 const next89='\t\tconst next = plainConfig(registration.schema(mergeLayers(registration.base ?? {}, user ?? {}))); // [dsh-purge] #86 plainConfig before validate + #89 ?? {} 兜 over=undefined 丢 base';
 const resolved86='\t\tconst resolved = plainConfig(schema(mergeLayers(options?.base, user))); // [dsh-purge] #86 plainConfig before validate';
 const next86='\t\tconst next = plainConfig(registration.schema(mergeLayers(registration.base, user))); // [dsh-purge] #86 plainConfig before validate';
 const variants=[
  canonical.replace(resolved89,resolved86).replace(next89,next86),
  canonical.replace(resolved89,'\t\tconst resolved = schema(mergeLayers(options?.base, user));').replace(next89,'\t\tconst next = registration.schema(mergeLayers(registration.base, user));').split('applyPathOp(section, op)').join('legacyApplyPath(section, op)'),
  canonical.split('applyPathOp(section, op)').join('legacyApplyPath(section, op)'),
 ];
 for(const old of variants){const migrated=applyReplacementsToText(old,patch);assert.equal(migrated.text,expected);assert.doesNotMatch(migrated.text,/legacyRegistrations|legacyApplyPath/);}
});
test('unknown modified shim fails before writing instead of clobbering it',()=>{
 const old=legacyInject(modern).replace('const stored = this.legacyDocument[ns];','const stored = customStorage(ns);');assert.throws(()=>applyReplacementsToText(old,patch),/historical shim differs/);
});
test('old host lacking describe/replace keeps legacy compatibility',()=>{
 const old=modern.replace('\tdescribe(options) { return this.ownerContext.value; }','').replace('\tasync replace(ns, section, expectedRevision) { this.ownerContext.value=section; }','');
 assert.match(applyReplacementsToText(old,patch).text,/register\(ns, schema, options\)/);
});
