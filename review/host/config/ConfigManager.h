
#pragma once
#include <string>
class ConfigManager{public:unsigned loads=0;std::string token;
    bool loadMountedReadOnly(bool valid){++loads;return valid;}
    void setApiToken(const char* t){token=t;}};
