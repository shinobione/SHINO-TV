String Stream::readStringUntil(char terminator) {
    String ret;
    int c = timedRead();
    while(c >= 0 && c != terminator) {
        ret += (char) c;
        c = timedRead();
    }
    return ret;
}

