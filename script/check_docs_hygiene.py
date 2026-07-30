#!/usr/bin/env python3
"""Check current docs for stale product-boundary wording."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib
import json
import re
import runpy
import sys

if __package__:
    from script.check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )
else:
    from check_release_version_ledger import (
        LedgerError,
        parse_release_version_ledger,
    )


ROOT = Path(__file__).resolve().parents[1]
README_PATH = ROOT / "README.md"
PHYSICAL_QR_OBSERVATION_MANIFEST = (
    ROOT / "docs/evidence/physical-qr-pairing-20260719.json"
)
OLLAMA_MULTILINGUAL_FULL_MATRIX_V3_RESULT = (
    ROOT
    / "docs"
    / "evidence"
    / "ollama-embedding-multilingual-full-matrix-v3.json"
)
LOCAL_RELEASE_MARKETING_VERSION = "1.0.0"
LOCAL_RELEASE_BUILD_NUMBER = 22
CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION = 4
LOCAL_RELEASE_ID = (
    f"aetherlink-{LOCAL_RELEASE_MARKETING_VERSION}"
    f"+{LOCAL_RELEASE_BUILD_NUMBER}-local-v1"
)
LOCAL_RELEASE_CURRENT_DOC = ROOT / "docs/releases/1.0.0-build-22-local-v1.md"
HISTORICAL_BUILD20_RELEASE_DOC = (
    ROOT / "docs/releases/1.0.0-build-20-local-v1.md"
)
HISTORICAL_BUILD20_RELEASE_DOCUMENT_SHA256 = (
    "fd0082f3bbc6922e25cd490d32c7b0c82e4b7ffd1e622f9951cc63813f8d1615"
)
LATEST_RECORDED_GIT_REFRESH_HEAD = (
    "88c0282722eb0afb3ce2d6f394fedb1f22a7ec7c"
)
LATEST_RECORDED_GIT_REFRESH_LABEL = "2026-07-30 11:44 KST"
LOCAL_RELEASE_FIXTURE_BUILD_NUMBER = 3
LOCAL_RELEASE_FIXTURE_ID = (
    f"aetherlink-{LOCAL_RELEASE_MARKETING_VERSION}"
    f"+{LOCAL_RELEASE_FIXTURE_BUILD_NUMBER}-local-v1"
)
LOCAL_RELEASE_FIXTURE_DOC = (
    ROOT / "docs/releases/1.0.0-build-3-local-v1.md"
)
LOCAL_RELEASE_FIXTURE_READBACK_COMMAND = (
    "python3 script/check_release_artifact_archive.py \\\n"
    "  --archive-dir dist/releases/aetherlink-1.0.0+3-local-v1 \\\n"
    "  --historical"
)
# Backward-compatible fixture handle for the focused fixture-mutation tests.
LOCAL_RELEASE_DOC = LOCAL_RELEASE_FIXTURE_DOC
LOCAL_RELEASE_ARCHIVE_DIR = ROOT / "dist/releases" / LOCAL_RELEASE_ID
LOCAL_RELEASE_REPRODUCIBILITY_RESULT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+22-local-v1-two-root-v4.json"
)
LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+22-local-v1-two-root-v4-prepublication.json"
)
MACOS_CLEAN_HOME_INSTALLED_APP_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-14-clean-home-install-v1.json"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-20-clean-home-install-v1.json"
)
MACOS_CLEAN_HOME_INSTALLED_APP_RUNNER = (
    ROOT / "script/run_macos_clean_home_installed_app_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_APP_TEST = (
    ROOT / "script/test_run_macos_clean_home_installed_app_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-14-clean-home-state-recovery-v1.json"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-packaged-app-build-20-local-dmg-install-v1.json"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER = (
    ROOT / "script/run_macos_local_dmg_install_smoke.py"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_TEST = (
    ROOT / "script/test_run_macos_local_dmg_install_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER = (
    ROOT
    / "script/run_macos_clean_home_installed_state_recovery_smoke.py"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_TEST = (
    ROOT
    / "script/test_run_macos_clean_home_installed_state_recovery_smoke.py"
)
MACOS_PACKAGED_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-13-state-recovery-v1.json"
)
HISTORICAL_BUILD12_STATE_RECOVERY_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-12-state-recovery-v1.json"
)
MACOS_PACKAGED_STATE_RECOVERY_RUNNER = (
    ROOT / "script/run_macos_packaged_app_state_recovery_smoke.py"
)
MACOS_PACKAGED_STATE_RECOVERY_TEST = (
    ROOT / "script/test_run_macos_packaged_app_state_recovery_smoke.py"
)
MACOS_PACKAGED_LIFECYCLE_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-10-lifecycle-v1.json"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RESULT = (
    ROOT
    / "dist/lifecycle/macos-packaged-app-build-9-lifecycle-v1.json"
)
MACOS_PACKAGED_LIFECYCLE_RUNNER = (
    ROOT / "script/run_macos_packaged_app_build10_lifecycle_smoke.py"
)
MACOS_PACKAGED_LIFECYCLE_TEST = (
    ROOT / "script/test_run_macos_packaged_app_build10_lifecycle_smoke.py"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RUNNER = (
    ROOT / "script/run_macos_packaged_app_lifecycle_smoke.py"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_TEST = (
    ROOT / "script/test_run_macos_packaged_app_lifecycle_smoke.py"
)
LOCAL_RELEASE_LEDGER = ROOT / "release/version-ledger.tsv"
LOCAL_RELEASE_G0_DECISION = ROOT / "docs/v1/g0/decision-v1.json"
LOCAL_RELEASE_EXPECTED_ZIP_SIZE = 165_705_774
LOCAL_RELEASE_EXPECTED_ZIP_SHA256 = (
    "478bd4210c11f7e2204e80a333bc8053b0d01b8deff3d0a3d2dd6795df1366c3"
)
LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE = 12_317
LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256 = (
    "a92ee387be3a900bad1682093b653da1fea1a8e1dd1580153bed91c01e2ff1c5"
)
LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE = 99
LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256 = (
    "5711d5926f1c3e053f864f55bccf93a3986fb8bb5a6bcc8818161ef686d75991"
)
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE = 20_353
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256 = (
    "330b671475c0769a0579a0af7cb7f82c746a5df4bb0aba4b305510e597d4081d"
)
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE = 19_645
LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256 = (
    "9293c578b2ca409966c79028ea2b8e9d5e717ae64159b58bd35b90c007d3d26b"
)
LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_RELATIVE = (
    "dist/releases/aetherlink-1.0.0+21-local-v1"
)
LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256 = (
    "8959b4891658101c218e9bf4cefb6ce6dbd894f238992f6a601bcc4f8a72f03a"
)
HISTORICAL_BUILD18_RELEASE_ID = "aetherlink-1.0.0+18-local-v1"
HISTORICAL_BUILD18_ARCHIVE_SIZE = 165_615_149
HISTORICAL_BUILD18_ARCHIVE_SHA256 = (
    "46e9b4884aa97291832e98aa4116a969ac54a7f217548f84a46c50dfeb4a3872"
)
HISTORICAL_BUILD18_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD18_MANIFEST_SHA256 = (
    "0355cb648dc9e25db37c25aa97c286035baf1234e0353e33960c3ad01f1e2bed"
)
HISTORICAL_BUILD18_CHECKSUM_SIZE = 99
HISTORICAL_BUILD18_CHECKSUM_SHA256 = (
    "7ef07058256bfe453b998ef197c5a953c97b058140e086da6f47f412848460b1"
)
HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SIZE = 19_786
HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SHA256 = (
    "6d0a4921e7f1e750d8e828db4057869511a323871fd1f4b53cb2ec83603ebf1f"
)
HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SIZE = 19_785
HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SHA256 = (
    "abcb3619509acacb48f9102386f1762895fdf51f4b6afdc730e519067b4131d7"
)
HISTORICAL_BUILD18_SOURCE_FILE_COUNT = 243
HISTORICAL_BUILD18_SOURCE_SNAPSHOT_SHA256 = (
    "b894108c8ecfdf1a3a914a3bfa67a2c4cd1cbfa59010b6555d26f0be172863d1"
)
HISTORICAL_BUILD18_SOURCE_OVERLAY_SHA256 = (
    "c979f1353df37d6833caf9aa9f0c28f4bc172624ca017c44f1ba2ca89937ce95"
)
HISTORICAL_BUILD18_SOURCE_INVENTORY_SIZE = 47_275
HISTORICAL_BUILD18_SOURCE_INVENTORY_SHA256 = (
    "6292d43773e6d890e17bc878d2874c5f2808b0593174ae9c5dcac56afc75663a"
)
HISTORICAL_BUILD18_MACOS_UUID = "A16CB949-C7E9-3BD7-A1AB-AC5D0662437F"
HISTORICAL_BUILD18_INSTALLED_APP_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-18-clean-home-install-v1.json"
)
HISTORICAL_BUILD18_INSTALLED_APP_RESULT_SIZE = 2_250
HISTORICAL_BUILD18_INSTALLED_APP_RESULT_SHA256 = (
    "b2b88a6fdf1649eab05b94e73b9d5b7f47baaefc9e352da3de982409ce201f62"
)
HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-18-clean-home-state-recovery-v1.json"
)
HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_SIZE = 3_364
HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_SHA256 = (
    "4f5df0d7bf9b15a042bd4430da83019499d6d8b642c2780bef637f46d3e8ce3d"
)
HISTORICAL_BUILD19_RELEASE_ID = "aetherlink-1.0.0+19-local-v1"
HISTORICAL_BUILD19_ARCHIVE_SIZE = 165_617_111
HISTORICAL_BUILD19_ARCHIVE_SHA256 = (
    "d792b3ab39a32b0076c97e206c773845cb1081a477ae1f309395c91699432ec8"
)
HISTORICAL_BUILD19_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD19_MANIFEST_SHA256 = (
    "7379a910bf055813d02bc0ec9810dfee3443655d6c6e4d0f30e548a0cbe2a99a"
)
HISTORICAL_BUILD19_CHECKSUM_SIZE = 99
HISTORICAL_BUILD19_CHECKSUM_SHA256 = (
    "e4a5e593ecbe73e2db9ae6aa4633415635bcfd0c9a6c9386c69f5155fac76f76"
)
HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SIZE = 19_786
HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SHA256 = (
    "e4d041540c73083970a90f4001ec68362824fcd7012e476f57489f40db195fcc"
)
HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SIZE = 19_785
HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SHA256 = (
    "409272907289385d69509ab8f5f9b90911ab11b78deed405490ec823a5d90dca"
)
HISTORICAL_BUILD19_SOURCE_FILE_COUNT = 245
HISTORICAL_BUILD19_SOURCE_SNAPSHOT_SHA256 = (
    "1f38043525dc622bf839137e5da9bbcd4d3731403b3c32b62508da465655ffc5"
)
HISTORICAL_BUILD19_SOURCE_OVERLAY_SHA256 = (
    "8619f1a4dc6c8bf671e8c574c0ebbe6437fb1bf579b1fd9b3eeb67d838a96749"
)
HISTORICAL_BUILD19_SOURCE_INVENTORY_SIZE = 47_645
HISTORICAL_BUILD19_SOURCE_INVENTORY_SHA256 = (
    "8c9c6f861391f3f6ef47f115e527aab81a22e78c99529113048683d7b4366215"
)
HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SIZE = 2_250
HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SHA256 = (
    "a89291227bde1f9f15caa3743339f569e9f7c79380f8f3a70df0a0fe8388b159"
)
HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SIZE = 3_364
HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SHA256 = (
    "1c72536188ce71388319d068489f4c351521f33d5431af36e7acc5ff76bdb2b7"
)
HISTORICAL_BUILD20_RELEASE_ID = "aetherlink-1.0.0+20-local-v1"
HISTORICAL_BUILD20_ARCHIVE_SIZE = 165_617_269
HISTORICAL_BUILD20_ARCHIVE_SHA256 = (
    "cba5a6531c35725aef7a2a3bf8b25d2155833b31b216906c80f8349249f6edf1"
)
HISTORICAL_BUILD20_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD20_MANIFEST_SHA256 = (
    "c633bf2c2ccc9d007f08e73929eed3d7f6b247d08579fa3695bcbad04348c99d"
)
HISTORICAL_BUILD20_CHECKSUM_SIZE = 99
HISTORICAL_BUILD20_CHECKSUM_SHA256 = (
    "dd803b0bc3313d833b0cdd1b2044c96a0f5873496ecdae94c5a4079bb02feaed"
)
HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SIZE = 20_010
HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SHA256 = (
    "ca71f3ad64ea744275035891c5d41faae9778c6be4f1a6fbadac2c1cf2b59a1c"
)
HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SIZE = 19_571
HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SHA256 = (
    "ad7e9b6e5f52a76d5a65b52bab5138ad86eb019b7b89fa7ee29c51b89c7cef2c"
)
HISTORICAL_BUILD20_MACOS_UUID = "0AD0CBED-7293-3151-84D1-9BAF07654A93"
HISTORICAL_BUILD20_SOURCE_FILE_COUNT = 246
HISTORICAL_BUILD20_SOURCE_SNAPSHOT_SHA256 = (
    "22f14e60d522b2720660e41a645a3e9832dd723b8b93b147c51bbf6c9125998c"
)
HISTORICAL_BUILD20_SOURCE_OVERLAY_SHA256 = (
    "f5d3ef4601129d5cde4595c73157d07fe89a3efd9904b3b9c6002504a4583606"
)
HISTORICAL_BUILD20_PREPUBLICATION_SOURCE_OVERLAY_SHA256 = (
    "0fdd31c2e1fcccb3915335b1cfc87c9a3b18c3c1b200f27463687014efc9ddba"
)
HISTORICAL_BUILD20_SOURCE_INVENTORY_SIZE = 47_803
HISTORICAL_BUILD20_SOURCE_INVENTORY_SHA256 = (
    "cb2a13fbc7e441fbad4b5841ca30545bf38ee52f4d1e9be8dfaadfd5f892a1d4"
)
HISTORICAL_BUILD20_RUNTIME_CHAT_HELPER_IDENTITY = (
    11_570,
    "137bcf0cb948f2d82718ef8c6df52147be5a9f713dd6743bc377a9940bece951",
)
HISTORICAL_BUILD20_RUNTIME_CHAT_RUNNER_IDENTITY = (
    26_948,
    "d5a7b11cbed4a0e04f3617a8cce7f69b09f285c95c5825f7ea7f415a811fde53",
)
HISTORICAL_BUILD20_RUNTIME_CHAT_TEST_IDENTITY = (
    13_950,
    "2a9d1add3ac6343aeeeb0b746f1182dbba148321f214a74211fe59b19e888e61",
)
HISTORICAL_BUILD21_RELEASE_ID = "aetherlink-1.0.0+21-local-v1"
HISTORICAL_BUILD21_ARCHIVE_SIZE = 165_617_441
HISTORICAL_BUILD21_ARCHIVE_SHA256 = (
    "b7acd3eb6c4089306dd8e597eb9b952d8dc993535ec13de63099090f155ca9a6"
)
HISTORICAL_BUILD21_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD21_MANIFEST_SHA256 = (
    "d12ceb13b60cbd165c5007d65dfcb50eb522e6df574b4de777d8a09aed815c5f"
)
HISTORICAL_BUILD21_CHECKSUM_SHA256 = (
    "850145f90cdb3ecd1fac90b8623b42c15b0bc5b357c08f7b47cbdc1086163953"
)
HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SIZE = 20_010
HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SHA256 = (
    "b628ee84164ff7405e67520c2ca33d57aee19caad6875cbe61c361c2f3d7da70"
)
HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SIZE = 19_571
HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SHA256 = (
    "5267f145d8237c11fe5425a7148d62237fae942a6d8413eda7f0e9443a0d1c16"
)
HISTORICAL_BUILD21_SOURCE_FILE_COUNT = 247
HISTORICAL_BUILD21_SOURCE_SNAPSHOT_SHA256 = (
    "d948d5abfed0ccfe72429b46104e30847840dd11a2f7a2380d75a29c3d1763b4"
)
HISTORICAL_BUILD21_SOURCE_INVENTORY_SIZE = 47_975
HISTORICAL_BUILD21_SOURCE_INVENTORY_SHA256 = (
    "620262cae041102653b455ac01bc75ebc42dccaf342e10f59244db842055c57e"
)
HISTORICAL_BUILD21_MACOS_UUID = "0AD0CBED-7293-3151-84D1-9BAF07654A93"
HISTORICAL_BUILD14_MARKETING_VERSION = "1.0.0"
HISTORICAL_BUILD14_RELEASE_ID = "aetherlink-1.0.0+14-local-v1"
HISTORICAL_BUILD14_ARCHIVE_SHA256 = (
    "88769137aa024d193a27483522c1986d2d05acf3f03704e690b19b4c578629f4"
)
HISTORICAL_BUILD14_MANIFEST_SHA256 = (
    "e8f7f0ec0358f63bde6a03ff5d7ae50e08b14e530ebed4c5f962704894f8d914"
)
HISTORICAL_BUILD14_MACOS_UUID = "A16CB949-C7E9-3BD7-A1AB-AC5D0662437F"
HISTORICAL_BUILD16_RELEASE_ID = "aetherlink-1.0.0+16-local-v1"
HISTORICAL_BUILD16_ARCHIVE_SIZE = 165_515_492
HISTORICAL_BUILD16_ARCHIVE_SHA256 = (
    "81f89ba20db75fa542f5b4910c469b82d555be2835c1a6bbb66b8daf71d752e7"
)
HISTORICAL_BUILD16_RESULT_SIZE = 19_745
HISTORICAL_BUILD16_RESULT_SHA256 = (
    "b87208f330701f196b6645fa206e5e80e4d8f7367c81611381ed237fbaf5435d"
)
HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE = 20_976
HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256 = (
    "3e489daf520db42683df2852af3d8df917b8d8dd755e3bcda68d11be7090966b"
)
HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE = 20_976
HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256 = (
    "d86b0bbe803e90b0e844ccbae283e9711e50eb21ac4e8f3e94d485e263c4053e"
)
HISTORICAL_BUILD16_DOC = (
    ROOT / "docs/releases/1.0.0-build-16-local-v1.md"
)
HISTORICAL_BUILD16_RESULT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+16-local-v1-two-root-v2.json"
)
HISTORICAL_BUILD16_FAILED_ATTEMPT = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+16-local-v1-two-root-v2-attempt1-failed.json"
)
HISTORICAL_BUILD16_FAILED_CONFIRMATION = (
    ROOT
    / "dist/reproducibility/"
    "aetherlink-1.0.0+16-local-v1-two-root-v2-confirmation.json"
)
HISTORICAL_BUILD17_BUILD_NUMBER = 17
HISTORICAL_BUILD17_RELEASE_ID = "aetherlink-1.0.0+17-local-v1"
HISTORICAL_BUILD17_ARCHIVE_SIZE = 165_515_496
HISTORICAL_BUILD17_ARCHIVE_SHA256 = (
    "ff7e68ffa33ce54a312e2874592528cec0227f3200679f9df6531c06ca32c64e"
)
HISTORICAL_BUILD17_MANIFEST_SIZE = 12_317
HISTORICAL_BUILD17_MANIFEST_SHA256 = (
    "5077da6e0d4c806a5df2112f9eb70ff53064fde7e4faf308662df30564a5cc6e"
)
HISTORICAL_BUILD17_SOURCE_FILE_COUNT = 243
HISTORICAL_BUILD17_SOURCE_INVENTORY_SIZE = 47_275
HISTORICAL_BUILD17_SOURCE_INVENTORY_SHA256 = (
    "6c02c68a64639ade37d9102f62d1e277c4efea383bbd04b21d31996ff462580e"
)
HISTORICAL_BUILD17_SOURCE_SNAPSHOT_SHA256 = (
    "0f57cd63e1fe2c27cfc567df742fe47c6bcb79109630e8830d250f0bd94f9187"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_PATH = (
    "dist/reproducibility/"
    "aetherlink-1.0.0+17-local-v1-two-root-v2.json"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SIZE = 19_786
HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SHA256 = (
    "f2582c6b84d305f34fe4d737604717f5ea9721d6ab8b1125354cbc1798464296"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_PATH = (
    "dist/reproducibility/"
    "aetherlink-1.0.0+17-local-v1-two-root-v2-confirmation.json"
)
HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SIZE = 19_785
HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SHA256 = (
    "616d70882ec8f09c78f7a57730366924c2cc6de28844b7f2c8763ee125f2867a"
)
HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START = (
    "<!-- aetherlink-historical-build17-lifecycle-v1:start -->"
)
HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_END = (
    "<!-- aetherlink-historical-build17-lifecycle-v1:end -->"
)
HISTORICAL_BUILD17_INSTALLED_APP_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-17-clean-home-install-v1.json"
)
HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SIZE = 2_250
HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SHA256 = (
    "c04b13caf494ce7a07c5726e59208c14221578513a3bd554c786636afeaba355"
)
HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_PATH = (
    "dist/lifecycle/"
    "macos-packaged-app-build-17-clean-home-state-recovery-v1.json"
)
HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SIZE = 3_364
HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SHA256 = (
    "c81605c27312c3d0d99134f4c178bd884875e183ac62917378ef1e3f9b9cf180"
)
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE = 2_250
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256 = (
    "dba559878af78be5057b50f4fb5a759e0308724f93b6c358ce2c5e6981d7f6c2"
)
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256 = (
    "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29"
)
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256 = (
    "56127b93951ede623f3b30a4149d83305104841717cd84b0541a44b357e6b161"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE = 3_364
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "434cec7c2fd396a56788abdcfa48edd913950331cedf91159a11f8acc02f657d"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a"
)
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "3a77f1773c927c9a1d7714138cb283bb2eaee5c93243dd9f558a3ca39e5245b2"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE = 2_250
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256 = (
    "4ce047a318e47568d647e1167cbaeebc603626073e098451a29c949086aa3d72"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256 = (
    "55441bb84a9d8e4681af558dc7a1d017333c88fcdeb6ab2a84561c0ee093ca29"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256 = (
    "55274ad4abc958d85c4df1193cfe1508d820768fbbe48eae71a4fee8c1c020aa"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE = 3_364
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "d12947e16e7b985515a90a13731947a5991bcd82a06039210e22bba43535bf0b"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "9d05896a5dcce7e3d7642b41acba2ee4bf6d28ffda85bc8f3b2b645f2a3b273a"
)
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "edfd6f89b2cecd6de5cbfcb337ba6f5643a8d74d7caf8735c467578488970664"
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START = (
    "<!-- aetherlink-historical-build20-lifecycle-v1:start -->"
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END = (
    "<!-- aetherlink-historical-build20-lifecycle-v1:end -->"
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_REPEATABILITY_CLAIM = (
    "Both clean-HOME runners were invoked twice and matched their canonical "
    "results."
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_BOUNDARY_CLAIM = (
    "These historical same-host, per-user Build 20 observations do not "
    "qualify a clean "
    "machine/account, signed/notarized distribution, "
    "UI/accessibility, live-provider behavior, a physical device, arbitrary "
    "histories, crash/power-loss, concurrent writers, backup/transfer, "
    "rollback, or production readiness."
)
CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_BOUNDARY_TERMS = (
    "Build 20",
    "clean machine/account",
    "signed/notarized distribution",
    "UI/accessibility",
    "live-provider behavior",
    "arbitrary histories",
    "crash/power-loss",
    "backup/transfer",
    "rollback",
    "production readiness",
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE = 2_434
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256 = (
    "e78b605278d5c5b7f5601778c38f35270f1db4a9e95055ff434b71af4c33cf78"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256 = (
    "e082ce1aaf7f65bfb63bb2b5fd58136af1510eb6d1689faa1014c018b74129fb"
)
CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256 = (
    "89e566ff26d22eced043ffa108f8719274f9608685d6ecd18e579291c021cf47"
)
CURRENT_RUNTIME_CHAT_SQLITE_SWIFT_TESTS = (
    (
        "testSQLiteCrossInstanceAppendWaitsForImmediateTransactionAnd"
        "CommitsExactlyOnce"
    ),
    "testSQLiteCrossInstanceBusyTimeoutRollsBackAndLaterReopenSucceeds",
    "testSQLiteBusyTimeoutAtCommitRollsBackEventAndFTSRowsBeforeReopen",
)
CURRENT_RUNTIME_CHAT_SQLITE_STABLE_BUSY_MESSAGE = (
    "Runtime chat history is temporarily busy. Try again."
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT = (
    ROOT
    / "dist/lifecycle/"
    "macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE = 2_223
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256 = (
    "db66614d7badd7a0f606c03f91a516dff6d77e539684dcb6daf52709bce0f16f"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START = (
    "<!-- aetherlink-current-build21-abrupt-recovery-v1:start -->"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END = (
    "<!-- aetherlink-current-build21-abrupt-recovery-v1:end -->"
)
CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_BLOCK_SHA256 = {
    "README.md": (
        "3fe613780130d575fc083d721d1b45677569661f7fffa8b4163386112c9cb06f"
    ),
    "docs/roadmap.md": (
        "bb63e6f5198d25908ac010ceb3a2b132462602398bf3f621530131bcccf49ceb"
    ),
    "docs/handoff.md": (
        "61af0160afd46516126d7b453edd689e6b091d394de2e2c80fd82e225b098f42"
    ),
    "docs/progress.md": (
        "c5906554dcc3ddec0b3fc8587f05d89639c6d61d4c3ab3670a67a33d58c52748"
    ),
    "docs/qa-evidence.md": (
        "69ce082b9bc2d0ffdfe63138c80012d375c80871fcbd37da3d80d9859e0a3ac7"
    ),
    "docs/releases/1.0.0-build-22-local-v1.md": (
        "d3a5e47b36a8a444f07c4a307e910141be4ae7784e5ea05ab00acad90a8361b2"
    ),
}
CURRENT_RUNTIME_CHAT_SQLITE_DOCUMENT_REQUIRED_PATTERNS = (
    (
        "production 5-second busy timeout",
        re.compile(
            r"\bproduction\b.{0,100}\b(?:five-second|5-second)\b"
            r".{0,50}\bbusy timeout\b.{0,80}\bevery\b.{0,40}"
            r"\b(?:connection|database connection)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "three deterministic Swift contention tests",
        re.compile(
            r"\bthree deterministic Swift tests\b.{0,500}\bBEGIN\b"
            r".{0,500}\bCOMMIT\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "two independent 48-event writers",
        re.compile(
            r"\btwo independent\b.{0,80}\b(?:helper processes|writer "
            r"processes|48-event writers)\b.{0,160}\b(?:each writer "
            r"appended 48|48 events each|48-event)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "third-process readback",
        re.compile(
            r"\bthird(?: independent|-process)\b.{0,40}\breadback\b"
            r".{0,60}\bprocess\b",
            re.IGNORECASE,
        ),
    ),
    (
        "96 disjoint exactly-once events",
        re.compile(
            r"\b48\+48=96\b.{0,160}\bdisjoint and exactly once\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "owner and session isolation",
        re.compile(r"\bowner/session isolation\b", re.IGNORECASE),
    ),
    (
        "per-writer append order",
        re.compile(
            r"\bper-writer (?:append )?order(?:ing)?\b",
            re.IGNORECASE,
        ),
    ),
    (
        "SQLite integrity",
        re.compile(
            r"\bSQLite integrity\b.{0,80}\bchecks passed\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "owner-only permissions",
        re.compile(
            r"\bpermissions\b.{0,80}`0700`.{0,40}`0600`",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "live evidence is outside the archive",
        re.compile(
            r"\blive\b.{0,100}\bseparate execution evidence\b"
            r".{0,80}\bnot an? (?:retained (?:Build 19 )?)?archive member\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
    (
        "non-production evidence boundary",
        re.compile(
            r"\bdoes not (?:establish|qualify)\b.{0,320}\bproduction (?:behavior|"
            r"readiness)\b",
            re.IGNORECASE | re.DOTALL,
        ),
    ),
)
CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START = (
    "<!-- aetherlink-current-android-drawer-search-ux-v2:start -->"
)
CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_END = (
    "<!-- aetherlink-current-android-drawer-search-ux-v2:end -->"
)
CURRENT_ANDROID_DRAWER_SEARCH_BEHAVIOR_CLAIM = (
    "The current unreleased Android drawer provides an explicit touch Search "
    "action with localized accessibility semantics and the keyboard Search "
    "action through one trimmed-query submission path."
)
CURRENT_ANDROID_DRAWER_SEARCH_ACTION_STATE_CLAIM = (
    "Blank, disconnected, streaming, bulk-mutation, and exact same-query "
    "pending states expose localized action-state descriptions without "
    "dispatching."
)
CURRENT_ANDROID_DRAWER_SEARCH_PENDING_CLAIM = (
    "Only the exact current pending query shows a polite localized progress "
    "live region and suppresses the no-results row; editing or clearing the "
    "query closes that request and invalidates its transient search authority."
)
CURRENT_ANDROID_DRAWER_SEARCH_RESULT_CLAIM = (
    "Only an exact current-query remote response is adopted; stale or absent "
    "response state falls back to immediate local filtering, while current "
    "remote results exclude archived sessions and retain global Runtime rank."
)
CURRENT_ANDROID_DRAWER_SEARCH_EVIDENCE_CLAIM = (
    "The current no-device gate passes 168 AppNavigationTest cases, 22 "
    "navigation-drawer Compose cases, 15 search-related "
    "RuntimeClientViewModelTest cases, and the complete 1,194-test app JVM "
    "suite; release lint reports 0 errors and 2 SDK-version warnings."
)
CURRENT_ANDROID_DRAWER_SEARCH_BOUNDARY_CLAIM = (
    "This source/JVM/Compose evidence is not part of the immutable Build 17 "
    "archive and is first source-bound by the immutable Build 18 archive; it "
    "does not establish physical touch, TalkBack, provider, device, network, "
    "installation, signing, or release behavior."
)
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SIZE = 2_185
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SHA256 = (
    "21f30e0b60e81bcbfb7e8a198c68ef53d6f6c739a63c80a1339278b7565ea769"
)
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256 = (
    "4f3094182ba3b87eb2bb89230df59a14ee10e1db15def87074e66c9ed68d2eca"
)
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_TEST_SHA256 = (
    "d40d3dac44606f2a1e17a44de5564894f68036a0ba0cf7778fba5574306de5db"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE = 1_313
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256 = (
    "c0ea4dba08e74130f7aaa1e9855121d02459249ff5e6a0fc27cd1b01f46f0ded"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE = 1_311
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256 = (
    "aad796ee3c768e37953f18eeea0e6642107750c3a8c398df798a46e96aabab53"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256 = (
    "76c4e5aebf9824d25bba1c57923f6610b648b64876977f7bc7ddc63afae89c0f"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256 = (
    "069372314018138e4781eceaf60b158798eca99d3ed847d71a0282f63695935b"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256 = (
    "3d7ae7ac5b29236babb239769e7e76f6e51b2fc054accb7d53bd88509aa6ee12"
)
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256 = (
    "4b01ac0161969077b027d44aad9f4f838caa1c14d1f807020ef5bca98d9de138"
)
LOCAL_RELEASE_EXPECTED_SOURCE_ROOT_BYTE_LENGTHS = {
    "build-a": 101,
    "build-b": 109,
}
LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT = 247
LOCAL_RELEASE_EXPECTED_SOURCE_SHA256 = (
    "d0ee21c6f288cafad0a0f634de2116b48c8a4716389f2d52daacd4e90c591eb6"
)
LOCAL_RELEASE_EXPECTED_SOURCE_OVERLAY_SHA256 = (
    "c259c24c88e5f88dacfa5eca2c4c6651f5347b10b6fb08f3698dd0822b4028f2"
)
LOCAL_RELEASE_EXPECTED_PREPUBLICATION_SOURCE_OVERLAY_SHA256 = (
    "c259c24c88e5f88dacfa5eca2c4c6651f5347b10b6fb08f3698dd0822b4028f2"
)
LOCAL_RELEASE_EXPECTED_SOURCE_HEAD = (
    "88c0282722eb0afb3ce2d6f394fedb1f22a7ec7c"
)
LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS = {
    "Package.swift": (
        5_893,
        "446f45034b4093735aeab8bffab87b87642741a379502206307b4419ee2100d8",
    ),
    "apps/macos/CompanionCore/Sources/SQLiteRuntimeChatEventStore.swift": (
        113_478,
        "2365118d7ebb7c808ca42caa69366a2cbf10f631cc088dafe9a3ea618c3346bb",
    ),
    (
        "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
        "RuntimeChatSQLiteCrossProcessQA.swift"
    ): (
        26_025,
        "e4251d009e2ac5775d4ad4beaf8d4528c0812749dae64768760c4ce454c20946",
    ),
    "script/run_macos_runtime_chat_cross_process_smoke.py": (
        52_697,
        "f14021e368372dbf14713974277f62c28aa16bd5160bb9d57b964186e0aa0a78",
    ),
    "script/test_run_macos_runtime_chat_cross_process_smoke.py": (
        25_065,
        "1229600eebdf95317e303f81bc60727fce06b81ee3c8a17be6d0c359bd6a1034",
    ),
}
LOCAL_RELEASE_EXPECTED_MEMBER_COUNT = 29
LOCAL_RELEASE_EXPECTED_MACOS_UUID = "E8178DE8-6DC5-3E3D-A8EA-5721BC4F70CA"
LOCAL_RELEASE_EXPECTED_MEMBERS = {
    "android/apk/app-release-unsigned.apk": (
        9_575_138,
        "31dc15d5f6af6fcaa57227818731af332e558a032a5e39b8d5cdc94b28c2af4a",
    ),
    "android/bundle/app-release.aab": (
        10_677_980,
        "324e1487978cef9d1397dfeae00a112ef0bcf37e4c20242cfb1d81cb3f37d410",
    ),
    "android/mapping/mapping.txt": (
        71_910_079,
        "df11c4119f7ddcab82084d93f377d50cd14a1c33d06eae30192df00a0fcc7514",
    ),
    "android/mapping/resources.txt": (
        134_768,
        "002f51ef322a3849b5c4671db6bb6dd89722dfacd0a3418e465939ac406c005a",
    ),
    "macos/AetherLink.app/Contents/MacOS/AetherLink": (
        18_300_464,
        "71c0273479e7121a47f0d788b19229dd8fe39b9c420108cb81a8b59580e251cd",
    ),
    "macos/AetherLink.dSYM/Contents/Resources/DWARF/AetherLink": (
        31_306_138,
        "b72230a02d95073c02b45a8666c20ceceb57d7f302f06944b0ce7bbcfe6b8d8c",
    ),
    "compliance/THIRD_PARTY_LICENSE_INVENTORY.txt": (
        109_725,
        "7bee5eee533db2b7c3ddc88c6e131287a0e641c92fa501bb8e680732da0e92c7",
    ),
    "compliance/release-compliance-metadata-v1.json": (
        94,
        "380bfb4b649035fc1ddbb1a8fa3e8da7bed97aa4910d22d557367332f87e0fdd",
    ),
    "compliance/sbom.spdx.json": (
        252_417,
        "73befa74fc1a5892a656996dcc226d166540d47ae2f165fc7c5914972795d32a",
    ),
    "compliance/third-party-license-inventory-v1.json": (
        411_087,
        "1f97b74e794e5e2b3092cc31ce8c67f634a299989658feca597bc301b67dcda5",
    ),
    "source-files.json": (
        47_975,
        "623a822a77eb033e4c827fc4ef875a5dfd238fe7a933c7a3a9801d966ed1d7e3",
    ),
}
LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK = {
    "member": "android/apk/app-release-unsigned.apk",
    "tool": "aapt2 dump xmltree + resources --no-values",
    "verifiedFields": [
        "allowBackup",
        "dataExtractionRules",
        "fullBackupContent",
    ],
}
LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK = {
    "member": "android/bundle/app-release.aab",
    "tool": "bundletool dump manifest",
    "verifiedFields": [
        "applicationId",
        "minSdk",
        "targetSdk",
        "versionCode",
        "versionName",
        "allowBackup",
        "dataExtractionRules",
        "fullBackupContent",
    ],
}
LOCAL_RELEASE_ANDROID_BACKUP_POLICY_REQUIRED_CLAIMS = (
    "`allowBackup=false`",
    "`dataExtractionRules=@xml/data_extraction_rules`",
    "`fullBackupContent=@xml/backup_rules`",
    "`cloud-backup`",
    "`device-transfer`",
    "`root`, `file`, `database`, `sharedpref`, and `external`",
    (
        "`device_root`, `device_file`, `device_database`, and "
        "`device_sharedpref`"
    ),
    '`path="."`',
    "No `<include>` rule is present.",
    "`aapt2 dump xmltree + resources --no-values`",
    "`bundletool dump manifest`",
    (
        "Build 15 is the first local release that requires both APK and AAB "
        "backup-policy manifest readback."
    ),
    (
        "Build 17 adds compiled XML body readback for both the APK and an "
        "AAB-derived universal APK."
    ),
)
MACOS_PACKAGED_LIFECYCLE_BUILD_NUMBER = 10
MACOS_PACKAGED_LIFECYCLE_RELEASE_ID = "aetherlink-1.0.0+10-local-v1"
MACOS_PACKAGED_LIFECYCLE_MACOS_UUID = "415765ED-429A-36D9-BC1A-BAC6DDF18B45"
MACOS_PACKAGED_LIFECYCLE_ARCHIVE_SHA256 = (
    "12a4fcccceac74248a0835765876bd9184c845696c83cbf3a6b1fe7613000cc0"
)
MACOS_PACKAGED_LIFECYCLE_MANIFEST_SHA256 = (
    "fcda01d30c61be8182fc294ee76d2583b98ec78fee8b0e6c2ec2f9208ea31741"
)
MACOS_PACKAGED_LIFECYCLE_EXECUTABLE_SHA256 = (
    "75f20fad8d5ce20ecdaa07bcdd526b20cb88f46b50dd1639f11f739858ad6ef4"
)
MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT = {
    "app": {
        "buildNumber": MACOS_PACKAGED_LIFECYCLE_BUILD_NUMBER,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": MACOS_PACKAGED_LIFECYCLE_EXECUTABLE_SHA256,
        "marketingVersion": HISTORICAL_BUILD14_MARKETING_VERSION,
        "uuid": MACOS_PACKAGED_LIFECYCLE_MACOS_UUID,
    },
    "isolation": {
        "afInetBindDeniedByPreflight": True,
        "nonTemporaryWriteDeniedByPreflight": True,
        "profile": "allow-default-deny-network-and-non-temp-writes-v1",
        "runtimeIdentity": (
            "temporary-file-override-with-memory-fallback-allowed"
        ),
        "sandboxed": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "release": {
        "archiveSha256": MACOS_PACKAGED_LIFECYCLE_ARCHIVE_SHA256,
        "manifestSha256": MACOS_PACKAGED_LIFECYCLE_MANIFEST_SHA256,
        "releaseId": MACOS_PACKAGED_LIFECYCLE_RELEASE_ID,
    },
    "runs": [
        {
            "activationPolicy": 0,
            "exitCode": 0,
            "finishedLaunching": True,
            "minimumObservationSeconds": 5.0,
            "observationDeadlineReached": True,
            "ordinal": ordinal,
            "terminationAccepted": True,
        }
        for ordinal in (1, 2)
    ],
    "schemaVersion": 1,
    "state": {
        "expectedApplicationSupportFilesPresentAfterRuns": [True, True],
        "identityFilePresentAfterRuns": [False, False],
        "identityFileUnchangedAcrossRuns": False,
        "runtimeIdentityFileOverrideConfigured": True,
    },
    "status": "passed",
}
HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT = {
    **MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT,
    "app": {
        **MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT["app"],
        "buildNumber": 9,
        "executableSha256": (
            "66f4fde6f4ba578f9f6f2a6a4f5fed6f2e27b26e169a868c405fe676535e2c8c"
        ),
        "uuid": "0711F00D-B4B5-316C-A159-2E8BE3FE9FCB",
    },
    "release": {
        "archiveSha256": (
            "e2cbd350bf031d04b6e29054ceb387bbe453e60244b47919c54f6d3c13ba7e1a"
        ),
        "manifestSha256": (
            "56380c239f916ba9d400cc73824ebbda111f61e0baa4d0dc66e8d14e044d05a5"
        ),
        "releaseId": "aetherlink-1.0.0+9-local-v1",
    },
}
MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT = {
    "app": {
        "buildNumber": 13,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": (
            "e4b91c631e460dc23aba8ac0a6d83107326321341dd9f98042d6c712b85fd514"
        ),
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "uuid": "A16CB949-C7E9-3BD7-A1AB-AC5D0662437F",
    },
    "canary": {
        "eventID": "packaged-state-recovery-canary-event-v1",
        "eventJsonSha256": (
            "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
        ),
        "eventJsonSize": 344,
        "legacyJsonlSha256": (
            "0e51fc924836465c4c0921eb3b3709b387f89787aabf2e100c7cff338f0aea2e"
        ),
        "legacyJsonlSize": 345,
        "model": "qa:packaged-state-recovery-canary-v1",
        "requestID": "packaged-state-recovery-canary-request-v1",
        "sessionID": "packaged-state-recovery-canary-session-v1",
    },
    "isolation": {
        "profile": "allow-default-deny-network-and-non-temp-writes-v1",
        "sandboxed": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "release": {
        "archiveSha256": (
            "d48bf8f837c104624b14b1cdc223d5c62aa2c68d13ff6d830f0a394dcd953191"
        ),
        "manifestSha256": (
            "3f720d7119a9196b9a7db085313ac0c9e796ce903b8738bf04406e3fc87b384b"
        ),
        "releaseId": "aetherlink-1.0.0+13-local-v1",
    },
    "runs": [
        {
            "activationPolicy": 0,
            "exitCode": 0,
            "finishedLaunching": True,
            "minimumObservationSeconds": 5.0,
            "observationDeadlineReached": True,
            "ordinal": ordinal,
            "terminationAccepted": True,
        }
        for ordinal in (1, 2)
    ],
    "schemaVersion": 1,
    "stateRecovery": {
        "legacyAbsentBeforeSecondRun": True,
        "legacyFixturePreservedUnchanged": True,
        "migrationObservation": {
            "mode": "migration-read-v1",
            "sha256": (
                "558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9"
            ),
            "size": 70,
            "status": "passed",
        },
        "migrationSQLite": {
            "eventJsonSha256": (
                "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
            ),
            "eventJsonSize": 344,
            "integrityCheck": "ok",
            "totalEventCount": 1,
        },
        "sqliteCanaryUnchangedAcrossRuns": True,
        "sqliteReadbackObservation": {
            "mode": "sqlite-readback-v1",
            "sha256": (
                "ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07"
            ),
            "size": 71,
            "status": "passed",
        },
        "sqliteReadbackSQLite": {
            "eventJsonSha256": (
                "da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef"
            ),
            "eventJsonSize": 344,
            "integrityCheck": "ok",
            "totalEventCount": 1,
        },
    },
    "status": "passed",
}
MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT = {
    "app": {
        "buildNumber": 14,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": (
            "619d96c01723e512e9cc857540f9ef5db97232237e549a419e65b6a62eead1d2"
        ),
        "marketingVersion": HISTORICAL_BUILD14_MARKETING_VERSION,
        "uuid": HISTORICAL_BUILD14_MACOS_UUID,
    },
    "installation": {
        "codesignVerified": True,
        "copyTool": "ditto",
        "installedRelativePath": "Applications/AetherLink.app",
        "regularFileTreeMatchesReleaseManifest": True,
        "tree": {
            "digestAlgorithm": (
                "sha256(path-nul-mode-octal-nul-size-nul-sha256-lf)-v1"
            ),
            "regularFileCount": 10,
            "sha256": (
                "74be59c1986fe6a703c4648a82b8d1c3264ac8e568df7aace186b655edeacc54"
            ),
            "totalRegularFileBytes": 20_828_180,
        },
    },
    "isolation": {
        "cleanHomeConfigured": True,
        "preexistingBundleApplicationsPreserved": True,
        "runtimeIdentityFileOverrideConfigured": True,
        "temporaryCFUserHomeConfigured": True,
    },
    "launchServices": {
        "commandPolicy": (
            "open-new-fresh-background-exact-app-path-v1"
        ),
        "distinctProcessIdentifiers": True,
        "runs": [
            {
                "activationPolicy": 0,
                "executablePathMatched": True,
                "finishedLaunching": True,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": True,
            }
            for ordinal in (1, 2)
        ],
    },
    "limitations": [
        "same-host-per-user-rehearsal-only",
        "not-a-clean-machine-or-dmg-installation",
        "not-developer-id-notarization-or-signed-distribution",
        "not-physical-device-or-live-provider-evidence",
    ],
    "release": {
        "archiveSha256": HISTORICAL_BUILD14_ARCHIVE_SHA256,
        "manifestSha256": HISTORICAL_BUILD14_MANIFEST_SHA256,
        "releaseId": HISTORICAL_BUILD14_RELEASE_ID,
    },
    "schemaVersion": 1,
    "scope": "same-host-per-user-clean-home-launchservices-rehearsal-v1",
    "state": {
        "expectedSQLiteFiles": [
            "runtime-chat-events.sqlite",
            "runtime-document-index.sqlite",
            "runtime-model-pull-approvals.sqlite",
        ],
        "regularFileBytesAndModesUnchangedAcrossRelaunch": True,
        "runtimeIdentityFilePresent": True,
        "sqlite": [
            {
                "filename": "runtime-chat-events.sqlite",
                "integrityCheck": "ok",
                "totalEventCount": 0,
            },
            {
                "filename": "runtime-document-index.sqlite",
                "integrityCheck": "ok",
            },
            {
                "filename": "runtime-model-pull-approvals.sqlite",
                "integrityCheck": "ok",
            },
        ],
    },
    "status": "passed",
}
MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT = {
    "app": MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["app"],
    "canary": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT["canary"],
    "installation": MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT[
        "installation"
    ],
    "isolation": MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["isolation"],
    "launchServices": {
        "commandPolicy": (
            "open-new-fresh-background-exact-app-path-captured-recovery-v1"
        ),
        "distinctProcessIdentifiers": True,
        "runs": [
            {
                "activationPolicy": 0,
                "executablePathMatched": True,
                "finishedLaunching": True,
                "minimumObservationSeconds": 5.0,
                "newProcessIdentifierDetected": True,
                "observationDeadlineReached": True,
                "ordinal": ordinal,
                "terminationAccepted": True,
            }
            for ordinal in (1, 2)
        ],
    },
    "limitations": [
        "same-host-per-user-rehearsal-only",
        "not-a-clean-machine-account-or-dmg-installation",
        "not-ui-accessibility-or-live-provider-evidence",
        "not-physical-device-or-signed-distribution-evidence",
    ],
    "release": {
        "archiveSha256": HISTORICAL_BUILD14_ARCHIVE_SHA256,
        "manifestSha256": HISTORICAL_BUILD14_MANIFEST_SHA256,
        "releaseId": HISTORICAL_BUILD14_RELEASE_ID,
    },
    "schemaVersion": 1,
    "scope": (
        "same-host-per-user-clean-home-launchservices-state-recovery-v1"
    ),
    "stateRecovery": {
        "auxiliarySQLite": [
            {
                "filename": "runtime-document-index.sqlite",
                "integrityCheck": "ok",
            },
            {
                "filename": "runtime-model-pull-approvals.sqlite",
                "integrityCheck": "ok",
            },
        ],
        "installedStateBytesAndModesUnchangedAcrossRelaunch": True,
        "legacyAbsentBeforeSecondRun": True,
        "legacyFixturePreservedUnchanged": True,
        "migrationObservation": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT[
            "stateRecovery"
        ]["migrationObservation"],
        "migrationSQLite": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT[
            "stateRecovery"
        ]["migrationSQLite"],
        "runtimeIdentityFilePresent": True,
        "sqliteCanaryUnchangedAcrossRuns": True,
        "sqliteReadbackObservation": (
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT["stateRecovery"][
                "sqliteReadbackObservation"
            ]
        ),
        "sqliteReadbackSQLite": MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT[
            "stateRecovery"
        ]["sqliteReadbackSQLite"],
    },
    "status": "passed",
}
CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT = {
    **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT,
    "app": {
        "buildNumber": 20,
        "bundleIdentifier": "dev.aetherlink.companion",
        "executableSha256": (
            "92070b85256532b23b327fec5b6a46df2d98f2de89f85750ea6189c838197fb6"
        ),
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "uuid": HISTORICAL_BUILD20_MACOS_UUID,
    },
    "installation": {
        **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"],
        "tree": {
            **MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"][
                "tree"
            ],
            "sha256": (
                "937433afa0f493365bcb823b88f02dbc0eb52294ca15d235a420ed8498572e46"
            ),
            "totalRegularFileBytes": 20_828_260,
        },
    },
    "release": {
        "archiveSha256": HISTORICAL_BUILD20_ARCHIVE_SHA256,
        "manifestSha256": HISTORICAL_BUILD20_MANIFEST_SHA256,
        "releaseId": HISTORICAL_BUILD20_RELEASE_ID,
    },
}
CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT = {
    **MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT,
    "app": CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["app"],
    "installation": (
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["installation"]
    ),
    "release": CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT["release"],
}
LOCAL_RELEASE_TRANSITION_FIXTURE_START = (
    "<!-- aetherlink-release-transition-fixture-v1:start -->"
)
LOCAL_RELEASE_TRANSITION_FIXTURE_END = (
    "<!-- aetherlink-release-transition-fixture-v1:end -->"
)
LOCAL_RELEASE_PROVIDER_FIXTURE_START = (
    "<!-- aetherlink-provider-compatibility-fixture-v1:start -->"
)
LOCAL_RELEASE_PROVIDER_FIXTURE_END = (
    "<!-- aetherlink-provider-compatibility-fixture-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START = (
    "<!-- aetherlink-ollama-exact-version-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END = (
    "<!-- aetherlink-ollama-exact-version-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_START = (
    "<!-- aetherlink-ollama-model-backed-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_END = (
    "<!-- aetherlink-ollama-model-backed-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_START = (
    "<!-- aetherlink-ollama-additional-chat-shape-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_END = (
    "<!-- aetherlink-ollama-additional-chat-shape-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_START = (
    "<!-- aetherlink-ollama-embedding-model-backed-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_END = (
    "<!-- aetherlink-ollama-embedding-model-backed-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_START = (
    "<!-- aetherlink-ollama-embedding-semantic-quality-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_END = (
    "<!-- aetherlink-ollama-embedding-semantic-quality-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_START = (
    "<!-- aetherlink-ollama-embedding-multilingual-semantic-quality-v2:"
    "start -->"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_END = (
    "<!-- aetherlink-ollama-embedding-multilingual-semantic-quality-v2:"
    "end -->"
)
LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_START = (
    "<!-- aetherlink-ollama-vision-model-backed-run-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_END = (
    "<!-- aetherlink-ollama-vision-model-backed-run-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_START = (
    "<!-- aetherlink-ollama-duration-observation-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_END = (
    "<!-- aetherlink-ollama-duration-observation-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_START = (
    "<!-- aetherlink-ollama-live-fault-injection-v1:start -->"
)
LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_END = (
    "<!-- aetherlink-ollama-live-fault-injection-v1:end -->"
)
LOCAL_RELEASE_OLLAMA_RUNNER = (
    ROOT / "script/run_ollama_compatibility_matrix.py"
)
LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_RUNNER = (
    ROOT / "script/run_ollama_additional_chat_shape_matrix.py"
)
LOCAL_RELEASE_OLLAMA_MULTILINGUAL_SEMANTIC_RUNNER = (
    ROOT / "script/run_ollama_multilingual_semantic_matrix.py"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaEmbeddingSemanticQualityTests.swift"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_LIVE_ASSERTION_SOURCE = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaBackendTests.swift"
)
LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_SOURCE = (
    ROOT
    / "apps"
    / "macos"
    / "OllamaBackend"
    / "Tests"
    / "OllamaEmbeddingMultilingualSemanticQualityTests.swift"
)
LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE = {
    "android": {
        "developmentBaseline": "0.1.0+1-debug",
        "inPlaceUpgradeSupported": False,
        "requiredAction": "clean-install-and-fresh-pair",
        "sourceApplicationId": "com.localagentbridge.android",
        "stateMigrationSupported": False,
    },
    "currentRelease": {
        "buildNumber": LOCAL_RELEASE_FIXTURE_BUILD_NUMBER,
        "marketingVersion": LOCAL_RELEASE_MARKETING_VERSION,
        "releaseId": LOCAL_RELEASE_FIXTURE_ID,
    },
    "evidenceBoundary": "policy-fixture-only-no-install-or-state-migration-executed",
    "fixtureId": "aetherlink-first-production-lineage-transition-v1",
    "macos": {
        "developmentBaseline": "pre-production-local-ad-hoc",
        "inPlaceUpgradeSupported": False,
        "requiredAction": "clean-install-and-fresh-pair",
        "sourceBundleId": "dev.aetherlink.companion",
        "stateMigrationSupported": False,
    },
    "nMinusOne": {
        "compatibleReleaseId": None,
        "status": "unproven-no-prior-production-release",
        "upgradePathTested": False,
    },
    "productionPredecessor": None,
    "schemaVersion": 1,
}
LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE = {
    "evidenceBoundary": (
        "exact-version-isolated-ollama-empty-catalog-and-existing-chat-plus-"
        "embedding-plus-vision-model-cold-restart-plus-focused-default-tests-"
        "no-lm-studio-live-or-semantic-qualification"
    ),
    "fixtureId": "aetherlink-provider-compatibility-baseline-v1",
    "lmStudio": {
        "access": "runtime_host_only",
        "currentCandidate": {
            "build": 1,
            "qualified": False,
            "releaseDate": "2026-07-22",
            "schemaSmokeObserved": False,
            "version": "0.4.20",
        },
        "localObservation": {
            "channel": "beta",
            "cliCommit": "6041ae0",
            "fallbackModelsEndpoint": {
                "arrayField": "data",
                "httpStatus": 200,
                "objectField": "list",
                "path": "/v1/models",
            },
            "nativeModelsEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/v1/models",
            },
            "version": "0.4.17-beta+3",
        },
        "minimumSupportedVersion": None,
        "officialSource": "https://lmstudio.ai/changelog",
        "previousCandidate": {
            "build": 2,
            "qualified": False,
            "releaseDate": "2026-07-07",
            "schemaSmokeObserved": False,
            "version": "0.4.19",
        },
        "providerId": "lm_studio",
        "releasePolicy": (
            "exact_rc_current_stable_and_previous_verified_versions"
        ),
        "supportStatus": "unresolved-no-minimum-or-full-qualification",
    },
    "ollama": {
        "access": "runtime_host_only",
        "currentCandidate": {
            "darwinArchiveSha256": (
                "5789dd037a86adb328c72c11fc45e6c558452d07e5b50814a8bdb7b0fbdbcd81"
            ),
            "darwinArchiveUrl": (
                "https://github.com/ollama/ollama/releases/download/"
                "v0.32.5/ollama-darwin.tgz"
            ),
            "isolatedAdapterSmoke": {
                "coldStartPassed": True,
                "emptyCatalogPassed": True,
                "restartPassed": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "chatCompletionPassed": True,
                "coldStartPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedEmbeddingModelBackedSmoke": {
                "catalogPopulated": True,
                "coldStartPassed": True,
                "embeddingBatchPassed": True,
                "embeddingShapePassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedVisionModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "coldStartPassed": True,
                "imageAttachmentPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
                "textChatPassed": True,
            },
            "qualified": False,
            "releaseDate": "2026-07-27",
            "schemaSmokeObserved": True,
            "version": "0.32.5",
        },
        "localObservation": {
            "catalogEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/tags",
            },
            "channel": "stable",
            "runningEndpoint": {
                "arrayField": "models",
                "httpStatus": 200,
                "path": "/api/ps",
            },
            "version": "0.32.4",
            "versionEndpoint": {
                "httpStatus": 200,
                "path": "/api/version",
                "versionField": "version",
            },
        },
        "minimumSupportedVersion": None,
        "officialSource": "https://github.com/ollama/ollama/releases",
        "previousCandidate": {
            "darwinArchiveSha256": (
                "15383493225d5e7e7fda052dc103ab4d2835a22eabb41655f1d6302c6d1577bc"
            ),
            "darwinArchiveUrl": (
                "https://github.com/ollama/ollama/releases/download/"
                "v0.32.4/ollama-darwin.tgz"
            ),
            "isolatedAdapterSmoke": {
                "coldStartPassed": True,
                "emptyCatalogPassed": True,
                "restartPassed": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "chatCompletionPassed": True,
                "coldStartPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedEmbeddingModelBackedSmoke": {
                "catalogPopulated": True,
                "coldStartPassed": True,
                "embeddingBatchPassed": True,
                "embeddingShapePassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
            },
            "isolatedVisionModelBackedSmoke": {
                "catalogPopulated": True,
                "chatCancellationPassed": True,
                "coldStartPassed": True,
                "imageAttachmentPassed": True,
                "installedStatePreserved": True,
                "modelUnloadPassed": True,
                "postCancellationRecoveryPassed": True,
                "restartPassed": True,
                "snapshotUnchanged": True,
                "stoppedEndpointUnavailable": True,
                "textChatPassed": True,
            },
            "qualified": False,
            "releaseDate": "2026-07-25",
            "schemaSmokeObserved": True,
            "version": "0.32.4",
        },
        "providerId": "ollama",
        "releasePolicy": (
            "exact_rc_current_stable_and_previous_verified_versions"
        ),
        "supportStatus": "unresolved-no-minimum-or-full-qualification",
    },
    "recordedDate": "2026-07-29",
    "schemaVersion": 1,
    "tests": {
        "isolatedOllamaExactVersion": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "isolatedOllamaModelBacked": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "isolatedOllamaEmbeddingModelBacked": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "isolatedOllamaVisionModelBacked": {
            "executed": 4,
            "failures": 0,
            "passed": 4,
        },
        "lmStudio": {
            "executed": 71,
            "failures": 0,
            "passed": 70,
            "skipped": 1,
        },
        "ollama": {
            "executed": 78,
            "failures": 0,
            "passed": 72,
            "skipped": 6,
        },
        "testKind": (
            "focused-default-plus-opt-in-isolated-exact-version-empty-and-"
            "chat-plus-embedding-plus-vision-model-backed"
        ),
    },
}


class DuplicateJSONKeyError(ValueError):
    pass


LIVE_FAULT_RUNNER_SOURCE_DIGEST_PATTERN = re.compile(
    r"(?m)^(RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256 = \(\n"
    r'    ")[0-9a-f]{64}("\n\))$'
)


def normalized_live_fault_runner_source_sha256(source: str) -> str:
    normalized, replacement_count = (
        LIVE_FAULT_RUNNER_SOURCE_DIGEST_PATTERN.subn(
            lambda match: (
                match.group(1)
                + ("0" * 64)
                + match.group(2)
            ),
            source,
        )
    )
    if replacement_count != 1:
        raise ValueError(
            "runner must contain exactly one canonical live-fault source "
            "SHA-256 declaration"
        )
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def reject_duplicate_json_keys(
    pairs: list[tuple[str, object]],
) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
        result[key] = value
    return result


def exact_json_values_equal(actual: object, expected: object) -> bool:
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, dict):
        return (
            isinstance(actual, dict)
            and set(actual) == set(expected)
            and all(
                exact_json_values_equal(actual[key], expected[key])
                for key in expected
            )
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(
                exact_json_values_equal(actual_value, expected_value)
                for actual_value, expected_value in zip(actual, expected)
            )
        )
    return actual == expected


@dataclass(frozen=True)
class DocsRule:
    name: str
    pattern: re.Pattern[str]
    guidance: str


@dataclass(frozen=True)
class DocsContract:
    name: str
    required_patterns: tuple[re.Pattern[str], ...]
    guidance: str


@dataclass(frozen=True)
class DocsFileContract:
    name: str
    target: str
    required_patterns: tuple[re.Pattern[str], ...]
    guidance: str


RULES = (
    DocsRule(
        "companion-runtime",
        re.compile(r"\bcompanion runtime\b", re.IGNORECASE),
        "Use AetherLink Runtime, trusted runtime, or runtime host.",
    ),
    DocsRule(
        "runtime-server-hybrid",
        re.compile(r"\bruntime/server\b", re.IGNORECASE),
        "Use runtime host, trusted runtime, or runtime target.",
    ),
    DocsRule(
        "server-targets",
        re.compile(r"\bserver targets?\b", re.IGNORECASE),
        "Use runtime targets unless describing an external infrastructure service.",
    ),
    DocsRule(
        "finished-e2e-transport-claim",
        re.compile(r"\bauthenticated end-to-end encrypted session\b", re.IGNORECASE),
        "Do not imply production transport encryption is complete.",
    ),
    DocsRule(
        "desktop-host-copy",
        re.compile(r"\b(this Mac|Mac alone|this computer|paired computer)\b", re.IGNORECASE),
        "Use runtime host wording so docs stay OS-neutral.",
    ),
    DocsRule(
        "runtime-companion-label",
        re.compile(r"\bAetherLink Runtime companion\b", re.IGNORECASE),
        "Use AetherLink Runtime.",
    ),
    DocsRule(
        "visible-app-language-system-option",
        re.compile(
            r"\b(?:language selector|app-language|app language|language support)\b.*"
            r"\bSystem/Device language\b",
            re.IGNORECASE,
        ),
        "Use the localized Follow system language setting name rather than the stale System/Device language label.",
    ),
    DocsRule(
        "stale-remote-route-diagnostics-title",
        re.compile(r"\bRemote Route Diagnostics\b", re.IGNORECASE),
        "Use Advanced Connection Setup or Connection Setup to match the current runtime UI.",
    ),
    DocsRule(
        "stale-route-host-copy",
        re.compile(r"\broute host(?:/port| and port)?\b", re.IGNORECASE),
        "Use connection address and port.",
    ),
)


HYGIENE_TARGETS = (
    "README.md",
    "apps/android/README.md",
    "apps/macos/README.md",
    "docs/architecture.md",
    "docs/connection-overlay.md",
    "docs/handoff.md",
    "docs/mvp-v0.1.md",
    "docs/protocol.md",
    "docs/qa-evidence.md",
    "docs/releases/1.0.0-build-1-local-v1.md",
    "docs/releases/1.0.0-build-2-local-v1.md",
    "docs/releases/1.0.0-build-3-local-v1.md",
    "docs/releases/1.0.0-build-4-local-v1.md",
    "docs/releases/1.0.0-build-5-local-v1.md",
    "docs/releases/1.0.0-build-6-local-v1.md",
    "docs/releases/1.0.0-build-7-local-v1.md",
    "docs/releases/1.0.0-build-8-local-v1.md",
    "docs/releases/1.0.0-build-9-local-v1.md",
    "docs/releases/1.0.0-build-10-local-v1.md",
    "docs/releases/1.0.0-build-11-local-v1.md",
    "docs/releases/1.0.0-build-12-local-v1.md",
    "docs/releases/1.0.0-build-13-local-v1.md",
    "docs/releases/1.0.0-build-14-local-v1.md",
    "docs/releases/1.0.0-build-15-local-v1.md",
    "docs/releases/1.0.0-build-16-local-v1.md",
    "docs/releases/1.0.0-build-17-local-v1.md",
    "docs/releases/1.0.0-build-18-local-v1.md",
    "docs/releases/1.0.0-build-19-local-v1.md",
    "docs/releases/1.0.0-build-20-local-v1.md",
    "docs/releases/1.0.0-build-21-local-v1.md",
    "docs/releases/1.0.0-build-22-local-v1.md",
    "docs/roadmap.md",
    "docs/security.md",
    "examples/README.md",
)

CONTRACT_TARGETS = tuple(
    target for target in HYGIENE_TARGETS if target != "docs/handoff.md"
)

CONTRACTS = (
    DocsContract(
        "runtime-mediated-backends",
        (
            re.compile(r"\bclient\b.*\b(?:must not|never)\b.*\b(?:call|connects?\s+directly\s+to)\b.*\bOllama\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bclient\b.*\b(?:must not|never)\b.*\b(?:call|connects?\s+directly\s+to)\b.*\bLM Studio\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bAetherLink Runtime\b|\bruntime host\b", re.IGNORECASE),
        ),
        "Docs must preserve the boundary that clients talk to AetherLink Runtime, never directly to Ollama or LM Studio.",
    ),
    DocsContract(
        "qr-overlay-route-model",
        (
            re.compile(r"\bQR-only\b|\bQR\b.*\b(?:pair|route|refresh)", re.IGNORECASE | re.DOTALL),
            re.compile(r"\broute\.refresh\b", re.IGNORECASE),
            re.compile(r"\bprivate overlay\b|\bremote P2P\b|\bNAT traversal\b", re.IGNORECASE),
            re.compile(r"\brelay_secret\b.*\brelay_expires_at\b.*\brelay_nonce\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must describe QR-first pairing/route refresh and remote overlay or relay material instead of fixed-IP reconnect.",
    ),
    DocsContract(
        "runtime-owned-chat-history",
        (
            re.compile(r"\bruntime-owned\b.*\bchat\b|\bchat\b.*\bruntime-owned\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bchat\.sessions\.list\b", re.IGNORECASE),
            re.compile(r"\bchat\.messages\.list\b", re.IGNORECASE),
            re.compile(r"\b(?:redact|redacted|omits?)\b.*\bmessage bodies\b|\bmessage bodies\b.*\b(?:redact|redacted|omits?)\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must keep runtime-owned chat history and client-cache redaction explicit.",
    ),
    DocsContract(
        "five-language-locale-handoff",
        (
            re.compile(r"\bEnglish, Korean, Japanese, Simplified Chinese, and French\b", re.IGNORECASE),
            re.compile(r"\bchat\.send\.locale\b|\blocale handoff\b|\bruntime request locale\b", re.IGNORECASE),
        ),
        "Docs must keep the five-language launch set and runtime locale handoff visible.",
    ),
    DocsContract(
        "runtime-mediated-memory-embedding",
        (
            re.compile(r"\bmemory\b.*\bruntime-(?:owned|mediated)|\bruntime-(?:owned|mediated)\b.*\bmemory\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bembedding models?\b.*\bseparate(?:ly)?\b|\bseparate\b.*\bembedding models?\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bselected embedding model\b|\bMemory indexing model\b", re.IGNORECASE),
        ),
        "Docs must keep memory runtime-mediated and embedding model selection separate from chat model selection.",
    ),
    DocsContract(
        "runtime-mediated-attachments",
        (
            re.compile(r"\battachments?\b.*\bruntime-(?:mediated|side)\b|\bruntime-(?:mediated|side)\b.*\battachments?\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bvision\b.*\bgating\b|\bgating\b.*\bvision\b|\bimage/vision gating\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bdocument ingestion\b|\bdocument attachments?\b", re.IGNORECASE),
        ),
        "Docs must distinguish current runtime-mediated attachment support from remaining physical QA and future ingestion hardening.",
    ),
    DocsContract(
        "future-tools-runtime-only",
        (
            re.compile(r"\bMCP\b.*\b(?:roadmap|future|not v0\.1)\b|\b(?:roadmap|future|not v0\.1)\b.*\bMCP\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bweb search\b.*\b(?:roadmap|future|not v0\.1)\b|\b(?:roadmap|future|not v0\.1)\b.*\bweb search\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\b(?:MCP|web search)\b.*\b(?:AetherLink Runtime|runtime host)\b|\b(?:AetherLink Runtime|runtime host)\b.*\b(?:MCP|web search)\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bclient\b.*\b(?:does not|must not|never)\b.*\b(?:MCP|web search)\b|\b(?:MCP|web search)\b.*\bclient\b.*\b(?:does not|must not|never)\b", re.IGNORECASE | re.DOTALL),
        ),
        "Docs must keep MCP and web search as future runtime-side features, never v0.1 client capabilities.",
    ),
)

FILE_CONTRACTS = (
    DocsFileContract(
        "local-release-qualification-boundary",
        "docs/releases/1.0.0-build-22-local-v1.md",
        (
            re.compile(
                r"\bStatus:\s*local release-engineering candidate,\s*not a production release\b",
                re.IGNORECASE,
            ),
            re.compile(
                r"\bAndroid Debug\b.*\b0\.1\.0\+1\b.*\bnon-migratable\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bN/N-1\b.*\bnot yet qualified\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bAndroid channel\b.*\brollback\b.*\bhigher\s+`versionCode`",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                r"\bcurrent\s+or\s+immediately\s+previous\b.*\bsigned DMG\b",
                re.IGNORECASE | re.DOTALL,
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_ZIP_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256}\b"
            ),
            re.compile(
                rf"\b{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256}\b"
            ),
            re.compile(
                r"\b101-\s+and\s+109-byte source roots\b",
                re.IGNORECASE,
            ),
        ),
        "The local release record must retain its exact artifact identity, non-production boundary, transition limits, and rollback posture.",
    ),
    DocsFileContract(
        "canonical-session-handoff",
        "docs/handoff.md",
        (
            re.compile(r"\bcanonical first document\b", re.IGNORECASE),
            re.compile(r"\bintentionally dirty\b.*\bworktree\b|\bworktree\b.*\bintentionally dirty\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bAndroid device state at handoff:\s*disconnected\b", re.IGNORECASE),
            re.compile(r"\bphysical\b.*\bcamera scan\b.*\bNo URI or deep-link injection\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bPairingQr\b.*\bBonjourDiscovery\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\blocal_diagnostic\b.*\brelease\b.*\bremote-required\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bCurrent Truth Versus Historical Evidence\b", re.IGNORECASE),
            re.compile(r"\bUI Callback Wiring Matrix\b", re.IGNORECASE),
            re.compile(r"\bPairingView\b.*\bmain\b.*\brequestPairingForUserInterface\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bPairing\b.*\bnested Connection Recovery\b.*\brequestRemotePairingForUserInterface\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bDebug And Release Evidence Matrix\b", re.IGNORECASE),
            re.compile(r"\bphysical-qr-pairing-20260719\.json\b", re.IGNORECASE),
            re.compile(r"\bprogress-v8\.json\b.*\bdecision-v6\.json\b.*\bhandoff-v9\.json\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bimplementationAuthorized=false\b.*\bruntimeNetworkIOAllowed=false\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bNot Yet Proven\b", re.IGNORECASE),
            re.compile(r"\bP2P/NAT\b.*\bPhase B\b.*\bproduction\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bGPT-5\.6 Sol\b", re.IGNORECASE),
            re.compile(r"\bHandoff Maintenance Rule\b", re.IGNORECASE),
        ),
        "docs/handoff.md must remain a current, bounded, and executable continuation contract rather than a stale narrative snapshot.",
    ),
    DocsFileContract(
        "roadmap-qr-history-supersession",
        "docs/roadmap.md",
        (
            re.compile(r"\bReading rule:.*\bHistorical Checkpoint\b.*\bcannot override\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bHistorical Checkpoint: macOS Pairing QR Recovery And Bounded Route Preparation \(Superseded\)", re.IGNORECASE),
            re.compile(r"\bProduct result at that checkpoint:", re.IGNORECASE),
            re.compile(r"\bHistorical Checkpoint: Cross-Platform Readiness UI Pass \(Superseded\)", re.IGNORECASE),
            re.compile(r"\blater physical debug result\b.*\bdoes not\b.*\bhistorical aggregate\b", re.IGNORECASE | re.DOTALL),
        ),
        "Historical QR and readiness checkpoints must remain explicitly superseded by the current handoff and roadmap sections.",
    ),
    DocsFileContract(
        "protocol-locale-contract",
        "docs/protocol.md",
        (
            re.compile(r"\bchat\.send\.locale\b", re.IGNORECASE),
            re.compile(r"\bEnglish, Korean, Japanese, Simplified Chinese, and French\b", re.IGNORECASE),
        ),
        "docs/protocol.md must directly define the runtime locale handoff and the five-language launch set.",
    ),
    DocsFileContract(
        "protocol-runtime-memory-client-boundary",
        "docs/protocol.md",
        (
            re.compile(r"\bCurrent clients\b.*\b(?:should not|do not)\b.*\bcached memory\b.*\bchat\.send\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bCompatibility clients?\b", re.IGNORECASE),
            re.compile(r"\bruntime-owned memory store\b|\bruntime-owned memory\b", re.IGNORECASE),
        ),
        "docs/protocol.md must distinguish current client behavior from stale compatibility memory stripping.",
    ),
    DocsFileContract(
        "readme-cross-platform-language-verification",
        "README.md",
        (
            re.compile(r"\bAndroid and macOS five-language app-language verification\b", re.IGNORECASE),
            re.compile(r"\bchat\.send\.locale\b", re.IGNORECASE),
        ),
        "README.md must keep cross-platform language verification and chat.send.locale handoff visible outside historical progress logs.",
    ),
    DocsFileContract(
        "readme-no-device-quality-caveats",
        "README.md",
        (
            re.compile(r"\bno-device gate\b", re.IGNORECASE),
            re.compile(r"\bdoes not require a connected phone\b", re.IGNORECASE),
            re.compile(r"\bphysical Android rendering\b", re.IGNORECASE),
            re.compile(r"\bTalkBack\b.*\bVoiceOver\b|\bVoiceOver\b.*\bTalkBack\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\boptical/camera QR\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat or cancel\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "README.md must keep no-device quality caveats explicit for physical rendering, screen-reader traversal, optical QR, live provider chat/cancel, and real different-network connectivity.",
    ),
    DocsFileContract(
        "qa-current-rule-no-device-quality-caveats",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bCurrent Rule\b", re.IGNORECASE),
            re.compile(r"\bNo-device evidence does not prove\b", re.IGNORECASE),
            re.compile(r"\bphysical Android rendering\b", re.IGNORECASE),
            re.compile(r"\bTalkBack\b.*\bVoiceOver\b|\bVoiceOver\b.*\bTalkBack\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\boptical/camera QR\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat/cancel\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md Current Rule must keep no-device quality caveats explicit before historical evidence entries.",
    ),
    DocsFileContract(
        "qa-owner-device-scoping-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Runtime Owner-Device History And Memory Scoping\b", re.IGNORECASE),
            re.compile(r"\bowner_device_id\b", re.IGNORECASE),
            re.compile(r"\btestAuthenticatedDevicesCannotCrossReadInjectOrMutateChatAndMemory\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeChatStoreScopesSessionsMessagesAndMutationsByOwnerDevice\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeMemoryStoreScopesEntriesByOwnerDevice\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep the latest runtime history/memory owner-device scoping proof visible.",
    ),
    DocsFileContract(
        "qa-android-archived-chat-composer-cleanup",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Archived Chat Composer Cleanup\b", re.IGNORECASE),
            re.compile(r"\barchiveActiveChatClearsNoActiveDraftAndPendingAttachments\b", re.IGNORECASE),
            re.compile(r"\barchiveAllChatsClearsNoActiveDraftAndPendingAttachments\b", re.IGNORECASE),
            re.compile(r"\bsanitizedDropsArchivedSessionComposerDrafts\b", re.IGNORECASE),
            re.compile(r"\bAndroid transient attachment cleanup on chat lifecycle exits\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep archived chat composer cleanup proof visible.",
    ),
    DocsFileContract(
        "qa-android-runtime-transcript-loading-state",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Runtime Transcript Loading State\b", re.IGNORECASE),
            re.compile(r"\bchatComposerHintExplainsActiveTranscriptLoadingLockout\b", re.IGNORECASE),
            re.compile(r"\bopeningRuntimeOwnedChatShowsLoadingAndBlocksComposerUntilMessagesArrive\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShowsLocalizedLoadingStateWhileRuntimeTranscriptLoads\b", re.IGNORECASE),
            re.compile(r"\bAndroid runtime transcript loading state\b", re.IGNORECASE),
            re.compile(r"\bAndroid runtime transcript lifecycle mutation lockout\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android runtime transcript loading proof visible.",
    ),
    DocsFileContract(
        "qa-macos-route-material-redaction",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Route Material Diagnostic Redaction\b", re.IGNORECASE),
            re.compile(r"\btestActivityTechnicalDetailsRedactRouteSecrets\b", re.IGNORECASE),
            re.compile(r"\btestRouteDiagnosticDisclosureRedactsSensitiveDetails\b", re.IGNORECASE),
            re.compile(r"\bmacOS route material diagnostic redaction\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep macOS route material diagnostic redaction proof visible.",
    ),
    DocsFileContract(
        "progress-macos-thinking-runtime-history-evidence",
        "docs/progress.md",
        (
            re.compile(r"\bmacOS Thinking Copy And Sidebar Header Accessibility\b", re.IGNORECASE),
            re.compile(r"\bRuntime History Inspector transcript reasoning\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep macOS Runtime History Thinking/reasoning evidence visible.",
    ),
    DocsFileContract(
        "qa-macos-thinking-runtime-history-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bmacOS Thinking Copy And Sidebar Header Accessibility\b", re.IGNORECASE),
            re.compile(r"\bRuntime History Inspector transcript reasoning\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeHistoryInspectorCopyLocalizesAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewStaysShortUntilExpanded\b", re.IGNORECASE),
            re.compile(r"\btestRuntimeTranscriptReasoningPreviewHandlesShortAndLongParagraphs\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep macOS Runtime History Thinking/reasoning proof visible.",
    ),
    DocsFileContract(
        "progress-android-preference-system-detail-guard",
        "docs/progress.md",
        (
            re.compile(r"\bAndroid Appearance System Detail Polish\b", re.IGNORECASE),
            re.compile(r"\bR\.string\.appearance_system_detail\b", re.IGNORECASE),
            re.compile(r"\blanguage_follow_system_detail\b", re.IGNORECASE),
            re.compile(r"\bAndroid appearance system detail copy\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep Android Settings system appearance/language detail guard evidence visible.",
    ),
    DocsFileContract(
        "qa-android-preference-system-detail-guard",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Appearance System Detail Polish\b", re.IGNORECASE),
            re.compile(r"\bsettingsPreferenceRowsExposeSelectedStateToAccessibility\b", re.IGNORECASE),
            re.compile(r"\blanguage_follow_system_detail\b", re.IGNORECASE),
            re.compile(r"\bAndroid Settings Appearance\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android Settings system appearance/language detail proof visible.",
    ),
    DocsFileContract(
        "progress-android-static-thinking-state-evidence",
        "docs/progress.md",
        (
            re.compile(r"\bAndroid Static Thinking Accessibility\b", re.IGNORECASE),
            re.compile(r"\bassistant_reasoning_state_shown\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\bAndroid short reasoning static accessibility state\b", re.IGNORECASE),
        ),
        "docs/progress.md must keep Android short Thinking static accessibility evidence visible.",
    ),
    DocsFileContract(
        "qa-android-static-thinking-state-evidence",
        "docs/qa-evidence.md",
        (
            re.compile(r"\bAndroid Static Thinking Accessibility\b", re.IGNORECASE),
            re.compile(r"\bassistant_reasoning_state_shown\b", re.IGNORECASE),
            re.compile(r"\bchatScreenShortReasoningIsReadAsStaticThinkingAcrossSupportedLanguages\b", re.IGNORECASE),
            re.compile(r"\bAndroid short reasoning static accessibility state\b", re.IGNORECASE),
        ),
        "docs/qa-evidence.md must keep Android short Thinking static accessibility proof visible.",
    ),
    DocsFileContract(
        "connection-overlay-production-bootstrap-verifier",
        "docs/connection-overlay.md",
        (
            re.compile(r"\bscript/verify_pairing_qr\.swift\b", re.IGNORECASE),
            re.compile(r"--require-production-bootstrap\b", re.IGNORECASE),
            re.compile(r"\bruntime_public_key\b.*\broute_token\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"--require-relay-route\b", re.IGNORECASE),
            re.compile(r"--forbid-direct-endpoint\b", re.IGNORECASE),
        ),
        "docs/connection-overlay.md must document the QR verifier flags that prove production bootstrap fields, relay route material, and no direct endpoint fallback.",
    ),
    DocsFileContract(
        "protocol-product-qr-bootstrap-contract",
        "docs/protocol.md",
        (
            re.compile(r"\bNormal product client scans\b.*\bruntime_public_key\b.*\broute_token\b.*\bremote route material\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bIdentity-only QR\b.*\bcompatibility or diagnostic\b.*\bnormal product scan path\b", re.IGNORECASE | re.DOTALL),
            re.compile(r"\bnormal product QR scans require\b.*\bruntime_public_key\b", re.IGNORECASE | re.DOTALL),
        ),
        "docs/protocol.md must state that normal product QR scans require runtime public key, route token, and remote route material while identity-only QR remains diagnostic/compatibility only.",
    ),
    DocsFileContract(
        "roadmap-no-device-live-proof-split",
        "docs/roadmap.md",
        (
            re.compile(r"\bContinue expanding smoke tests while separating no-device gate coverage from live proof gaps\b", re.IGNORECASE),
            re.compile(r"\bNamed no-device/default-gate coverage currently includes\b", re.IGNORECASE),
            re.compile(r"\bLive/physical proof that remains separate\b", re.IGNORECASE),
            re.compile(r"\bphysical Android QR scan\b", re.IGNORECASE),
            re.compile(r"\blive provider-backed chat/cancel\b", re.IGNORECASE),
            re.compile(r"\bproduction relay allocation\b", re.IGNORECASE),
            re.compile(r"\breal different-network runtime connectivity\b", re.IGNORECASE),
        ),
        "docs/roadmap.md must separate named no-device/default-gate coverage from live physical or production proof gaps.",
    ),
)


PROGRESS_DOC = ROOT / "docs/progress.md"
QA_EVIDENCE_DOC = ROOT / "docs/qa-evidence.md"
QA_CURRENT_RELEASE_READBACK_MARKER = (
    "The Build 22 archive is the latest ledger entry"
)
QA_STALE_RELEASE_READBACK_MARKERS = (
    "The Build 21 archive is the latest ledger entry",
    "The Build 20 archive is the latest ledger entry",
    "The Build 19 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 18 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 17 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 16 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 15 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 14 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 13 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The Build 11 archive is the latest ledger entry and its source-bound "
    "snapshot matches the current release inputs.",
    "The current build 6 archive includes the terminal-less EOF fix and the "
    "settled provider-quality source snapshot.",
    "The current build 5 archive includes the terminal-less EOF fix and the "
    "settled provider-quality source snapshot.",
    "The current build 3 archive includes the terminal-less EOF fix and the "
    "settled provider-quality source snapshot.",
    "The existing local release archive predates the terminal-less EOF fix"
)
RELEASE_READBACK_COMMAND_DOCS = (
    PROGRESS_DOC,
    QA_EVIDENCE_DOC,
    ROOT / "docs/handoff.md",
    LOCAL_RELEASE_CURRENT_DOC,
)


def target_files() -> list[Path]:
    return [path for path in (ROOT / target for target in HYGIENE_TARGETS) if path.is_file()]


def current_release_qa_evidence_failures(
    document_text: str | None = None,
) -> list[str]:
    if document_text is None:
        if not QA_EVIDENCE_DOC.is_file():
            return ["docs/qa-evidence.md: missing current QA evidence file."]
        document_text = QA_EVIDENCE_DOC.read_text(
            encoding="utf-8",
            errors="replace",
        )
    normalized_text = " ".join(document_text.split())
    failures: list[str] = []
    if QA_CURRENT_RELEASE_READBACK_MARKER not in normalized_text:
        failures.append(
            "docs/qa-evidence.md: Build 22 current-source readback marker is "
            "missing."
        )
    for stale_marker in QA_STALE_RELEASE_READBACK_MARKERS:
        if stale_marker in normalized_text:
            failures.append(
                "docs/qa-evidence.md: stale current-release EOF readback claim "
                "must not remain current."
            )
    return failures


def current_release_summary_document_failures(
    *,
    ledger_bytes: bytes | None = None,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    try:
        entries = parse_release_version_ledger(
            LOCAL_RELEASE_LEDGER.read_bytes()
            if ledger_bytes is None
            else ledger_bytes
        )
    except (OSError, LedgerError) as error:
        return [
            "release/version-ledger.tsv: cannot validate current release "
            f"summary documents: {error}"
        ]
    if len(entries) < 2:
        return [
            "release/version-ledger.tsv: current release summary validation "
            "requires a current and previous entry."
        ]

    current = entries[-1]
    previous = entries[-2]
    current_id = (
        f"aetherlink-{current.marketing_version}"
        f"+{current.build_number}-local-v1"
    )
    previous_id = (
        f"aetherlink-{previous.marketing_version}"
        f"+{previous.build_number}-local-v1"
    )
    result_version = CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION
    required_claims_by_relative = {
        "docs/handoff.md": (
            f"Build {current.build_number} is the latest immutable ledger archive.",
            f"v{result_version} comparison-only prepublication result",
            f"v{result_version} publish-qualified result",
            current_id,
            f"Builds 1 through {previous.build_number} are historical",
        ),
        "docs/progress.md": (
            f"Local V1 Build {current.build_number} Qualification",
            (
                f"Build {current.build_number} is the current local "
                "qualification record; Builds 1 through "
                f"{previous.build_number} are immutable historical records."
            ),
            f"Both v{result_version} two-root runs",
            current_id,
            f"Historical Local V1 Build {previous.build_number} Qualification",
        ),
        "docs/qa-evidence.md": (
            f"Local V1 Build {current.build_number} Qualification Checklist",
            (
                f"The Build {current.build_number} archive is the latest "
                "ledger entry"
            ),
            f"Builds 1 through {previous.build_number} remain immutable historical records.",
            current_id,
            (
                f"Historical Local V1 Build {previous.build_number} "
                "Qualification Checklist"
            ),
        ),
        "docs/roadmap.md": (
            (
                f"Build {current.build_number} is the latest immutable local "
                "G6 package qualification record"
            ),
            f"publish-qualified schema-v{result_version} executions",
            f"latest immutable ledger archive is `{current_id}`",
            (
                f"Builds 1 through {previous.build_number} remain separately "
                "readable historical archives."
            ),
        ),
    }
    forbidden_claims_by_relative = {
        "docs/handoff.md": (
            (
                f"Build {previous.build_number} is the latest immutable "
                "ledger archive."
            ),
            f"The v{result_version - 1} comparison-only prepublication result is",
            f"The v{result_version - 1} publish-qualified result is",
        ),
        "docs/progress.md": (
            (
                f"Build {previous.build_number} is the current local "
                "qualification record"
            ),
        ),
        "docs/qa-evidence.md": (
            (
                f"The Build {previous.build_number} archive is the latest "
                "ledger entry"
            ),
        ),
        "docs/roadmap.md": (
            (
                f"Build {previous.build_number} is the latest immutable local "
                "G6 package qualification record"
            ),
            f"latest immutable ledger archive is `{previous_id}`",
            (
                f"publish-qualified schema-v{result_version - 1} executions "
                "reproduced the same"
            ),
        ),
    }
    summary_line_limits = {
        "docs/handoff.md": 650,
        "docs/progress.md": 360,
        "docs/qa-evidence.md": 330,
        "docs/roadmap.md": 380,
    }

    failures: list[str] = []
    for relative, required_claims in required_claims_by_relative.items():
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else (ROOT / relative).read_text(encoding="utf-8")
            )
        except (KeyError, OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current release summary: {error}"
            )
            continue
        summary_text = "\n".join(
            document_text.splitlines()[: summary_line_limits[relative]]
        )
        normalized_text = " ".join(summary_text.split())
        for claim in required_claims:
            normalized_claim = " ".join(claim.split())
            if normalized_claim not in normalized_text:
                failures.append(
                    f"{relative}: missing ledger-derived current release "
                    f"summary claim {claim!r}."
                )
        for claim in forbidden_claims_by_relative[relative]:
            normalized_claim = " ".join(claim.split())
            if normalized_claim in normalized_text:
                failures.append(
                    f"{relative}: stale previous-release summary claim "
                    f"{claim!r} must not coexist with the current release."
                )
        previous_build_reference = re.compile(
            rf"\bBuild\s+{previous.build_number}\b",
            re.IGNORECASE,
        )
        release_context = re.compile(
            r"\b(?:qualification|ledger|archive|release|package|record|"
            r"entry|evidence|result|prepublication|publication)\b",
            re.IGNORECASE,
        )
        current_or_latest = re.compile(
            r"(?<!then-)\b(?:current|latest)\b",
            re.IGNORECASE,
        )
        state_verb = re.compile(
            r"\b(?:is|remain|remains|continues|serves)\b",
            re.IGNORECASE,
        )
        negated_current = re.compile(
            r"\b(?:not|no longer)\b.{0,24}\b(?:current|latest)\b",
            re.IGNORECASE,
        )
        previous_result_version = result_version - 1
        stale_result_version = re.compile(
            (
                rf"(?:\bschema-v{previous_result_version}\b|"
                rf"\bv{previous_result_version}\b.{{0,80}}"
                r"\b(?:comparison-only|publish-qualified)\b|"
                r"\b(?:comparison-only|publish-qualified)\b.{0,80}"
                rf"\bv{previous_result_version}\b)"
            ),
            re.IGNORECASE,
        )
        for sentence in re.split(r"(?<=[.!?])\s+", normalized_text):
            if (
                previous_build_reference.search(sentence)
                and release_context.search(sentence)
                and current_or_latest.search(sentence)
                and state_verb.search(sentence)
                and "historical" not in sentence.lower()
                and not negated_current.search(sentence)
            ):
                failures.append(
                    f"{relative}: previous Build {previous.build_number} "
                    "must not be semantically re-attributed as the current "
                    "or latest release summary."
                )
                break
        for sentence in re.split(r"(?<=[.!?])\s+", normalized_text):
            if (
                stale_result_version.search(sentence)
                and release_context.search(sentence)
                and current_or_latest.search(sentence)
                and state_verb.search(sentence)
                and "historical" not in sentence.lower()
                and not negated_current.search(sentence)
            ):
                failures.append(
                    f"{relative}: reproducibility result schema v"
                    f"{previous_result_version} must not be semantically "
                    "re-attributed as current release evidence."
                )
                break
    return failures


def release_readback_command_mode_failures(
    document_text_by_path: dict[str, str] | None = None,
) -> list[str]:
    failures: list[str] = []
    release_pattern = re.compile(
        r"--archive-dir\s+dist/releases/"
        r"aetherlink-[0-9]+\.[0-9]+\.[0-9]+\+"
        r"(?P<build>[1-9][0-9]*)-local-v1"
    )
    historical_pattern = re.compile(
        r"(?<![\w-])--historical(?![\w-])"
    )

    for path in RELEASE_READBACK_COMMAND_DOCS:
        relative = str(path.relative_to(ROOT))
        if document_text_by_path is None:
            try:
                document_text = path.read_text(
                    encoding="utf-8",
                    errors="replace",
                )
            except OSError as error:
                failures.append(
                    f"{relative}: cannot inspect release readback commands: "
                    f"{error}"
                )
                continue
        else:
            document_text = document_text_by_path.get(relative, "")

        for line_number, line in enumerate(document_text.splitlines(), 1):
            if "check_release_artifact_archive.py" not in line:
                continue
            match = release_pattern.search(line)
            if match is None:
                failures.append(
                    f"{relative}:{line_number}: release readback command must "
                    "name a canonical versioned archive directory on the same "
                    "line."
                )
                continue

            build_number = int(match.group("build"))
            historical_mode = historical_pattern.search(line) is not None
            if build_number < LOCAL_RELEASE_BUILD_NUMBER and not historical_mode:
                failures.append(
                    f"{relative}:{line_number}: historical Build "
                    f"{build_number} release readback command requires "
                    "`--historical`."
                )
            elif (
                build_number == LOCAL_RELEASE_BUILD_NUMBER
                and historical_mode
            ):
                failures.append(
                    f"{relative}:{line_number}: current Build "
                    f"{build_number} release readback command must not use "
                    "`--historical`."
                )
            elif build_number > LOCAL_RELEASE_BUILD_NUMBER:
                failures.append(
                    f"{relative}:{line_number}: release readback command names "
                    f"future Build {build_number}; current Build is "
                    f"{LOCAL_RELEASE_BUILD_NUMBER}."
                )

    return failures


def contract_text() -> str:
    chunks: list[str] = []
    for target in CONTRACT_TARGETS:
        path = ROOT / target
        if path.is_file():
            chunks.append(path.read_text(encoding="utf-8", errors="replace"))
    return "\n".join(chunks)


def file_contract_text(target: str) -> str:
    path = ROOT / target
    if not path.is_file():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def embedded_json_fixture_body(
    document_text: str,
    *,
    start_marker: str,
    end_marker: str,
    fixture_label: str,
) -> tuple[str | None, list[str]]:
    pattern = re.compile(
        re.escape(start_marker)
        + r"\n```json\n(?P<body>.*?)\n```\n"
        + re.escape(end_marker),
        re.DOTALL,
    )
    matches = list(pattern.finditer(document_text))
    if (
        len(matches) != 1
        or document_text.count(start_marker) != 1
        or document_text.count(end_marker) != 1
    ):
        return (
            None,
            [
                "docs/releases/1.0.0-build-3-local-v1.md: expected exactly "
                f"one canonical {fixture_label} fixture block."
            ],
        )

    fixture_body = matches[0].group("body")

    try:
        json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (json.JSONDecodeError, DuplicateJSONKeyError) as error:
        return (
            None,
            [
                "docs/releases/1.0.0-build-3-local-v1.md: invalid "
                f"{fixture_label} fixture JSON: {error}"
            ],
        )

    return fixture_body, []


def local_release_transition_fixture_failures(
    document_text: str,
) -> list[str]:
    failures: list[str] = []
    fixture_body, parse_failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_TRANSITION_FIXTURE_START,
        end_marker=LOCAL_RELEASE_TRANSITION_FIXTURE_END,
        fixture_label="release-transition",
    )
    if fixture_body is None:
        return parse_failures

    expected_body = json.dumps(
        LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: release-transition "
            "fixture must match the canonical first-lineage schema, exact "
            "values, JSON types, and key order."
        )

    try:
        ledger_bytes = LOCAL_RELEASE_LEDGER.read_bytes()
        ledger_entries = parse_release_version_ledger(ledger_bytes)
        fixture_entries = [
            entry
            for entry in ledger_entries
            if entry.build_number == LOCAL_RELEASE_FIXTURE_BUILD_NUMBER
            and entry.marketing_version == LOCAL_RELEASE_MARKETING_VERSION
        ]
        if len(fixture_entries) != 1:
            raise LedgerError(
                "expected exactly one build 3 fixture entry in the release ledger"
            )
        fixture_entry = fixture_entries[0]
        ledger_fixture = {
            "buildNumber": fixture_entry.build_number,
            "marketingVersion": fixture_entry.marketing_version,
            "releaseId": (
                f"aetherlink-{fixture_entry.marketing_version}"
                f"+{fixture_entry.build_number}-local-v1"
            ),
        }
    except (OSError, LedgerError) as error:
        failures.append(
            "release/version-ledger.tsv: cannot cross-check local release "
            f"transition fixture: {error}"
        )
    else:
        if json.dumps(
            ledger_fixture,
            sort_keys=True,
        ) != json.dumps(
            LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"],
            sort_keys=True,
        ):
            failures.append(
                "release/version-ledger.tsv: build 3 entry differs from the "
                "historical local release transition fixture."
            )

    try:
        g0 = json.loads(
            LOCAL_RELEASE_G0_DECISION.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        g0_projection = {
            "androidCurrentApplicationId": (
                g0["releasePolicy"]["android"]["currentApplicationId"]
            ),
            "androidDebugTransition": (
                g0["releasePolicy"]["android"]["currentDebugDataMigration"]
            ),
            "androidProductionApplicationId": (
                g0["releasePolicy"]["android"]["productionApplicationId"]
            ),
            "macosCurrentBundleId": (
                g0["releasePolicy"]["macos"]["currentBundleId"]
            ),
            "macosProductionBundleId": (
                g0["releasePolicy"]["macos"]["productionBundleId"]
            ),
            "marketingVersion": g0["productScope"]["releaseVersion"],
            "policyMarketingVersion": (
                g0["releasePolicy"]["versioning"]["marketingVersion"]
            ),
            "wireCompatibility": (
                g0["releasePolicy"]["compatibility"]["wireAndService"]
            ),
        }
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
        KeyError,
        TypeError,
    ) as error:
        failures.append(
            "docs/v1/g0/decision-v1.json: cannot cross-check local release "
            f"transition fixture: {error}"
        )
    else:
        expected_g0_projection = {
            "androidCurrentApplicationId": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["android"][
                    "sourceApplicationId"
                ]
            ),
            "androidDebugTransition": (
                "unsupported_clean_install_and_fresh_pair_required"
            ),
            "androidProductionApplicationId": None,
            "macosCurrentBundleId": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["macos"][
                    "sourceBundleId"
                ]
            ),
            "macosProductionBundleId": None,
            "marketingVersion": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"][
                    "marketingVersion"
                ]
            ),
            "policyMarketingVersion": (
                LOCAL_RELEASE_EXPECTED_TRANSITION_FIXTURE["currentRelease"][
                    "marketingVersion"
                ]
            ),
            "wireCompatibility": "n_and_n_minus_1",
        }
        if json.dumps(
            g0_projection,
            sort_keys=True,
        ) != json.dumps(
            expected_g0_projection,
            sort_keys=True,
        ):
            failures.append(
                "docs/v1/g0/decision-v1.json: non-security release version, "
                "identity, migration, or compatibility fields differ from "
                "the local transition fixture."
            )

    return failures


def local_release_provider_fixture_failures(
    document_text: str,
) -> list[str]:
    failures: list[str] = []
    fixture_body, parse_failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_PROVIDER_FIXTURE_START,
        end_marker=LOCAL_RELEASE_PROVIDER_FIXTURE_END,
        fixture_label="provider-compatibility",
    )
    if fixture_body is None:
        return parse_failures

    expected_body = json.dumps(
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "provider-compatibility fixture must match the canonical "
            "recorded-date schema, exact values, JSON types, and key order."
        )

    try:
        g0 = json.loads(
            LOCAL_RELEASE_G0_DECISION.read_text(encoding="utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
        providers = g0["productScope"]["providers"]
        if not isinstance(providers, list):
            raise TypeError("productScope.providers must be an array")
        g0_projection = sorted(
            (
                {
                    "access": provider["access"],
                    "minimumSupportedVersion": (
                        provider["minimumSupportedVersion"]
                    ),
                    "providerId": provider["id"],
                    "releasePolicy": provider["releasePolicy"],
                }
                for provider in providers
            ),
            key=lambda provider: provider["providerId"],
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
        KeyError,
        TypeError,
    ) as error:
        failures.append(
            "docs/v1/g0/decision-v1.json: cannot cross-check local "
            f"provider-compatibility fixture: {error}"
        )
    else:
        expected_projection = sorted(
            (
                {
                    "access": provider["access"],
                    "minimumSupportedVersion": (
                        provider["minimumSupportedVersion"]
                    ),
                    "providerId": provider["providerId"],
                    "releasePolicy": provider["releasePolicy"],
                }
                for provider in (
                    LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"],
                    LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["lmStudio"],
                )
            ),
            key=lambda provider: provider["providerId"],
        )
        if json.dumps(g0_projection, sort_keys=True) != json.dumps(
            expected_projection,
            sort_keys=True,
        ):
            failures.append(
                "docs/v1/g0/decision-v1.json: non-security provider IDs, "
                "runtime-host access, minimum versions, or release policies "
                "differ from the local provider-compatibility fixture."
            )

    return failures


def local_release_ollama_runner_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_START,
        end_marker=LOCAL_RELEASE_OLLAMA_RUNNER_FIXTURE_END,
        fixture_label="ollama-exact-version-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: missing exact-version runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        runner_id = runner["RUNNER_ID"]
        recorded_date = runner["RECORDED_DATE"]
        evidence_boundary = runner["EVIDENCE_BOUNDARY"]
        candidates = runner["EXACT_CANDIDATES"]
        live_test_filter = runner["LIVE_TEST_FILTER"]
        default_port = runner["DEFAULT_OLLAMA_PORT"]
        if not isinstance(runner_id, str) or not runner_id:
            raise TypeError("RUNNER_ID must be a non-empty string")
        if not isinstance(recorded_date, str) or not recorded_date:
            raise TypeError("RECORDED_DATE must be a non-empty string")
        if not isinstance(evidence_boundary, str) or not evidence_boundary:
            raise TypeError("EVIDENCE_BOUNDARY must be a non-empty string")
        if type(candidates) is not tuple or len(candidates) != 2:
            raise TypeError("EXACT_CANDIDATES must contain exactly two rows")
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionEmptyCatalogCompatibility"
        ):
            raise ValueError("LIVE_TEST_FILTER differs from the canonical test")
        if type(default_port) is not int or default_port != 11_434:
            raise ValueError("DEFAULT_OLLAMA_PORT differs from 11434")

        versions: list[dict[str, object]] = []
        for candidate in candidates:
            if type(candidate) is not dict:
                raise TypeError("candidate rows must be objects")
            archive_sha256 = candidate["archiveSha256"]
            archive_url = candidate["archiveUrl"]
            version = candidate["version"]
            if not all(
                isinstance(value, str) and value
                for value in (archive_sha256, archive_url, version)
            ):
                raise TypeError("candidate strings must be non-empty")
            versions.append(
                {
                    "archiveSha256": archive_sha256,
                    "archiveUrl": archive_url,
                    "coldStart": {
                        "adapterTestPassed": True,
                        "endpointUnavailableAfterStop": True,
                    },
                    "restart": {
                        "adapterTestPassed": True,
                        "endpointUnavailableAfterStop": True,
                    },
                    "testRuns": 2,
                    "version": version,
                }
            )
        expected_fixture = {
            "evidenceBoundary": evidence_boundary,
            "fixtureId": runner_id,
            "recordedDate": recorded_date,
            "schemaVersion": 1,
            "versions": versions,
        }
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            f"cannot derive canonical runner fixture: {error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-exact-version-run fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        versions,
    ):
        if (
            provider_candidate["version"] != runner_candidate["version"]
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate["archiveSha256"]
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate["archiveUrl"]
            or provider_candidate["isolatedAdapterSmoke"]
            != {
                "coldStartPassed": runner_candidate["coldStart"][
                    "adapterTestPassed"
                ],
                "emptyCatalogPassed": True,
                "restartPassed": runner_candidate["restart"][
                    "adapterTestPassed"
                ],
                "stoppedEndpointUnavailable": (
                    runner_candidate["coldStart"][
                        "endpointUnavailableAfterStop"
                    ]
                    and runner_candidate["restart"][
                        "endpointUnavailableAfterStop"
                    ]
                ),
            }
        ):
            failures.append(
                "provider-compatibility fixture and exact-version runner "
                "fixture differ in Ollama version, archive identity, or "
                "isolated adapter result."
            )
            break

    return failures


def local_release_ollama_model_backed_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_START,
        end_marker=LOCAL_RELEASE_OLLAMA_MODEL_BACKED_FIXTURE_END,
        fixture_label="ollama-model-backed-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: missing model-backed runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        live_test_filter = runner["MODEL_BACKED_LIVE_TEST_FILTER"]
        fixture_builder = runner["recorded_model_backed_fixture"]
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledChatModelCompatibility"
        ):
            raise ValueError(
                "MODEL_BACKED_LIVE_TEST_FILTER differs from the canonical test"
            )
        if not callable(fixture_builder):
            raise TypeError("recorded_model_backed_fixture must be callable")
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError("recorded model-backed fixture must be an object")
        if (
            expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get("modelNameRetained")
            is not False
            or expected_fixture.get("source", {}).get("modelNameRetained")
            is not False
        ):
            raise ValueError(
                "recorded model-backed fixture has an invalid evidence boundary"
            )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            f"cannot derive canonical model-backed fixture: {error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-model-backed-run fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    runner_versions = expected_fixture.get("versions")
    if type(runner_versions) is not list or len(runner_versions) != 2:
        failures.append(
            "model-backed runner fixture must contain exactly two versions."
        )
        return failures

    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        runner_versions,
    ):
        if type(runner_candidate) is not dict:
            failures.append(
                "model-backed runner version rows must be objects."
            )
            break
        cold_start = runner_candidate.get("coldStart")
        restart = runner_candidate.get("restart")
        if type(cold_start) is not dict or type(restart) is not dict:
            failures.append(
                "model-backed runner phases must be objects."
            )
            break
        expected_smoke = {
            "catalogPopulated": (
                cold_start.get("catalogPopulated") is True
                and restart.get("catalogPopulated") is True
            ),
            "chatCancellationPassed": (
                cold_start.get("chatCancellationConfirmed") is True
                and restart.get("chatCancellationConfirmed") is True
            ),
            "chatCompletionPassed": (
                cold_start.get("chatCompleted") is True
                and restart.get("chatCompleted") is True
            ),
            "coldStartPassed": (
                cold_start.get("adapterTestPassed") is True
            ),
            "installedStatePreserved": (
                cold_start.get("installedStatePreserved") is True
                and restart.get("installedStatePreserved") is True
            ),
            "modelUnloadPassed": (
                cold_start.get("modelUnloadConfirmed") is True
                and restart.get("modelUnloadConfirmed") is True
            ),
            "postCancellationRecoveryPassed": (
                cold_start.get("postCancellationRecoveryPassed") is True
                and restart.get("postCancellationRecoveryPassed") is True
            ),
            "restartPassed": restart.get("adapterTestPassed") is True,
            "snapshotUnchanged": (
                cold_start.get("snapshotUnchanged") is True
                and restart.get("snapshotUnchanged") is True
            ),
            "stoppedEndpointUnavailable": (
                cold_start.get("endpointUnavailableAfterStop") is True
                and restart.get("endpointUnavailableAfterStop") is True
            ),
        }
        if (
            provider_candidate["version"] != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
            or provider_candidate["isolatedModelBackedSmoke"]
            != expected_smoke
        ):
            failures.append(
                "provider-compatibility fixture and model-backed runner "
                "fixture differ in Ollama version, archive identity, or "
                "model-backed adapter result."
            )
            break

    return failures


def local_release_ollama_additional_chat_shape_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_FIXTURE_END
        ),
        fixture_label="ollama-additional-chat-shape",
    )
    if fixture_body is None:
        return failures

    runner_path = LOCAL_RELEASE_OLLAMA_ADDITIONAL_CHAT_SHAPE_RUNNER
    if not runner_path.is_file():
        return failures + [
            "script/run_ollama_additional_chat_shape_matrix.py: "
            "missing additional chat-shape runner."
        ]

    try:
        runner = runpy.run_path(str(runner_path))
        fixture_builder = runner["recorded_fixture"]
        fixture_validator = runner["validate_recorded_fixture"]
        source_assertion = runner["assert_bound_sources"]
        profile = runner["PROFILE"]
        if not all(
            callable(value)
            for value in (
                fixture_builder,
                fixture_validator,
                source_assertion,
            )
        ):
            raise TypeError(
                "additional chat-shape fixture helpers must be callable"
            )
        if profile.live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledChatModelCompatibility"
        ):
            raise ValueError(
                "additional chat-shape live filter differs from the "
                "canonical chat assertion"
            )
        if profile.required_capabilities != frozenset({"completion"}):
            raise ValueError(
                "additional chat-shape profile must require completion"
            )
        source_assertion()
        expected_fixture = fixture_builder()
        fixture_validator(expected_fixture)
        if (
            type(expected_fixture) is not dict
            or expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("observationCount") != 4
            or expected_fixture.get("profile") != "chat"
            or expected_fixture.get("selection")
            != {
                "completionCandidateCount": 3,
                "selectionOrdinal": 2,
                "targetCapabilityCount": 3,
                "targetInitiallyUnloaded": True,
                "targetVisionCapable": False,
            }
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get(
                "modelNameRetained"
            )
            is not False
            or expected_fixture.get("source", {}).get(
                "modelNameRetained"
            )
            is not False
        ):
            raise ValueError(
                "recorded additional chat-shape fixture has an invalid "
                "evidence boundary"
            )
    except Exception as error:
        return failures + [
            "script/run_ollama_additional_chat_shape_matrix.py: "
            "cannot derive canonical additional chat-shape fixture: "
            f"{error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-additional-chat-shape fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    versions = expected_fixture.get("versions")
    if type(versions) is not list or len(versions) != 2:
        failures.append(
            "additional chat-shape runner fixture must contain exactly "
            "two versions."
        )
        return failures
    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        versions,
    ):
        if (
            type(runner_candidate) is not dict
            or provider_candidate["version"]
            != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
        ):
            failures.append(
                "provider-compatibility fixture and additional chat-shape "
                "fixture differ in Ollama version or archive identity."
            )
            break

    return failures


def local_release_ollama_embedding_model_backed_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MODEL_BACKED_FIXTURE_END
        ),
        fixture_label="ollama-embedding-model-backed-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing embedding-model-backed runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        live_test_filter = runner["EMBEDDING_BACKED_LIVE_TEST_FILTER"]
        fixture_builder = runner[
            "recorded_embedding_model_backed_fixture"
        ]
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledEmbeddingModelCompatibility"
        ):
            raise ValueError(
                "EMBEDDING_BACKED_LIVE_TEST_FILTER differs from the "
                "canonical test"
            )
        if not callable(fixture_builder):
            raise TypeError(
                "recorded_embedding_model_backed_fixture must be callable"
            )
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError(
                "recorded embedding-model-backed fixture must be an object"
            )
        if (
            expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get(
                "modelNameRetained"
            )
            is not False
            or expected_fixture.get("source", {}).get(
                "modelNameRetained"
            )
            is not False
        ):
            raise ValueError(
                "recorded embedding-model-backed fixture has an invalid "
                "evidence boundary"
            )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical embedding-model-backed fixture: "
            f"{error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-model-backed-run fixture must match the "
            "runner's canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    runner_versions = expected_fixture.get("versions")
    if type(runner_versions) is not list or len(runner_versions) != 2:
        failures.append(
            "embedding-model-backed runner fixture must contain exactly "
            "two versions."
        )
        return failures

    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        runner_versions,
    ):
        if type(runner_candidate) is not dict:
            failures.append(
                "embedding-model-backed runner version rows must be objects."
            )
            break
        cold_start = runner_candidate.get("coldStart")
        restart = runner_candidate.get("restart")
        if type(cold_start) is not dict or type(restart) is not dict:
            failures.append(
                "embedding-model-backed runner phases must be objects."
            )
            break
        expected_smoke = {
            "catalogPopulated": (
                cold_start.get("catalogPopulated") is True
                and restart.get("catalogPopulated") is True
            ),
            "coldStartPassed": (
                cold_start.get("adapterTestPassed") is True
            ),
            "embeddingBatchPassed": (
                cold_start.get("embeddingBatchCompleted") is True
                and restart.get("embeddingBatchCompleted") is True
            ),
            "embeddingShapePassed": (
                cold_start.get("embeddingShapeValidated") is True
                and restart.get("embeddingShapeValidated") is True
            ),
            "installedStatePreserved": (
                cold_start.get("installedStatePreserved") is True
                and restart.get("installedStatePreserved") is True
            ),
            "modelUnloadPassed": (
                cold_start.get("modelUnloadConfirmed") is True
                and restart.get("modelUnloadConfirmed") is True
            ),
            "restartPassed": restart.get("adapterTestPassed") is True,
            "snapshotUnchanged": (
                cold_start.get("snapshotUnchanged") is True
                and restart.get("snapshotUnchanged") is True
            ),
            "stoppedEndpointUnavailable": (
                cold_start.get("endpointUnavailableAfterStop") is True
                and restart.get("endpointUnavailableAfterStop") is True
            ),
        }
        if (
            provider_candidate["version"]
            != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
            or provider_candidate["isolatedEmbeddingModelBackedSmoke"]
            != expected_smoke
        ):
            failures.append(
                "provider-compatibility fixture and "
                "embedding-model-backed runner fixture differ in Ollama "
                "version, archive identity, or adapter result."
            )
            break

    return failures


def local_release_ollama_embedding_semantic_quality_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_QUALITY_FIXTURE_END
        ),
        fixture_label="ollama-embedding-semantic-quality",
    )
    if fixture_body is None:
        return failures
    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing embedding semantic-quality runner."
        ]

    try:
        runner_source = LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
            encoding="utf-8"
        )
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        fixture_builder = runner[
            "recorded_embedding_semantic_quality_fixture"
        ]
        validator = runner[
            "validate_recorded_embedding_semantic_quality_fixture"
        ]
        task_set_validator = runner[
            "validate_embedding_semantic_quality_task_set"
        ]
        expected_runner_source_sha256 = runner[
            "RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256"
        ]
        expected_task_set_sha256 = runner[
            "EMBEDDING_SEMANTIC_QUALITY_TASK_SET_SHA256"
        ]
        expected_scorer_source_sha256 = runner[
            "EMBEDDING_SEMANTIC_QUALITY_SCORER_SOURCE_SHA256"
        ]
        expected_live_assertion_source_sha256 = runner[
            "EMBEDDING_SEMANTIC_QUALITY_LIVE_ASSERTION_SOURCE_SHA256"
        ]
        semantic_filter = runner[
            "EMBEDDING_SEMANTIC_QUALITY_LIVE_TEST_FILTER"
        ]
        recovery_filter = runner[
            "EMBEDDING_SEMANTIC_QUALITY_RECOVERY_TEST_FILTER"
        ]
        if (
            not callable(fixture_builder)
            or not callable(validator)
            or not callable(task_set_validator)
        ):
            raise TypeError(
                "embedding semantic-quality builders and validators "
                "must be callable"
            )
        if semantic_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledEmbeddingSemanticQuality"
        ):
            raise ValueError(
                "embedding semantic-quality test filter drifted"
            )
        if recovery_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledEmbeddingSemanticRecovery"
        ):
            raise ValueError(
                "embedding semantic-quality recovery filter drifted"
            )
        for label, value in (
            ("runner source", expected_runner_source_sha256),
            ("task set", expected_task_set_sha256),
            ("semantic scorer source", expected_scorer_source_sha256),
            (
                "semantic live assertion source",
                expected_live_assertion_source_sha256,
            ),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in value
                )
            ):
                raise ValueError(f"{label} SHA-256 was invalid")
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError(
                "recorded embedding semantic-quality fixture must be "
                "an object"
            )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        task_set_path = (
            ROOT
            / "shared"
            / "evaluation"
            / "ollama-embedding-semantic-quality-v1.json"
        )
        task_set_data = task_set_path.read_bytes()
        task_set = json.loads(
            task_set_data,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        for label, source_path in (
            (
                "semantic scorer",
                LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE,
            ),
            (
                "semantic live assertion",
                LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_LIVE_ASSERTION_SOURCE,
            ),
        ):
            if source_path.is_symlink() or not source_path.is_file():
                raise OSError(f"{label} source was not a regular file")
        scorer_source_data = (
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_SCORER_SOURCE.read_bytes()
        )
        live_assertion_source_data = (
            LOCAL_RELEASE_OLLAMA_EMBEDDING_SEMANTIC_LIVE_ASSERTION_SOURCE
            .read_bytes()
        )
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical embedding semantic-quality fixture: "
            f"{error}"
        ]

    observed_runner_source_sha256 = (
        normalized_live_fault_runner_source_sha256(runner_source)
    )
    if observed_runner_source_sha256 != expected_runner_source_sha256:
        failures.append(
            "script/run_ollama_compatibility_matrix.py: embedding "
            "semantic-quality runner source differs from the recorded "
            "normalized SHA-256."
        )
    if hashlib.sha256(task_set_data).hexdigest() != (
        expected_task_set_sha256
    ):
        failures.append(
            "shared/evaluation/ollama-embedding-semantic-quality-v1.json: "
            "task-set bytes differ from the recorded SHA-256."
        )
    if hashlib.sha256(scorer_source_data).hexdigest() != (
        expected_scorer_source_sha256
    ):
        failures.append(
            "apps/macos/OllamaBackend/Tests/"
            "OllamaEmbeddingSemanticQualityTests.swift: semantic scorer "
            "source bytes differ from the recorded SHA-256."
        )
    if hashlib.sha256(live_assertion_source_data).hexdigest() != (
        expected_live_assertion_source_sha256
    ):
        failures.append(
            "apps/macos/OllamaBackend/Tests/OllamaBackendTests.swift: "
            "semantic live assertion source bytes differ from the recorded "
            "SHA-256."
        )
    try:
        task_set_validator(task_set)
    except Exception as error:
        failures.append(
            "shared/evaluation/ollama-embedding-semantic-quality-v1.json: "
            f"task-set schema is invalid: {error}"
        )

    try:
        validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-semantic-quality fixture violates the "
            f"runner schema: {error}"
        )
        return failures

    canonical_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-semantic-quality fixture must match the "
            "runner's canonical exact values, JSON types, and key order."
        )
    return failures


def local_release_ollama_embedding_multilingual_semantic_quality_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_EMBEDDING_MULTILINGUAL_SEMANTIC_QUALITY_FIXTURE_END
        ),
        fixture_label=(
            "ollama-embedding-multilingual-semantic-quality"
        ),
    )
    if fixture_body is None:
        return failures
    runner_path = LOCAL_RELEASE_OLLAMA_MULTILINGUAL_SEMANTIC_RUNNER
    if not runner_path.is_file():
        return failures + [
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "missing multilingual semantic-quality runner."
        ]

    try:
        runner_source = runner_path.read_text(encoding="utf-8")
        runner = runpy.run_path(str(runner_path))
        fixture_builder = runner["recorded_fixture"]
        fixture_validator = runner["validate_recorded_fixture"]
        task_set_bytes_reader = runner["recorded_task_set_bytes"]
        task_set_validator = runner["validate_task_set"]
        normalized_source_sha256 = runner[
            "normalized_runner_source_sha256"
        ]
        expected_runner_source_sha256 = runner[
            "RECORDED_RUNNER_SOURCE_SHA256"
        ]
        expected_task_set_sha256 = runner["TASK_SET_SHA256"]
        expected_swift_source_sha256 = runner["SWIFT_SOURCE_SHA256"]
        expected_base_runner_source_sha256 = runner[
            "BASE_RUNNER_SOURCE_SHA256"
        ]
        expected_recovery_source_sha256 = runner[
            "RECOVERY_SOURCE_SHA256"
        ]
        task_set_path = runner["TASK_SET_PATH"]
        swift_source_path = runner["SWIFT_SOURCE_PATH"]
        base_runner_source_path = runner["BASE_RUNNER_SOURCE_PATH"]
        recovery_source_path = runner["RECOVERY_SOURCE_PATH"]
        live_filter = runner["LIVE_TEST_FILTER"]
        if (
            not callable(fixture_builder)
            or not callable(fixture_validator)
            or not callable(task_set_bytes_reader)
            or not callable(task_set_validator)
            or not callable(normalized_source_sha256)
        ):
            raise TypeError(
                "multilingual semantic builders and validators must be "
                "callable"
            )
        if live_filter != (
            "OllamaEmbeddingMultilingualSemanticQualityTests."
            "testLiveOllamaExactVersionInstalledEmbeddingMultilingual"
            "SemanticQuality"
        ):
            raise ValueError(
                "multilingual semantic live test filter drifted"
            )
        for label, value in (
            ("runner source", expected_runner_source_sha256),
            ("task set", expected_task_set_sha256),
            ("Swift source", expected_swift_source_sha256),
            ("base runner source", expected_base_runner_source_sha256),
            ("recovery source", expected_recovery_source_sha256),
        ):
            if (
                not isinstance(value, str)
                or len(value) != 64
                or any(
                    character not in "0123456789abcdef"
                    for character in value
                )
            ):
                raise ValueError(f"{label} SHA-256 was invalid")
        # The V2 fixture is a historical observation bound to its recorded
        # product-source digests. The live runner still calls
        # assert_bound_sources() and refuses re-execution after product-source
        # drift; documentation validation must not relabel current bytes as the
        # bytes that produced the observation.
        expected_fixture = fixture_builder()
        if type(expected_fixture) is not dict:
            raise TypeError(
                "recorded multilingual semantic fixture must be an object"
            )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        task_set_data = task_set_bytes_reader()
        task_set = json.loads(
            task_set_data,
            object_pairs_hook=reject_duplicate_json_keys,
        )
        for label, path in (
            ("task set", task_set_path),
            ("Swift source", swift_source_path),
            ("base runner source", base_runner_source_path),
            ("recovery source", recovery_source_path),
        ):
            if (
                not isinstance(path, Path)
                or path.is_symlink()
                or not path.is_file()
            ):
                raise OSError(f"{label} was not a regular file")
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "cannot derive canonical multilingual semantic fixture: "
            f"{error}"
        ]
    except Exception as error:
        return failures + [
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "multilingual semantic source validation failed: "
            f"{error}"
        ]

    if normalized_source_sha256(runner_source) != (
        expected_runner_source_sha256
    ):
        failures.append(
            "script/run_ollama_multilingual_semantic_matrix.py: "
            "multilingual semantic runner source differs from the recorded "
            "normalized SHA-256."
        )
    for label, path, expected_sha256 in (
        (
            "task-set",
            task_set_path,
            expected_task_set_sha256,
        ),
        (
            "Swift scorer/live assertion",
            swift_source_path,
            expected_swift_source_sha256,
        ),
        (
            "base runner",
            base_runner_source_path,
            expected_base_runner_source_sha256,
        ),
        (
            "recovery assertion",
            recovery_source_path,
            expected_recovery_source_sha256,
        ),
    ):
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
            failures.append(
                f"{path.relative_to(ROOT)}: multilingual semantic "
                f"{label} bytes differ from the recorded SHA-256."
            )
    try:
        task_set_validator(task_set)
    except Exception as error:
        failures.append(
            "shared/evaluation/"
            "ollama-embedding-multilingual-semantic-quality-v2.json: "
            f"task-set schema is invalid: {error}"
        )
    try:
        fixture_validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-multilingual-semantic-quality fixture "
            f"violates the runner schema: {error}"
        )
        return failures

    canonical_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-embedding-multilingual-semantic-quality fixture must "
            "match the runner's canonical exact values, JSON types, and "
            "key order."
        )
    return failures


def local_release_ollama_vision_model_backed_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_START,
        end_marker=LOCAL_RELEASE_OLLAMA_VISION_MODEL_BACKED_FIXTURE_END,
        fixture_label="ollama-vision-model-backed-run",
    )
    if fixture_body is None:
        return failures

    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing vision-model-backed runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        live_test_filter = runner["VISION_BACKED_LIVE_TEST_FILTER"]
        fixture_builder = runner["recorded_vision_model_backed_fixture"]
        if live_test_filter != (
            "OllamaBackendTests."
            "testLiveOllamaExactVersionInstalledVisionModelCompatibility"
        ):
            raise ValueError(
                "VISION_BACKED_LIVE_TEST_FILTER differs from the canonical test"
            )
        if not callable(fixture_builder):
            raise TypeError(
                "recorded_vision_model_backed_fixture must be callable"
            )
        expected_fixture = fixture_builder()
        if (
            type(expected_fixture) is not dict
            or expected_fixture.get("schemaVersion") != 1
            or expected_fixture.get("snapshot", {}).get(
                "modelDownloadAttempted"
            )
            is not False
            or expected_fixture.get("snapshot", {}).get(
                "modelNameRetained"
            )
            is not False
            or expected_fixture.get("source", {}).get(
                "modelNameRetained"
            )
            is not False
        ):
            raise ValueError(
                "recorded vision-model-backed fixture has an invalid "
                "evidence boundary"
            )
    except (
        KeyError,
        OSError,
        TypeError,
        ValueError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical vision-model-backed fixture: "
            f"{error}"
        ]

    expected_body = json.dumps(
        expected_fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != expected_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-vision-model-backed-run fixture must match the runner's "
            "canonical exact values, JSON types, and key order."
        )

    provider_candidates = (
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "currentCandidate"
        ],
        LOCAL_RELEASE_EXPECTED_PROVIDER_FIXTURE["ollama"][
            "previousCandidate"
        ],
    )
    runner_versions = expected_fixture.get("versions")
    if type(runner_versions) is not list or len(runner_versions) != 2:
        failures.append(
            "vision-model-backed runner fixture must contain exactly two versions."
        )
        return failures

    phase_keys = {
        "catalogPopulated": "catalogPopulated",
        "chatCancellationPassed": "chatCancellationConfirmed",
        "imageAttachmentPassed": "imageAttachmentCompleted",
        "installedStatePreserved": "installedStatePreserved",
        "modelUnloadPassed": "modelUnloadConfirmed",
        "postCancellationRecoveryPassed": (
            "postCancellationRecoveryPassed"
        ),
        "snapshotUnchanged": "snapshotUnchanged",
        "stoppedEndpointUnavailable": "endpointUnavailableAfterStop",
        "textChatPassed": "textChatCompleted",
    }
    for provider_candidate, runner_candidate in zip(
        provider_candidates,
        runner_versions,
    ):
        if type(runner_candidate) is not dict:
            failures.append(
                "vision-model-backed runner version rows must be objects."
            )
            break
        cold_start = runner_candidate.get("coldStart")
        restart = runner_candidate.get("restart")
        if type(cold_start) is not dict or type(restart) is not dict:
            failures.append(
                "vision-model-backed runner phases must be objects."
            )
            break
        expected_smoke = {
            output_key: (
                cold_start.get(phase_key) is True
                and restart.get(phase_key) is True
            )
            for output_key, phase_key in phase_keys.items()
        }
        expected_smoke.update(
            {
                "coldStartPassed": (
                    cold_start.get("adapterTestPassed") is True
                ),
                "restartPassed": (
                    restart.get("adapterTestPassed") is True
                ),
            }
        )
        if (
            provider_candidate["version"]
            != runner_candidate.get("version")
            or provider_candidate["darwinArchiveSha256"]
            != runner_candidate.get("archiveSha256")
            or provider_candidate["darwinArchiveUrl"]
            != runner_candidate.get("archiveUrl")
            or provider_candidate["isolatedVisionModelBackedSmoke"]
            != expected_smoke
        ):
            failures.append(
                "provider-compatibility fixture and vision-model-backed "
                "runner fixture differ in Ollama version, archive identity, "
                "or adapter result."
            )
            break

    return failures


def local_release_ollama_duration_observation_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_START
        ),
        end_marker=LOCAL_RELEASE_OLLAMA_DURATION_OBSERVATION_FIXTURE_END,
        fixture_label="ollama-duration-observation",
    )
    if fixture_body is None:
        return failures
    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing duration-observation runner."
        ]

    try:
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        validator = runner[
            "validate_recorded_duration_observation_fixture"
        ]
        expected_sha256 = runner[
            "RECORDED_DURATION_OBSERVATION_SHA256"
        ]
        if not callable(validator):
            raise TypeError(
                "duration-observation validator must be callable"
            )
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_sha256
            )
        ):
            raise ValueError(
                "RECORDED_DURATION_OBSERVATION_SHA256 must be a SHA-256"
            )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical duration-observation fixture: "
            f"{error}"
        ]

    try:
        validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-duration-observation fixture violates the runner schema: "
            f"{error}"
        )
        return failures

    canonical_body = json.dumps(
        fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-duration-observation fixture must use canonical JSON "
            "types and key order."
        )
    observed_sha256 = hashlib.sha256(
        fixture_body.encode("utf-8")
    ).hexdigest()
    if observed_sha256 != expected_sha256:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-duration-observation fixture differs from the recorded "
            "runner SHA-256."
        )
    return failures


def local_release_ollama_live_fault_injection_fixture_failures(
    document_text: str,
) -> list[str]:
    fixture_body, failures = embedded_json_fixture_body(
        document_text,
        start_marker=(
            LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_START
        ),
        end_marker=(
            LOCAL_RELEASE_OLLAMA_LIVE_FAULT_INJECTION_FIXTURE_END
        ),
        fixture_label="ollama-live-fault-injection",
    )
    if fixture_body is None:
        return failures
    if not LOCAL_RELEASE_OLLAMA_RUNNER.is_file():
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "missing live-fault-injection runner."
        ]

    try:
        runner_source = LOCAL_RELEASE_OLLAMA_RUNNER.read_text(
            encoding="utf-8"
        )
        runner = runpy.run_path(str(LOCAL_RELEASE_OLLAMA_RUNNER))
        validator = runner[
            "validate_recorded_live_fault_injection_fixture"
        ]
        expected_sha256 = runner[
            "RECORDED_LIVE_FAULT_INJECTION_SHA256"
        ]
        expected_runner_source_sha256 = runner[
            "RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256"
        ]
        if not callable(validator):
            raise TypeError(
                "live-fault-injection validator must be callable"
            )
        if (
            not isinstance(expected_sha256, str)
            or len(expected_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_sha256
            )
        ):
            raise ValueError(
                "RECORDED_LIVE_FAULT_INJECTION_SHA256 must be a SHA-256"
            )
        if (
            not isinstance(expected_runner_source_sha256, str)
            or len(expected_runner_source_sha256) != 64
            or any(
                character not in "0123456789abcdef"
                for character in expected_runner_source_sha256
            )
        ):
            raise ValueError(
                "RECORDED_LIVE_FAULT_INJECTION_RUNNER_SOURCE_SHA256 "
                "must be a SHA-256"
            )
        observed_runner_source_sha256 = (
            normalized_live_fault_runner_source_sha256(runner_source)
        )
        fixture = json.loads(
            fixture_body,
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        DuplicateJSONKeyError,
        KeyError,
        OSError,
        TypeError,
        ValueError,
        json.JSONDecodeError,
    ) as error:
        return failures + [
            "script/run_ollama_compatibility_matrix.py: "
            "cannot derive canonical live-fault-injection fixture: "
            f"{error}"
        ]

    if observed_runner_source_sha256 != expected_runner_source_sha256:
        failures.append(
            "script/run_ollama_compatibility_matrix.py: "
            "live-fault-injection runner source differs from the recorded "
            "normalized SHA-256."
        )

    try:
        validator(fixture)
    except Exception as error:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-live-fault-injection fixture violates the runner schema: "
            f"{error}"
        )
        return failures

    canonical_body = json.dumps(
        fixture,
        ensure_ascii=True,
        indent=2,
        sort_keys=True,
    )
    if fixture_body != canonical_body:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-live-fault-injection fixture must use canonical JSON "
            "types and key order."
        )
    observed_sha256 = hashlib.sha256(
        fixture_body.encode("utf-8")
    ).hexdigest()
    if observed_sha256 != expected_sha256:
        failures.append(
            "docs/releases/1.0.0-build-3-local-v1.md: "
            "ollama-live-fault-injection fixture differs from the recorded "
            "runner SHA-256."
        )
    return failures


def current_release_android_backup_policy_document_failures(
    document_text: str,
    *,
    relative: str = "docs/releases/1.0.0-build-22-local-v1.md",
) -> list[str]:
    failures: list[str] = []
    normalized_document = re.sub(r"\s+", " ", document_text)
    for index, claim in enumerate(
        LOCAL_RELEASE_ANDROID_BACKUP_POLICY_REQUIRED_CLAIMS,
        1,
    ):
        normalized_claim = re.sub(r"\s+", " ", claim)
        if normalized_claim not in normalized_document:
            failures.append(
                f"{relative}: missing exact Android backup-policy claim "
                f"{index} claim {claim!r}."
            )
    return failures


def current_release_android_manifest_readback_failures(
    manifest: object,
    *,
    relative: str = (
        "dist/releases/aetherlink-1.0.0+22-local-v1/"
        "aetherlink-1.0.0+22-local-v1.manifest.json"
    ),
) -> list[str]:
    if not isinstance(manifest, dict):
        return [f"{relative}: manifest root must be a JSON object."]

    def read_path(path: tuple[str, ...]) -> object:
        value: object = manifest
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    failures: list[str] = []
    expectations = (
        (
            ("platforms", "android", "apkManifestReadback"),
            LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK,
        ),
        (
            ("platforms", "android", "bundleManifestReadback"),
            LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK,
        ),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )
    return failures


def current_handoff_git_attribution_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/handoff.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate Git-state attribution: {error}"
            ]

    normalized = re.sub(r"\s+", " ", document_text).strip()
    required_bindings = (
        (
            "Build 22 qualification-time source attribution",
            (
                "The Build 22 manifest captured source HEAD and "
                "`origin/main` as "
                f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}` at qualification time."
            ),
        ),
        (
            "timestamped post-qualification Git refresh",
            (
                f"at the {LATEST_RECORDED_GIT_REFRESH_LABEL} refresh, `main` "
                "and `origin/main` both resolved to "
                f"`{LATEST_RECORDED_GIT_REFRESH_HEAD}`."
            ),
        ),
        (
            "live HEAD refresh command",
            "`git rev-parse HEAD`",
        ),
        (
            "live origin/main refresh command",
            "`git rev-parse origin/main`",
        ),
        (
            "archive source identity boundary",
            (
                "The archived source inventory, not either commit alone, "
                "remains the Build 22 source identity."
            ),
        ),
    )
    failures: list[str] = []
    for label, binding in required_bindings:
        normalized_binding = re.sub(r"\s+", " ", binding).strip()
        if normalized.count(normalized_binding) != 1:
            failures.append(
                f"{relative}: {label} must appear exactly once."
            )

    stale_live_claims = (
        (
            "`main` and `origin/main` both resolve to "
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`"
        ),
        (
            "HEAD and `origin/main` are "
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`"
        ),
    )
    for claim in stale_live_claims:
        if claim in normalized:
            failures.append(
                f"{relative}: qualification-time source HEAD is presented "
                "as a live Git-state claim."
            )
    return failures


def local_release_document_failures() -> list[str]:
    try:
        relative_doc = LOCAL_RELEASE_CURRENT_DOC.relative_to(ROOT)
    except ValueError:
        relative_doc = LOCAL_RELEASE_CURRENT_DOC
    if not LOCAL_RELEASE_CURRENT_DOC.is_file():
        return [f"{relative_doc}: missing local release qualification record."]

    try:
        document_text = LOCAL_RELEASE_CURRENT_DOC.read_text(encoding="utf-8")
    except (OSError, UnicodeError) as error:
        return [f"{relative_doc}: unreadable local release qualification record: {error}"]

    failures: list[str] = []
    try:
        relative_fixture_doc = LOCAL_RELEASE_FIXTURE_DOC.relative_to(ROOT)
    except ValueError:
        relative_fixture_doc = LOCAL_RELEASE_FIXTURE_DOC
    try:
        fixture_document_text = LOCAL_RELEASE_FIXTURE_DOC.read_text(
            encoding="utf-8"
        )
    except (OSError, UnicodeError) as error:
        fixture_document_text = None
        failures.append(
            f"{relative_fixture_doc}: unreadable historical release fixture "
            f"record: {error}"
        )

    required_claims = (
        ("release ID", f"`{LOCAL_RELEASE_ID}`"),
        (
            "ZIP size",
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SIZE:,} bytes",
        ),
        ("ZIP SHA-256", f"`{LOCAL_RELEASE_EXPECTED_ZIP_SHA256}`"),
        (
            "manifest size",
            f"{LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE:,} bytes",
        ),
        (
            "manifest SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256}`",
        ),
        (
            "checksum sidecar size",
            f"{LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE:,} bytes",
        ),
        (
            "checksum sidecar SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256}`",
        ),
        (
            "reproducibility result path",
            (
                "`dist/reproducibility/"
                "aetherlink-1.0.0+22-local-v1-two-root-v4.json`"
            ),
        ),
        (
            "reproducibility result size",
            f"{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        ),
        (
            "reproducibility result SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256}`",
        ),
        (
            "reproducibility prepublication path",
            (
                "`dist/reproducibility/"
                "aetherlink-1.0.0+22-local-v1-two-root-v4-prepublication.json`"
            ),
        ),
        (
            "reproducibility prepublication size",
            (
                f"{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "reproducibility prepublication SHA-256",
            (
                f"`{LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256}`"
            ),
        ),
        (
            "reproducibility comparison-only boundary",
            "`executionMode=comparison-only`",
        ),
        (
            "reproducibility publish-qualified boundary",
            "`executionMode=publish-qualified`",
        ),
        (
            "reproducibility verified publication outcome",
            "`outcome=published-verified`",
        ),
        (
            "reproducibility new publication state",
            "`alreadyMatched=false`",
        ),
        (
            "reproducibility exact prepublication binding",
            "`prepublicationBinding.matched=true`",
        ),
        (
            "protected previous-archive policy",
            "`previous-ledger-entry-archive-v1`",
        ),
        (
            "protected previous-archive identity",
            (
                f"`{LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256}`"
            ),
        ),
        (
            "Swift frontend serialization",
            "`-Xswiftc -num-threads -Xswiftc 1`",
        ),
        (
            "Build 21 abrupt recovery result path",
            (
                "`dist/lifecycle/"
                "macos-runtime-chat-sqlite-abrupt-process-recovery-"
                "build-21-v1.json`"
            ),
        ),
        (
            "Build 21 abrupt recovery result size",
            f"{CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE:,} bytes",
        ),
        (
            "Build 21 abrupt recovery result SHA-256",
            f"`{CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256}`",
        ),
        (
            "Build 21 abrupt recovery boundary",
            "bounded same-host abrupt child-process `SIGKILL` recovery evidence",
        ),
        (
            "Build 21 production append crash-point exclusion",
            "`not-production-append-crash-point`",
        ),
        (
            "current Build 20 clean-HOME installed-app result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-clean-home-install-v1.json`"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app result size",
            (
                f"{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app result SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app runner SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "current Build 20 clean-HOME installed-app test SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "current Build 20 installed state-recovery result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-clean-home-state-recovery-v1.json`"
            ),
        ),
        (
            "current Build 20 installed state-recovery result size",
            (
                f"{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "current Build 20 installed state-recovery result SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "current Build 20 installed state-recovery runner SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "current Build 20 installed state-recovery test SHA-256",
            (
                f"`{CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "current Build 20 lifecycle repeatability",
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_REPEATABILITY_CLAIM,
        ),
        (
            "current Build 20 local DMG result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-20-local-dmg-install-v1.json`"
            ),
        ),
        (
            "current Build 20 local DMG result size",
            f"{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE:,} bytes",
        ),
        (
            "current Build 20 local DMG result SHA-256",
            f"`{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256}`",
        ),
        (
            "current Build 20 local DMG runner SHA-256",
            f"`{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256}`",
        ),
        (
            "current Build 20 local DMG test SHA-256",
            f"`{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256}`",
        ),
        (
            "historical Build 16 release ID",
            f"`{HISTORICAL_BUILD16_RELEASE_ID}`",
        ),
        (
            "historical Build 16 archive size",
            f"{HISTORICAL_BUILD16_ARCHIVE_SIZE:,} bytes",
        ),
        (
            "historical Build 16 archive SHA-256",
            f"`{HISTORICAL_BUILD16_ARCHIVE_SHA256}`",
        ),
        (
            "historical Build 16 successful result size",
            f"{HISTORICAL_BUILD16_RESULT_SIZE:,} bytes",
        ),
        (
            "historical Build 16 successful result SHA-256",
            f"`{HISTORICAL_BUILD16_RESULT_SHA256}`",
        ),
        (
            "historical Build 16 failed attempt size",
            f"{HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE:,} bytes",
        ),
        (
            "historical Build 16 failed attempt SHA-256",
            f"`{HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256}`",
        ),
        (
            "historical Build 16 failed confirmation size",
            f"{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE:,} bytes",
        ),
        (
            "historical Build 16 failed confirmation SHA-256",
            f"`{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256}`",
        ),
        (
            "historical Build 16 failed publication boundary",
            "`publication=null`",
        ),
        (
            "historical Build 16 non-transfer boundary",
            (
                "Build 17 does not retroactively qualify Build 16."
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-14-clean-home-install-v1.json`"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app result size",
            (
                f"{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app result SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app runner SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "historical Build 14 clean-HOME installed-app test SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "historical Build 14 clean-HOME distinct relaunch identifiers",
            "`distinctProcessIdentifiers=true`",
        ),
        (
            "historical Build 14 clean-HOME state identity",
            (
                "`regularFileBytesAndModesUnchangedAcrossRelaunch=true`"
            ),
        ),
        (
            "historical Build 14 clean-HOME empty chat state",
            "`totalEventCount=0`",
        ),
        (
            "historical Build 14 installed state-recovery result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-14-clean-home-state-recovery-v1.json`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery result size",
            (
                f"{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "historical Build 14 installed state-recovery result SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery runner SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery test SHA-256",
            (
                f"`{MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`"
            ),
        ),
        (
            "historical Build 14 installed state-recovery state identity",
            "`installedStateBytesAndModesUnchangedAcrossRelaunch=true`",
        ),
        (
            "historical Build 14 installed state-recovery identity file",
            "`runtimeIdentityFilePresent=true`",
        ),
        (
            "historical Build 14 installed state-recovery separation",
            (
                "Build 14 installed state-recovery evidence remains bound to "
                "Build 14 and is not reinterpreted as Build 17 evidence."
            ),
        ),
        (
            "packaged state-recovery result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-13-state-recovery-v1.json`"
            ),
        ),
        (
            "packaged state-recovery result size",
            f"{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SIZE:,} bytes",
        ),
        (
            "packaged state-recovery result SHA-256",
            f"`{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SHA256}`",
        ),
        (
            "packaged state-recovery runner SHA-256",
            f"`{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256}`",
        ),
        (
            "packaged state-recovery test SHA-256",
            f"`{MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_TEST_SHA256}`",
        ),
        (
            "packaged state-recovery legacy removal",
            "`legacyAbsentBeforeSecondRun=true`",
        ),
        (
            "packaged state-recovery legacy identity",
            "`legacyFixturePreservedUnchanged=true`",
        ),
        (
            "packaged state-recovery SQLite identity",
            "`sqliteCanaryUnchangedAcrossRuns=true`",
        ),
        (
            "packaged state-recovery event JSON identity",
            (
                "`da3320c2cbdf9146b0ee21c084a9474715caf9f5e1d568853f6a2359cd9f4cef`"
            ),
        ),
        (
            "packaged state-recovery migration observation identity",
            (
                "`558fbc563c3f07474b4a28093290216a8fcfdade66cee5ee8354c8fc867fd5f9`"
            ),
        ),
        (
            "packaged state-recovery readback observation identity",
            (
                "`ab8c927b33c3f3b2350eefd357c696c92b076f8c950da9c46823859cddeaad07`"
            ),
        ),
        (
            "Build 12 state-recovery non-transfer boundary",
            (
                "Build 12 state-recovery result was not published, and Build "
                "13 evidence is not reinterpreted as Build 12 evidence."
            ),
        ),
        (
            "Build 13 state-recovery non-transfer boundary",
            (
                "Build 13 state-recovery evidence remains bound to Build 13 "
                "and is not reinterpreted as Build 17 evidence."
            ),
        ),
        (
            "packaged-app lifecycle result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-10-lifecycle-v1.json`"
            ),
        ),
        (
            "packaged-app lifecycle result size",
            f"{MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE:,} bytes",
        ),
        (
            "packaged-app lifecycle result SHA-256",
            f"`{MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256}`",
        ),
        (
            "packaged-app lifecycle runner SHA-256",
            f"`{MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256}`",
        ),
        (
            "packaged-app lifecycle test SHA-256",
            f"`{MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256}`",
        ),
        (
            "historical packaged-app lifecycle runner SHA-256",
            (
                f"`{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256}`"
            ),
        ),
        (
            "historical packaged-app lifecycle test SHA-256",
            f"`{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256}`",
        ),
        (
            "packaged-app minimum observation",
            "`minimumObservationSeconds=5.0`",
        ),
        (
            "packaged-app observation deadline",
            "`observationDeadlineReached=true`",
        ),
        (
            "packaged-app identity-file observation",
            "`identityFilePresentAfterRuns=[false, false]`",
        ),
        (
            "historical packaged-app lifecycle result path",
            (
                "`dist/lifecycle/"
                "macos-packaged-app-build-9-lifecycle-v1.json`"
            ),
        ),
        (
            "historical packaged-app lifecycle result size",
            (
                f"{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE:,} "
                "bytes"
            ),
        ),
        (
            "historical packaged-app lifecycle result SHA-256",
            (
                f"`{HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256}`"
            ),
        ),
        (
            "Build 10 lifecycle non-transfer boundary",
            (
                "Build 10 observations remain bound to Build 10 and are not "
                "reinterpreted as Build 17 evidence."
            ),
        ),
        (
            "unequal source-root byte lengths",
            "101- and 109-byte source roots",
        ),
        (
            "unequal source-root result",
            "`sourceRootLengthsDiffer=true`",
        ),
        (
            "independent publication readback",
            "`independentReadback=true`",
        ),
        (
            "published lane identity",
            "`publishedBytesEqualLaneA=true`",
        ),
        (
            "publication source freshness",
            "`sourceSnapshotUnchanged=true`",
        ),
        (
            "AAB structure validation",
            "`bundletool validate`",
        ),
        (
            "source inventory count",
            f"{LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT}-file source inventory",
        ),
        (
            "source inventory SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_SHA256}`",
        ),
        (
            "source overlay SHA-256",
            f"`{LOCAL_RELEASE_EXPECTED_SOURCE_OVERLAY_SHA256}`",
        ),
        ("source HEAD", f"`{LOCAL_RELEASE_EXPECTED_SOURCE_HEAD}`"),
        ("dirty source boundary", "`dirty-content-snapshot`"),
        (
            "commit-only reconstruction boundary",
            "The Git commit alone cannot reconstruct these release bytes.",
        ),
        (
            "POM body retention boundary",
            "Original POM bodies are not archived.",
        ),
        (
            "license text retention boundary",
            "License/NOTICE texts are not archived.",
        ),
        (
            "offline evidence boundary",
            "The offline checker does not re-fetch or re-parse those originals.",
        ),
        (
            "compliance profile",
            "`aetherlink-release-compliance-v2`",
        ),
        ("compliance schema", "`schemaVersion=2`"),
        ("runtime relationship count", "202 runtime"),
        ("build dependency relationship count", "155 build dependency"),
        ("build tool relationship count", "335 build tool"),
        ("total relationship count", "692 exact role relationships"),
        (
            "payload member count",
            f"{LOCAL_RELEASE_EXPECTED_MEMBER_COUNT} payload members",
        ),
        ("macOS app/dSYM UUID", f"`{LOCAL_RELEASE_EXPECTED_MACOS_UUID}`"),
    )
    historical_claim_prefixes = (
        "historical ",
        "packaged state-recovery ",
        "Build 12 state-recovery ",
        "Build 13 state-recovery ",
        "packaged-app ",
        "Build 10 lifecycle ",
    )
    required_claims = tuple(
        claim
        for claim in required_claims
        if not claim[0].startswith(historical_claim_prefixes)
    )
    for member_path, (size, sha256) in LOCAL_RELEASE_EXPECTED_MEMBERS.items():
        required_claims += (
            (f"{member_path} size", f"{size:,} bytes"),
            (f"{member_path} SHA-256", f"`{sha256}`"),
        )

    normalized_document = re.sub(r"\s+", " ", document_text)
    for label, expected_text in required_claims:
        normalized_expected = re.sub(r"\s+", " ", expected_text)
        if normalized_expected not in normalized_document:
            failures.append(
                f"{relative_doc}: missing exact {label} claim {expected_text!r}."
            )
    failures.extend(
        current_release_android_backup_policy_document_failures(
            document_text,
            relative=str(relative_doc),
        )
    )

    if fixture_document_text is not None:
        failures.extend(
            local_release_transition_fixture_failures(fixture_document_text)
        )
        failures.extend(
            local_release_provider_fixture_failures(fixture_document_text)
        )
        failures.extend(
            local_release_ollama_runner_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_model_backed_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_additional_chat_shape_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_embedding_model_backed_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_embedding_semantic_quality_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_embedding_multilingual_semantic_quality_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_vision_model_backed_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_duration_observation_fixture_failures(
                fixture_document_text
            )
        )
        failures.extend(
            local_release_ollama_live_fault_injection_fixture_failures(
                fixture_document_text
            )
        )

    if not LOCAL_RELEASE_ARCHIVE_DIR.exists():
        return failures
    if not LOCAL_RELEASE_ARCHIVE_DIR.is_dir():
        failures.append(
            f"{LOCAL_RELEASE_ARCHIVE_DIR.relative_to(ROOT)}: local release archive path is not a directory."
        )
        return failures

    archive_path = LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip"
    manifest_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.manifest.json"
    )
    checksum_path = (
        LOCAL_RELEASE_ARCHIVE_DIR / f"{LOCAL_RELEASE_ID}.zip.sha256"
    )
    for path in (archive_path, manifest_path, checksum_path):
        if not path.is_file():
            failures.append(
                f"{path.relative_to(ROOT)}: missing local release readback input."
            )
    if failures and any(not path.is_file() for path in (archive_path, manifest_path, checksum_path)):
        return failures

    def reject_duplicate_keys(
        pairs: list[tuple[str, object]],
    ) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        manifest_bytes = manifest_path.read_bytes()
        manifest = json.loads(
            manifest_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
        checksum_fields = checksum_path.read_text(encoding="ascii").split()
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: unreadable local release identity: {error}"
        )
        return failures

    if not isinstance(manifest, dict):
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: manifest root must be a JSON object."
        )
        return failures
    failures.extend(
        current_release_android_manifest_readback_failures(
            manifest,
            relative=str(manifest_path.relative_to(ROOT)),
        )
    )

    def read_path(path: tuple[str, ...]) -> object:
        value: object = manifest
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    manifest_expectations = (
        (("schemaVersion",), 2),
        (("release", "releaseId"), LOCAL_RELEASE_ID),
        (
            ("archive", "memberCountExcludingManifest"),
            LOCAL_RELEASE_EXPECTED_MEMBER_COUNT,
        ),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (("source", "snapshotSha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
        (("source", "head"), LOCAL_RELEASE_EXPECTED_SOURCE_HEAD),
        (("source", "worktreeState"), "dirty-content-snapshot"),
        (("platforms", "android", "applicationId"), "com.localagentbridge.android"),
        (
            ("platforms", "android", "versionCode"),
            LOCAL_RELEASE_BUILD_NUMBER,
        ),
        (
            ("platforms", "android", "versionName"),
            LOCAL_RELEASE_MARKETING_VERSION,
        ),
        (("platforms", "android", "minSdk"), 26),
        (("platforms", "android", "targetSdk"), 36),
        (("platforms", "android", "abis"), ["arm64-v8a"]),
        (("platforms", "android", "signatureState"), "unsigned"),
        (
            ("platforms", "android", "bundleStructureValidation"),
            {
                "member": "android/bundle/app-release.aab",
                "moduleSet": ["base"],
                "status": "passed",
                "tool": "bundletool validate",
            },
        ),
        (
            ("platforms", "android", "apkManifestReadback"),
            LOCAL_RELEASE_EXPECTED_APK_MANIFEST_READBACK,
        ),
        (
            ("platforms", "android", "bundleManifestReadback"),
            LOCAL_RELEASE_EXPECTED_BUNDLE_MANIFEST_READBACK,
        ),
        (("platforms", "macos", "bundleId"), "dev.aetherlink.companion"),
        (
            ("platforms", "macos", "marketingVersion"),
            LOCAL_RELEASE_MARKETING_VERSION,
        ),
        (
            ("platforms", "macos", "buildNumber"),
            LOCAL_RELEASE_BUILD_NUMBER,
        ),
        (("platforms", "macos", "minimumSystemVersion"), "14.0"),
        (("platforms", "macos", "architectures"), ["arm64"]),
        (("platforms", "macos", "signatureState"), "ad-hoc-local"),
        (("platforms", "macos", "uuid"), LOCAL_RELEASE_EXPECTED_MACOS_UUID),
        (
            ("platforms", "macos", "dSYM", "uuid"),
            LOCAL_RELEASE_EXPECTED_MACOS_UUID,
        ),
        (("compliance", "gradleLockedPackageCount"), 350),
        (("compliance", "swiftExternalDependencyCount"), 0),
        (("compliance", "artifactFilesAnalyzed"), False),
        (
            ("compliance", "licenseCompatibilityConclusionIncluded"),
            False,
        ),
        (("compliance", "licenseConcluded"), "NOASSERTION"),
        (("compliance", "networkRequiredForReleaseBuild"), False),
        (
            ("compliance", "profile"),
            "aetherlink-release-compliance-v2",
        ),
        (("compliance", "schemaVersion"), 2),
        (("compliance", "spdx", "format"), "SPDX-2.3"),
        (("compliance", "spdx", "packageCount"), 351),
        (("compliance", "spdx", "relationshipCount"), 692),
    )
    for path, expected in manifest_expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{manifest_path.relative_to(ROOT)}: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )

    member_rows = manifest.get("members")
    actual_members: dict[str, tuple[object, object]] = {}
    if not isinstance(member_rows, list):
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: members must be a JSON array."
        )
    else:
        for index, row in enumerate(member_rows):
            if not isinstance(row, dict):
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: members[{index}] must be an object."
                )
                continue
            path = row.get("path")
            if not isinstance(path, str):
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: members[{index}].path must be a string."
                )
                continue
            if path in actual_members:
                failures.append(
                    f"{manifest_path.relative_to(ROOT)}: duplicate member path {path!r}."
                )
                continue
            actual_members[path] = (row.get("size"), row.get("sha256"))

    for member_path, expected_identity in LOCAL_RELEASE_EXPECTED_MEMBERS.items():
        actual_identity = actual_members.get(member_path)
        if actual_identity != expected_identity:
            failures.append(
                f"{manifest_path.relative_to(ROOT)}: expected {member_path} "
                f"identity {expected_identity!r}, found {actual_identity!r}."
            )

    manifest_identity = (len(manifest_bytes), hashlib.sha256(manifest_bytes).hexdigest())
    expected_manifest_identity = (
        LOCAL_RELEASE_EXPECTED_MANIFEST_SIZE,
        LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
    )
    if manifest_identity != expected_manifest_identity:
        failures.append(
            f"{manifest_path.relative_to(ROOT)}: expected manifest identity "
            f"{expected_manifest_identity!r}, found {manifest_identity!r}."
        )

    archive_size = archive_path.stat().st_size
    if archive_size != LOCAL_RELEASE_EXPECTED_ZIP_SIZE:
        failures.append(
            f"{archive_path.relative_to(ROOT)}: expected size "
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SIZE}, found {archive_size}."
        )
    if (
        len(checksum_fields) != 2
        or checksum_fields[0] != LOCAL_RELEASE_EXPECTED_ZIP_SHA256
        or checksum_fields[1] != archive_path.name
    ):
        failures.append(
            f"{checksum_path.relative_to(ROOT)}: checksum sidecar does not match "
            f"{LOCAL_RELEASE_EXPECTED_ZIP_SHA256} and {archive_path.name}."
        )

    checksum_bytes = checksum_path.read_bytes()
    checksum_identity = (
        len(checksum_bytes),
        hashlib.sha256(checksum_bytes).hexdigest(),
    )
    expected_checksum_identity = (
        LOCAL_RELEASE_EXPECTED_CHECKSUM_SIZE,
        LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256,
    )
    if checksum_identity != expected_checksum_identity:
        failures.append(
            f"{checksum_path.relative_to(ROOT)}: expected checksum sidecar "
            f"identity {expected_checksum_identity!r}, found "
            f"{checksum_identity!r}."
        )

    result_relative = (
        "dist/reproducibility/"
        "aetherlink-1.0.0+22-local-v1-two-root-v4.json"
    )
    if not LOCAL_RELEASE_REPRODUCIBILITY_RESULT.is_file():
        failures.append(
            f"{result_relative}: missing current reproducibility result."
        )
        return failures

    try:
        result_bytes = LOCAL_RELEASE_REPRODUCIBILITY_RESULT.read_bytes()
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_keys,
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{result_relative}: unreadable current reproducibility result: "
            f"{error}"
        )
        return failures

    result_identity = (
        len(result_bytes),
        hashlib.sha256(result_bytes).hexdigest(),
    )
    expected_result_identity = (
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SIZE,
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_RESULT_SHA256,
    )
    if result_identity != expected_result_identity:
        failures.append(
            f"{result_relative}: expected identity "
            f"{expected_result_identity!r}, found {result_identity!r}."
        )

    if not isinstance(result, dict):
        failures.append(
            f"{result_relative}: result root must be a JSON object."
        )
        return failures

    missing_result_path = object()

    def read_result_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return missing_result_path
            value = value[key]
        return value

    result_expectations = (
        (("schemaVersion",), 4),
        (("executionMode",), "publish-qualified"),
        (("releaseId",), LOCAL_RELEASE_ID),
        (("status",), "passed"),
        (("failure",), None),
        (
            ("scratch", "sourceRoots", "policy"),
            "distinct-unequal-utf8-byte-length-v1",
        ),
        (
            ("scratch", "sourceRoots", "sourceRootByteLengths"),
            LOCAL_RELEASE_EXPECTED_SOURCE_ROOT_BYTE_LENGTHS,
        ),
        (("scratch", "sourceRoots", "sourceRootLengthsDiffer"), True),
        (("comparison", "archiveBytesEqual"), True),
        (("comparison", "memberSetEqual"), True),
        (("comparison", "memberMetadataEqual"), True),
        (("comparison", "memberBytesEqual"), True),
        (("comparison", "differences"), []),
        (("comparison", "memberDifferences"), []),
        (("prepublicationBinding", "matched"), True),
        (
            ("prepublicationBinding", "path"),
            (
                "dist/reproducibility/"
                "aetherlink-1.0.0+22-local-v1-two-root-v4-"
                "prepublication.json"
            ),
        ),
        (
            ("prepublicationBinding", "policy"),
            "canonical-comparison-result-exact-source-builds-and-comparison-v1",
        ),
        (
            ("prepublicationBinding", "sha256"),
            LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256,
        ),
        (
            ("prepublicationBinding", "size"),
            LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE,
        ),
        (
            ("protectedArchive", "policy"),
            "previous-ledger-entry-archive-v1",
        ),
        (
            ("protectedArchive", "relativePath"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_RELATIVE,
        ),
        (
            ("protectedArchive", "beforeIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (
            ("protectedArchive", "afterIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (("protectedArchive", "unchanged"), True),
        (
            ("toolchainPolicy", "scope"),
            "same-host-fixed-toolchain-cache-snapshot",
        ),
        (
            ("publication", "archiveSha256"),
            LOCAL_RELEASE_EXPECTED_ZIP_SHA256,
        ),
        (
            ("publication", "manifestSha256"),
            LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256,
        ),
        (
            ("publication", "checksumSha256"),
            LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256,
        ),
        (
            ("publication", "archiveDirectory"),
            f"dist/releases/{LOCAL_RELEASE_ID}",
        ),
        (("publication", "alreadyMatched"), False),
        (("publication", "attempted"), True),
        (("publication", "independentReadback"), True),
        (("publication", "outcome"), "published-verified"),
        (
            ("publication", "policy"),
            "publish-qualified-build-a-after-exact-two-root-match",
        ),
        (("publication", "publishedBytesEqualLaneA"), True),
        (("publication", "qualifiedArchivePublished"), True),
        (("publication", "sourceLane"), "build-a"),
        (("publication", "sourceSnapshotUnchanged"), True),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (
            ("source", "overlaySha256"),
            LOCAL_RELEASE_EXPECTED_SOURCE_OVERLAY_SHA256,
        ),
        (("source", "sha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
    )
    for path, expected in result_expectations:
        actual = read_result_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{result_relative}: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )
    swift_arguments = read_result_path(("toolchainPolicy", "swiftArguments"))
    serialized_frontend = ["-Xswiftc", "-num-threads", "-Xswiftc", "1"]
    if (
        not isinstance(swift_arguments, list)
        or not any(
            swift_arguments[index : index + len(serialized_frontend)]
            == serialized_frontend
            for index in range(
                len(swift_arguments) - len(serialized_frontend) + 1
            )
        )
    ):
        failures.append(
            f"{result_relative}: toolchainPolicy.swiftArguments must include "
            f"the exact contiguous sequence {serialized_frontend!r}."
        )

    failures.extend(
        current_release_reproducibility_build_failures(
            result,
            result_relative,
        )
    )
    failures.extend(current_release_reproducibility_prepublication_failures())
    return failures


def current_release_reproducibility_build_failures(
    result: dict[str, object],
    relative: str,
) -> list[str]:
    failures: list[str] = []
    builds = result.get("builds")
    if not isinstance(builds, list) or len(builds) != 2:
        return [
            f"{relative}: builds must contain exact build-a/build-b results."
        ]
    for index, expected_id in enumerate(("build-a", "build-b")):
        build = builds[index]
        if not isinstance(build, dict):
            failures.append(
                f"{relative}: builds[{index}] must be an object."
            )
            continue
        build_expectations = (
            ("id", expected_id),
            ("status", "passed"),
            ("commandExitCode", 0),
        )
        for key, expected in build_expectations:
            actual = build.get(key)
            if type(actual) is not type(expected) or actual != expected:
                failures.append(
                    f"{relative}: expected builds[{index}].{key}="
                    f"{expected!r}, found {actual!r}."
                )
        archive = build.get("archive")
        if not isinstance(archive, dict):
            failures.append(
                f"{relative}: builds[{index}].archive must be an object."
            )
            continue
        archive_expectations = (
            ("size", LOCAL_RELEASE_EXPECTED_ZIP_SIZE),
            ("sha256", LOCAL_RELEASE_EXPECTED_ZIP_SHA256),
            ("manifestSha256", LOCAL_RELEASE_EXPECTED_MANIFEST_SHA256),
            ("checksumSha256", LOCAL_RELEASE_EXPECTED_CHECKSUM_SHA256),
            ("sourceSha256", LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
            ("payloadMemberCount", LOCAL_RELEASE_EXPECTED_MEMBER_COUNT),
            ("zipEntryCount", LOCAL_RELEASE_EXPECTED_MEMBER_COUNT + 1),
        )
        for key, expected in archive_expectations:
            actual = archive.get(key)
            if type(actual) is not type(expected) or actual != expected:
                failures.append(
                    f"{relative}: expected builds[{index}].archive.{key}="
                    f"{expected!r}, found {actual!r}."
                )
        members = archive.get("members")
        expected_member_count = LOCAL_RELEASE_EXPECTED_MEMBER_COUNT + 1
        if not isinstance(members, list) or len(members) != expected_member_count:
            failures.append(
                f"{relative}: builds[{index}].archive.members must contain "
                f"exactly {expected_member_count} entries."
            )
    return failures


def current_release_reproducibility_prepublication_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    relative = (
        "dist/reproducibility/"
        "aetherlink-1.0.0+22-local-v1-two-root-v4-prepublication.json"
    )
    if result_bytes is None:
        if not LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT.is_file():
            return [f"{relative}: missing reproducibility prepublication result."]
        try:
            result_bytes = (
                LOCAL_RELEASE_REPRODUCIBILITY_PREPUBLICATION_RESULT.read_bytes()
            )
        except OSError as error:
            return [
                f"{relative}: unreadable reproducibility prepublication "
                f"result: {error}"
            ]

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SIZE,
        LOCAL_RELEASE_EXPECTED_REPRODUCIBILITY_PREPUBLICATION_SHA256,
    )
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected identity {expected_identity!r}, "
            f"found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{relative}: invalid reproducibility prepublication JSON: {error}"
        )
        return failures
    if not isinstance(result, dict):
        failures.append(
            f"{relative}: reproducibility prepublication root must be an object."
        )
        return failures

    missing_result_path = object()

    def read_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return missing_result_path
            value = value[key]
        return value

    expectations = (
        (("schemaVersion",), 4),
        (("executionMode",), "comparison-only"),
        (("releaseId",), LOCAL_RELEASE_ID),
        (("status",), "passed"),
        (("failure",), None),
        (
            ("scratch", "sourceRoots", "policy"),
            "distinct-unequal-utf8-byte-length-v1",
        ),
        (
            ("scratch", "sourceRoots", "sourceRootByteLengths"),
            LOCAL_RELEASE_EXPECTED_SOURCE_ROOT_BYTE_LENGTHS,
        ),
        (("scratch", "sourceRoots", "sourceRootLengthsDiffer"), True),
        (("comparison", "archiveBytesEqual"), True),
        (("comparison", "memberSetEqual"), True),
        (("comparison", "memberMetadataEqual"), True),
        (("comparison", "memberBytesEqual"), True),
        (("comparison", "differences"), []),
        (("comparison", "memberDifferences"), []),
        (("prepublicationBinding",), None),
        (
            ("protectedArchive", "policy"),
            "previous-ledger-entry-archive-v1",
        ),
        (
            ("protectedArchive", "relativePath"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_RELATIVE,
        ),
        (
            ("protectedArchive", "beforeIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (
            ("protectedArchive", "afterIdentitySha256"),
            LOCAL_RELEASE_EXPECTED_PROTECTED_ARCHIVE_IDENTITY_SHA256,
        ),
        (("protectedArchive", "unchanged"), True),
        (
            ("toolchainPolicy", "scope"),
            "same-host-fixed-toolchain-cache-snapshot",
        ),
        (("publication", "attempted"), False),
        (("publication", "independentReadback"), False),
        (("publication", "outcome"), "disabled-comparison-only"),
        (("publication", "policy"), "comparison-only-no-publication"),
        (("publication", "qualifiedArchivePublished"), False),
        (("source", "fileCount"), LOCAL_RELEASE_EXPECTED_SOURCE_FILE_COUNT),
        (
            ("source", "overlaySha256"),
            LOCAL_RELEASE_EXPECTED_PREPUBLICATION_SOURCE_OVERLAY_SHA256,
        ),
        (("source", "sha256"), LOCAL_RELEASE_EXPECTED_SOURCE_SHA256),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )

    swift_arguments = read_path(("toolchainPolicy", "swiftArguments"))
    serialized_frontend = ["-Xswiftc", "-num-threads", "-Xswiftc", "1"]
    if (
        not isinstance(swift_arguments, list)
        or not any(
            swift_arguments[index : index + len(serialized_frontend)]
            == serialized_frontend
            for index in range(
                len(swift_arguments) - len(serialized_frontend) + 1
            )
        )
    ):
        failures.append(
            f"{relative}: toolchainPolicy.swiftArguments must include the "
            f"exact contiguous sequence {serialized_frontend!r}."
        )

    failures.extend(
        current_release_reproducibility_build_failures(result, relative)
    )
    return failures


def macos_clean_home_installed_app_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_CLEAN_HOME_INSTALLED_APP_RUNNER,
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256,
        ),
        (
            MACOS_CLEAN_HOME_INSTALLED_APP_TEST,
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256,
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(f"{relative}: missing clean-HOME source.")
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(
                f"{relative}: unreadable clean-HOME source: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected SHA-256 {expected_sha256}, "
                f"found {actual_sha256}."
            )
    return failures


def macos_clean_home_installed_state_recovery_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RUNNER,
            (
                CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
            ),
        ),
        (
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_TEST,
            (
                CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256
            ),
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(
                f"{relative}: missing installed state-recovery source."
            )
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(
                f"{relative}: unreadable installed state-recovery source: "
                f"{error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected SHA-256 {expected_sha256}, "
                f"found {actual_sha256}."
            )
    return failures


def macos_packaged_lifecycle_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_PACKAGED_LIFECYCLE_RUNNER,
            MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256,
        ),
        (
            MACOS_PACKAGED_LIFECYCLE_TEST,
            MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256,
        ),
        (
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RUNNER,
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RUNNER_SHA256,
        ),
        (
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_TEST,
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_TEST_SHA256,
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(f"{relative}: missing lifecycle source.")
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(f"{relative}: unreadable lifecycle source: {error}")
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected SHA-256 {expected_sha256}, "
                f"found {actual_sha256}."
            )
    return failures


def macos_packaged_state_recovery_source_failures() -> list[str]:
    expected_sources = (
        (
            MACOS_PACKAGED_STATE_RECOVERY_RUNNER,
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256,
        ),
        (
            MACOS_PACKAGED_STATE_RECOVERY_TEST,
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_TEST_SHA256,
        ),
    )
    failures: list[str] = []
    for path, expected_sha256 in expected_sources:
        relative = path.relative_to(ROOT)
        if not path.is_file():
            failures.append(f"{relative}: missing state-recovery source.")
            continue
        try:
            payload = path.read_bytes()
        except OSError as error:
            failures.append(
                f"{relative}: unreadable state-recovery source: {error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{relative}: expected SHA-256 {expected_sha256}, "
                f"found {actual_sha256}."
            )
    return failures


def packaged_lifecycle_evidence_failures(
    *,
    result_path: Path,
    relative: str,
    expected_size: int,
    expected_sha256: str,
    expected_result: dict[str, object],
    build_label: str,
    result_bytes: bytes | None = None,
) -> list[str]:
    if result_bytes is None:
        if not result_path.is_file():
            return [f"{relative}: missing packaged-app lifecycle result."]
        try:
            result_bytes = result_path.read_bytes()
        except OSError as error:
            return [
                f"{relative}: unreadable packaged-app lifecycle result: {error}"
            ]

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (expected_size, expected_sha256)
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected identity {expected_identity!r}, "
            f"found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(
            f"{relative}: invalid packaged-app lifecycle JSON: {error}"
        )
        return failures

    if not exact_json_values_equal(
        result,
        expected_result,
    ):
        failures.append(
            f"{relative}: result does not match the exact closed "
            f"{build_label} lifecycle contract."
        )
    return failures


def macos_clean_home_installed_app_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_CLEAN_HOME_INSTALLED_APP_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-14-clean-home-install-v1.json"
        ),
        expected_size=(
            MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256
        ),
        expected_result=MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT,
        build_label="historical Build 14 clean-HOME installed-app",
        result_bytes=result_bytes,
    )


def current_macos_clean_home_installed_app_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-install-v1.json"
        ),
        expected_size=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256
        ),
        expected_result=CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT,
        build_label="historical Build 20 clean-HOME installed-app",
        result_bytes=result_bytes,
    )


def macos_clean_home_installed_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-14-clean-home-state-recovery-v1.json"
        ),
        expected_size=(
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
        ),
        build_label="historical Build 14 clean-HOME installed state-recovery",
        result_bytes=result_bytes,
    )


def current_macos_clean_home_installed_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
        ),
        expected_size=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT
        ),
        build_label="historical Build 20 clean-HOME installed state-recovery",
        result_bytes=result_bytes,
    )


def current_macos_local_dmg_install_evidence_failures(
    result_bytes: bytes | None = None,
    source_bytes_by_path: dict[Path, bytes] | None = None,
) -> list[str]:
    relative = str(CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT.relative_to(ROOT))
    failures: list[str] = []

    for path, expected_sha256 in (
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_RUNNER,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RUNNER_SHA256,
        ),
        (
            CURRENT_MACOS_LOCAL_DMG_INSTALL_TEST,
            CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_TEST_SHA256,
        ),
    ):
        try:
            payload = (
                source_bytes_by_path[path]
                if source_bytes_by_path is not None
                else path.read_bytes()
            )
        except (KeyError, OSError) as error:
            failures.append(
                f"{path.relative_to(ROOT)}: cannot read local DMG source: "
                f"{error}"
            )
            continue
        actual_sha256 = hashlib.sha256(payload).hexdigest()
        if actual_sha256 != expected_sha256:
            failures.append(
                f"{path.relative_to(ROOT)}: expected local DMG source "
                f"SHA-256 {expected_sha256}, found {actual_sha256}."
            )

    if result_bytes is None:
        try:
            result_bytes = CURRENT_MACOS_LOCAL_DMG_INSTALL_RESULT.read_bytes()
        except OSError as error:
            failures.append(f"{relative}: cannot read local DMG result: {error}")
            return failures

    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE,
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256,
    )
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected identity {expected_identity!r}, "
            f"found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("utf-8"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(f"{relative}: invalid local DMG result JSON: {error}")
        return failures
    if not isinstance(result, dict):
        failures.append(f"{relative}: local DMG result root must be an object.")
        return failures

    def read_path(path: tuple[str, ...]) -> object:
        value: object = result
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    expectations = (
        (("schemaVersion",), 1),
        (("status",), "passed"),
        (("scope",), "same-host-per-user-ephemeral-local-dmg-install-v1"),
        (("release", "releaseId"), HISTORICAL_BUILD20_RELEASE_ID),
        (
            ("release", "archiveSha256"),
            HISTORICAL_BUILD20_ARCHIVE_SHA256,
        ),
        (
            ("release", "manifestSha256"),
            HISTORICAL_BUILD20_MANIFEST_SHA256,
        ),
        (("image", "filesystem"), "HFS+"),
        (("image", "format"), "UDZO"),
        (("image", "verified"), True),
        (("image", "ephemeral"), True),
        (("image", "retained"), False),
        (("mount", "readOnly"), True),
        (("mount", "exactFreshMountpoint"), True),
        (("mount", "detachedBeforeLaunch"), True),
        (("mount", "unmountedVerified"), True),
        (("installation", "exactReleaseTreeCopied"), True),
        (("launchServices", "distinctProcessIdentifiers"), True),
        (("state", "databaseCount"), 3),
        (("state", "integrityChecks"), "passed"),
        (("state", "stableAcrossRelaunch"), True),
    )
    for path, expected in expectations:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                f"{relative}: expected {'.'.join(path)}={expected!r}, "
                f"found {actual!r}."
            )

    runs = read_path(("launchServices", "runs"))
    if not isinstance(runs, list) or len(runs) != 2:
        failures.append(
            f"{relative}: launchServices.runs must contain two launches."
        )
    limitations = result.get("limitations")
    required_limitations = {
        "not-finder-ui-or-drag-and-drop-evidence",
        "not-developer-id-notarized-or-stapled-distribution",
        "not-gatekeeper-quarantine-or-download-evidence",
        "not-clean-machine-account-or-system-applications",
        "not-upgrade-n-or-n-minus-one-rollback-production-or-security-evidence",
    }
    if not isinstance(limitations, list) or not required_limitations.issubset(
        {item for item in limitations if isinstance(item, str)}
    ):
        failures.append(
            f"{relative}: local DMG result lost required scope limitations."
        )
    return failures


def current_runtime_chat_sqlite_abrupt_recovery_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        LOCAL_RELEASE_CURRENT_DOC,
    )
    result_path = (
        "dist/lifecycle/"
        "macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json"
    )
    common_patterns = (
        (
            "bounded recovery claim",
            re.compile(
                r"\bbounded same-host abrupt child-\s*process "
                r"`SIGKILL` recovery evidence\b",
                re.IGNORECASE,
            ),
        ),
        (
            "committed prefix",
            re.compile(
                r"\b(?:24 committed events|(?:committed|commits) 24 events)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "in-flight event and FTS row",
            re.compile(
                r"\b(?:dirty uncommitted|QA-only raw SQLite transaction)"
                r".{0,120}\b25th event and FTS row\b",
                re.IGNORECASE,
            ),
        ),
        (
            "recovery to the committed prefix",
            re.compile(r"\brecover(?:y|ed|s)?\b.{0,100}\b24\b", re.IGNORECASE),
        ),
        (
            "production-store resume",
            re.compile(
                r"\b(?:production-store resume|"
                r"resumes? through the production store)\b",
                re.IGNORECASE,
            ),
        ),
        (
            "final contiguous exactly-once event set",
            re.compile(r"\b48 contiguous exactly-once events\b", re.IGNORECASE),
        ),
        (
            "power-loss and kernel-crash exclusion",
            re.compile(
                r"\bnot power-loss or kernel-crash evidence\b",
                re.IGNORECASE,
            ),
        ),
        (
            "arbitrary-history and long-soak exclusion",
            re.compile(
                r"\bnot arbitrary-history or long-soak evidence\b",
                re.IGNORECASE,
            ),
        ),
        (
            "distribution and device exclusion",
            re.compile(
                r"\bnot clean-machine, signed-distribution, or "
                r"physical-device evidence\b",
                re.IGNORECASE,
            ),
        ),
    )
    forbidden_scope = re.compile(
        r"\b(?:production[- ]append[- ]crash[- ]point|"
        r"power[- ]loss(?: recovery)?|kernel[- ]crash(?: recovery)?|"
        r"clean[- ]machine(?: recovery)?|signed[- ]distribution|"
        r"physical[- ]device(?: behavior)?)\b",
        re.IGNORECASE,
    )
    explicit_scope_boundary = re.compile(
        r"\b(?:not|no|never|cannot|does not|do not|is not|are not|"
        r"unqualified|unproven|unknown|deferred|remains? open|"
        r"requires? future)\b",
        re.IGNORECASE,
    )

    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate Build 21 abrupt recovery "
                f"documentation: {error}"
            )
            continue

        start_count = document_text.count(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: Build 21 abrupt recovery block must contain "
                "exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START
        ) + len(CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_START)
        end_index = document_text.index(
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_END
        )
        if end_index <= start_index:
            failures.append(
                f"{relative}: Build 21 abrupt recovery markers are reversed "
                "or empty."
            )
            continue

        block = document_text[start_index:end_index]
        block_sha256 = hashlib.sha256(block.encode("utf-8")).hexdigest()
        expected_block_sha256 = (
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_DOCUMENT_BLOCK_SHA256[relative]
        )
        if block_sha256 != expected_block_sha256:
            failures.append(
                f"{relative}: Build 21 abrupt recovery block must retain "
                "its exact bounded block SHA-256 "
                f"{expected_block_sha256}; found {block_sha256}."
            )
        normalized_block = re.sub(r"\s+", " ", block).strip()
        for binding in (
            result_path,
            CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256,
            "`not-production-append-crash-point`",
        ):
            count = normalized_block.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: Build 21 abrupt recovery block must contain "
                    f"{binding!r} exactly once; found {count}."
                )
        formatted_size = f"{CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE:,}"
        if not re.search(
            rf"\b{re.escape(formatted_size)}(?:-byte| bytes)\b",
            normalized_block,
        ):
            failures.append(
                f"{relative}: Build 21 abrupt recovery block is missing "
                f"the exact {formatted_size}-byte result size."
            )
        for label, pattern in common_patterns:
            if not pattern.search(normalized_block):
                failures.append(
                    f"{relative}: Build 21 abrupt recovery block is missing "
                    f"its {label}."
                )

        if path == LOCAL_RELEASE_CURRENT_DOC:
            for binding in (
                "`writerProcessReapedBeforeJournalObservation=true`",
                "25 event rows",
                "mutation revision 25",
                "validated revision 24",
            ):
                if normalized_block.count(binding) != 1:
                    failures.append(
                        f"{relative}: detailed abrupt recovery record must "
                        f"contain {binding!r} exactly once."
                    )

        for sentence in re.split(r"(?<=[.!?])\s+", normalized_block):
            plain_sentence = sentence.replace("`", "")
            scope_match = forbidden_scope.search(plain_sentence)
            if scope_match and not explicit_scope_boundary.search(
                plain_sentence
            ):
                failures.append(
                    f"{relative}: Build 21 abrupt recovery block contains "
                    "an unbounded or contradictory forbidden-scope claim."
                )
                break
    return failures


def current_runtime_chat_sqlite_cross_process_document_failures(
    document_text: str | None = None,
    *,
    relative: str = "docs/releases/1.0.0-build-22-local-v1.md",
) -> list[str]:
    if document_text is None:
        try:
            document_text = LOCAL_RELEASE_CURRENT_DOC.read_text(
                encoding="utf-8"
            )
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate current Runtime-chat SQLite "
                f"cross-process evidence: {error}"
            ]

    normalized_text = re.sub(r"\s+", " ", document_text).strip()
    failures: list[str] = []
    for label, pattern in CURRENT_RUNTIME_CHAT_SQLITE_DOCUMENT_REQUIRED_PATTERNS:
        if not pattern.search(normalized_text):
            failures.append(
                f"{relative}: current Build 22 Runtime-chat SQLite "
                f"cross-process record is missing {label}."
            )

    stable_message_count = normalized_text.count(
        CURRENT_RUNTIME_CHAT_SQLITE_STABLE_BUSY_MESSAGE
    )
    if stable_message_count != 1:
        failures.append(
            f"{relative}: current Build 22 Runtime-chat SQLite stable busy "
            "message must appear exactly once; found "
            f"{stable_message_count}."
        )

    for source_path in (
        (
            "apps/macos/RuntimeChatSQLiteCrossProcessQA/Sources/"
            "RuntimeChatSQLiteCrossProcessQA.swift"
        ),
        "script/run_macos_runtime_chat_cross_process_smoke.py",
        "script/test_run_macos_runtime_chat_cross_process_smoke.py",
    ):
        size, sha256 = (
            LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS[
                source_path
            ]
        )
        required_source_bindings = (
            f"`{source_path}`",
            f"{size:,} bytes",
            f"`{sha256}`",
        )
        for binding in required_source_bindings:
            count = normalized_text.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: Build 22 source inventory must bind "
                    f"{source_path!r} with {binding!r} exactly once; found "
                    f"{count}."
                )
    return failures


def current_runtime_chat_sqlite_source_failures(
    source_bytes_by_relative: dict[str, bytes] | None = None,
) -> list[str]:
    failures: list[str] = []
    for relative, expected_identity in (
        LOCAL_RELEASE_EXPECTED_RUNTIME_CHAT_SQLITE_SOURCE_MEMBERS.items()
    ):
        try:
            source_bytes = (
                source_bytes_by_relative[relative]
                if source_bytes_by_relative is not None
                else (ROOT / relative).read_bytes()
            )
        except (KeyError, OSError) as error:
            failures.append(
                f"{relative}: cannot validate Build 22 Runtime-chat SQLite "
                f"source binding: {error}"
            )
            continue
        identity = (
            len(source_bytes),
            hashlib.sha256(source_bytes).hexdigest(),
        )
        if identity != expected_identity:
            failures.append(
                f"{relative}: expected Build 22 source inventory identity "
                f"{expected_identity!r}, found {identity!r}."
            )

    test_relative = (
        "apps/macos/CompanionCore/Tests/SQLiteRuntimeChatEventStoreTests.swift"
    )
    try:
        test_source = (
            source_bytes_by_relative[test_relative]
            if source_bytes_by_relative is not None
            else (ROOT / test_relative).read_bytes()
        ).decode("utf-8")
    except (KeyError, OSError, UnicodeError) as error:
        failures.append(
            f"{test_relative}: cannot validate Build 22 Runtime-chat SQLite "
            f"Swift regressions: {error}"
        )
        test_source = ""
    for test_name in CURRENT_RUNTIME_CHAT_SQLITE_SWIFT_TESTS:
        declaration = f"func {test_name}() throws"
        count = test_source.count(declaration)
        if count != 1:
            failures.append(
                f"{test_relative}: exact Swift regression {test_name!r} must "
                f"appear once; found {count}."
            )

    store_relative = (
        "apps/macos/CompanionCore/Sources/SQLiteRuntimeChatEventStore.swift"
    )
    try:
        store_source = (
            source_bytes_by_relative[store_relative]
            if source_bytes_by_relative is not None
            else (ROOT / store_relative).read_bytes()
        ).decode("utf-8")
    except (KeyError, OSError, UnicodeError):
        store_source = ""
    for binding in (
        "private static let busyTimeoutMilliseconds: Int32 = 5_000",
        "sqlite3_busy_timeout(openedDatabase, Self.busyTimeoutMilliseconds)",
    ):
        if store_source.count(binding) != 1:
            failures.append(
                f"{store_relative}: exact production busy-timeout binding "
                f"{binding!r} must appear once."
            )
    return failures


def current_runtime_chat_sqlite_abrupt_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    relative = str(
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT.relative_to(ROOT)
    )
    if result_bytes is None:
        try:
            result_bytes = CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT.read_bytes()
        except OSError as error:
            return [f"{relative}: cannot read abrupt recovery result: {error}"]

    failures: list[str] = []
    identity = (len(result_bytes), hashlib.sha256(result_bytes).hexdigest())
    expected_identity = (
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SIZE,
        CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256,
    )
    if identity != expected_identity:
        failures.append(
            f"{relative}: expected abrupt recovery identity "
            f"{expected_identity!r}, found {identity!r}."
        )

    try:
        result = json.loads(
            result_bytes.decode("ascii"),
            object_pairs_hook=reject_duplicate_json_keys,
        )
    except (
        UnicodeError,
        json.JSONDecodeError,
        DuplicateJSONKeyError,
    ) as error:
        failures.append(f"{relative}: invalid abrupt recovery JSON: {error}")
        return failures

    expected_result = {
        "abruptTermination": {
            "checkpoint": {
                "committedPrefixCount": 24,
                "databaseCacheFlushed": True,
                "inFlightEventID": (
                    "qa-writer-a-inflight-uncommitted-v1"
                ),
                "insideTransactionEventCount": 25,
                "insideTransactionFTSEventCount": 25,
                "insideTransactionMutationRevision": 25,
                "insideTransactionValidatedRevision": 24,
                "journalMode": "delete",
                "schemaVersion": 1,
                "status": "ready-for-abrupt-termination",
                "transactionOpen": True,
                "writer": "writer-a",
            },
            "dirtyDatabaseBeforeRecovery": {
                "appendStateMutationRevision": 25,
                "appendStateValidatedRevision": 24,
                "eventCount": 25,
                "ftsEventCount": 25,
                "immutableReadIgnoredJournal": True,
                "inFlightEventAndFTSPresent": True,
            },
            "journal": {
                "hotJournalHeaderObserved": True,
                "journalMode": "delete",
                "ownerOnlyMode": "0600",
                "pageRecordCountPositive": True,
                "pageSize": 4_096,
                "sectorSize": 512,
            },
            "processGroup": "new-session-exact-child-only",
            "terminationSignal": "SIGKILL",
            "writerProcessReapedBeforeJournalObservation": True,
        },
        "cleanup": "passed",
        "committedPrefixCount": 24,
        "committedPrefixWritePath": (
            "production-SQLiteRuntimeChatEventStore"
        ),
        "final": {
            "appendStateRevision": 48,
            "eventCount": 48,
            "ftsEventCount": 48,
            "hotJournalCleared": True,
            "inFlightEventAndFTSAbsent": True,
            "integrityCheck": "ok",
            "residualJournalHeaderZeroed": False,
            "sequencesContiguous": True,
        },
        "finalReadbackProcess": "independent",
        "inFlightEventID": "qa-writer-a-inflight-uncommitted-v1",
        "inFlightTransactionWritePath": "qa-raw-sql-event-plus-fts-v1",
        "limitations": [
            "same-host-abrupt-child-process-termination-only",
            "not-production-append-crash-point",
            "not-power-loss-or-kernel-crash-evidence",
            "not-arbitrary-history-or-long-soak-evidence",
            "not-clean-machine-signed-distribution-or-device-evidence",
        ],
        "permissions": {
            "checkpointAndSQLiteFiles": "0600",
            "databaseRoot": "0700",
        },
        "recovered": {
            "appendStateRevision": 24,
            "eventCount": 24,
            "ftsEventCount": 24,
            "hotJournalCleared": True,
            "inFlightEventAndFTSAbsent": True,
            "integrityCheck": "ok",
            "residualJournalHeaderZeroed": False,
            "sequencesContiguous": True,
        },
        "recoveryReadbackProcess": "independent",
        "resume": {
            "endExclusive": 48,
            "eventCount": 24,
            "startOrdinal": 24,
            "status": "passed",
            "writer": "writer-a",
        },
        "resumeWritePath": "production-SQLiteRuntimeChatEventStore",
        "schemaVersion": 1,
        "scope": "macos-runtime-chat-sqlite-abrupt-process-recovery-v1",
        "status": "passed",
    }
    if not exact_json_values_equal(result, expected_result):
        failures.append(
            f"{relative}: result does not match the exact closed abrupt "
            "child-process recovery contract."
        )

    canonical = (
        json.dumps(
            result,
            ensure_ascii=True,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("ascii")
        + b"\n"
    )
    if result_bytes != canonical:
        failures.append(
            f"{relative}: result must be canonical sorted compact ASCII JSON "
            "with one final LF."
        )
    return failures


def current_macos_clean_home_lifecycle_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    required_once = (
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-install-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256,
    )
    required_claims = (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_REPEATABILITY_CLAIM,
    )
    dmg_required_once = (
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-local-dmg-install-v1.json"
        ),
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256,
    )
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
        HISTORICAL_BUILD20_RELEASE_DOC,
        LOCAL_RELEASE_CURRENT_DOC,
    )
    release_document_paths = {
        HISTORICAL_BUILD20_RELEASE_DOC,
        LOCAL_RELEASE_CURRENT_DOC,
    }
    failures: list[str] = []
    for path in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Build 20 lifecycle "
                f"bindings: {error}"
            )
            continue
        start_count = document_text.count(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Build 20 lifecycle block must contain "
                f"exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue
        start_index = document_text.index(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        body_start = start_index + len(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START
        )
        end_index = document_text.index(
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END
        )
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Build 20 lifecycle markers are "
                "reversed or empty."
            )
            continue
        block = document_text[body_start:end_index]
        normalized_block = re.sub(r"\s+", " ", block).strip()
        if "Build 20" not in normalized_block:
            failures.append(
                f"{relative}: current lifecycle block is not explicitly "
                "bound to Build 20."
            )
        historical_build_mentions = {
            int(value)
            for value in re.findall(
                r"\bBuild\s+([1-9][0-9]*)\b",
                normalized_block,
                re.IGNORECASE,
            )
            if int(value) < 20
        }
        historical_path_mentions = {
            int(value)
            for value in re.findall(
                r"macos-packaged-app-build-([1-9][0-9]*)-",
                normalized_block,
                re.IGNORECASE,
            )
            if int(value) < 20
        }
        historical_contamination = sorted(
            historical_build_mentions | historical_path_mentions
        )
        if historical_contamination:
            failures.append(
                f"{relative}: historical Build "
                f"{historical_contamination!r} content entered the current "
                "Build 20 lifecycle block."
            )
        future_build_mentions = {
            int(value)
            for value in re.findall(
                r"\bBuild\s+([1-9][0-9]*)\b",
                normalized_block,
                re.IGNORECASE,
            )
            if int(value) > 20
        }
        if future_build_mentions:
            failures.append(
                f"{relative}: current Build 20 lifecycle block contains future "
                f"Build {sorted(future_build_mentions)!r} content."
            )
        block_required_once = list(required_once)
        if path in release_document_paths:
            block_required_once.extend(
                (
                    CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RUNNER_SHA256,
                    CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_TEST_SHA256,
                    (
                        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RUNNER_SHA256
                    ),
                    (
                        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_TEST_SHA256
                    ),
                )
            )
        for binding in block_required_once:
            count = block.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: current Build 20 lifecycle block must "
                    f"contain binding {binding!r} exactly once; found {count}."
                )
        dmg_scope = document_text if path in release_document_paths else block
        for binding in dmg_required_once:
            count = dmg_scope.count(binding)
            if count != 1:
                failures.append(
                    f"{relative}: current Build 20 DMG evidence must contain "
                    f"binding {binding!r} exactly once; found {count}."
                )
        size_expectations = (
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SIZE,
            CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SIZE,
        )
        for expected_size in size_expectations:
            formatted_size = f"{expected_size:,}"
            if not re.search(
                rf"\b{re.escape(formatted_size)}(?:-byte| bytes)\b",
                normalized_block,
            ):
                failures.append(
                    f"{relative}: current Build 20 lifecycle block is "
                    f"missing exact {formatted_size}-byte result size."
                )
        dmg_size_scope = (
            re.sub(r"\s+", " ", document_text).strip()
            if path in release_document_paths
            else normalized_block
        )
        dmg_size = f"{CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SIZE:,}"
        if not re.search(
            rf"\b{re.escape(dmg_size)}(?:-byte| bytes)\b",
            dmg_size_scope,
        ):
            failures.append(
                f"{relative}: current Build 20 DMG evidence is missing exact "
                f"{dmg_size}-byte result size."
            )
        for claim in required_claims:
            normalized_claim = re.sub(r"\s+", " ", claim).strip()
            count = normalized_block.count(normalized_claim)
            if count != 1:
                failures.append(
                    f"{relative}: current Build 20 lifecycle block is "
                    f"required to contain exact bounded claim {claim!r} "
                    f"once; found {count}."
                )
        boundary_match = re.search(
            r"\bThese historical same-host, per-user Build 20\b.*?"
            r"\bproduction readiness\.",
            normalized_block,
            re.IGNORECASE,
        )
        if boundary_match is None:
            failures.append(
                f"{relative}: current Build 20 lifecycle block is missing "
                "its bounded non-production sentence."
            )
            block_without_boundary = normalized_block
        else:
            boundary = boundary_match.group(0)
            for term in CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_BOUNDARY_TERMS:
                if term.lower() not in boundary.lower():
                    failures.append(
                        f"{relative}: current Build 20 lifecycle boundary is "
                        f"missing {term!r}."
                    )
            if not re.search(
                r"\bdo not (?:themselves )?qualify\b",
                boundary,
                re.IGNORECASE,
            ):
                failures.append(
                    f"{relative}: current Build 20 lifecycle boundary must "
                    "remain explicitly non-qualifying."
                )
            block_without_boundary = (
                normalized_block[: boundary_match.start()]
                + normalized_block[boundary_match.end() :]
            )
        prohibited_positive_claims = (
            r"\bqualif(?:y|ies|ied|ication)\b",
            r"\bprov(?:e|es|ed|en)\b",
            r"\bcertif(?:y|ies|ied|ication)\b",
            r"\bproduction[- ]ready\b",
            (
                r"\b(?:clean[- ]machine|DMG/Finder|signed/notarized|"
                r"physical[- ]device)\b.{0,100}\b(?:passes?|passed|"
                r"supports?|supported)\b"
            ),
            (
                r"\b(?:passes?|passed|supports?|supported)\b.{0,100}"
                r"\b(?:clean[- ]machine|DMG/Finder|signed/notarized|"
                r"physical[- ]device)\b"
            ),
        )
        for pattern in prohibited_positive_claims:
            if re.search(pattern, block_without_boundary, re.IGNORECASE):
                failures.append(
                    f"{relative}: current Build 20 lifecycle block contains "
                    "a contradictory positive qualification claim."
                )
                break
    return failures


def current_android_drawer_search_document_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    documentation_targets = (
        (
            ROOT / "docs/roadmap.md",
            "The current unreleased G5 product-quality slice",
            "The current G5 accessibility slice",
        ),
        (
            ROOT / "docs/handoff.md",
            CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END,
            "- The multilingual full-matrix V3 path",
        ),
        (
            ROOT / "docs/progress.md",
            "## 2026-07-29 Unreleased Android Drawer Semantic Chat Search UX",
            "## 2026-07-29 Unreleased Multilingual Full-Matrix V3 Preparation",
        ),
        (
            ROOT / "docs/qa-evidence.md",
            "## 2026-07-29 Android Drawer Semantic Chat Search UX Checklist",
            "## 2026-07-29 Multilingual Full-Matrix V3 Preparation Checklist",
        ),
    )
    required_claims = (
        CURRENT_ANDROID_DRAWER_SEARCH_BEHAVIOR_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_ACTION_STATE_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_PENDING_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_RESULT_CLAIM,
        CURRENT_ANDROID_DRAWER_SEARCH_EVIDENCE_CLAIM,
    )
    stale_current_markers = (
        "1,179 tests",
        "1,191-test",
        "1,192-test",
        "167 AppNavigationTest",
        "167-test navigation",
        "167 navigation-policy",
        "12 search-related RuntimeClientViewModelTest",
        "13 search-related RuntimeClientViewModelTest",
        "24 drawer Compose",
        "24-test drawer Compose",
        "24 navigation-drawer",
        "three previously recorded project warnings",
    )
    failures: list[str] = []

    for path, current_section_start, next_section_start in documentation_targets:
        relative = str(path.relative_to(ROOT))
        try:
            document_text = (
                document_text_by_relative[relative]
                if (
                    document_text_by_relative is not None
                    and relative in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative}: cannot validate current Android drawer search "
                f"documentation: {error}"
            )
            continue

        start_count = document_text.count(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START
        )
        end_count = document_text.count(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_END
        )
        if (start_count, end_count) != (1, 1):
            failures.append(
                f"{relative}: current Android drawer search block must "
                f"contain exactly one start and end marker; found "
                f"{start_count} and {end_count}."
            )
            continue

        start_index = document_text.index(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START
        )
        body_start = start_index + len(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_START
        )
        end_index = document_text.index(
            CURRENT_ANDROID_DRAWER_SEARCH_DOCUMENT_END
        )
        if end_index <= body_start:
            failures.append(
                f"{relative}: current Android drawer search markers are "
                "reversed or empty."
            )
            continue
        current_section_index = document_text.find(current_section_start)
        next_section_index = document_text.find(
            next_section_start,
            max(current_section_index, 0) + len(current_section_start),
        )
        if not (
            current_section_index >= 0
            and next_section_index >= 0
            and current_section_index < start_index
            and end_index < next_section_index
        ):
            failures.append(
                f"{relative}: current Android drawer search block must remain "
                "inside its canonical current section."
            )

        block = document_text[body_start:end_index]
        normalized_block = re.sub(r"\s+", " ", block).strip()
        closed_block_remainder = normalized_block
        for claim in required_claims:
            normalized_claim = re.sub(r"\s+", " ", claim).strip()
            count = normalized_block.count(normalized_claim)
            if count != 1:
                failures.append(
                    f"{relative}: current Android drawer search block must "
                    f"contain exact claim {claim!r} once; found {count}."
                )
            else:
                closed_block_remainder = closed_block_remainder.replace(
                    normalized_claim,
                    "",
                    1,
                )
        boundary_match = re.search(
            r"This source/JVM/Compose evidence is not part of the immutable "
            r"Build 17 archive and (?:is|was) first source-bound by the "
            r"immutable Build 18 archive; (?:Build 19 retains it\. )?It does "
            r"not establish physical touch, TalkBack, provider, device, "
            r"network, installation, signing, or release behavior\.",
            normalized_block,
            re.IGNORECASE,
        )
        if boundary_match is None:
            failures.append(
                f"{relative}: current Android drawer search block is missing "
                "its Build 17/18/19 archive boundary."
            )
        else:
            closed_block_remainder = closed_block_remainder.replace(
                boundary_match.group(0),
                "",
                1,
            )

        closed_block_remainder = re.sub(
            r"-\s*(?:\[[ xX]\]\s*)?",
            " ",
            closed_block_remainder,
        ).strip()
        if closed_block_remainder:
            failures.append(
                f"{relative}: current Android drawer search block is closed "
                f"to additional claims; found {closed_block_remainder!r}."
            )

        for stale_marker in stale_current_markers:
            if stale_marker in normalized_block:
                failures.append(
                    f"{relative}: current Android drawer search block retains "
                    f"stale evidence marker {stale_marker!r}."
                )

        block_without_boundary = (
            normalized_block[: boundary_match.start()]
            + normalized_block[boundary_match.end() :]
            if boundary_match is not None
            else normalized_block
        )
        prohibited_positive_claims = (
            (
                r"\bphysical touch\b.{0,100}\b"
                r"(?:pass(?:es|ed)?|prov(?:e|es|ed|en)|"
                r"qualif(?:y|ies|ied|ication))\b"
            ),
            (
                r"\bTalkBack\b.{0,100}\b"
                r"(?:pass(?:es|ed)?|prov(?:e|es|ed|en)|"
                r"qualif(?:y|ies|ied|ication))\b"
            ),
            (
                r"\b(?:pass(?:es|ed)?|prov(?:e|es|ed|en)|"
                r"qualif(?:y|ies|ied|ication))\b.{0,100}\bTalkBack\b"
            ),
            r"\bpart of the immutable Build 17 archive\b",
            r"\bproduction[- ]ready\b",
        )
        if any(
            re.search(pattern, block_without_boundary, re.IGNORECASE)
            for pattern in prohibited_positive_claims
        ):
            failures.append(
                f"{relative}: current Android drawer search block contains "
                "a contradictory device, archive, or production claim."
            )

    return failures


def macos_packaged_lifecycle_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_PACKAGED_LIFECYCLE_RESULT,
        relative=(
            "dist/lifecycle/macos-packaged-app-build-10-lifecycle-v1.json"
        ),
        expected_size=MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE,
        expected_sha256=MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256,
        expected_result=MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT,
        build_label="Build 10",
        result_bytes=result_bytes,
    )


def historical_macos_packaged_lifecycle_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=HISTORICAL_MACOS_PACKAGED_LIFECYCLE_RESULT,
        relative=(
            "dist/lifecycle/macos-packaged-app-build-9-lifecycle-v1.json"
        ),
        expected_size=(
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SIZE
        ),
        expected_sha256=(
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT_SHA256
        ),
        expected_result=(
            HISTORICAL_MACOS_PACKAGED_LIFECYCLE_EXPECTED_RESULT
        ),
        build_label="Build 9",
        result_bytes=result_bytes,
    )


def macos_packaged_state_recovery_evidence_failures(
    result_bytes: bytes | None = None,
) -> list[str]:
    return packaged_lifecycle_evidence_failures(
        result_path=MACOS_PACKAGED_STATE_RECOVERY_RESULT,
        relative=(
            "dist/lifecycle/"
            "macos-packaged-app-build-13-state-recovery-v1.json"
        ),
        expected_size=MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SIZE,
        expected_sha256=(
            MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT_SHA256
        ),
        expected_result=MACOS_PACKAGED_STATE_RECOVERY_EXPECTED_RESULT,
        build_label="Build 13 state-recovery",
        result_bytes=result_bytes,
    )


def historical_build12_state_recovery_absence_failures(
    *,
    result_exists: bool | None = None,
) -> list[str]:
    exists = (
        HISTORICAL_BUILD12_STATE_RECOVERY_RESULT.exists()
        if result_exists is None
        else result_exists
    )
    if not exists:
        return []
    return [
        "dist/lifecycle/macos-packaged-app-build-12-state-recovery-v1.json: "
        "Build 12 failed closed and must not have a published state-recovery "
        "result."
    ]


def latest_progress_entry() -> tuple[int, str]:
    if not PROGRESS_DOC.is_file():
        return (0, "")

    lines = PROGRESS_DOC.read_text(encoding="utf-8", errors="replace").splitlines()
    implemented_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "## Implemented So Far"),
        -1,
    )
    if implemented_index < 0:
        return (0, "")

    start_index = next(
        (
            index
            for index in range(implemented_index + 1, len(lines))
            if lines[index].startswith("### ")
        ),
        -1,
    )
    if start_index < 0:
        return (0, "")

    end_index = next(
        (
            index
            for index in range(start_index + 1, len(lines))
            if lines[index].startswith("### ")
        ),
        len(lines),
    )
    return (start_index + 1, "\n".join(lines[start_index:end_index]))


def latest_qa_evidence_entry() -> tuple[int, str]:
    if not QA_EVIDENCE_DOC.is_file():
        return (0, "")

    lines = QA_EVIDENCE_DOC.read_text(encoding="utf-8", errors="replace").splitlines()
    current_rule_index = next(
        (index for index, line in enumerate(lines) if line.strip() == "## Current Rule"),
        -1,
    )
    if current_rule_index < 0:
        return (0, "")

    start_index = next(
        (
            index
            for index in range(current_rule_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        -1,
    )
    if start_index < 0:
        return (0, "")

    end_index = next(
        (
            index
            for index in range(start_index + 1, len(lines))
            if lines[index].startswith("## ")
        ),
        len(lines),
    )
    return (start_index + 1, "\n".join(lines[start_index:end_index]))


def latest_progress_evidence_failures() -> list[str]:
    failures: list[str] = []
    start_line, entry = latest_progress_entry()
    if not entry:
        return [
            "docs/progress.md: missing latest implemented progress entry under '## Implemented So Far'."
        ]

    required_patterns = (
        (
            re.compile(r"^### \d{4}-\d{2}-\d{2} .+", re.MULTILINE),
            "Latest progress entry must start with a dated implementation heading.",
        ),
        (
            re.compile(r"\bno-device\b", re.IGNORECASE),
            "Latest progress entry must state whether verification was no-device.",
        ),
        (
            re.compile(r"\bCaveat:", re.IGNORECASE),
            "Latest progress entry must include an explicit caveat.",
        ),
        (
            re.compile(r"\bphysical\b|\bcamera QR\b|\breal different-network\b", re.IGNORECASE),
            "Latest progress caveat must name physical or real-network coverage limits.",
        ),
        (
            re.compile(r"\bVerified after this change:", re.IGNORECASE),
            "Latest progress entry must list current verification commands.",
        ),
        (
            re.compile(r"`(?:swift|python3|JAVA_HOME=|git diff|bash)\b", re.IGNORECASE),
            "Latest progress entry must include concrete verification commands in backticks.",
        ),
    )

    for pattern, guidance in required_patterns:
        if not pattern.search(entry):
            failures.append(f"docs/progress.md:{start_line}: {guidance}")

    if "artifacts/" in entry and "device/runtime state" not in entry:
        failures.append(
            f"docs/progress.md:{start_line}: Progress entries that cite artifacts must explain the device/runtime state."
        )

    return failures


def latest_qa_evidence_failures() -> list[str]:
    failures: list[str] = []
    start_line, entry = latest_qa_evidence_entry()
    if not entry:
        return [
            "docs/qa-evidence.md: missing latest QA evidence entry after '## Current Rule'."
        ]

    required_patterns = (
        (
            re.compile(r"^## \d{4}-\d{2}-\d{2} .+", re.MULTILINE),
            "Latest QA evidence entry must start with a dated evidence heading.",
        ),
        (
            re.compile(r"\bproof-boundary\b|\bproof boundary\b", re.IGNORECASE),
            "Latest QA evidence entry must name the proof boundary.",
        ),
        (
            re.compile(r"\bno-device\b", re.IGNORECASE),
            "Latest QA evidence entry must state whether no-device evidence is involved.",
        ),
        (
            re.compile(r"\bphysical\b|\blive-provider\b|\blive provider\b", re.IGNORECASE),
            "Latest QA evidence entry must separate physical or live-provider proof from no-device evidence.",
        ),
        (
            re.compile(r"\bAgent state:.*\bGPT-5\.3-Codex-Spark was not used\b", re.IGNORECASE | re.DOTALL),
            "Latest QA evidence entry must record that GPT-5.3-Codex-Spark was not used.",
        ),
        (
            re.compile(r"\bCaveat:", re.IGNORECASE),
            "Latest QA evidence entry must include an explicit caveat.",
        ),
        (
            re.compile(r"\bVerification commands:", re.IGNORECASE),
            "Latest QA evidence entry must list verification commands.",
        ),
        (
            re.compile(r"`(?:swift|python3|JAVA_HOME=|git diff|bash|./script|script/)\b", re.IGNORECASE),
            "Latest QA evidence entry must include concrete verification commands in backticks.",
        ),
    )

    for pattern, guidance in required_patterns:
        if not pattern.search(entry):
            failures.append(f"docs/qa-evidence.md:{start_line}: {guidance}")

    if "artifacts/" in entry and "device/runtime state" not in entry:
        failures.append(
            f"docs/qa-evidence.md:{start_line}: QA entries that cite artifacts must explain the device/runtime state."
        )

    return failures


def syntax_only_no_device_gate_evidence_failures() -> list[str]:
    failures: list[str] = []
    syntax_command = "bash -n script/check_no_device_quality.sh"

    progress_start_line, progress_entry = latest_progress_entry()
    if syntax_command in progress_entry and "syntax only" not in progress_entry.lower():
        failures.append(
            f"docs/progress.md:{progress_start_line}: `{syntax_command}` is shell syntax validation only; "
            "label it as syntax only or record a real `bash script/check_no_device_quality.sh` run."
        )

    qa_path = ROOT / "docs/qa-evidence.md"
    if qa_path.exists():
        qa_lines = qa_path.read_text(encoding="utf-8", errors="replace").splitlines()
        for line_number, line in enumerate(qa_lines[:60], 1):
            if syntax_command in line and "syntax only" not in line.lower():
                failures.append(
                    f"docs/qa-evidence.md:{line_number}: `{syntax_command}` is shell syntax validation only; "
                    "label it as syntax only or record a real `bash script/check_no_device_quality.sh` run."
                )

    return failures


def historical_build16_reproducibility_failures(
    *,
    document_text: str | None = None,
    result_bytes_by_path: dict[str, bytes] | None = None,
) -> list[str]:
    relative_doc = HISTORICAL_BUILD16_DOC.relative_to(ROOT)
    if document_text is None:
        if not HISTORICAL_BUILD16_DOC.is_file():
            return [f"{relative_doc}: missing Build 16 historical record."]
        try:
            document_text = HISTORICAL_BUILD16_DOC.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative_doc}: unreadable Build 16 historical record: "
                f"{error}"
            ]

    failures: list[str] = []
    required_document_claims = (
        f"{HISTORICAL_BUILD16_ARCHIVE_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_ARCHIVE_SHA256}`",
        f"{HISTORICAL_BUILD16_RESULT_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_RESULT_SHA256}`",
        f"{HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256}`",
        f"{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE:,} bytes",
        f"`{HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256}`",
        "`publication=null`",
        "Build 17 does not retroactively qualify Build 16.",
    )
    for claim in required_document_claims:
        if claim not in document_text:
            failures.append(
                f"{relative_doc}: missing exact Build 16 history claim "
                f"{claim!r}."
            )

    result_specs = (
        (
            HISTORICAL_BUILD16_RESULT,
            HISTORICAL_BUILD16_RESULT_SIZE,
            HISTORICAL_BUILD16_RESULT_SHA256,
            "passed",
        ),
        (
            HISTORICAL_BUILD16_FAILED_ATTEMPT,
            HISTORICAL_BUILD16_FAILED_ATTEMPT_SIZE,
            HISTORICAL_BUILD16_FAILED_ATTEMPT_SHA256,
            "failed",
        ),
        (
            HISTORICAL_BUILD16_FAILED_CONFIRMATION,
            HISTORICAL_BUILD16_FAILED_CONFIRMATION_SIZE,
            HISTORICAL_BUILD16_FAILED_CONFIRMATION_SHA256,
            "failed",
        ),
    )
    expected_failed_member_paths = [
        "macos/AetherLink.app/Contents/MacOS/AetherLink",
        "macos/AetherLink.dSYM/Contents/Resources/DWARF/AetherLink",
        "macos/AetherLink.dSYM/Contents/Resources/Relocations/aarch64/AetherLink.yml",
        "manifest.json",
    ]
    expected_failure_categories = [
        "checksum",
        "manifest",
        "member-bytes",
        "member-metadata",
        "zip",
    ]
    for path, expected_size, expected_sha256, expected_status in result_specs:
        relative = path.relative_to(ROOT)
        if result_bytes_by_path is None:
            if not path.is_file():
                failures.append(
                    f"{relative}: missing Build 16 reproducibility result."
                )
                continue
            try:
                payload = path.read_bytes()
            except OSError as error:
                failures.append(
                    f"{relative}: unreadable Build 16 result: {error}"
                )
                continue
        else:
            payload = result_bytes_by_path.get(str(relative))
            if payload is None:
                failures.append(
                    f"{relative}: missing injected Build 16 result."
                )
                continue
        try:
            result = json.loads(
                payload.decode("utf-8"),
                object_pairs_hook=reject_duplicate_json_keys,
            )
        except (
            UnicodeError,
            json.JSONDecodeError,
            DuplicateJSONKeyError,
        ) as error:
            failures.append(f"{relative}: unreadable Build 16 result: {error}")
            continue
        identity = (len(payload), hashlib.sha256(payload).hexdigest())
        expected_identity = (expected_size, expected_sha256)
        if identity != expected_identity:
            failures.append(
                f"{relative}: expected identity {expected_identity!r}, "
                f"found {identity!r}."
            )
        if not isinstance(result, dict):
            failures.append(f"{relative}: result root must be an object.")
            continue
        if result.get("status") != expected_status:
            failures.append(
                f"{relative}: expected status={expected_status!r}, found "
                f"{result.get('status')!r}."
            )
        publication = result.get("publication")
        if expected_status == "passed":
            if (
                not isinstance(publication, dict)
                or publication.get("archiveSha256")
                != HISTORICAL_BUILD16_ARCHIVE_SHA256
            ):
                failures.append(
                    f"{relative}: successful Build 16 result must retain the "
                    "published archive identity."
                )
            continue
        if publication is not None:
            failures.append(
                f"{relative}: failed Build 16 result must retain publication=null."
            )
        comparison = result.get("comparison")
        if not isinstance(comparison, dict):
            failures.append(
                f"{relative}: failed Build 16 result must retain comparison."
            )
            continue
        member_differences = comparison.get("memberDifferences")
        actual_member_paths = (
            [
                item.get("path")
                for item in member_differences
                if isinstance(item, dict)
            ]
            if isinstance(member_differences, list)
            else None
        )
        if actual_member_paths != expected_failed_member_paths:
            failures.append(
                f"{relative}: expected failed member paths "
                f"{expected_failed_member_paths!r}, found "
                f"{actual_member_paths!r}."
            )
        if comparison.get("differences") != expected_failure_categories:
            failures.append(
                f"{relative}: expected failure categories "
                f"{expected_failure_categories!r}, found "
                f"{comparison.get('differences')!r}."
            )
    return failures


def historical_build17_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-17-local-v1.md"
    if document_text is None:
        path = ROOT / relative
        try:
            document_text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 17 history: "
                f"{error}"
            ]

    normalized_text = re.sub(r"\s+", " ", document_text).strip()
    required_once = (
        (
            "archive directory",
            f"`dist/releases/{HISTORICAL_BUILD17_RELEASE_ID}/`",
        ),
        (
            "canonical ZIP identity",
            (
                f"| Canonical ZIP | {HISTORICAL_BUILD17_ARCHIVE_SIZE:,} bytes | "
                f"`{HISTORICAL_BUILD17_ARCHIVE_SHA256}` |"
            ),
        ),
        (
            "manifest identity",
            (
                "| External/embedded manifest | "
                f"{HISTORICAL_BUILD17_MANIFEST_SIZE:,} bytes | "
                f"`{HISTORICAL_BUILD17_MANIFEST_SHA256}` |"
            ),
        ),
        (
            "source inventory identity",
            (
                "| Source inventory | "
                f"{HISTORICAL_BUILD17_SOURCE_INVENTORY_SIZE:,} bytes | "
                f"`{HISTORICAL_BUILD17_SOURCE_INVENTORY_SHA256}` |"
            ),
        ),
        (
            "source inventory duplicate identity",
            (
                f"- `source-files.json`: "
                f"{HISTORICAL_BUILD17_SOURCE_INVENTORY_SIZE:,} bytes, "
                f"`{HISTORICAL_BUILD17_SOURCE_INVENTORY_SHA256}`."
            ),
        ),
        (
            "source snapshot identity",
            (
                f"Its {HISTORICAL_BUILD17_SOURCE_FILE_COUNT}-file source "
                "inventory has snapshot digest "
                f"`{HISTORICAL_BUILD17_SOURCE_SNAPSHOT_SHA256}`."
            ),
        ),
        (
            "primary reproducibility identity",
            (
                "The first result is "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_PATH}`. "
                f"It is {HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SIZE:,} "
                "bytes with SHA-256 "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_RESULT_SHA256}`."
            ),
        ),
        (
            "reproducibility confirmation identity",
            (
                "The separate confirmation result is "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_PATH}`. "
                "It is "
                f"{HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SIZE:,} "
                "bytes with SHA-256 "
                f"`{HISTORICAL_BUILD17_REPRODUCIBILITY_CONFIRMATION_SHA256}`."
            ),
        ),
    )
    failures: list[str] = []
    for label, claim in required_once:
        normalized_claim = re.sub(r"\s+", " ", claim).strip()
        count = normalized_text.count(normalized_claim)
        if count != 1:
            failures.append(
                f"{relative}: immutable Build 17 {label} must appear exactly "
                f"once; found {count}."
            )

    start_count = document_text.count(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START
    )
    end_count = document_text.count(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_END
    )
    if (start_count, end_count) != (1, 1):
        failures.append(
            f"{relative}: historical Build 17 lifecycle block must contain "
            "exactly one distinct start and end marker; found "
            f"{start_count} and {end_count}."
        )
        return failures

    start_index = document_text.index(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START
    )
    body_start = start_index + len(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_START
    )
    end_index = document_text.index(
        HISTORICAL_BUILD17_LIFECYCLE_DOCUMENT_END
    )
    if end_index <= body_start:
        failures.append(
            f"{relative}: historical Build 17 lifecycle markers are reversed "
            "or empty."
        )
        return failures

    block = document_text[body_start:end_index]
    normalized_block = re.sub(r"\s+", " ", block).strip()
    lifecycle_claims = (
        (
            "installed-app result identity",
            (
                f"`{HISTORICAL_BUILD17_INSTALLED_APP_RESULT_PATH}`, "
                f"{HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SIZE:,} bytes with "
                "SHA-256 "
                f"`{HISTORICAL_BUILD17_INSTALLED_APP_RESULT_SHA256}`."
            ),
        ),
        (
            "state-recovery result identity",
            (
                f"`{HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_PATH}`, "
                f"{HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SIZE:,} bytes with "
                "SHA-256 "
                f"`{HISTORICAL_BUILD17_STATE_RECOVERY_RESULT_SHA256}`."
            ),
        ),
    )
    for label, claim in lifecycle_claims:
        count = normalized_block.count(claim)
        if count != 1:
            failures.append(
                f"{relative}: historical Build 17 lifecycle {label} must "
                f"appear exactly once inside its distinct block; found {count}."
            )
    if (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START in document_text
        or CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END in document_text
    ):
        failures.append(
            f"{relative}: current Build 20 lifecycle markers must not enter "
            "the immutable historical Build 17 record."
        )
    return failures


def historical_build18_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-18-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 18 history: "
                f"{error}"
            ]

    required_bindings = (
        HISTORICAL_BUILD18_RELEASE_ID,
        f"{HISTORICAL_BUILD18_ARCHIVE_SIZE:,} bytes",
        HISTORICAL_BUILD18_ARCHIVE_SHA256,
        f"{HISTORICAL_BUILD18_MANIFEST_SIZE:,} bytes",
        HISTORICAL_BUILD18_MANIFEST_SHA256,
        f"{HISTORICAL_BUILD18_CHECKSUM_SIZE:,} bytes",
        HISTORICAL_BUILD18_CHECKSUM_SHA256,
        f"{HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD18_REPRODUCIBILITY_RESULT_SHA256,
        (
            f"{HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SIZE:,} "
            "bytes"
        ),
        HISTORICAL_BUILD18_REPRODUCIBILITY_CONFIRMATION_SHA256,
        f"{HISTORICAL_BUILD18_SOURCE_FILE_COUNT}-file source inventory",
        HISTORICAL_BUILD18_SOURCE_SNAPSHOT_SHA256,
        HISTORICAL_BUILD18_SOURCE_OVERLAY_SHA256,
        f"{HISTORICAL_BUILD18_SOURCE_INVENTORY_SIZE:,} bytes",
        HISTORICAL_BUILD18_SOURCE_INVENTORY_SHA256,
        HISTORICAL_BUILD18_MACOS_UUID,
        HISTORICAL_BUILD18_INSTALLED_APP_RESULT_PATH,
        HISTORICAL_BUILD18_INSTALLED_APP_RESULT_SHA256,
        HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_PATH,
        HISTORICAL_BUILD18_STATE_RECOVERY_RESULT_SHA256,
    )
    failures = [
        f"{relative}: immutable Build 18 binding {binding!r} is missing."
        for binding in required_bindings
        if binding not in document_text
    ]
    if (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START in document_text
        or CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END in document_text
    ):
        failures.append(
            f"{relative}: current Build 20 lifecycle markers must not enter "
            "the immutable historical Build 18 record."
        )
    return failures


def historical_build19_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-19-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 19 history: "
                f"{error}"
            ]

    required_bindings = (
        "Build 19 is retained as an immutable historical qualification record.",
        "Run this historical source-bound readback with historical mode:",
        HISTORICAL_BUILD19_RELEASE_ID,
        f"{HISTORICAL_BUILD19_ARCHIVE_SIZE:,} bytes",
        HISTORICAL_BUILD19_ARCHIVE_SHA256,
        f"{HISTORICAL_BUILD19_MANIFEST_SIZE:,} bytes",
        HISTORICAL_BUILD19_MANIFEST_SHA256,
        f"{HISTORICAL_BUILD19_CHECKSUM_SIZE:,} bytes",
        HISTORICAL_BUILD19_CHECKSUM_SHA256,
        f"{HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD19_REPRODUCIBILITY_RESULT_SHA256,
        (
            f"{HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SIZE:,} "
            "bytes"
        ),
        HISTORICAL_BUILD19_REPRODUCIBILITY_CONFIRMATION_SHA256,
        f"{HISTORICAL_BUILD19_SOURCE_FILE_COUNT}-file source inventory",
        HISTORICAL_BUILD19_SOURCE_SNAPSHOT_SHA256,
        HISTORICAL_BUILD19_SOURCE_OVERLAY_SHA256,
        f"{HISTORICAL_BUILD19_SOURCE_INVENTORY_SIZE:,} bytes",
        HISTORICAL_BUILD19_SOURCE_INVENTORY_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-19-clean-home-install-v1.json"
        ),
        f"{HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD19_INSTALLED_APP_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-19-clean-home-state-recovery-v1.json"
        ),
        f"{HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD19_STATE_RECOVERY_RESULT_SHA256,
    )
    failures = [
        f"{relative}: immutable Build 19 binding {binding!r} is missing."
        for binding in required_bindings
        if binding not in document_text
    ]
    if (
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START in document_text
        or CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END in document_text
    ):
        failures.append(
            f"{relative}: current Build 20 lifecycle markers must not enter "
            "the immutable historical Build 19 record."
        )
    for stale_claim in (
        "Run the current source-bound readback without historical mode:",
        "carries current same-host, per-user macOS installed-lifecycle",
    ):
        if stale_claim in document_text:
            failures.append(
                f"{relative}: immutable Build 19 record contains stale "
                f"current-state claim {stale_claim!r}."
            )
    return failures


def historical_build20_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-20-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 20 history: "
                f"{error}"
            ]

    helper_size, helper_sha256 = (
        HISTORICAL_BUILD20_RUNTIME_CHAT_HELPER_IDENTITY
    )
    runner_size, runner_sha256 = (
        HISTORICAL_BUILD20_RUNTIME_CHAT_RUNNER_IDENTITY
    )
    test_size, test_sha256 = HISTORICAL_BUILD20_RUNTIME_CHAT_TEST_IDENTITY
    required_bindings = (
        "Build 20 is retained as an immutable historical qualification record.",
        "Run this historical source-bound readback with historical mode:",
        HISTORICAL_BUILD20_RELEASE_ID,
        f"{HISTORICAL_BUILD20_ARCHIVE_SIZE:,} bytes",
        HISTORICAL_BUILD20_ARCHIVE_SHA256,
        f"{HISTORICAL_BUILD20_MANIFEST_SIZE:,} bytes",
        HISTORICAL_BUILD20_MANIFEST_SHA256,
        f"{HISTORICAL_BUILD20_CHECKSUM_SIZE:,} bytes",
        HISTORICAL_BUILD20_CHECKSUM_SHA256,
        f"{HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SIZE:,} bytes",
        HISTORICAL_BUILD20_REPRODUCIBILITY_RESULT_SHA256,
        (
            f"{HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SIZE:,} "
            "bytes"
        ),
        HISTORICAL_BUILD20_REPRODUCIBILITY_PREPUBLICATION_SHA256,
        f"{HISTORICAL_BUILD20_SOURCE_FILE_COUNT}-file source inventory",
        HISTORICAL_BUILD20_SOURCE_SNAPSHOT_SHA256,
        HISTORICAL_BUILD20_SOURCE_OVERLAY_SHA256,
        HISTORICAL_BUILD20_PREPUBLICATION_SOURCE_OVERLAY_SHA256,
        f"{HISTORICAL_BUILD20_SOURCE_INVENTORY_SIZE:,} bytes",
        HISTORICAL_BUILD20_SOURCE_INVENTORY_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-install-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_APP_EXPECTED_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-clean-home-state-recovery-v1.json"
        ),
        CURRENT_MACOS_CLEAN_HOME_INSTALLED_STATE_RECOVERY_EXPECTED_RESULT_SHA256,
        (
            "dist/lifecycle/"
            "macos-packaged-app-build-20-local-dmg-install-v1.json"
        ),
        CURRENT_MACOS_LOCAL_DMG_INSTALL_EXPECTED_RESULT_SHA256,
        f"{helper_size:,} bytes",
        helper_sha256,
        f"{runner_size:,} bytes",
        runner_sha256,
        f"{test_size:,}-byte test source",
        test_sha256,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_START,
        CURRENT_MACOS_CLEAN_HOME_LIFECYCLE_DOCUMENT_END,
    )
    failures: list[str] = []
    document_sha256 = hashlib.sha256(
        document_text.encode("utf-8")
    ).hexdigest()
    if document_sha256 != HISTORICAL_BUILD20_RELEASE_DOCUMENT_SHA256:
        failures.append(
            f"{relative}: exact immutable document SHA-256 must remain "
            f"{HISTORICAL_BUILD20_RELEASE_DOCUMENT_SHA256}; found "
            f"{document_sha256}."
        )
    failures.extend(
        f"{relative}: immutable Build 20 binding {binding!r} is missing."
        for binding in required_bindings
        if binding not in document_text
    )
    for stale_claim in (
        "Build 20 is the current local qualification record.",
        "Run the current source-bound readback without historical mode:",
        "aetherlink-current-build20-lifecycle-v1",
    ):
        if stale_claim in document_text:
            failures.append(
                f"{relative}: immutable Build 20 record contains stale "
                f"current-state claim {stale_claim!r}."
            )
    build21_evidence_association = re.compile(
        r"\b(?:evidence|observation|lifecycle|DMG|"
        r"belong(?:s|ed)?|inherit(?:s|ed)?|"
        r"transfer(?:s|red|ring)?|relabel(?:s|ed|led)?|"
        r"reinterpret(?:s|ed)?|part of)\b",
        re.IGNORECASE,
    )
    explicit_negation = re.compile(
        r"\b(?:no|not|never|cannot|does not|do not|is not|are not)\b",
        re.IGNORECASE,
    )
    normalized_document = re.sub(r"\s+", " ", document_text).strip()
    for sentence in re.split(r"(?<=[.!?])\s+", normalized_document):
        if (
            re.search(r"\bBuild\s+21\b", sentence, re.IGNORECASE)
            and build21_evidence_association.search(sentence)
            and not explicit_negation.search(sentence)
        ):
            failures.append(
                f"{relative}: immutable Build 20 record contains an "
                "unnegated transfer or relabeling claim into Build 21."
            )
            break
    return failures


def historical_build21_release_document_failures(
    document_text: str | None = None,
) -> list[str]:
    relative = "docs/releases/1.0.0-build-21-local-v1.md"
    if document_text is None:
        try:
            document_text = (ROOT / relative).read_text(encoding="utf-8")
        except (OSError, UnicodeError) as error:
            return [
                f"{relative}: cannot validate immutable Build 21 history: "
                f"{error}"
            ]

    required_binding_counts = (
        (
            "Build 21 is an immutable historical local qualification record",
            1,
        ),
        (HISTORICAL_BUILD21_RELEASE_ID, 5),
        (f"{HISTORICAL_BUILD21_ARCHIVE_SIZE:,} bytes", 1),
        (f"{HISTORICAL_BUILD21_ARCHIVE_SIZE:,}-byte", 1),
        (HISTORICAL_BUILD21_ARCHIVE_SHA256, 2),
        (f"{HISTORICAL_BUILD21_MANIFEST_SIZE:,} bytes", 1),
        (f"{HISTORICAL_BUILD21_MANIFEST_SIZE:,}-byte", 1),
        (HISTORICAL_BUILD21_MANIFEST_SHA256, 1),
        (HISTORICAL_BUILD21_CHECKSUM_SHA256, 1),
        (
            "dist/reproducibility/"
            "aetherlink-1.0.0+21-local-v1-two-root-v3.json",
            1,
        ),
        (f"{HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SIZE:,} bytes", 1),
        (HISTORICAL_BUILD21_REPRODUCIBILITY_RESULT_SHA256, 1),
        (
            "dist/reproducibility/"
            "aetherlink-1.0.0+21-local-v1-two-root-v3-prepublication.json",
            1,
        ),
        (
            f"{HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SIZE:,} "
            "bytes",
            1,
        ),
        (HISTORICAL_BUILD21_REPRODUCIBILITY_PREPUBLICATION_SHA256, 1),
        (f"{HISTORICAL_BUILD21_SOURCE_FILE_COUNT}-file source inventory", 1),
        (HISTORICAL_BUILD21_SOURCE_SNAPSHOT_SHA256, 2),
        (f"{HISTORICAL_BUILD21_SOURCE_INVENTORY_SIZE:,} bytes", 2),
        (HISTORICAL_BUILD21_SOURCE_INVENTORY_SHA256, 2),
        (HISTORICAL_BUILD21_MACOS_UUID, 1),
        (
            "dist/lifecycle/"
            "macos-runtime-chat-sqlite-abrupt-process-recovery-build-21-v1.json",
            1,
        ),
        (CURRENT_RUNTIME_CHAT_SQLITE_ABRUPT_RESULT_SHA256, 1),
    )
    failures = [
        (
            f"{relative}: immutable Build 21 binding {binding!r} must appear "
            f"exactly {expected_count} time(s); found "
            f"{document_text.count(binding)}."
        )
        for binding, expected_count in required_binding_counts
        if document_text.count(binding) != expected_count
    ]
    for stale_claim in (
        "Build 21 is the current local qualification record",
        "The Build 21 archive is the latest ledger entry",
        "Build 21 is the latest immutable ledger archive",
        "Run the current source-bound readback without historical mode",
    ):
        if stale_claim in document_text:
            failures.append(
                f"{relative}: immutable Build 21 record contains stale "
                f"current-state claim {stale_claim!r}."
            )
    return failures


def historical_local_release_document_failures(
    *,
    ledger_bytes: bytes | None = None,
    document_text_by_build: dict[int, str] | None = None,
) -> list[str]:
    try:
        raw_ledger = (
            LOCAL_RELEASE_LEDGER.read_bytes()
            if ledger_bytes is None
            else ledger_bytes
        )
        entries = parse_release_version_ledger(raw_ledger)
    except (OSError, LedgerError) as error:
        return [
            "release/version-ledger.tsv: cannot validate historical release "
            f"document lineage: {error}"
        ]

    failures: list[str] = []
    for entry in entries[:-1]:
        relative = (
            "docs/releases/"
            f"{entry.marketing_version}-build-{entry.build_number}-local-v1.md"
        )
        if document_text_by_build is None:
            path = ROOT / relative
            if not path.is_file():
                failures.append(
                    f"{relative}: missing historical local release record."
                )
                continue
            try:
                document_text = path.read_text(encoding="utf-8")
            except (OSError, UnicodeError) as error:
                failures.append(
                    f"{relative}: unreadable historical local release "
                    f"record: {error}"
                )
                continue
        else:
            document_text = document_text_by_build.get(entry.build_number)
            if document_text is None:
                failures.append(
                    f"{relative}: missing injected historical release record."
                )
                continue

        release_id = (
            f"aetherlink-{entry.marketing_version}"
            f"+{entry.build_number}-local-v1"
        )
        expected_status = (
            "superseded local release-engineering candidate, "
            "not a production release."
        )
        status_claims = re.findall(
            r"^Status:\s*(.+?)\s*$",
            document_text,
            re.MULTILINE,
        )
        if status_claims != [expected_status]:
            failures.append(
                f"{relative}: historical status must appear exactly once as "
                f"{expected_status!r}; found {status_claims!r}."
            )
        release_id_claims = re.findall(
            r"^Release ID:\s*`?([^`\s]+)`?\s*$",
            document_text,
            re.MULTILINE,
        )
        if release_id_claims != [release_id]:
            failures.append(
                f"{relative}: historical Release ID must appear exactly once "
                f"as {release_id!r}; found {release_id_claims!r}."
            )
        readback_targets = re.findall(
            r"--archive-dir\s+dist/releases/(aetherlink-[^\s`\\]+)",
            document_text,
        )
        is_fixture_record = (
            entry.build_number == LOCAL_RELEASE_FIXTURE_BUILD_NUMBER
            and entry.marketing_version == LOCAL_RELEASE_MARKETING_VERSION
        )
        if is_fixture_record:
            fixture_command_count = document_text.count(
                LOCAL_RELEASE_FIXTURE_READBACK_COMMAND
            )
            if fixture_command_count != 2:
                failures.append(
                    f"{relative}: exact historical Build 3 readback command "
                    "must appear twice; found "
                    f"{fixture_command_count}."
                )
            if readback_targets.count(release_id) != 2:
                failures.append(
                    f"{relative}: historical archive readback target must "
                    f"include exactly two {release_id!r}; found "
                    f"{readback_targets!r}."
                )
        elif readback_targets != [release_id]:
            failures.append(
                f"{relative}: historical archive readback target must appear "
                f"exactly once as {release_id!r}; found "
                f"{readback_targets!r}."
            )
        historical_mode_count = len(
            re.findall(
                r"(?<![\w-])--historical(?![\w-])",
                document_text,
            )
        )
        if not is_fixture_record and historical_mode_count != 1:
            failures.append(
                f"{relative}: historical readback mode must appear exactly "
                f"once; found {historical_mode_count}."
            )
        if entry.build_number == HISTORICAL_BUILD17_BUILD_NUMBER:
            failures.extend(
                historical_build17_release_document_failures(document_text)
            )
        if entry.build_number == 18:
            failures.extend(
                historical_build18_release_document_failures(document_text)
            )
        if entry.build_number == 19:
            failures.extend(
                historical_build19_release_document_failures(document_text)
            )
        if entry.build_number == 20:
            failures.extend(
                historical_build20_release_document_failures(document_text)
            )
        if entry.build_number == 21:
            failures.extend(
                historical_build21_release_document_failures(document_text)
            )

    return failures


def readme_current_local_release_failures(
    *,
    ledger_bytes: bytes | None = None,
    readme_text: str | None = None,
) -> list[str]:
    try:
        entries = parse_release_version_ledger(
            LOCAL_RELEASE_LEDGER.read_bytes()
            if ledger_bytes is None
            else ledger_bytes
        )
    except (OSError, LedgerError) as error:
        return [
            "release/version-ledger.tsv: cannot validate README current "
            f"release lineage: {error}"
        ]
    try:
        document_text = (
            README_PATH.read_text(encoding="utf-8")
            if readme_text is None
            else readme_text
        )
    except (OSError, UnicodeError) as error:
        return [f"README.md: unreadable current release guidance: {error}"]

    current = entries[-1]
    current_release_id = (
        f"aetherlink-{current.marketing_version}"
        f"+{current.build_number}-local-v1"
    )
    current_doc = (
        "docs/releases/"
        f"{current.marketing_version}-build-"
        f"{current.build_number}-local-v1.md"
    )
    failures: list[str] = []

    ledger_claims = re.findall(
        r"`release/version-ledger\.tsv`; its current entry is marketing "
        r"version `([^`]+)`\s+and shared build number `([1-9][0-9]*)`\.",
        document_text,
    )
    expected_ledger_claim = [
        (current.marketing_version, str(current.build_number))
    ]
    if ledger_claims != expected_ledger_claim:
        failures.append(
            "README.md: current ledger claim must appear exactly once as "
            f"{expected_ledger_claim[0]!r}; found {ledger_claims!r}."
        )

    output_claims = re.findall(
        r"The current output is\s+"
        r"`dist/releases/(aetherlink-[^`/]+)/`\.",
        document_text,
    )
    if output_claims != [current_release_id]:
        failures.append(
            "README.md: current output must appear exactly once as "
            f"{current_release_id!r}; found {output_claims!r}."
        )

    qualification_claims = [
        int(value)
        for value in re.findall(
            r"\bThe Build ([1-9][0-9]*) qualification runner created "
            r"two isolated lane worktrees\b",
            document_text,
        )
    ]
    if qualification_claims != [current.build_number]:
        failures.append(
            "README.md: current qualification runner must name build "
            f"{current.build_number} exactly once; found "
            f"{qualification_claims!r}."
        )

    current_record_claims = re.findall(
        r"\[[^\]\n]*build ([1-9][0-9]*) local qualification record\]"
        r"\((docs/releases/[0-9]+\.[0-9]+\.[0-9]+-build-"
        r"[1-9][0-9]*-local-v1\.md)\)\s+defines the current release notes",
        document_text,
    )
    expected_record_claim = [(str(current.build_number), current_doc)]
    if current_record_claims != expected_record_claim:
        failures.append(
            "README.md: current release-record guidance must appear exactly "
            f"once as {expected_record_claim[0]!r}; found "
            f"{current_record_claims!r}."
        )

    historical_range_claims = [
        int(value)
        for value in re.findall(
            r"\bImmutable Builds 1 through ([1-9][0-9]*) remain "
            r"available for historical\s+readback\b",
            document_text,
        )
    ]
    expected_historical_upper = current.build_number - 1
    if historical_range_claims != [expected_historical_upper]:
        failures.append(
            "README.md: historical release range must end at build "
            f"{expected_historical_upper} exactly once; found "
            f"{historical_range_claims!r}."
        )

    current_section_start_markers = [
        match.start()
        for match in re.finditer(
            r"^The current output is$",
            document_text,
            re.MULTILINE,
        )
    ]
    current_section_end_markers = [
        match.start()
        for match in re.finditer(
            r"^Refresh public POM evidence only as an explicit maintenance "
            r"action with$",
            document_text,
            re.MULTILINE,
        )
    ]
    if (
        len(current_section_start_markers) != 1
        or len(current_section_end_markers) != 1
        or current_section_end_markers[0] <= current_section_start_markers[0]
    ):
        failures.append(
            "README.md: current local-release evidence section must have "
            "exactly one ordered output and compliance boundary."
        )
        current_section = ""
    else:
        current_section = document_text[
            current_section_start_markers[0]:
            current_section_end_markers[0]
        ]

    result_claims = re.findall(
        r"`dist/reproducibility/"
        rf"(aetherlink-[^`/]+-two-root-v"
        rf"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}\.json)`",
        current_section,
    )
    expected_result_claim = [
        f"{current_release_id}-two-root-v"
        f"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}.json"
    ]
    if result_claims != expected_result_claim:
        failures.append(
            "README.md: current reproducibility result must appear exactly "
            f"once as {expected_result_claim[0]!r}; found {result_claims!r}."
        )

    prepublication_claims = re.findall(
        r"`dist/reproducibility/"
        rf"(aetherlink-[^`/]+-two-root-v"
        rf"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}"
        r"-prepublication\.json)`",
        current_section,
    )
    expected_prepublication_claim = [
        f"{current_release_id}-two-root-v"
        f"{CURRENT_REPRODUCIBILITY_RESULT_PATH_VERSION}-prepublication.json"
    ]
    if prepublication_claims != expected_prepublication_claim:
        failures.append(
            "README.md: current reproducibility prepublication must appear "
            f"exactly once as {expected_prepublication_claim[0]!r}; found "
            f"{prepublication_claims!r}."
        )

    compliance_claims = [
        int(value)
        for value in re.findall(
            r"\bBuild ([1-9][0-9]*) preserves compliance profile\b",
            current_section,
        )
    ]
    if compliance_claims != [current.build_number]:
        failures.append(
            "README.md: current compliance profile must name build "
            f"{current.build_number} exactly once; found "
            f"{compliance_claims!r}."
        )
    return failures


def ollama_multilingual_full_matrix_v3_evidence_failures(
    *,
    document_text_by_relative: dict[str, str] | None = None,
) -> list[str]:
    try:
        if __package__:
            from script import (
                run_ollama_multilingual_semantic_matrix_v3 as runner,
            )
        else:
            import run_ollama_multilingual_semantic_matrix_v3 as runner

        result = runner.recorded_result()
        data = OLLAMA_MULTILINGUAL_FULL_MATRIX_V3_RESULT.read_bytes()
    except (OSError, UnicodeError, ValueError, RuntimeError) as error:
        return [
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            f"recorded V3 result was invalid: {error}"
        ]

    failures: list[str] = []
    if result.get("qualityGatePassed") is not False:
        failures.append(
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            "the recorded product-quality gate must remain false."
        )
    versions = result["versions"]
    summaries = [
        runner.projection_summary(version["observation"])
        for version in versions
    ]
    ranking_passed_values = {
        summary["rankingComparisonsPassed"]
        for summary in summaries
    }
    repeatability_passed_values = {
        summary["repeatabilityComparisonsPassed"]
        for summary in summaries
    }
    coordinate_sets = {
        tuple(
            (
                row["locale"],
                row["scenarioOrdinalWithinLocale"],
            )
            for row in version["observation"]["rankingFailures"]
        )
        for version in versions
    }
    if (
        len(ranking_passed_values) != 1
        or len(repeatability_passed_values) != 1
        or len(coordinate_sets) != 1
    ):
        failures.append(
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            "exact candidates must share one documentable comparison summary "
            "and ranking-failure coordinate set."
        )
        return failures
    ranking_passed = next(iter(ranking_passed_values))
    repeatability_passed = next(iter(repeatability_passed_values))
    ranking_total = runner.RANKING_COMPARISON_COUNT
    repeatability_total = runner.REPEATABILITY_COMPARISON_COUNT
    failure_coordinates = next(iter(coordinate_sets))
    locale_labels = {
        "en": "English",
        "ko": "Korean",
        "ja": "Japanese",
        "zh-CN": "Simplified Chinese",
        "fr": "French",
    }
    if any(locale not in locale_labels for locale, _ in failure_coordinates):
        failures.append(
            "docs/evidence/ollama-embedding-multilingual-full-matrix-v3.json: "
            "ranking-failure locale lacks a documentation label."
        )
        return failures
    recoveries_passed = all(
        version["recoveryPassed"] is True
        for version in versions
    )
    relative = (
        "docs/evidence/"
        "ollama-embedding-multilingual-full-matrix-v3.json"
    )
    raw_sha256 = hashlib.sha256(data).hexdigest()
    documentation_targets = (
        README_PATH,
        ROOT / "docs/roadmap.md",
        ROOT / "docs/handoff.md",
        ROOT / "docs/progress.md",
        ROOT / "docs/qa-evidence.md",
    )
    for path in documentation_targets:
        relative_path = str(path.relative_to(ROOT))
        try:
            text = (
                document_text_by_relative[relative_path]
                if (
                    document_text_by_relative is not None
                    and relative_path in document_text_by_relative
                )
                else path.read_text(encoding="utf-8")
            )
        except (OSError, UnicodeError) as error:
            failures.append(
                f"{relative_path}: cannot validate V3 evidence "
                f"guidance: {error}"
            )
            continue
        missing = [
            value
            for value in (relative, raw_sha256)
            if value not in text
        ]
        if missing:
            failures.append(
                f"{relative_path}: missing recorded V3 evidence "
                f"binding(s) {missing!r}."
            )
            continue

        anchor = text.index(raw_sha256)
        claim_window = re.sub(
            r"\s+",
            " ",
            text[max(0, anchor - 700):anchor + 700],
        )
        if not re.search(
            rf"\b{ranking_passed}(?:/| of ){ranking_total} "
            r"ranking\b",
            claim_window,
            re.IGNORECASE,
        ):
            failures.append(
                f"{relative_path}: V3 claim must report exactly "
                f"{ranking_passed}/{ranking_total} ranking comparisons."
            )
        if not re.search(
            rf"(?:\b{repeatability_passed}/"
            rf"{repeatability_total}\b|\ball "
            rf"{repeatability_passed}\b) repeatability\b",
            claim_window,
            re.IGNORECASE,
        ):
            failures.append(
                f"{relative_path}: V3 claim must report exactly "
                f"{repeatability_passed}/{repeatability_total} "
                "repeatability comparisons."
            )
        for locale, ordinal in failure_coordinates:
            label = locale_labels[locale]
            optional_shared_locale = (
                r"(?:\s+and\s+French)?"
                if locale == "ko" and ("fr", ordinal) in failure_coordinates
                else ""
            )
            if not re.search(
                rf"\b{re.escape(label)}\b"
                rf"{optional_shared_locale}\s+scenario ordinal {ordinal}\b",
                claim_window,
                re.IGNORECASE,
            ):
                failures.append(
                    f"{relative_path}: V3 claim must report the "
                    f"{label} scenario ordinal {ordinal} ranking failure."
                )
        recovery_pass_pattern = (
            r"(?:\bboth pass fresh-provider recover(?:y|ies)\b|"
            r"\bboth fresh-provider recover(?:y|ies)"
            r"(?: phases)? pass\b)"
        )
        if recoveries_passed and not re.search(
            recovery_pass_pattern,
            claim_window,
            re.IGNORECASE,
        ):
            failures.append(
                f"{relative_path}: V3 claim must report that both "
                "fresh-provider recoveries pass."
            )
    return failures


def physical_qr_observation_manifest_failures() -> list[str]:
    if not PHYSICAL_QR_OBSERVATION_MANIFEST.is_file():
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: missing sanitized physical QR observation manifest."
        ]

    def reject_duplicate_keys(pairs: list[tuple[str, object]]) -> dict[str, object]:
        result: dict[str, object] = {}
        for key, value in pairs:
            if key in result:
                raise DuplicateJSONKeyError(f"duplicate JSON key {key!r}")
            result[key] = value
        return result

    try:
        raw_text = PHYSICAL_QR_OBSERVATION_MANIFEST.read_text(encoding="utf-8")
        document = json.loads(raw_text, object_pairs_hook=reject_duplicate_keys)
    except (OSError, UnicodeError, json.JSONDecodeError, DuplicateJSONKeyError) as error:
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: unreadable or invalid JSON: "
            f"{error}"
        ]

    if not isinstance(document, dict):
        return [
            "docs/evidence/physical-qr-pairing-20260719.json: root must be a JSON object."
        ]

    failures: list[str] = []

    def read_path(path: tuple[str, ...]) -> object:
        value: object = document
        for key in path:
            if not isinstance(value, dict) or key not in value:
                return None
            value = value[key]
        return value

    allowed_keys_by_path = {
        (): {
            "documentType",
            "schemaVersion",
            "recordedDate",
            "source",
            "device",
            "topology",
            "qrObservation",
            "observedMilestones",
            "retention",
            "proofBoundary",
        },
        ("source",): {
            "repository",
            "branch",
            "headAtObservation",
            "worktreeDirty",
            "exactTreeDigestRetained",
            "laterSourceDelta",
        },
        ("device",): {
            "model",
            "operatingSystem",
            "apiLevel",
            "appBuildVariant",
            "deviceIdentifierRetained",
        },
        ("topology",): {
            "runtimeHost",
            "deviceAndRuntimeNetwork",
            "usbRouteUsedForOpticalClaim",
            "externalRelayUsed",
            "p2pNatTraversalUsed",
        },
        ("qrObservation",): {
            "captureSurface",
            "scanMethod",
            "uriInjectionUsed",
            "routeScope",
            "queryKeyCount",
            "listenerPortAtObservation",
            "endpointReusable",
            "payloadSha256",
            "fullPayloadRetained",
        },
        ("observedMilestones",): {
            "pairingQrSourceConnected",
            "pairingRequestSent",
            "pairingResultReceived",
            "helloSent",
            "authenticationChallengeReceived",
            "authenticationResponseCompleted",
            "runtimeHealthCompleted",
            "trustedDeviceReportedByMacos",
            "bonjourReconnectAfterForceStop",
            "storedTrustAuthenticationCompleted",
            "runtimeHealthAfterReconnect",
        },
        ("retention",): {
            "rawLogcatRetained",
            "screenCaptureRetainedInRepository",
            "completeQrVerifierOutputRetained",
            "apkDigestRetained",
            "sanitizedManifestRetained",
            "sensitiveMaterialIncluded",
        },
        ("proofBoundary",): {"proves", "doesNotProve"},
    }
    for path, allowed_keys in allowed_keys_by_path.items():
        value = read_path(path)
        if not isinstance(value, dict):
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: expected object at "
                f"{'.'.join(path) or '<root>'}."
            )
            continue
        actual_keys = set(value)
        if actual_keys != allowed_keys:
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: closed schema mismatch at "
                f"{'.'.join(path) or '<root>'}; missing={sorted(allowed_keys - actual_keys)}, "
                f"unexpected={sorted(actual_keys - allowed_keys)}."
            )

    forbidden_key_names = {
        "serial",
        "deviceserial",
        "fullpayload",
        "fullqrpayload",
        "fullqruri",
        "verifieroutput",
        "completeqrverifieroutput",
        "pairingcode",
        "pairingnonce",
        "nonce",
        "relaysecret",
        "allocationtoken",
        "routetoken",
        "privatekey",
        "identityprivatekey",
        "privateidentitymaterial",
        "devicecredential",
        "devicecredentials",
    }
    sensitive_string_patterns = (
        re.compile(r"\baetherlink\s*:\s*//\s*pair\b", re.IGNORECASE),
        re.compile(
            r"\b(?:pairing[\s_-]*(?:code|nonce)|nonce|secret|token|"
            r"relay[\s_-]*secret|allocation[\s_-]*token|route[\s_-]*token|"
            r"private[\s_-]*(?:key|identity))\b\s*[:=]",
            re.IGNORECASE,
        ),
    )

    def reject_sensitive_content(value: object, path: tuple[str, ...] = ()) -> None:
        if isinstance(value, dict):
            for key, child in value.items():
                normalized_key = re.sub(r"[^a-z0-9]", "", key.lower())
                if normalized_key in forbidden_key_names:
                    failures.append(
                        "docs/evidence/physical-qr-pairing-20260719.json: prohibited sensitive key "
                        f"{'.'.join(path + (key,))}."
                    )
                reject_sensitive_content(child, path + (key,))
        elif isinstance(value, list):
            for index, child in enumerate(value):
                reject_sensitive_content(child, path + (str(index),))
        elif isinstance(value, str) and any(
            pattern.search(value) for pattern in sensitive_string_patterns
        ):
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: prohibited credential-like string value at "
                f"{'.'.join(path) or '<root>'}."
            )

    reject_sensitive_content(document)

    expected_values = (
        (("documentType",), "aetherlink.physical-qr-pairing-observation"),
        (("schemaVersion",), 1),
        (("recordedDate",), "2026-07-19"),
        (("source", "repository"), "/Users/hanchangha/Desktop/project"),
        (("source", "branch"), "main"),
        (("source", "headAtObservation"), "df19c53a"),
        (("source", "worktreeDirty"), True),
        (("source", "exactTreeDigestRetained"), False),
        (("source", "laterSourceDelta"), "macos_ui_and_launcher_only_without_android_retest"),
        (("device", "model"), "SM-S936N"),
        (("device", "operatingSystem"), "Android 16"),
        (("device", "apiLevel"), 36),
        (("device", "appBuildVariant"), "debug"),
        (("device", "deviceIdentifierRetained"), False),
        (("topology", "runtimeHost"), "macos_development_app"),
        (("topology", "deviceAndRuntimeNetwork"), "same_wifi_lan"),
        (("topology", "usbRouteUsedForOpticalClaim"), False),
        (("topology", "externalRelayUsed"), False),
        (("topology", "p2pNatTraversalUsed"), False),
        (("qrObservation", "captureSurface"), "actual_macos_window_screen"),
        (("qrObservation", "scanMethod"), "physical_android_camera"),
        (("qrObservation", "uriInjectionUsed"), False),
        (("qrObservation", "routeScope"), "local_diagnostic"),
        (("qrObservation", "queryKeyCount"), 11),
        (("qrObservation", "listenerPortAtObservation"), 43170),
        (("qrObservation", "endpointReusable"), False),
        (("qrObservation", "payloadSha256"), "efc77b1402ed6270b741e5ee69bb30a7527ad563876f58eee31e7587ef9544ef"),
        (("qrObservation", "fullPayloadRetained"), False),
        (("observedMilestones", "pairingQrSourceConnected"), True),
        (("observedMilestones", "pairingRequestSent"), True),
        (("observedMilestones", "pairingResultReceived"), True),
        (("observedMilestones", "helloSent"), True),
        (("observedMilestones", "authenticationChallengeReceived"), True),
        (("observedMilestones", "authenticationResponseCompleted"), True),
        (("observedMilestones", "runtimeHealthCompleted"), True),
        (("observedMilestones", "trustedDeviceReportedByMacos"), True),
        (("observedMilestones", "bonjourReconnectAfterForceStop"), True),
        (("observedMilestones", "storedTrustAuthenticationCompleted"), True),
        (("observedMilestones", "runtimeHealthAfterReconnect"), True),
        (("retention", "rawLogcatRetained"), False),
        (("retention", "screenCaptureRetainedInRepository"), False),
        (("retention", "completeQrVerifierOutputRetained"), False),
        (("retention", "apkDigestRetained"), False),
        (("retention", "sanitizedManifestRetained"), True),
        (("retention", "sensitiveMaterialIncluded"), False),
        (("proofBoundary", "proves"), [
            "one_same_wifi_debug_optical_pairing",
            "challenge_response_and_runtime_health",
            "one_stored_trust_bonjour_reconnect",
        ]),
        (("proofBoundary", "doesNotProve"), [
            "release_apk_camera_pairing",
            "expired_or_rotated_qr_recovery",
            "camera_permission_recovery",
            "talkback_or_voiceover",
            "different_network_pairing",
            "external_relay_operation",
            "p2p_nat_or_phase_b",
            "production_capacity_reliability_or_readiness",
        ]),
    )
    for path, expected in expected_values:
        actual = read_path(path)
        if type(actual) is not type(expected) or actual != expected:
            failures.append(
                "docs/evidence/physical-qr-pairing-20260719.json: expected "
                f"{'.'.join(path)}={expected!r}, found {actual!r}."
            )

    payload_digest = read_path(("qrObservation", "payloadSha256"))
    if not isinstance(payload_digest, str) or re.fullmatch(r"[0-9a-f]{64}", payload_digest) is None:
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: qrObservation.payloadSha256 must be one lowercase SHA-256 digest."
        )

    if isinstance(payload_digest, str):
        for relative_path in ("docs/progress.md", "docs/qa-evidence.md"):
            path = ROOT / relative_path
            if payload_digest not in path.read_text(encoding="utf-8", errors="replace"):
                failures.append(
                    f"{relative_path}: physical QR payload digest must match the sanitized observation manifest."
                )

    nonclaims = read_path(("proofBoundary", "doesNotProve"))
    required_nonclaims = {
        "release_apk_camera_pairing",
        "different_network_pairing",
        "external_relay_operation",
        "p2p_nat_or_phase_b",
        "production_capacity_reliability_or_readiness",
    }
    if not isinstance(nonclaims, list) or not required_nonclaims.issubset(
        {value for value in nonclaims if isinstance(value, str)}
    ):
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: proofBoundary.doesNotProve must retain release, different-network, relay, P2P/Phase B, and production limits."
        )

    if re.search(r"\baetherlink\s*:\s*(?:\\?/){2}\s*pair\b", raw_text, re.IGNORECASE):
        failures.append(
            "docs/evidence/physical-qr-pairing-20260719.json: full credential-bearing QR URI must not be retained."
        )

    return failures


def main() -> int:
    failures: list[str] = []

    for path in target_files():
        relative = path.relative_to(ROOT)
        for line_number, line in enumerate(path.read_text(encoding="utf-8", errors="replace").splitlines(), 1):
            for rule in RULES:
                if rule.pattern.search(line):
                    failures.append(f"{relative}:{line_number}: {rule.name}: {rule.guidance}")

    docs_text = contract_text()
    for contract in CONTRACTS:
        missing = [
            pattern.pattern
            for pattern in contract.required_patterns
            if not pattern.search(docs_text)
        ]
        if missing:
            failures.append(
                f"documentation-contract:{contract.name}: {contract.guidance} "
                f"Missing pattern(s): {', '.join(missing)}"
            )

    for contract in FILE_CONTRACTS:
        target_text = file_contract_text(contract.target)
        if not target_text:
            failures.append(
                f"documentation-file-contract:{contract.name}: Missing target file {contract.target}. "
                f"{contract.guidance}"
            )
            continue
        missing = [
            pattern.pattern
            for pattern in contract.required_patterns
            if not pattern.search(target_text)
        ]
        if missing:
            failures.append(
                f"documentation-file-contract:{contract.name}: {contract.guidance} "
                f"Missing pattern(s): {', '.join(missing)}"
            )

    failures.extend(latest_progress_evidence_failures())
    failures.extend(latest_qa_evidence_failures())
    failures.extend(current_release_qa_evidence_failures())
    failures.extend(current_release_summary_document_failures())
    failures.extend(release_readback_command_mode_failures())
    failures.extend(syntax_only_no_device_gate_evidence_failures())
    failures.extend(current_handoff_git_attribution_failures())
    failures.extend(local_release_document_failures())
    failures.extend(macos_clean_home_installed_app_source_failures())
    failures.extend(
        macos_clean_home_installed_state_recovery_source_failures()
    )
    failures.extend(macos_packaged_lifecycle_source_failures())
    failures.extend(macos_packaged_state_recovery_source_failures())
    failures.extend(
        current_macos_clean_home_installed_app_evidence_failures()
    )
    failures.extend(
        current_macos_clean_home_installed_state_recovery_evidence_failures()
    )
    failures.extend(current_macos_local_dmg_install_evidence_failures())
    failures.extend(
        current_runtime_chat_sqlite_cross_process_document_failures()
    )
    failures.extend(
        current_runtime_chat_sqlite_abrupt_recovery_document_failures()
    )
    failures.extend(current_runtime_chat_sqlite_source_failures())
    failures.extend(
        current_runtime_chat_sqlite_abrupt_recovery_evidence_failures()
    )
    failures.extend(current_macos_clean_home_lifecycle_document_failures())
    failures.extend(current_android_drawer_search_document_failures())
    failures.extend(macos_clean_home_installed_app_evidence_failures())
    failures.extend(
        macos_clean_home_installed_state_recovery_evidence_failures()
    )
    failures.extend(macos_packaged_lifecycle_evidence_failures())
    failures.extend(
        historical_macos_packaged_lifecycle_evidence_failures()
    )
    failures.extend(macos_packaged_state_recovery_evidence_failures())
    failures.extend(
        historical_build12_state_recovery_absence_failures()
    )
    failures.extend(historical_build16_reproducibility_failures())
    failures.extend(historical_local_release_document_failures())
    failures.extend(readme_current_local_release_failures())
    failures.extend(ollama_multilingual_full_matrix_v3_evidence_failures())
    failures.extend(physical_qr_observation_manifest_failures())

    if failures:
        print("Docs hygiene check failed:", file=sys.stderr)
        for failure in failures:
            print(f" - {failure}", file=sys.stderr)
        return 1

    print(f"Docs hygiene OK across {len(target_files())} current documentation file(s).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
