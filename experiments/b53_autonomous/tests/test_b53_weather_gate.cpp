// SPDX-License-Identifier: GPL-3.0-or-later
#include "B53WeatherGate.h"
#include <cassert>
#include <cstdio>
int main(){
using namespace B53WeatherGate;
assert(allowed(true,true,true,true,false,false,HEAP_MIN,BLOCK_MIN,STACK_MIN,FRAG_MAX));
assert(!allowed(false,true,true,true,false,false,50000,45000,4000,0));
assert(!allowed(true,false,true,true,false,false,50000,45000,4000,0));
assert(!allowed(true,true,false,true,false,false,50000,45000,4000,0));
assert(!allowed(true,true,true,false,false,false,50000,45000,4000,0));
assert(!allowed(true,true,true,true,true,false,50000,45000,4000,0));
assert(!allowed(true,true,true,true,false,true,50000,45000,4000,0));
assert(!allowed(true,true,true,true,false,false,HEAP_MIN-1,BLOCK_MIN,STACK_MIN,0));
assert(!allowed(true,true,true,true,false,false,HEAP_MIN,BLOCK_MIN-1,STACK_MIN,0));
assert(!allowed(true,true,true,true,false,false,HEAP_MIN,BLOCK_MIN,STACK_MIN-1,0));
assert(!allowed(true,true,true,true,false,false,HEAP_MIN,BLOCK_MIN,STACK_MIN,FRAG_MAX+1));
assert(!allowed(true,true,true,true,false,false,28848,28216,2496,3));
std::puts("B53_TLS_RESOURCE_GATE_PASS");
}
