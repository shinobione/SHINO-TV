"""Prepare one private A/B qualification packet. Offline; no hardware APIs."""
import argparse
import hashlib
import json
import shutil
import subprocess
from pathlib import Path
from shino_http_ota_build import build,ROOT,ENV
from shino_owner_transition import OWNER,load


def prepare_uart(directory,label="A",reference=None):
    """Bind a private copy of the existing single-attempt writer; never run it."""
    directory=Path(directory).resolve()
    if OWNER.resolve() not in directory.parents:raise ValueError("Owner-local packet required")
    report=json.loads((directory/label/"report.json").read_text(encoding="utf-8"))
    from m9_stage1_readback_verify import candidate_bytes
    binary=directory/label/".pio/build"/ENV/"firmware.bin"
    data,inspected=candidate_bytes(binary,report["sha256"])
    if len(data)!=report["bytes"] or report["private"] is not True:raise ValueError("Exact private A required")
    bound=directory/("uart-"+label);bound.mkdir() # A fresh copy, no change to historical tools.
    names=("m9_single_attempt_app_write.py","m9_single_attempt_physical_runner.py",
           "m9_executor_preflight.py","m9_stage1_readback_verify.py","m9_first_migration.py",
           "m9_rtc_neutralization.py","m9_flash_layout.py","m9_phase_l_sources.json","m9_executor_sources.json")
    from m9_executor_preflight import check_hashes
    pins=json.loads((ROOT/"tools/m9_phase_l_sources.json").read_text(encoding="utf-8"))
    check_hashes(ROOT/"tools",pins["executor_helpers_sha256_lf"])
    for name in names:shutil.copyfile(ROOT/"tools"/name,bound/name)
    shutil.copyfile(ROOT/"tools/shino_http_ota_packet_control.py",bound/"packet_control.py")
    rounded=inspected["sector_rounded_write_extent"];blocks=rounded//4096
    target=bound/"m9_single_attempt_app_write.py";body=target.read_text(encoding="utf-8")
    replacements={"FROZEN_BYTES = 399264":f'FROZEN_BYTES = {len(data)}',
                  "FROZEN_SHA256 = '78a8d2d50409974fc775dd3dc9f3dbec4ac8eda839f6d9b338cadf35aab2467c'":f'FROZEN_SHA256 = {report["sha256"]!r}',
                  "ROUNDED_END = 0x062000":f'ROUNDED_END = {rounded:#x}',"BLOCK_COUNT = 98":f'BLOCK_COUNT = {blocks}'}
    for old,new in replacements.items():
        if body.count(old)!=1:raise ValueError("Existing writer binding drift")
        body=body.replace(old,new)
    target.write_text(body,encoding="utf-8")
    # Under Python -I, sys.path excludes the directory containing the script.
    # The sibling m9_stage1_readback_verify.py imports other pinned sibling
    # modules, so calling it directly with -I failed on the owner's first POST
    # verification. Keep -I and restore ONLY this pinned private helper directory.
    post_entry=bound/"verify_post_entry.py"
    post_entry.write_text(
        "import sys\nfrom pathlib import Path\n"
        "sys.path.insert(0, str(Path(__file__).resolve().parent))\n"
        "from m9_stage1_readback_verify import main\n"
        "if __name__ == '__main__':\n    raise SystemExit(main())\n",
        encoding="utf-8")
    runner=bound/"m9_single_attempt_physical_runner.py"
    runner.write_text(runner.read_text(encoding="utf-8").replace("rounded_extent='0x000000..0x061FFF'",f"rounded_extent='0x000000..0x{rounded-1:06X}'"),encoding="utf-8")
    pins["executor_helpers_sha256_lf"][target.name]=hashlib.sha256(body.replace("\r\n","\n").encode()).hexdigest()
    (bound/"m9_phase_l_sources.json").write_text(json.dumps(pins,indent=2)+"\n",encoding="utf-8")
    from m9_rtc_neutralization import LOCAL_PYTHON
    argv=[LOCAL_PYTHON,"-I",str(runner),"--candidate",str(binary),"--expected-sha256",report["sha256"],"--port","COM8",
          "--stub-audit-root",str(ROOT/"research-local/m9-phase-c")]
    reader=[LOCAL_PYTHON,"-I","-m","esptool","--chip","esp8266","--port","COM8","--baud","115200",
            "--stub-version","2","--before","no-reset","--after","no-reset-stub","--connect-attempts","1","read-flash","0","0x400000"]
    commands=dict(status="PRINT_ONLY_NO_COMMAND_EXECUTED",physical_authorized=False,candidate_sha256=report["sha256"],
                  target=0,rounded_end=rounded,begin_count=1,data_blocks=blocks,finish_count=1,automatic_retries=0,
                  uart_audit_argv=argv,uart_execute_argv=argv+["--execute","--owner-go","GO SINGLE ATTEMPT "+report["sha256"]],
                  fresh_pre_argv=reader+[str(directory/"PRE-4MiB.bin")],fresh_post_argv=reader+[str(directory/"POST-4MiB.bin")],
                  verify_post_argv=[LOCAL_PYTHON,"-I",str(post_entry),str(binary),str(directory/"PRE-4MiB.bin"),str(directory/"POST-4MiB.bin"),"--expected-sha256",report["sha256"]],
                  source_sha256_lf={p.name:hashlib.sha256(p.read_bytes().replace(b"\r\n",b"\n")).hexdigest() for p in bound.iterdir()},
                  prerequisites=["Explicit owner permission for exact A, COM8 and PRE/POST reads", "Manually established ROM download mode with GPIO0 LOW", "Fresh private PRE, exact installed image and same 4MiB device verified", "Independent POST verification before manual normal boot"],
                  stop="Any missing acknowledgement, uncertain write or identity mismatch: stop; no retry or recovery write")
    commands["writer_internal_argv"]=commands.pop("uart_execute_argv")
    commands["physical_control"]=dict(candidate=str(binary),helper_directory=bound.name,reference=reference,
        owner_go=dict(pre="GO READ PRE 4MiB "+report["sha256"],write="GO SINGLE ATTEMPT "+report["sha256"],
                      post="GO READ POST 4MiB "+report["sha256"]))
    (directory/"uart-commands.json").write_text(json.dumps(commands,indent=2)+"\n",encoding="utf-8")
    book=directory/"uart-commands.json";digest=hashlib.sha256(book.read_bytes()).hexdigest()
    for action,caption in (("pre","PRE"),("write","WRITE"),("post","POST")):
        launcher=(f'@echo off\ncd /d "{ROOT}"\n'
                  f'echo {caption} {label} - SHA256 {report["sha256"]}\n'
                  'choice /C ON /N /M "Autoriser cette operation physique exacte (O/N) ? "\nif errorlevel 2 exit /b 1\n'
                  f'"{LOCAL_PYTHON}" "{bound/"packet_control.py"}" "{book}" {action} --expected-sha256 {digest} '
                  f'--execute --owner-go "{commands["physical_control"]["owner_go"][action]}"\n'
                  'set "SHINO_PACKET_EXIT=%ERRORLEVEL%"\npause\nexit /b %SHINO_PACKET_EXIT%\n')
        (directory/(caption+"-"+label+".cmd")).write_text(launcher,encoding="utf-8")
    verify=' '.join('"'+argument+'"' for argument in commands["verify_post_argv"])
    (directory/("VERIFY-POST-"+label+".cmd")).write_text(
        f'@echo off\ncd /d "{ROOT}"\n{verify}\n'
        'set "SHINO_VERIFY_EXIT=%ERRORLEVEL%"\npause\nexit /b %SHINO_VERIFY_EXIT%\n',encoding="utf-8")
    return commands


