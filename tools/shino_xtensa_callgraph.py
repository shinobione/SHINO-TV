"""Read Xtensa objdump -dC as a direct-call graph: do not confuse linked with callable.

Machine code can call an out-of-line C++ Maintenance::tick(), which then calls
Native::pump(). Checking only the StageA::loop disassembly is too strict.
Indirect callx is NEVER treated as proved reachability.
"""
from collections import deque
import re

HEAD = re.compile(r'(?m)^([0-9a-fA-F]+) <(.+)>:\s*$')
CALL = re.compile(r'\bcall(?:0|4|8|12)\s+([0-9a-fA-F]+)\s+<(.+)>')

def audit(disassembly, root='M9NormalStageA::loop()'):
    hits=list(HEAD.finditer(disassembly))
    if not hits:
        raise ValueError('No Xtensa function labels found in objdump -dC')
    nodes={}
    addresses={}
    for i,m in enumerate(hits):
        addr=int(m.group(1),16)
        name=m.group(2)
        body=disassembly[m.end():hits[i+1].start() if i+1<len(hits) else len(disassembly)]
        nodes[addr]=(name,[(int(x.group(1),16),x.group(2)) for x in CALL.finditer(body)])
        addresses[name]=addr
    roots=[addr for addr,(name,_) in nodes.items() if name==root]
    if len(roots)!=1:
        raise ValueError(f'Expected one compiled {root}, got {len(roots)}')
    start=roots[0]
    visited={start:[nodes[start][0]]}
    queue=deque([start])
    while queue:
        addr=queue.popleft()
        for target,label in nodes[addr][1]:
            if target not in nodes:
                canonical=re.sub(r'\+0x[0-9a-fA-F]+$', '', label)
                target=addresses.get(canonical,target)
            if target in nodes and target not in visited:
                visited[target]=visited[addr]+[nodes[target][0]]
                queue.append(target)
    return visited,nodes

def require_paths(disassembly,markers=(
    'shinoMaintenanceConsent',
    'ShinoInstall::Native::pump',
    'ShinoInstall::Native::begin',
    'ShinoInstall::ReclaimingHttp::quiesce')):
    visited,nodes=audit(disassembly)
    paths={}
    for marker in markers:
        matches=[v for v in visited.values() if marker in v[-1]]
        if not matches:
            root_addr=next(k for k,v in nodes.items() if v[0]=='M9NormalStageA::loop()')
            root_calls=[label for _,label in nodes[root_addr][1]]
            known=[name for name,_ in nodes.values() if marker in name]
            raise AssertionError(
                f'Compiled {marker} NOT reachable from StageA loop: '
                f'symbols_in_elf={known[:8]}; '
                f'loop_direct_calls={root_calls[:15]}; '
                f'reachable_functions={len(visited)}')
        paths[marker]=min(matches,key=len)
    return paths
