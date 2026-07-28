buildscript {
    configurations.classpath {
        resolutionStrategy.activateDependencyLocking()
    }
}

plugins {
    alias(libs.plugins.android.application) apply false
    alias(libs.plugins.android.library) apply false
    alias(libs.plugins.kotlin.serialization) apply false
    alias(libs.plugins.kotlin.compose) apply false
}

val strictReleaseDependencyLocks = providers
    .gradleProperty("aetherlinkStrictReleaseDependencyLocks")
    .map { value ->
        require(value == "true" || value == "false") {
            "aetherlinkStrictReleaseDependencyLocks must be true or false"
        }
        value == "true"
    }
    .orElse(false)

allprojects {
    dependencyLocking {
        lockAllConfigurations()
        ignoredDependencies.add(
            "org.jetbrains.kotlin:kotlin-stdlib-common"
        )
        if (strictReleaseDependencyLocks.get()) {
            lockMode.set(LockMode.STRICT)
        }
    }
}

if (
    strictReleaseDependencyLocks.get() &&
    !gradle.startParameter.isWriteDependencyLocks
) {
    listOf(
        "buildscript-gradle.lockfile",
        "settings-gradle.lockfile",
    ).forEach { relative ->
        require(file(relative).isFile) {
            "Strict Release requires $relative"
        }
    }
}

tasks.register("printBundletoolRuntimeClasspath") {
    description = "Prints the AGP-pinned bundletool runtime classpath."
    group = "help"

    doLast {
        println(
            "AETHERLINK_BUNDLETOOL_CLASSPATH=" +
                buildscript.configurations
                    .getByName("classpath")
                    .asPath
        )
    }
}
