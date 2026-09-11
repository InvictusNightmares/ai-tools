"""Private, encrypted US-to-Tokyo delivery; activation remains in the admin UI.

Only encrypted archives are placed in the existing nginx container. The password
and expected digest travel over the existing authenticated SSH control channel.
The nginx location additionally restricts downloads to the Tokyo server address.
"""
import json
import re
import shlex

PULL_ORIGIN = "http://47.251.166.27:8080"
ASSET_PATH = "/policy-release-assets/"
TOKYO_IP = "8.216.44.189"

NGINX_LOCATION = '''        # Encrypted policy update packages; authenticated control travels over SSH.
        location ^~ /policy-release-assets/ {
            allow 8.216.44.189;
            deny all;
            limit_except GET { deny all; }
            root /usr/share/nginx/html;
            autoindex off;
            default_type application/octet-stream;
            add_header Cache-Control "no-store" always;
        }

'''


def nginx_config(original):
    if "location ^~ /policy-release-assets/ {" in original:
        if NGINX_LOCATION not in original:
            raise RuntimeError("Existing update download location differs; inspect before changing")
        return original
    anchor = "        location / {"
    if original.count(anchor) != 1:
        raise RuntimeError("Expected one existing gateway fallback location")
    return original.replace(anchor, NGINX_LOCATION + anchor, 1)


PUBLISHER = r'''
import hashlib,json,os,pathlib,re,secrets,subprocess,sys,tarfile,tempfile
root=pathlib.Path('/opt/sub2api-deploy/policy-releases')
control=json.load(sys.stdin); record=control['record']; catalog=control['catalog']
sha=record['sha256']
if not re.fullmatch('[a-f0-9]{64}',sha):raise RuntimeError('invalid binary digest')
source=root/'releases'/sha
def digest(path):
 h=hashlib.sha256()
 with path.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 return h.hexdigest()
if json.loads((source/'release.json').read_text())!=record:raise RuntimeError('release record mismatch')
if digest(source/'sub2api')!=sha:raise RuntimeError('source binary mismatch')
if catalog['status']!='ready' or catalog['releases'][0]!=record:raise RuntimeError('catalog not ready')
with tempfile.TemporaryDirectory(prefix='.pull-',dir=root) as tmp:
 tmp=pathlib.Path(tmp); archive=tmp/'package.tar.gz'
 (tmp/'catalog.json').write_text(json.dumps(catalog,ensure_ascii=False))
 with tarfile.open(str(archive),'w:gz') as tar:
  tar.add(str(tmp/'catalog.json'),arcname='catalog.json')
  tar.add(str(source/'sub2api'),arcname='sub2api')
  tar.add(str(source/'release.json'),arcname='release.json')
 password=secrets.token_urlsafe(48)
 key=tmp/'password';key.write_text(password+'\n');key.chmod(0o600)
 encrypted=tmp/'package.enc'
 # A random 384-bit secret avoids dependence on password-hardening support in
 # older system OpenSSL. Ciphertext and the final binary are both SHA256 checked.
 subprocess.run(['openssl','enc','-aes-256-cbc','-md','sha256','-salt','-pass','file:'+str(key),'-in',str(archive),'-out',str(encrypted)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 encrypted.chmod(0o644); encrypted_sha=digest(encrypted)
 assets='/usr/share/nginx/html/policy-release-assets'
 subprocess.run(['docker','exec','sub2api-proxy','mkdir','-p',assets],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['docker','exec','sub2api-proxy','find',assets,'-maxdepth','1','-type','f','-name','*.enc','-mmin','+180','-delete'],check=True,stdout=subprocess.DEVNULL)
 subprocess.run(['docker','cp',str(encrypted),'sub2api-proxy:'+assets+'/'+encrypted_sha+'.enc'],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 print(json.dumps({'password':password,'cipher_sha256':encrypted_sha,'cipher_size':encrypted.stat().st_size}),flush=True)
'''

DOWNLOADER = r'''
import hashlib,json,pathlib,re,subprocess,sys,tempfile,urllib.parse
control=json.load(sys.stdin)
sha=control['cipher_sha256']
if not re.fullmatch('[a-f0-9]{64}',sha):raise RuntimeError('invalid cipher digest')
url='http://47.251.166.27:8080/policy-release-assets/'+sha+'.enc'
root=pathlib.Path('/opt/sub2api-deploy/policy-releases')
with tempfile.TemporaryDirectory(prefix='.incoming-pull-',dir=root) as tmp:
 tmp=pathlib.Path(tmp); encrypted=tmp/'package.enc'; archive=tmp/'package.tar.gz'
 subprocess.run(['curl','--noproxy','*','--fail','--silent','--show-error','--max-time','900','--retry','2','--retry-delay','2','--output',str(encrypted),url],check=True,timeout=1000)
 h=hashlib.sha256()
 with encrypted.open('rb') as f:
  for b in iter(lambda:f.read(1048576),b''):h.update(b)
 if h.hexdigest()!=sha or encrypted.stat().st_size!=control['cipher_size']:raise RuntimeError('encrypted download checksum mismatch')
 key=tmp/'password';key.write_text(control['password']+'\n');key.chmod(0o600)
 subprocess.run(['openssl','enc','-d','-aes-256-cbc','-md','sha256','-pass','file:'+str(key),'-in',str(encrypted),'-out',str(archive)],check=True,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
 with archive.open('rb') as stream:
  subprocess.run(['python3','-c',control['receiver']],stdin=stream,check=True)
'''


def stage_tokyo(catalog, record, receiver, run):
    """US staging must succeed first. Never print the captured transport secret."""
    result = run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "qiyuan-us",
                  "python3 -c " + shlex.quote(PUBLISHER)],
                 input=json.dumps({"catalog":catalog,"record":record}),
                 capture_output=True, text=True, timeout=300)
    control = json.loads(result.stdout)
    if not re.fullmatch('[a-f0-9]{64}', control['cipher_sha256']):
        raise RuntimeError('Invalid private publication digest')
    if not isinstance(control['cipher_size'], int) or control['cipher_size'] <= 0:
        raise RuntimeError('Invalid private publication size')
    control['receiver'] = receiver
    try:
        run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "qiyuan-tokyo",
             "python3 -c " + shlex.quote(DOWNLOADER)],
            input=json.dumps(control), text=True, timeout=1200)
    finally:
        # The filename is a validated digest; a failed cleanup leaves ciphertext
        # only. Later publications also prune these temporary files after 3h.
        try:
            run(["ssh", "-T", "-o", "BatchMode=yes", "-o", "ConnectTimeout=20", "qiyuan-us",
                 "docker exec sub2api-proxy rm -f /usr/share/nginx/html/policy-release-assets/" + control['cipher_sha256'] + ".enc"],
                timeout=90, stdout=__import__('subprocess').DEVNULL)
        except Exception:
            print('Encrypted package cleanup deferred to the next publication',flush=True)
