// SPDX-License-Identifier: GPL-3.0-or-later
#pragma once
// V2.1 HOST FIXTURE RESPONSE-STATUS CONTRACT ONLY. Not included by the live
// FirstBootBridge, no ESP8266WebServer handler, WiFiServer, actual Digest
// verifier, real HTML/JS, ArduinoJson decoder, LCD update, FS, or OTA writer.
// "DigestPassed" decisions originate ONLY from explicit host fixtures; never
// from an Authorization header. A preview HTTP 200 is NOT device authorization
// and must NOT be used as a production response or telemetry acknowledgment.
#include "boot/NativeOtaLegacySessionReview.h"
#include "boot/NativeOtaLegacyTelemetryReview.h"
#include <cstddef>
#include <cstdint>

namespace ShinoNativeOta {

struct LegacyHttpPreview final {
    int status=403;
    const char* contentType="application/json";
    const char* body="{\"error\":\"HOST_FIXTURE_ONLY_NO_DISPATCH\"}";
    bool wouldChallengeDigest=false; // No real WWW-Authenticate generated.
    bool wouldIssueCookie=false; // No real Set-Cookie generated.
    bool wouldApplyTelemetry=false; // Models success, always false in host fixture.
    bool hasNoStore=true;
    bool hasNoSniff=true; // Security fixture default; live dashboard has separate CSP.
    bool wouldUseDashboardCsp=false;
    bool actualAuthChecked=false;
    bool actualHandlerDispatched=false;
    bool otaWriterPresent=false;
};

class NativeOtaLegacyResponsePreview final {
public:
    // JSON syntax and typed numeric status MUST come from separate fixture
    // decoding/model tests. This object deliberately does not parse JSON.
    static LegacyHttpPreview decide(Port80Plan route,const LegacyDecision& decision,
                                    size_t bodyBytes=0u,bool fixtureJsonParsed=false,
                                    LegacyTelemetryResult fixtureTelemetry=
                                        LegacyTelemetryResult::InvalidEnvelope) {
        LegacyHttpPreview out{};
        if(route==Port80Plan::OtaReservedArm ||
           route==Port80Plan::OtaReservedUpload ||
           route==Port80Plan::OtaReservedReject ||
           route==Port80Plan::LegacyFactoryReturnPost ||
           decision.decision==LegacySessionDecision::FactoryPostDisabled) {
            out.body="{\"error\":\"HOST_FIXTURE_DISABLED_WRITE_NO_FLASH\"}";
            return out;
        }
        switch(decision.decision) {
        case LegacySessionDecision::DigestChallengeOnly:
            out.status=401;
            out.wouldChallengeDigest=true;
            out.body="{\"error\":\"HOST_FIXTURE_DIGEST_CHALLENGE_REQUIRED\"}";
            return out;
        case LegacySessionDecision::BackgroundForbiddenNoChallenge:
            out.status=403;
            out.body="{\"error\":\"Browser session expired; reopen / and authenticate\"}";
            return out; // Never trigger a new background Digest prompt.
        case LegacySessionDecision::UnknownRequiresDigestThen404:
            out.status=404;
            out.body="{\"error\":\"No arbitrary update, erase or filesystem route exists\"}";
            return out;
        case LegacySessionDecision::WouldAcceptMetricsPost:
            if(route!=Port80Plan::LegacyMetricsPost)return out;
            if(bodyBytes<16u || bodyBytes>384u) {
                out.status=413;
                out.body="{\"error\":\"Invalid bounded telemetry payload length\"}";
                return out;
            }
            if(!fixtureJsonParsed) {
                out.status=422;
                out.body="{\"error\":\"Invalid JSON telemetry\"}";
                return out;
            }
            if(fixtureTelemetry!=LegacyTelemetryResult::AcceptedIntoHostFixtureRamOnly) {
                out.status=422;
                out.body="{\"error\":\"Invalid, missing or out-of-range telemetry fields\"}";
                return out;
            }
            out.status=200;
            // The original firmware emits this body only AFTER it actually
            // accepts/apply()s the sample; the host preview does NEITHER.
            out.body="{\"status\":\"RAM_SAMPLE_ACCEPTED\",\"persisted\":false}";
            return out;
        case LegacySessionDecision::WouldIssueReadSession:
            if(route!=Port80Plan::LegacyDashboardGet)return out;
            out.wouldIssueCookie=decision.wouldIssueCookie;
            // Fall through to the read-only route content type.
            break;
        case LegacySessionDecision::ReadAllowed:
            break;
        default:
            return out;
        }
        out.status=200;
        switch(route) {
        case Port80Plan::LegacyDashboardGet:
            out.contentType="text/html; charset=utf-8";
            out.body="HOST_FIXTURE_DASHBOARD_HTML_NOT_SERVED";
            out.wouldUseDashboardCsp=true;
            return out;
        case Port80Plan::LegacyJavascriptGet:
            out.contentType="application/javascript; charset=utf-8";
            out.body="HOST_FIXTURE_JAVASCRIPT_NOT_SERVED";
            return out;
        case Port80Plan::LegacyMetricsGet:
            out.body="{\"mode\":\"FSLESS_PC_TELEMETRY_RAM_ONLY\",\"host_fixture_only\":true,\"real_device_sample_read\":false}";
            return out;
        case Port80Plan::LegacyStatusGet:
            out.body="{\"mode\":\"FIRST_BOOT_BRIDGE\",\"host_fixture_only\":true}";
            return out;
        case Port80Plan::LegacyFsPlanGet:
            out.body="{\"mode\":\"READ_ONLY_FS_MIGRATION_PLAN\",\"host_fixture_only\":true}";
            return out;
        case Port80Plan::LegacyCapabilitiesGet:
            out.body="{\"mode\":\"OTA_MANAGER_READ_ONLY_PREFLIGHT\",\"native_ota_writer_compiled\":false,\"native_ota_upload_route_registered\":false,\"physical_installation_authorized\":false,\"host_fixture_only\":true}";
            return out;
        case Port80Plan::LegacyFactoryReturnGet:
            out.body="{\"host_fixture_only\":true,\"manufacturer_application_return_NOT_EXECUTED\":true}";
            return out;
        default:
            out.status=403;
            out.body="{\"error\":\"HOST_FIXTURE_UNHANDLED_ROUTE\"}";
            return out;
        }
    }
};
} // namespace ShinoNativeOta
