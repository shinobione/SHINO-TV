// SPDX-License-Identifier: GPL-3.0-or-later
// Included in generated B5.2 Normal TU, behind existing LAN/Digest admission.
// Reuse only the existing transfer/response scratch and reentrancy lease.
volatile const bool clockPermitted=SHINO_OTA_PRIVATE;
static_assert(sizeof(ClockFreshness::Workspace)<=sizeof(transferStorage),"Borrow existing OTA scratch only");
static_assert(alignof(ClockFreshness::Workspace)<=alignof(ShinoHttpOta::Transfer),"Crypto scratch alignment");
__attribute__((noinline)) void clockSync(){
    ResponseLease lease;
    if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    if(!clockPermitted){respond(403,"{\"error\":\"PUBLIC_INERT_CLOCK_HOLD\"}");return;}
    if(uploadBusy||!budget().safe()){respond(503,"{\"error\":\"CLOCK_RESOURCE_HOLD\"}");return;}
    uint32_t bytes=0;
    if(!length(bytes)||bytes!=B52Clock::FRAME_BYTES){respond(413,"{\"error\":\"CLOCK_FRAME_BOUND\"}");return;}
    size_t received=0;auto& client=server.client();
    while(received<bytes){
        if(uint32_t(millis()-server.requestStarted())>=2000||!client.connected()){
            client.stop();return;
        }
        const size_t n=std::min(size_t(client.available()),size_t(bytes-received));
        if(n){
            const int got=client.read(transferBuffer+received,n);
            if(got<=0){client.stop();return;}
            received+=size_t(got);
        }else yield();
    }
    if(uint32_t(millis()-server.requestStarted())>=2000||!client.connected()||client.available()){
        respond(409,"{\"error\":\"CLOCK_BODY_INCOMPLETE_OR_EXTRA\"}");return;
    }
    if(uploadBusy||!budget().safe()){respond(503,"{\"error\":\"CLOCK_RESOURCE_HOLD\"}");return;}
    auto* crypto=new(transferStorage) ClockFreshness::Workspace;
    const bool accepted=B52Clock::synchronize(transferBuffer,received,server.requestStarted(),millis(),SHINO_RESCUE_HTTP_PASSWORD,*crypto);
    crypto->~Workspace();ClockFreshness::wipe(transferStorage,sizeof(ClockFreshness::Workspace));
    if(!accepted){
        respond(422,"{\"error\":\"CLOCK_FRAME_INVALID\"}");return;
    }
    respond(200,"{\"status\":\"CLOCK_SAMPLE_ACCEPTED\",\"persisted\":false}");
}
__attribute__((noinline)) void clockStatus(){
    ResponseLease lease;if(!lease){respond(503,"{\"error\":\"RESPONSE_BUSY\"}");return;}
    const bool issued=clockPermitted&&B52Clock::challenge(millis());
    if(clockPermitted&&!issued){respond(503,"{\"error\":\"CLOCK_CHALLENGE_HOLD\"}");return;}
    char* bootHex=reinterpret_cast<char*>(transferBuffer);char* nonceHex=bootHex+33;
    bootHex[0]=nonceHex[0]='\0';
    if(issued){ShinoHttpOta::encode(B52Clock::bootToken(),16,bootHex);ShinoHttpOta::encode(B52Clock::challengeToken(),16,nonceHex);}
    const auto s=B52Clock::snapshot(millis());
    const int n=std::snprintf(responseBody,sizeof(responseBody),
        "{\"protocol\":\"shino-pc-clock-2\",\"clock_enabled\":%s,\"valid\":%s,\"synced\":%s,"
        "\"utc_s\":%u,\"offset_min\":%d,\"age_ms\":%u,\"remaining_ms\":%u,"
        "\"boot\":\"%s\",\"challenge\":\"%s\",\"challenge_ms\":%u}",
        clockPermitted?"true":"false",s.valid?"true":"false",s.synced?"true":"false",
        unsigned(s.utc),int(s.offsetMinutes),unsigned(s.ageMs),unsigned(s.remainingMs),bootHex,nonceHex,
        issued?unsigned(ClockFreshness::CHALLENGE_MS):0U);
    if(n<0||size_t(n)>=sizeof(responseBody)){respond(500,"{\"error\":\"CLOCK_STATUS_BOUND\"}");return;}
    respond(200,responseBody);
}

