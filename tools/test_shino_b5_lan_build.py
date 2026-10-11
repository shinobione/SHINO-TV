"""B5 LAN offline composition tests; no network, UART, device or secrets."""
import unittest
from pathlib import Path
from shino_b5_lan_build import ROOT,patch_normal,add_b5_routes,once


class B5LanComposition(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.b4=(ROOT/"ota/firmware/Normal.cpp").read_text(encoding="utf-8")
        cls.b5=add_b5_routes(patch_normal(cls.b4))

    def test_retains_b4_ota_critical_path(self):
        for literal in (
            "SHINO-HTTP-OTA-1|", "Transfer(uploadHealthy)",
            "transfer->begin(incoming", "transfer->finish(budget())",
            "ESP.restart()", '"/api/v1/update"',
            '"/api/v1/bridge/metrics"', "FslessMetrics::apply",
            "M9NormalDashboard::render()", "M9LittleFsMountProbe::begin()",
            "return b.safe()", "minima.stack",
        ):
            self.assertIn(literal,self.b5,literal)
        self.assertEqual(self.b5.count("Transfer(uploadHealthy)"),1)
        self.assertEqual(self.b5.count("transfer->finish(budget())"),1)
        self.assertEqual(self.b5.count("ESP.restart()"),1)

    def test_lan_requires_network_authority_and_digest_before_body(self):
        self.assertIn("B5Lan::permitted(server)",self.b5)
        self.assertIn("B5Lan::apPeer(server)",self.b5)
        self.assertIn('server.header("X-Shino-Lan-Intent")',self.b5)
        self.assertIn('if(!auth())return false;',self.b5)
        self.assertIn("bytes<3||bytes>99",self.b5)
        self.assertIn("HomeLan::wipe(transferBuffer,sizeof(transferBuffer))",self.b5)
        self.assertIn("B5Lan::poll(uploadBusy)",self.b5)
        self.assertNotIn("network.startAccessPointMode()",self.b5)

    def test_lan_policy_uses_4m2m_in_disposable_copy(self):
        original=(ROOT/"firmware/include/boot/HomeLanPolicy.h").read_text(encoding="utf-8")
        self.assertIn("fsStart==0x100000",original)
        generated=once(original,"fsStart==0x100000","fsStart==0x200000")
        self.assertIn("fsStart==0x200000",generated)
        self.assertIn("sdkStart=0x3fd000",generated)
        self.assertIn("sdkEnd=0x400000",generated)
        self.assertNotEqual(generated,original)

    def test_ap_recovery_and_dhcp_are_source_gated(self):
        b5=(ROOT/"ota/lan/B5Lan.cpp").read_text(encoding="utf-8")
        for phrase in ("wifi_station_get_config_default", "wifi_station_set_config",
                       "wifi_station_set_config_current", "wifi_station_dhcpc_start",
                       "wifi_station_connect", "HomeLan::Controller",
                       "WiFi.softAPdisconnect(false)", "WiFi.enableSTA(true)", "WIFI_STA",
                       "HomeLan::peerOnSubnet", "HomeLan::authority",
                       "challenge.consume", "sdk.safe()", "pendingSince"):
            self.assertIn(phrase,b5)

    def test_failed_sta_start_keeps_protected_recovery_http(self):
        cpp=(ROOT/"ota/lan/B5Lan.cpp").read_text(encoding="utf-8")
        # AP listener success must not be cancelled by a failed SDK STA
        # connection, even on reboot with stored but invalid credentials.
        start=cpp.index("bool applyEffects(unsigned flags)")
        end=cpp.index("} // anonymous namespace",start)
        effects=cpp[start:end]
        self.assertIn("WiFi.softAP(recoveryName,recoverySecret",effects)
        self.assertIn("(void)connectSaved();",effects)
        self.assertNotIn("if(!sdk.connectSaved())return false;",effects)
        self.assertIn("return started;",effects)
        self.assertIn("if(!WiFi.softAP",effects)

    def test_initial_config_store_activates_sta_before_sdk_read(self):
        # Critical for first provisioning from AP-only mode. The earlier
        # Store::change read preceded Sdk::write's enableSTA(true).
        source=(ROOT/"ota/lan/B5Lan.cpp").read_text(encoding="utf-8")
        start=source.index("ProvisionCode provision(")
        body=source[start:source.index("} // namespace B5Lan",start)]
        self.assertLess(body.index("HomeLan::decode("),
                        body.index("WiFi.enableSTA(true)"))
        self.assertLess(body.index("WiFi.enableSTA(true)"),body.index("sdk.read(check)"))
        self.assertIn("if(!WiFi.enableSTA(true))",body)
        # AP persists; no disconnect, reboot or Wi-Fi mode STA-only here.
        self.assertNotIn("WiFi.softAPdisconnect",body)
        self.assertNotIn("WIFI_STA)",body)

    def test_provision_failures_identifiable_without_secrets(self):
        generated=self.b5
        header=(ROOT/"ota/lan/B5Lan.h").read_text(encoding="utf-8")
        cpp=(ROOT/"ota/lan/B5Lan.cpp").read_text(encoding="utf-8")
        codes=("PROVISION_BODY_INCOMPLETE","PROVISION_AP_STATE",
               "PROVISION_INTENT_INVALID","PROVISION_PAYLOAD_INVALID",
               "PROVISION_SDK_READ_FAILED","PROVISION_SDK_WRITE_FAILED_UNKNOWN")
        for code in codes:
            with self.subTest(code=code):
                self.assertIn(code,generated+cpp)
        self.assertNotIn("PROVISION_HOLD",generated)
        self.assertIn("enum class ProvisionCode",header)
        self.assertIn("HomeLan::decode(raw,size,desired,forget)",cpp)
        self.assertIn("check.same(desired)",cpp)
        self.assertIn("HomeLan::wipe(transferBuffer,sizeof(transferBuffer))",generated)
        self.assertNotIn("printf(ssid",generated)
        self.assertNotIn("printf(password",generated)
        # When the parser has not supplied the entire body, NO SDK write.
        self.assertLess(generated.index('PROVISION_BODY_INCOMPLETE'),
                        generated.index('B5Lan::provision(server,transferBuffer'))

    def test_no_implicit_ota_or_source_mutation(self):
        builder=(ROOT/"tools/shino_b5_lan_build.py").read_text(encoding="utf-8")
        self.assertIn("validate_image(raw)",builder)
        self.assertIn("64000<=len(raw)<=0xFEFF0",builder)
        self.assertIn('physical="NOT_RUN"',builder)
        self.assertIn("ota_posts=0",builder)
        self.assertNotIn('["git","push"',builder)
        self.assertNotIn("esptool",builder)

    def test_anchor_fail_closed(self):
        with self.assertRaises(ValueError):
            once("one","missing","two")
        with self.assertRaises(ValueError):
            once("twice twice","twice","once")


if __name__=="__main__":
    unittest.main()
