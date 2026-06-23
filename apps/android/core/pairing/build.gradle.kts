plugins {
    alias(libs.plugins.android.library)
}

android {
    namespace = "com.localagentbridge.android.core.pairing"
    compileSdk = 36

    defaultConfig {
        minSdk = 26
    }
}

dependencies {
    implementation(libs.androidx.datastore.preferences)
    implementation(libs.kotlinx.coroutines.android)

    testImplementation(libs.junit)
}
