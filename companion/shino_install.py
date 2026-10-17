"""SHINO // INSTALL. Default GUI/verify is offline; live requires explicit consent."""
import argparse,getpass,hashlib,hmac,ipaddress,json,re,secrets,socket,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
from m9_signed_release import validate_image
HEX64=re.compile(r'[0-9a-f]{64}\Z');DEVICE=re.compile(r'[0-9a-f]{16}\Z')
# Offline qualification did not establish the simultaneous native memory floor.
# This is a release gate, not a CLI switch. No device path in this delivery.
QUALIFIED_LIVE=False
class InstallError(ValueError):pass
def inspect(image,manifest):
    image=Path(image);manifest=Path(manifest)
    if image.is_symlink() or manifest.is_symlink() or not image.is_file() or not manifest.is_file():raise InstallError('Regular BIN and manifest files required')
    if image.stat().st_size>0xFEFF0 or manifest.stat().st_size>4096:raise InstallError('File size limit')
    def unique(pairs):
        out={}
        for k,v in pairs:
            if k in out:raise InstallError('Duplicate manifest field')
            out[k]=v
        return out
    m=json.loads(manifest.read_text(encoding='utf-8'),object_pairs_hook=unique)
    if set(m)!={'schema','family','layout','protocol','bytes','sha256','build_id'} or m['schema']!=1 or m['family']!='SHINO-StageA' or m['layout']!='4m2m' or m['protocol']!='shino-install-1':raise InstallError('Incompatible build manifest')
    if type(m['bytes']) is not int or not isinstance(m['sha256'],str) or not HEX64.fullmatch(m['sha256']) or not isinstance(m['build_id'],str) or not HEX64.fullmatch(m['build_id']):raise InstallError('Invalid identity fields')
    raw=image.read_bytes()
    if len(raw)!=m['bytes'] or hashlib.sha256(raw).hexdigest()!=m['sha256']:raise InstallError('BIN differs from selected manifest')
    validate_image(raw)
    return m,raw
def proof(key,text):return hmac.new(key,text.encode('ascii'),hashlib.sha256).hexdigest()
def capability(io,device,key,nonce):
    if not DEVICE.fullmatch(device):raise InstallError('Expected device identity required')
    io.line(f'CAP {device} {nonce}')
    fields=io.read().split(' ')
    if len(fields)!=8 or fields[:3]!=['CAP',device,nonce] or not HEX64.fullmatch(fields[3]) or fields[4:6]!=['4m2m','APP_ONLY'] or not re.fullmatch('[0-9a-f]{32}',fields[6]) or not hmac.compare_digest(proof(key,' '.join(fields[:-1])),fields[-1]):raise InstallError('Compatible authenticated receiver unavailable; current StageA has no receiver')
    return fields
def send(io,device,password,m,raw,progress=lambda n,total:None,nonce=None):
    # Called only after exact inspection and explicit GUI/CLI confirmation.
    if len(password)<32:raise InstallError('Distinct maintenance password must have at least 32 characters')
    key=hashlib.sha256(password.encode('utf-8')).digest();cn=nonce or secrets.token_hex(16)
    cap=capability(io,device,key,cn)
    if cap[3]==m['build_id']:raise InstallError('Selected build already installed')
    auth=f"AUTH {device} {cn} {cap[6]} 0 {len(raw)} {m['sha256']} {m['build_id']}"
    io.line(f"AUTH 0 {len(raw)} {m['sha256']} {m['build_id']} {proof(key,auth)}")
    if io.read()!='READY':raise InstallError('Update not admitted; no retry')
    for at in range(0,len(raw),512):
        io.write(raw[at:at+512]);done=min(at+512,len(raw))
        if io.read()!=f'ACK {done}':raise InstallError('Transfer interrupted; no retry, device state unconfirmed')
        progress(done,len(raw))
    io.line('COMMIT')
    if io.read()!=f"STAGED {m['build_id']}":raise InstallError('Commit result unconfirmed; do not retry')
    return 'STAGED_PENDING_BOOT_CONFIRMATION'
class SocketIO:
    def __init__(self,host):
        if str(ipaddress.IPv4Address(host))!='192.168.4.1':raise InstallError('Only the existing private SHINO AP target is supported')
        self.sock=socket.create_connection((host,8266),timeout=3);self.start=time.monotonic();self.stream=self.sock.makefile('rb')
    def line(self,text):self.write(text.encode('ascii')+b'\n')
    def write(self,data):
        if time.monotonic()-self.start>=60:raise InstallError('Total transfer deadline')
        self.sock.sendall(data)
    def read(self):
        raw=self.stream.readline(513)
        if not raw.endswith(b'\n') or len(raw)>512:raise InstallError('Receiver disconnected or invalid response')
        return raw[:-1].decode('ascii')
    def close(self):self.stream.close();self.sock.close()
def live(image,manifest,device,password,host,progress=lambda n,total:None,expected=None):
    if not QUALIFIED_LIVE:raise InstallError('NO_GO: native simultaneous memory floor not established; installer is offline-only')
    m,raw=inspect(image,manifest);io=None
    if expected is not None and m!=expected:raise InstallError('Selected build changed after confirmation')
    try:
        io=SocketIO(host);result=send(io,device,password,m,raw,progress)
    finally:
        if io:io.close()
    # Poll only capabilities after commit; never resend an update. Lost reply
    # remains UNKNOWN even if the image actually booted. No success from ACK.
    until=time.monotonic()+30
    while time.monotonic()<until:
        time.sleep(1);check=None
        try:
            check=SocketIO(host)
            cap=capability(check,device,hashlib.sha256(password.encode()).digest(),secrets.token_hex(16))
            if cap[3]==m['build_id']:return 'BOOT_CONFIRMED'
        except (OSError,ValueError):pass
        finally:
            if check:check.close()
    return result
