plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "com.localagentbridge.android.core.transport"
    compileSdk = 36

    defaultConfig {
        minSdk = 26
    }
}

dependencies {
    implementation(project(":core:protocol"))
    implementation(libs.androidx.core.ktx)
    implementation(libs.kotlinx.coroutines.android)
}
