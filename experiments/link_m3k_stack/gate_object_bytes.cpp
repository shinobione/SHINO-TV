// Precise sizeof of the same real C++ Gate across feature variants.
// Only tests static allocation trade-off, never device heap.
#include "../link_m3c_crypto/M3CAuthenticatedIngress.h"
#include <cstdio>
int main() { std::printf("%zu\n",sizeof(ShinoM3C::Gate)); }
