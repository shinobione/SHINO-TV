#pragma once
struct Logger { template<class... A> static void info(A...){} template<class... A>static void error(A...){} };
