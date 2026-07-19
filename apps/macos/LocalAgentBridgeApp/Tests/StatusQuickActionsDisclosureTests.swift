import XCTest
@testable import LocalAgentBridge

final class StatusQuickActionsDisclosureTests: XCTestCase {
    func testInitialAndToggleStateContract() {
        XCTAssertFalse(quickActionsDisclosureInitialState())
        XCTAssertTrue(quickActionsDisclosureStateAfterToggle(isExpanded: false))
        XCTAssertFalse(quickActionsDisclosureStateAfterToggle(isExpanded: true))
    }

    func testAccessibilityCopyUsesSelectedLanguageAndCurrentState() {
        let expectations: [(
            languageTag: String,
            label: String,
            expanded: String,
            collapsed: String,
            expandHint: String,
            collapseHint: String
        )] = [
            (
                "en",
                "Quick Actions",
                "Quick Actions expanded",
                "Quick Actions collapsed",
                "Expand to show maintenance and inspection actions.",
                "Collapse to hide maintenance and inspection actions."
            ),
            (
                "ko",
                "빠른 작업",
                "빠른 작업 펼쳐짐",
                "빠른 작업 접힘",
                "유지 관리 및 검사 작업을 표시하려면 펼치세요.",
                "유지 관리 및 검사 작업을 숨기려면 접으세요."
            ),
            (
                "ja",
                "クイックアクション",
                "クイックアクションは展開済み",
                "クイックアクションは折りたたみ済み",
                "展開してメンテナンスと検査のアクションを表示します。",
                "折りたたんでメンテナンスと検査のアクションを非表示にします。"
            ),
            (
                "zh-Hans",
                "快速操作",
                "快速操作已展开",
                "快速操作已折叠",
                "展开以显示维护和检查操作。",
                "折叠以隐藏维护和检查操作。"
            ),
            (
                "fr",
                "Actions rapides",
                "Actions rapides développées",
                "Actions rapides réduites",
                "Développer pour afficher les actions de maintenance et d’inspection.",
                "Réduire pour masquer les actions de maintenance et d’inspection."
            ),
        ]

        XCTAssertEqual(expectations.map(\.languageTag), AetherLinkAppLanguage.allCases.map(\.rawValue))
        for expectation in expectations {
            withStoredAppLanguage(expectation.languageTag) {
                XCTAssertEqual(quickActionsDisclosureAccessibilityLabel(), expectation.label)
                XCTAssertEqual(
                    quickActionsDisclosureAccessibilityValue(isExpanded: true),
                    expectation.expanded
                )
                XCTAssertEqual(
                    quickActionsDisclosureAccessibilityValue(isExpanded: false),
                    expectation.collapsed
                )
                XCTAssertEqual(
                    quickActionsDisclosureAccessibilityHint(isExpanded: false),
                    expectation.expandHint
                )
                XCTAssertEqual(
                    quickActionsDisclosureAccessibilityHint(isExpanded: true),
                    expectation.collapseHint
                )
            }
        }
    }

    private func withStoredAppLanguage(_ languageTag: String, assertions: () -> Void) {
        let previous = UserDefaults.standard.string(forKey: AetherLinkAppLanguageStorageKey)
        UserDefaults.standard.set(languageTag, forKey: AetherLinkAppLanguageStorageKey)
        defer {
            if let previous {
                UserDefaults.standard.set(previous, forKey: AetherLinkAppLanguageStorageKey)
            } else {
                UserDefaults.standard.removeObject(forKey: AetherLinkAppLanguageStorageKey)
            }
        }
        assertions()
    }
}
