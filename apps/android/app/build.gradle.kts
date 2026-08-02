import java.io.File

plugins {
    alias(libs.plugins.android.application)
    alias(libs.plugins.kotlin.compose)
    alias(libs.plugins.kotlin.serialization)
}

data class ReleaseVersion(
    val buildNumber: Int,
    val marketingVersion: String,
    val semanticVersion: List<Int>,
)

fun loadReleaseVersionLedger(file: File): ReleaseVersion {
    require(file.isFile) { "Release version ledger not found: $file" }
    val raw = file.readBytes()
    require(raw.isNotEmpty() && raw.last() == '\n'.code.toByte()) {
        "Release version ledger must end with one LF"
    }
    require(
        raw.all { byte ->
            val value = byte.toInt() and 0xff
            value == '\t'.code ||
                value == '\n'.code ||
                value in 0x20..0x7e
        },
    ) {
        "Release version ledger may contain only printable ASCII, tab, and LF"
    }
    val text = raw.toString(Charsets.US_ASCII)
    require(text.toByteArray(Charsets.US_ASCII).contentEquals(raw)) {
        "Release version ledger must be ASCII"
    }

    val lines = text.split('\n').dropLast(1)
    require(lines.firstOrNull() == "build_number\tmarketing_version") {
        "Release version ledger header is invalid"
    }
    require(lines.size >= 2) { "Release version ledger has no entries" }

    val buildNumberPattern = Regex("[1-9][0-9]*")
    val marketingVersionPattern =
        Regex("(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)\\.(0|[1-9][0-9]*)")
    var current: ReleaseVersion? = null
    for ((entryIndex, line) in lines.drop(1).withIndex()) {
        val lineNumber = entryIndex + 2
        val fields = line.split('\t')
        require(fields.size == 2 && fields.none(String::isEmpty)) {
            "Release version ledger line $lineNumber must have exactly two fields"
        }

        val buildNumberText = fields[0]
        require(buildNumberPattern.matches(buildNumberText)) {
            "Release version ledger line $lineNumber has an invalid build number"
        }
        val buildNumber = buildNumberText.toIntOrNull()
        require(buildNumber != null && buildNumber <= 2_100_000_000) {
            "Release version ledger line $lineNumber exceeds the Android versionCode limit"
        }

        val marketingVersion = fields[1]
        val versionMatch = marketingVersionPattern.matchEntire(marketingVersion)
        require(versionMatch != null) {
            "Release version ledger line $lineNumber has an invalid marketing version"
        }
        val semanticVersion = versionMatch.groupValues.drop(1).map { component ->
            requireNotNull(component.toIntOrNull()) {
                "Release version ledger line $lineNumber has an oversized marketing version"
            }
        }

        current?.let { previous ->
            require(buildNumber > previous.buildNumber) {
                "Release version ledger build numbers must be strictly increasing"
            }
            require(
                semanticVersion[0] > previous.semanticVersion[0] ||
                    (
                        semanticVersion[0] == previous.semanticVersion[0] &&
                            (
                                semanticVersion[1] > previous.semanticVersion[1] ||
                                    (
                                        semanticVersion[1] == previous.semanticVersion[1] &&
                                            semanticVersion[2] >= previous.semanticVersion[2]
                                    )
                            )
                    )
            ) {
                "Release version ledger marketing versions must not decrease"
            }
        }
        current = ReleaseVersion(buildNumber, marketingVersion, semanticVersion)
    }
    return requireNotNull(current)
}

val releaseVersionProvider = providers.provider {
    loadReleaseVersionLedger(rootProject.file("release/version-ledger.tsv"))
}

android {
    namespace = "com.localagentbridge.android"
    compileSdk = 36

    defaultConfig {
        applicationId = "com.localagentbridge.android"
        minSdk = 26
        targetSdk = 36
        versionCode = 1
        versionName = "0.1.0"
    }

    buildFeatures {
        buildConfig = true
    }

    bundle {
        language {
            enableSplit = false
        }
    }

    buildTypes {
        release {
            isMinifyEnabled = true
            isShrinkResources = true
            ndk {
                abiFilters += "arm64-v8a"
                debugSymbolLevel = "SYMBOL_TABLE"
            }
            proguardFiles(
                getDefaultProguardFile("proguard-android-optimize.txt"),
            )
        }
    }

    lint {
        // V1 stays on the fully qualified API 36/AGP 9.2 dependency set.
        // Availability notices are reviewed during a separate toolchain
        // upgrade; every other Release warning is a build failure.
        warningsAsErrors = true
        disable += setOf(
            "AndroidGradlePluginVersion",
            "GradleDependency",
            "NewerVersionAvailable",
            "OldTargetApi",
        )
        // V1 ships only Android arm64-v8a; ChromeOS/x86_64 is outside the
        // declared support matrix.
        disable += "ChromeOsAbiSupport"
    }

    testOptions {
        unitTests.isReturnDefaultValues = true
        unitTests.isIncludeAndroidResources = true
    }
}

androidComponents {
    onVariants(selector().withBuildType("release")) { variant ->
        variant.outputs.forEach { output ->
            output.versionCode.set(releaseVersionProvider.map { it.buildNumber })
            output.versionName.set(releaseVersionProvider.map { it.marketingVersion })
        }
    }
}

dependencies {
    implementation(project(":core:protocol"))
    implementation(project(":core:transport"))
    implementation(project(":core:pairing"))

    implementation(libs.androidx.activity.compose)
    implementation(libs.androidx.camera.camera2)
    implementation(libs.androidx.camera.core)
    implementation(libs.androidx.camera.lifecycle)
    implementation(libs.androidx.camera.view)
    implementation(platform(libs.androidx.compose.bom))
    implementation(libs.androidx.compose.foundation)
    implementation(libs.androidx.compose.material.icons)
    implementation(libs.androidx.compose.material3)
    implementation(libs.androidx.compose.ui)
    implementation(libs.androidx.compose.ui.tooling.preview)
    implementation(libs.androidx.core.ktx)
    implementation(libs.androidx.lifecycle.runtime.compose)
    implementation(libs.androidx.lifecycle.viewmodel.compose)
    implementation(libs.androidx.lifecycle.viewmodel.ktx)
    implementation(libs.google.mlkit.barcode.scanning)
    implementation(libs.kotlinx.coroutines.android)
    implementation(libs.kotlinx.serialization.json)
    debugImplementation(libs.androidx.compose.ui.tooling)

    testImplementation(platform(libs.androidx.compose.bom))
    testImplementation(libs.androidx.compose.ui.test.junit4)
    testImplementation(libs.androidx.test.core)
    testImplementation(libs.androidx.test.ext.junit)
    testImplementation(libs.junit)
    testImplementation(libs.kotlinx.coroutines.test)
    testImplementation(libs.robolectric)
    debugImplementation(libs.androidx.compose.ui.test.manifest)
}
