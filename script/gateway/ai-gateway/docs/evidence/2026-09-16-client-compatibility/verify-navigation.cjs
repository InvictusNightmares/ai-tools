const fs=require('fs'),vm=require('vm'),path=require('path');
const ts=require('/Users/invictus/github/ohos-command-line-tools/codelinter/node_modules/typescript/lib/typescript.js');
const root=process.argv[2];
const src=fs.readFileSync(path.join(root,'entry/src/main/ets/capabilities/Navigation.ets'),'utf8');
const js=ts.transpileModule(src,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText;
const fields=['KEY_LOGIN_INFO','KEY_LOGIN_USER_INFO','KEY_NEXT_APPROVAL_HINT','KEY_FILTER_INFO'];
const StorageKey=Object.fromEntries([...fields,'STORAGE_NAME'].map(k=>[k,k]));
let stored,events;
const PreferencesUtil={deleteSync(k){stored.delete(k);events.push('delete:'+k)},async delete(k){this.deleteSync(k)},getStringSync(k){return stored.get(k)||''}};
const exportsObject={};
vm.runInNewContext(js,{exports:exportsObject,require:n=>n==='@pura/harmony-utils'?{PreferencesUtil,LogUtil:{error(){},warn(){}}}:{StorageKey},console});
const Navigation=exportsObject.Navigation;
async function check(name){
 stored=new Map(fields.map(k=>[k,'synthetic-state']));stored.set('theme','dark');events=[];
 const stack={clear(){events.push('clear')},pushDestinationByName(n){events.push('push:'+n);return Promise.resolve()}};
 Navigation.setStack(stack);await Navigation.resetTo(name);await Promise.resolve();
 return {route:name,login_survives_cold_start:stored.has('KEY_LOGIN_INFO'),user_survives:stored.has('KEY_LOGIN_USER_INFO'),approval_survives:stored.has('KEY_NEXT_APPROVAL_HINT'),filter_survives:stored.has('KEY_FILTER_INFO'),unrelated_preserved:stored.get('theme')==='dark',events};
}
(async()=>{const login=await check('Login'),main=await check('Main');
const checks={login_state_removed:!login.login_survives_cold_start,user_approval_filter_removed:!login.user_survives&&!login.approval_survives&&!login.filter_survives,cleanup_before_navigation:fields.every(k=>login.events.indexOf('delete:'+k)>=0&&login.events.indexOf('delete:'+k)<login.events.indexOf('push:Login')),other_routes_preserve_login:main.login_survives_cold_start&&main.user_survives&&main.approval_survives&&main.filter_survives,unrelated_preferences_preserved:login.unrelated_preserved&&main.unrelated_preserved};
console.log(JSON.stringify({scope:'execute transpiled Navigation with synthetic persistent-store and navigation adapters; not HarmonyOS device UI',workspace:root,checks,pass:Object.values(checks).every(Boolean)},null,2));})();
