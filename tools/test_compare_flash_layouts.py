import unittest
from compare_flash_layouts import compare, report_total, rounded, IMAGE_BYTES, LAYOUTS, FS_END


class ComparativeLayoutGateTests(unittest.TestCase):
    def test_real_owner_storage_matches_4m3m_exactly_not_other_maps(self):
        report=compare(3121152)
        self.assertEqual(report["matching_linker_layouts"], ["4m3m"])
        self.assertEqual(FS_END-LAYOUTS["4m3m"],3121152)
        self.assertEqual(FS_END-LAYOUTS["4m2m"],2072576)
        self.assertEqual(FS_END-LAYOUTS["4m1m"],1024000)

    def test_known_bin_sizes_and_theoretical_stock_staging(self):
        result=compare(3121152)
        images={x["image"]:x for x in result["image_comparison"]}
        self.assertEqual(rounded(IMAGE_BYTES["official_Ultra_V9_0_44"]),495616)
        self.assertEqual(result["modeled_stock_free_sketch_bytes_NOT_measured"],552960)
        self.assertEqual(images["SHINO_experimental_CI_36267887773"]["rounded_to_sector"],458752)
        self.assertTrue(images["SHINO_experimental_CI_36267887773"]["modeled_4m3m_free_sketch_fit"])
        self.assertFalse(images["smalltv_mod_v2_16_0"]["modeled_4m3m_free_sketch_fit"])
        self.assertFalse(images["smalltv_mod_lean_v2_16_0"]["modeled_4m3m_free_sketch_fit"])

    def test_full_release_is_not_mistaken_for_small_loader(self):
        result=compare(3121152)
        by_name={x["image"]:x for x in result["image_comparison"]}
        self.assertTrue(by_name["smalltv_mod_loader_v2_16_0"]["modeled_4m3m_free_sketch_fit"])
        self.assertGreater(by_name["smalltv_mod_v2_16_0"]["bytes"],by_name["smalltv_mod_loader_v2_16_0"]["bytes"])

    def test_no_size_comparison_can_authorize_real_flash_or_erase(self):
        result=compare(3121152)
        for field in ("stock_OTA_capacity_proven","manufacturer_full_flash_backup_available",
                      "OEM_FS_preserved_after_layout_switch_proven","permission_to_flash"):
            self.assertFalse(result[field])
        self.assertTrue(all(x["device_upload_tested"] is False for x in result["image_comparison"]))

    def test_unknown_storage_total_does_not_force_a_match(self):
        report=compare(2000000)
        self.assertEqual(report["matching_linker_layouts"],[])
        self.assertFalse(report["stock_OTA_capacity_proven"])

    def test_accepts_only_sanitized_report_and_named_filesystem_field(self):
        report={"tool":"SHINO-TV_stock_V9.0.44_readonly_audit","observations":{
           "/space.json":{"status":"observed","data":{
               "storage_kind":"images_and_gifs_filesystem_NOT_OTA_slot",
               "total_bytes":3121152,"free_bytes":1056268
           }}}}
        self.assertEqual(report_total(report),3121152)
        report["observations"]["/space.json"]["data"]["storage_kind"]="ota"
        with self.assertRaisesRegex(ValueError,"storage type"):
            report_total(report)
        report["observations"]["/space.json"]["data"]["storage_kind"]="images_and_gifs_filesystem_NOT_OTA_slot"
        report["observations"]["/space.json"]["data"]["total_bytes"]="3121152"
        with self.assertRaisesRegex(ValueError,"filesystem size"):
            report_total(report)


if __name__=="__main__":
    unittest.main()
