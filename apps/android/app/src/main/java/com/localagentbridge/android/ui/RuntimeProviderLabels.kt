package com.localagentbridge.android.ui

import androidx.compose.runtime.Composable
import androidx.compose.ui.res.stringResource
import com.localagentbridge.android.R
import java.util.Locale

@Composable
internal fun runtimeProviderDisplayName(provider: String): String {
    return when (provider.normalizedProviderId()) {
        "ollama" -> stringResource(R.string.provider_ollama)
        "lm_studio", "lmstudio" -> stringResource(R.string.provider_lm_studio)
        "companion_runtime", "local_runtime", "runtime" ->
            stringResource(R.string.provider_companion_runtime)
        else -> provider.prettifiedProviderId()
    }
}

private fun String.normalizedProviderId(): String =
    trim()
        .lowercase(Locale.US)
        .replace('-', '_')
        .replace(' ', '_')

private fun String.prettifiedProviderId(): String {
    val raw = trim().ifBlank { return "" }
    return raw
        .replace('_', ' ')
        .replace('-', ' ')
        .split(Regex("\\s+"))
        .joinToString(" ") { word ->
            word.replaceFirstChar { char ->
                if (char.isLowerCase()) char.titlecase(Locale.US) else char.toString()
            }
        }
}
