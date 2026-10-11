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
                       "WiFi.softAPdisconnect(false)", "WIFI_AP_STA", "WIFI_STA",
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
        self.assertIn("(void)sdk.connectSaved();",effects)
        self.assertNotIn("if(!sdk.connectSaved())return false;",effects)
        self.assertIn("return started;",effects)
        self.assertIn("if(!WiFi.softAP",effects)

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