def operator_readme(directory,labels,a,b):
    """Short local procedure, exact private identities, no physical execution."""
    a_label,b_label=labels
    lines=["# SHINO // TV — paquet privé "+a_label+" / "+b_label,
           "", "PRÉPARÉ HORS LIGNE. Aucune opération physique autorisée ou exécutée.",
           "Un nouvel accord propriétaire distinct est requis pour chaque opération exacte.",
           "Ne jamais supprimer un marqueur .attempt, réutiliser une sauvegarde PRE ou relancer un résultat inconnu.",
           "", "Source propre : "+a["source_commit"]+" ; layout 4m2m ; même receiver dans les deux images."]
    for label,report in ((a_label,a),(b_label,b)):
        lines.extend(["", "## "+label, "BIN : "+str(directory/label/".pio/build"/ENV/"firmware.bin"),
                      "Manifest : "+str(directory/label/"release.json"),
                      "Octets : "+str(report["bytes"]), "SHA-256 : "+report["sha256"],
                      "Build ID privé : "+report["build_id"]])
    lines.extend(["", "## Parcours opérateur après les accords exacts", "",
        "1. Établir manuellement le mode ROM connu, GPIO0 LOW. Lancer PRE-"+a_label+".cmd : nouvelle capture 4 MiB, aucun écrasement.",
        "2. Après le PRE, réétablir manuellement le mode ROM connu avec GPIO0 LOW : la lecture laisse un stub actif, que le writer refuse comme session préexistante. Lancer WRITE-"+a_label+".cmd une fois. Le PRE doit correspondre à l'application A installée et au fingerprint privé FS/SDK. Un Begin, blocs DATA uniques, un Finish et un MD5 ; zéro retry.",
        "3. Lancer POST-"+a_label+".cmd puis VERIFY-POST-"+a_label+".cmd. Exiger le BIN exact, son padding et tous les octets protégés inchangés. Arrêter sur tout écart.",
        "4. Après accord de démarrage, libérer GPIO0 et démarrer normalement. Connecter LINK, vérifier les quatre cartes, puis QUALIFY-"+a_label+".cmd. Exiger SHA/build exacts, boot stable, LittleFS/hashs vérifiés, métriques fraîches et planchers mémoire.",
        "5. Après accord OTA portant sur le SHA de "+b_label+", lancer UPDATE-"+b_label+".cmd une fois. Il exige le SHA exécuté de "+a_label+" et réserve un marqueur durable avant l'unique POST. Relancer LINK pour la confirmation après boot ; jamais renvoyer le BIN.",
        "6. Exiger BOOT_AND_TELEMETRY_CONFIRMED : nouveau boot ID, SHA/build de "+b_label+", LittleFS valide, métriques fraîches, OTA enabled et heap d'admission. QUALIFY-"+b_label+".cmd confirme la stabilité et la disponibilité pour une future OTA.",
        "", "Tout reset, seuil non tenu, fingerprint incorrect ou résultat inconnu : STOP, aucun retry ni écriture de récupération.",
        "Heap réception ≥20480, bloc ≥16384, continuation historique libre ≥2048, fragmentation ≤25 ; admission heap ≥25600.",
        "La mémoire RAM des bancs et le saut eboot capturé ne sont pas une preuve physique. Pas de rollback automatique pendant copy_raw.",
        "Les anciens A/B et sauvegardes restent archivés. Ne retirer les pinces/refermer qu'après acceptation physique A2→B2.", ""])
    (directory/"README-OPERATEUR.md").write_text("\n".join(lines),encoding="utf-8")