def gui():
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    import threading,queue
    root=tk.Tk();root.title('SHINO // INSTALL');root.geometry('640x490');root.resizable(False,False)
    frame=ttk.Frame(root,padding=20);frame.pack(fill='both',expand=True)
    ttk.Label(frame,text='SHINO // INSTALL',font=('Segoe UI',20,'bold')).pack(anchor='w')
    ttk.Label(frame,text='NO-GO: native memory budget is not qualified.\nCurrent StageA has no Wi-Fi update receiver. Installation is disabled.',foreground='#a34300').pack(anchor='w',pady=10)
    paths={};status=tk.StringVar(value='Choose a BIN and its exact 4m2m build manifest. Offline by default.');device=tk.StringVar();password=tk.StringVar();allow=tk.BooleanVar(value=False)
    def choose(kind):
        p=filedialog.askopenfilename(title='Choose '+kind,filetypes=[(kind,'*.bin' if kind=='BIN' else '*.json')])
        if p:paths[kind]=p;status.set(kind+': '+Path(p).name);install.configure(state='disabled')
    row=ttk.Frame(frame);row.pack(anchor='w',pady=6)
    ttk.Button(row,text='Choose BIN',command=lambda:choose('BIN')).pack(side='left',padx=3)
    ttk.Button(row,text='Choose manifest',command=lambda:choose('manifest')).pack(side='left',padx=3)
    verified={}
    def verify():
        try:
            m,_=inspect(paths['BIN'],paths['manifest']);verified.clear();verified.update(m)
            status.set(f"Verified: {m['bytes']} bytes / 4m2m\nSHA-256: {m['sha256']}\nUpload begins only after authenticated APP_ONLY capability.")
            install.configure(state='normal' if QUALIFIED_LIVE and allow.get() else 'disabled')
        except (ValueError,OSError,KeyError) as e:status.set('Verification failed: '+str(e));install.configure(state='disabled')
    ttk.Button(row,text='Verify offline',command=verify).pack(side='left',padx=3)
    for label,var,secret in [('Expected device identity (16 hex)',device,False),('Distinct maintenance password',password,True)]:
        ttk.Label(frame,text=label).pack(anchor='w',pady=(6,0));ttk.Entry(frame,textvariable=var,show='*' if secret else '').pack(fill='x')
    ttk.Checkbutton(frame,text='I explicitly authorize this Wi-Fi install and reboot',variable=allow,state='normal' if QUALIFIED_LIVE else 'disabled',command=lambda:install.configure(state='normal' if QUALIFIED_LIVE and allow.get() and verified else 'disabled')).pack(anchor='w',pady=12)
    bar=ttk.Progressbar(frame,maximum=100);bar.pack(fill='x');messages=queue.Queue()
    def run():
        if not allow.get() or not messagebox.askyesno('Confirm exact application',f"Install {paths.get('BIN')}\nDevice: {device.get()}\nSHA-256: {verified.get('sha256')}\nNo atomic rollback. Do not interrupt power."):return
        install.configure(state='disabled');identity=device.get();secret=password.get();password.set('');image=paths['BIN'];manifest=paths['manifest'];selected=dict(verified)
        def work():
            try:messages.put(('result',live(image,manifest,identity,secret,'192.168.4.1',lambda n,total:messages.put(('progress',100*n/total)),expected=selected)))
            except (ValueError,OSError) as e:messages.put(('result','FAILED / UNCONFIRMED: '+str(e)))
        threading.Thread(target=work,daemon=True).start()
    install=ttk.Button(frame,text='Install by Wi-Fi',command=run,state='disabled');install.pack(anchor='w',pady=8)
    ttk.Label(frame,textvariable=status,wraplength=595).pack(anchor='w',pady=6)
    def poll():
        while not messages.empty():
            kind,value=messages.get()
            if kind=='progress':bar['value']=value
            else:status.set(value+' — no automatic retry')
        root.after(100,poll)
    poll();root.mainloop()
def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--gui',action='store_true');p.add_argument('--bin',type=Path);p.add_argument('--manifest',type=Path);p.add_argument('--device');p.add_argument('--live',action='store_true');p.add_argument('--confirm-sha256');p.add_argument('--host',default='192.168.4.1');a=p.parse_args(argv)
    if a.gui or not a.bin:gui();return 0
    try:
        m,_=inspect(a.bin,a.manifest)
        if not a.live:print(json.dumps(dict(status='VERIFIED_OFFLINE',**m,current_stagea_receiver=False)));return 0
        if not QUALIFIED_LIVE:raise InstallError('NO_GO: offline-only delivery; no receiver contact permitted')
        if a.confirm_sha256!=m['sha256'] or not a.device:raise InstallError('Explicit exact hash and device confirmation required')
        result=live(a.bin,a.manifest,a.device,getpass.getpass('Private maintenance password: '),a.host,lambda n,total:print(f'{n}/{total}'),expected=m)
        print(result);return 0 if result=='BOOT_CONFIRMED' else 2
    except (ValueError,OSError,TypeError) as e:print('FAILED / UNCONFIRMED: '+str(e),file=sys.stderr);return 2
if __name__=='__main__':raise SystemExit(main())
