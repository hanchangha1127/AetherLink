package com.localagentbridge.android

import java.io.File
import java.io.StringReader
import javax.xml.parsers.DocumentBuilderFactory
import org.junit.Assert.fail
import org.junit.Test
import org.w3c.dom.Document
import org.w3c.dom.Element
import org.xml.sax.InputSource

class AndroidBackupPolicyResourceTest {
    @Test
    fun manifestBindsBothBackupRuleGenerationsWithBackupDisabled() {
        validateManifestPolicy(repositoryFile(MANIFEST_PATH).readText())
    }

    @Test
    fun legacyBackupRulesExcludeEverySupportedDomain() {
        validateLegacyRules(repositoryFile(LEGACY_RULES_PATH).readText())
    }

    @Test
    fun currentExtractionRulesExcludeCloudAndDeviceTransferDomains() {
        validateCurrentRules(repositoryFile(CURRENT_RULES_PATH).readText())
    }

    @Test
    fun manifestPolicyRejectsMissingOrDriftingAttributes() {
        val source = repositoryFile(MANIFEST_PATH).readText()
        val invalid = listOf(
            source.replaceFirst(
                "android:allowBackup=\"false\"",
                "android:allowBackup=\"true\"",
            ),
            source.replaceFirst(
                "        android:fullBackupContent=\"@xml/backup_rules\"\n",
                "",
            ),
            source.replaceFirst(
                "@xml/data_extraction_rules",
                "@xml/other_data_extraction_rules",
            ),
            source.replaceFirst(
                "</manifest>",
                "<application android:allowBackup=\"false\" />\n</manifest>",
            ),
        )

        invalid.forEach(::assertManifestRejected)
    }

    @Test
    fun legacyRulesRejectMissingDuplicateIncludeAndWrongPath() {
        val source = repositoryFile(LEGACY_RULES_PATH).readText()
        val invalid = listOf(
            source.replaceFirst(
                "    <exclude domain=\"external\" path=\".\" />\n",
                "",
            ),
            source.replaceFirst(
                "</full-backup-content>",
                "    <exclude domain=\"root\" path=\".\" />\n" +
                    "</full-backup-content>",
            ),
            source.replaceFirst("<exclude ", "<include "),
            source.replaceFirst("path=\".\"", "path=\"files\""),
        )

        invalid.forEach { document ->
            assertRejected { validateLegacyRules(document) }
        }
    }

    @Test
    fun currentRulesRejectMissingDuplicateIncludeWrongPathAndSection() {
        val source = repositoryFile(CURRENT_RULES_PATH).readText()
        val invalid = listOf(
            source.replaceFirst(
                "        <exclude domain=\"device_sharedpref\" path=\".\" />\n",
                "",
            ),
            source.replaceFirst(
                "    </device-transfer>",
                "        <exclude domain=\"root\" path=\".\" />\n" +
                    "    </device-transfer>",
            ),
            source.replaceFirst("<exclude ", "<include "),
            source.replaceFirst("path=\".\"", "path=\"files\""),
            source.replaceFirst(
                "    <device-transfer>\n",
                "",
            ).replaceFirst(
                "    </device-transfer>\n",
                "",
            ),
        )

        invalid.forEach { document ->
            assertRejected { validateCurrentRules(document) }
        }
    }

    private fun assertManifestRejected(source: String) {
        assertRejected { validateManifestPolicy(source) }
    }

    private fun assertRejected(block: () -> Unit) {
        try {
            block()
            fail("mutated backup policy was accepted")
        } catch (_: IllegalArgumentException) {
            // Expected: every mutation must fail the exact local policy.
        }
    }

    private fun validateManifestPolicy(source: String) {
        val root = parseXml(source).documentElement
        require(root.tagName == "manifest")
        val applications = root.directChildren().filter {
            it.tagName == "application"
        }
        require(applications.size == 1)
        val application = applications.single()
        require(
            application.getAttributeNS(ANDROID_NAMESPACE, "allowBackup") ==
                "false",
        )
        require(
            application.getAttributeNS(
                ANDROID_NAMESPACE,
                "fullBackupContent",
            ) == "@xml/backup_rules",
        )
        require(
            application.getAttributeNS(
                ANDROID_NAMESPACE,
                "dataExtractionRules",
            ) == "@xml/data_extraction_rules",
        )
    }

    private fun validateLegacyRules(source: String) {
        val root = parseXml(source).documentElement
        require(root.tagName == "full-backup-content")
        require(root.attributes.length == 0)
        validateExclusions(root, LEGACY_DOMAINS)
    }

    private fun validateCurrentRules(source: String) {
        val root = parseXml(source).documentElement
        require(root.tagName == "data-extraction-rules")
        require(root.attributes.length == 0)
        val sections = root.directChildren()
        require(
            sections.map(Element::getTagName) ==
                listOf("cloud-backup", "device-transfer"),
        )
        sections.forEach { section ->
            require(section.attributes.length == 0)
            validateExclusions(section, CURRENT_DOMAINS)
        }
    }

    private fun validateExclusions(
        parent: Element,
        expectedDomains: Set<String>,
    ) {
        val rules = parent.directChildren()
        require(rules.size == expectedDomains.size)
        val domains = rules.map { rule ->
            require(rule.tagName == "exclude")
            require(rule.attributes.length == 2)
            require(rule.getAttribute("path") == ".")
            val domain = rule.getAttribute("domain")
            require(domain in expectedDomains)
            domain
        }
        require(domains.toSet() == expectedDomains)
        require(domains.size == domains.toSet().size)
    }

    private fun parseXml(source: String): Document {
        try {
            val factory = DocumentBuilderFactory.newInstance()
            factory.isNamespaceAware = true
            factory.isXIncludeAware = false
            factory.setFeature(
                "http://apache.org/xml/features/disallow-doctype-decl",
                true,
            )
            return factory.newDocumentBuilder().parse(
                InputSource(StringReader(source)),
            )
        } catch (error: Exception) {
            throw IllegalArgumentException("invalid backup policy XML", error)
        }
    }

    private fun Element.directChildren(): List<Element> =
        (0 until childNodes.length).mapNotNull { index ->
            childNodes.item(index) as? Element
        }

    private fun repositoryFile(relative: String): File {
        val start = File(System.getProperty("user.dir") ?: ".").canonicalFile
        return generateSequence(start) { current -> current.parentFile }
            .map { root -> File(root, relative) }
            .firstOrNull(File::isFile)
            ?: error("repository file not found: $relative")
    }

    private companion object {
        const val ANDROID_NAMESPACE =
            "http://schemas.android.com/apk/res/android"
        const val MANIFEST_PATH =
            "apps/android/app/src/main/AndroidManifest.xml"
        const val LEGACY_RULES_PATH =
            "apps/android/app/src/main/res/xml/backup_rules.xml"
        const val CURRENT_RULES_PATH =
            "apps/android/app/src/main/res/xml/data_extraction_rules.xml"

        val LEGACY_DOMAINS = setOf(
            "root",
            "file",
            "database",
            "sharedpref",
            "external",
        )
        val CURRENT_DOMAINS = LEGACY_DOMAINS + setOf(
            "device_root",
            "device_file",
            "device_database",
            "device_sharedpref",
        )
    }
}