def prepare(directory,labels=("A","B"),reference_post=None,installed_manifest=None):
    directory=Path(directory).resolve()
    if OWNER.resolve() not in directory.parents or directory.exists():raise ValueError("Fresh owner-local packet directory required")
    if subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip()!="feature/shino-tv-m9-flash-layout-liberation":raise ValueError("Wrong branch")
    if subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip():raise ValueError("Commit reviewed source before private pair")
    config=load();protected={}
    reference=None
    if reference_post is not None:
        ref=Path(reference_post).resolve();installed=json.loads(Path(installed_manifest).read_text(encoding="utf-8"))
        if OWNER.resolve() not in ref.parents or ref.is_symlink() or ref.stat().st_size!=0x400000:raise ValueError("Private 4MiB reference required")
        raw=ref.read_bytes()
        if hashlib.sha256(raw[:installed["bytes"]]).hexdigest()!=installed["sha256"]:raise ValueError("Archived POST does not match installed A")
        reference=dict(path=str(ref),sha256=hashlib.sha256(raw).hexdigest(),installed_bytes=installed["bytes"],installed_sha256=installed["sha256"])
    old=OWNER/"transition-build/.pio/build"/ENV/"firmware.bin"
    for path in (old,OWNER/"owner-credentials.json",OWNER/"transition-report.json",OWNER/"transition-manifest.json"):
        protected[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
    directory.mkdir(parents=True)
    a_label,b_label=labels
    if labels not in (("A","B"),("A2","B2")):raise ValueError("Expected A/B or A2/B2 labels")
    a=build(directory/a_label,True);b=build(directory/b_label,True)
    if a["sha256"]==b["sha256"] or a["build_id"]==b["build_id"]:raise ValueError("A/B must differ")
    for name in labels:
        raw=(directory/name/".pio/build"/ENV/"firmware.bin").read_bytes()
        for field in ("ap_psk","api_token","digest_password"):
            if config[field].encode() not in raw:raise ValueError("Owner credentials not retained in candidate")
        if hashlib.sha256(config["maintenance_password"].encode()).digest() not in raw:raise ValueError("Update key differs")
    for path,sha in protected.items():
        if hashlib.sha256((ROOT/path).read_bytes()).hexdigest()!=sha:raise ValueError("Protected owner file changed")
    updater=ROOT/"companion/shino_update.py"
    launcher=(f'@echo off\ncd /d "{ROOT}"\n'
        f'echo OTA {a_label} vers {b_label} - SHA256 {b["sha256"]}\n'
        'choice /C ON /N /M "Autoriser une unique OTA de cette image exacte (O/N) ? "\nif errorlevel 2 exit /b 1\n'
        f'python "{updater}" --bin "{directory/b_label/".pio/build"/ENV/"firmware.bin"}" '
        f'--manifest "{directory/b_label/"release.json"}" --install --confirm-sha256 {b["sha256"]} '
        f'--expected-current-sha256 {a["sha256"]} --attempt-marker "{directory/("OTA-"+b_label+".attempt")}" '
        f'--receipt "{directory/("OTA-"+b_label+"-receipt.json")}"\n'
        'set "SHINO_OTA_EXIT=%ERRORLEVEL%"\npause\nexit /b %SHINO_OTA_EXIT%\n')
    (directory/("UPDATE-"+b_label+".cmd")).write_text(launcher,encoding="utf-8")
    for name,report in ((a_label,a),(b_label,b)):
        launcher=(f'@echo off\ncd /d "{ROOT}"\n'
                  f'echo SHINO qualification {name}: lectures HTTP seulement, LINK doit fonctionner.\n'
                  f'echo SHA-256 {report["sha256"]}\n'
                  'choice /C ON /N /M "Autoriser ces lectures appareil (O/N) ? "\nif errorlevel 2 exit /b 1\n'
                  f'python "{ROOT/"companion/shino_qualify.py"}" --bin "{directory/name/".pio/build"/ENV/"firmware.bin"}" '
                  f'--manifest "{directory/name/"release.json"}" --authorize-read --receipt "{directory/(name+"-readonly-receipt.json")}"\n'
                  'set "SHINO_QUALIFY_EXIT=%ERRORLEVEL%"\n'
                  'if not "%SHINO_QUALIFY_EXIT%"=="0" echo Qualification interrompue : voir le diagnostic ci-dessus.\n'
                  'pause\nexit /b %SHINO_QUALIFY_EXIT%\n')
        (directory/("QUALIFY-"+name+".cmd")).write_text(launcher,encoding="utf-8")
    packet=dict(status="OFFLINE_READY_PHYSICAL_NOT_RUN",A=a,B=b,source_commit=a["source_commit"],protected_files_unchanged=True,
                serial_port="COM8",device_contacts=0,physical_authorized=False,
                sequence=["Fresh private 4MiB PRE readback and exact identity/size check under separate physical approval",
                          "One UART app-only write of exact A at address 0; independent POST protects application tail, LittleFS and SDK tail",
                          "Release GPIO0, boot A normally; read-only qualification with LINK and stable authenticated GET/POST",
                          "If A qualifies, one authenticated Wi-Fi upload of exact B; no repeated upload",
                          "Confirm new boot, full SHA256/build ID, LittleFS inventory/payload hashes, fresh metrics and future OTA capability",
                          "Only after physical acceptance: disconnect CH340 and close enclosure"],
                stop_on=["Reset/corruption","Memory floor failure","Identity or LittleFS mismatch","Uncertain write/boot","Unavailable recovery"],
                recovery="Private 4MiB backup and UART are the recovery path; no automatic rollback; no recovery write authorized")
    (directory/"qualification-packet.json").write_text(json.dumps(packet,indent=2)+"\n",encoding="utf-8")
    prepare_uart(directory,a_label,reference)
    operator_readme(directory,labels,a,b)
    print("PRIVATE_PAIR_PACKET_READY — PHYSICAL_NOT_RUN")
    print(a_label,a["bytes"],a["sha256"]);print(b_label,b["bytes"],b["sha256"])
    return packet



def prepare_installed_b3(directory, installed_bin, installed_manifest, reference_flash):
    """OFFLINE B2 -> B3 single-app UART packet. Never opens a port or AP.

    A full archived 4MiB dump is an FS/SDK-tail reference, NOT proof that B2
    is installed. Only a separate fresh PRE read validates the running B2
    application bytes and that protected tail before any UART write.
    """
    from m9_stage1_readback_verify import regular_file
    from m9_signed_release import validate_image
    directory=Path(directory).resolve()
    if OWNER.resolve() not in directory.parents or directory.exists():
        raise ValueError("Fresh owner-private B3 packet directory required")
    def owner_file(value):
        path=regular_file(Path(value))
        if OWNER.resolve() not in path.resolve().parents:
            raise ValueError("Installed B2 evidence must remain owner-private")
        return path
    installed_bin=owner_file(installed_bin)
    installed_manifest=owner_file(installed_manifest)
    reference_flash=owner_file(reference_flash)
    if subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip()!="feature/shino-tv-b3-telemetry-scratch-experiment":
        raise ValueError("B3 packet must be built from the reviewed PR #47 branch")
    if subprocess.check_output(["git","status","--porcelain"],cwd=ROOT,text=True).strip():
        raise ValueError("Commit reviewed source before preparing private B3")
    head=subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip()
    if len(head)!=40:raise ValueError("Exact source commit required")
    config=load()
    def unique(pairs):
        out={}
        for key,value in pairs:
            if key in out:raise ValueError("Duplicate installed B2 manifest field")
            out[key]=value
        return out
    old=json.loads(installed_manifest.read_text(encoding="utf-8"),object_pairs_hook=unique)
    if set(old)!={"schema","family","layout","protocol","device","bytes","sha256","build_id"} or (
        type(old["schema"]) is not int or old["schema"]!=1 or
        old["family"]!="SHINO-StageA" or old["layout"]!="4m2m" or
        old["protocol"]!="shino-http-ota-1" or old["device"]!=config["device"] or
        not isinstance(old["sha256"],str) or len(old["sha256"])!=64 or
        not isinstance(old["build_id"],str) or len(old["build_id"])!=64 or
        any(c not in "0123456789abcdef" for c in old["sha256"]+old["build_id"]) or
        type(old["bytes"]) is not int or not 64000<=old["bytes"]<=0xFEFF0):
        raise ValueError("Installed B2 manifest not an exact compatible private 4m2m release")
    installed=installed_bin.read_bytes()
    if len(installed)!=old["bytes"] or hashlib.sha256(installed).hexdigest()!=old["sha256"]:
        raise ValueError("Local B2 BIN and manifest do not match")
    validate_image(installed)
    tail=reference_flash.read_bytes()
    if len(tail)!=0x400000:raise ValueError("Archived private FS/SDK reference must be exactly 4MiB")
    # No assumption that archived A2 application equals currently installed B2:
    # the fresh PRE captured immediately before a future write must prove B2,
    # while the archived reference protects LittleFS and the SDK tail.
    reference=dict(path=str(reference_flash),sha256=hashlib.sha256(tail).hexdigest(),
                   installed_bytes=old["bytes"],installed_sha256=old["sha256"])
    protected={}
    for path in (OWNER/"transition-build/.pio/build"/ENV/"firmware.bin",
                 OWNER/"owner-credentials.json",OWNER/"transition-report.json",
                 OWNER/"transition-manifest.json"):
        local=owner_file(path)
        protected[str(local)]=hashlib.sha256(local.read_bytes()).hexdigest()
    directory.mkdir(parents=True)
    new=build(directory/"B3",True)
    if new.get("private") is not True or new.get("source_dirty") is not False or new.get("source_commit")!=head or (
        new.get("device")!=old["device"] or new.get("sha256")==old["sha256"] or
        new.get("build_id")==old["build_id"] or new.get("layout")!="4m2m"):
        raise ValueError("B3 build provenance or device identity invalid")
    binary=directory/"B3/.pio/build"/ENV/"firmware.bin"
    raw=binary.read_bytes()
    if len(raw)!=new["bytes"] or hashlib.sha256(raw).hexdigest()!=new["sha256"]:
        raise ValueError("B3 BIN changed after private compilation")
    for key in ("ap_psk","api_token","digest_password"):
        if config[key].encode() not in raw:raise ValueError("B3 owner credential missing")
    if hashlib.sha256(config["maintenance_password"].encode()).digest() not in raw:
        raise ValueError("B3 maintenance key changed")
    for name,sha in protected.items():
        if hashlib.sha256(Path(name).read_bytes()).hexdigest()!=sha:
            raise ValueError("Historical owner artifact changed")
    commands=prepare_uart(directory,"B3",reference)
    receipt=directory/"B3-readonly-receipt.json"
    qualifier=ROOT/"companion/shino_coordinated_qualify.py"
    launcher=(f'@echo off\\ncd /d "{ROOT}"\\n'
              f'echo B3 readonly qualification of SHA256 {new["sha256"]}\\n'
              'choice /C ON /N /M "Authorize read-only B3 GETs (O/N) ? "\\nif errorlevel 2 exit /b 1\\n'
              f'python "{qualifier}" --bin "{binary}" --manifest "{directory/"B3/release.json"}" --authorize-read --receipt "{receipt}"\\n'
              'set "SHINO_QUALIFY_EXIT=%ERRORLEVEL%"\\npause\\nexit /b %SHINO_QUALIFY_EXIT%\\n')
    (directory/"QUALIFY-B3.cmd").write_text(launcher,encoding="utf-8")
    guidance=[
        "# SHINO // TV — B2 installed -> B3 UART migration (owner only)",
        "", "**Prepared offline. No physical permission granted. No device contacted.**",
        "This is a single app-only UART path because installed B2 failed its immutable",
        "2048-byte continuation-stack OTA admission (observed historical minimum 1968).",
        "Never lower that floor, repaint its watermark, or retry the failed B2 qualification.",
        "", "## Immutable identities",
        "Source HEAD: "+head,
        "Expected installed B2 SHA256: "+old["sha256"],
        "Candidate B3 SHA256: "+new["sha256"],
        "Candidate B3 bytes: "+str(new["bytes"]),
        "Archived FS/SDK-tail reference SHA256: "+reference["sha256"],
        "", "## Stop-gated owner sequence — requires fresh separate approval",
        "1. Preserve the current working B2 and original private backups; do not reboot/flash automatically.",
        "2. Verify UART clips, 3.3V logic/GND and a stable USB-C supply independently; no powered rewiring.",
        "3. Manually enter ESP8266 ROM mode, then run PRE-B3.cmd once for a NEW full 4MiB backup.",
        "4. The sealed WRITE-B3.cmd refuses to open COM8 unless fresh PRE proves installed",
        "   B2 application bytes and equality of the full protected [0x200000,0x400000)",
        "   LittleFS/SDK tail with the archived reference. No retry if ambiguous.",
        "5. Only after an explicit distinct write approval, run WRITE-B3.cmd once.",
        "6. Re-enter ROM mode manually for POST-B3.cmd once; run VERIFY-POST-B3.cmd",
        "   to compare B3 payload AND all untouched flash against fresh PRE.",
        "7. Remove GPIO0 bridge/CH340 for normal boot. Check four cards, LINK and exact",
        "   B3 identity, then run QUALIFY-B3.cmd read-only once, with LINK coordinated.",
        "", "Any identity, PRE/POST, memory floor, FS inventory or boot discrepancy: STOP.",
        "Keep original 4MiB backup offline. There is no automatic eboot rollback.",
        "Do NOT run an OTA B2->B3 or use historical UPDATE-B.cmd for this transition.",
        "No operation above has been executed by the packet generator.",
    ]
    (directory/"B3-OWNER-OPERATIONS.md").write_text("\\n".join(guidance)+"\\n",encoding="utf-8")
    packet=dict(status="B3_OWNER_PACKET_OFFLINE_ONLY",source_commit=head,
                installed_B2_sha256=old["sha256"],candidate_B3_sha256=new["sha256"],
                archived_FS_reference_sha256=reference["sha256"],
                pre_write_b2_and_fs_crosscheck=True,physical_authorized=False,
                device_contacts=0,serial_io=0,flash_writes=0,ota_writes=0,
                commands=["PRE-B3.cmd","WRITE-B3.cmd","POST-B3.cmd",
                          "VERIFY-POST-B3.cmd","QUALIFY-B3.cmd"])
    (directory/"B3-owner-packet.json").write_text(json.dumps(packet,indent=2)+"\\n",encoding="utf-8")
    print("B3_OWNER_PACKET_OFFLINE_ONLY — NO DEVICE, NO UART, NO OTA")
    return packet


if __name__=="__main__":
    p=argparse.ArgumentParser(description=__doc__);p.add_argument("directory",type=Path);p.add_argument("--prepare-uart-only",action="store_true")
    p.add_argument("--a2-b2",action="store_true");p.add_argument("--reference-post",type=Path);p.add_argument("--installed-manifest",type=Path)
    p.add_argument("--single-b3",action="store_true")
    p.add_argument("--installed-bin",type=Path)
    a=p.parse_args()
    if a.single_b3:
        if a.prepare_uart_only or a.a2_b2 or not a.installed_bin or not a.installed_manifest or not a.reference_post:
            p.error("--single-b3 requires --installed-bin, --installed-manifest and --reference-post only")
        prepare_installed_b3(a.directory,a.installed_bin,a.installed_manifest,a.reference_post)
    elif a.prepare_uart_only:prepare_uart(a.directory,"A2" if a.a2_b2 else "A");print("UART_COMMANDS_PREPARED_OFFLINE_NO_PORT_OPEN")
    else:prepare(a.directory,("A2","B2") if a.a2_b2 else ("A","B"),a.reference_post,a.installed_manifest)
