pluginManagement {
    repositories {
        google()
        mavenCentral()
        gradlePluginPortal()
    }
}

dependencyResolutionManagement {
    repositoriesMode.set(RepositoriesMode.FAIL_ON_PROJECT_REPOS)
    repositories {
        google()
        mavenCentral()
    }
}

rootProject.name = "AetherLink"

include(":app")
project(":app").projectDir = file("apps/android/app")

include(":core:protocol")
project(":core").projectDir = file("apps/android/core")
project(":core:protocol").projectDir = file("apps/android/core/protocol")

include(":core:transport")
project(":core:transport").projectDir = file("apps/android/core/transport")

include(":core:pairing")
project(":core:pairing").projectDir = file("apps/android/core/pairing")
