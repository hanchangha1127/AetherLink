package com.localagentbridge.android

import android.content.Context
import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.padding
import androidx.compose.material.icons.automirrored.filled.Chat
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material.icons.filled.Sync
import androidx.annotation.StringRes
import androidx.compose.material3.ColorScheme
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.NavigationBar
import androidx.compose.material3.NavigationBarItem
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.lifecycle.viewmodel.compose.viewModel
import com.google.mlkit.vision.barcode.common.Barcode
import com.google.mlkit.vision.codescanner.GmsBarcodeScannerOptions
import com.google.mlkit.vision.codescanner.GmsBarcodeScanning
import com.localagentbridge.android.runtime.RuntimeClientViewModel
import com.localagentbridge.android.ui.ChatScreen
import com.localagentbridge.android.ui.ConnectionStatusScreen
import com.localagentbridge.android.ui.ModelPickerScreen
import com.localagentbridge.android.ui.PairingScreen
import com.localagentbridge.android.ui.SettingsScreen

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            LocalAgentBridgeApp()
        }
    }
}

@Composable
private fun LocalAgentBridgeApp() {
    AetherLinkTheme {
        Surface(
            modifier = Modifier.fillMaxSize(),
            color = MaterialTheme.colorScheme.background,
        ) {
            val viewModel: RuntimeClientViewModel = viewModel()
            val state by viewModel.state.collectAsStateWithLifecycle()
            val context = LocalContext.current
            var tab by rememberSaveable { mutableStateOf(AppTab.Pairing) }

            Scaffold(
                bottomBar = {
                    NavigationBar {
                        AppTab.entries.forEach { item ->
                            val label = stringResource(item.labelRes)
                            NavigationBarItem(
                                selected = tab == item,
                                onClick = { tab = item },
                                label = { Text(label) },
                                icon = { Icon(item.icon(), contentDescription = label) },
                            )
                        }
                    }
                },
            ) { padding ->
                when (tab) {
                    AppTab.Pairing -> PairingScreen(
                        state = state,
                        onHostChange = viewModel::updateHost,
                        onPortChange = viewModel::updatePort,
                        onUseUsbReverse = viewModel::useUsbReverseEndpoint,
                        onUseEmulator = viewModel::useEmulatorEndpoint,
                        onStartDiscovery = viewModel::startDiscovery,
                        onStopDiscovery = viewModel::stopDiscovery,
                        onUseDiscoveredMac = viewModel::useDiscoveredMac,
                        onForgetTrustedMac = viewModel::forgetTrustedMac,
                        onScanPairingQr = {
                            startPairingQrScanner(
                                context = context,
                                onResult = viewModel::trustMacFromPairingQr,
                                onFailure = viewModel::showQrScanFailed,
                            )
                        },
                        onConnect = viewModel::connectToTrustedRuntime,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                    )
                    AppTab.Status -> ConnectionStatusScreen(
                        state = state,
                        onRefreshHealth = viewModel::requestRuntimeHealth,
                        onDisconnect = viewModel::disconnect,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                    )
                    AppTab.Models -> ModelPickerScreen(
                        state = state,
                        onRequestModels = viewModel::requestModels,
                        onSelectModel = viewModel::selectModel,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                    )
                    AppTab.Chat -> ChatScreen(
                        state = state,
                        onInputChange = viewModel::updateChatInput,
                        onSend = viewModel::sendChatMessage,
                        onCancel = viewModel::cancelGeneration,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                    )
                    AppTab.Settings -> SettingsScreen(
                        state = state,
                        onHostChange = viewModel::updateHost,
                        onPortChange = viewModel::updatePort,
                        onUseUsbReverse = viewModel::useUsbReverseEndpoint,
                        onUseEmulator = viewModel::useEmulatorEndpoint,
                        onForgetTrustedMac = viewModel::forgetTrustedMac,
                        modifier = Modifier
                            .fillMaxSize()
                            .padding(padding),
                    )
                }
            }
        }
    }
}

@Composable
private fun AetherLinkTheme(content: @Composable () -> Unit) {
    val colorScheme = if (isSystemInDarkTheme()) {
        AetherLinkDarkColors
    } else {
        AetherLinkLightColors
    }
    MaterialTheme(
        colorScheme = colorScheme,
        content = content,
    )
}

private val AetherLinkLightColors: ColorScheme = lightColorScheme(
    primary = Color(0xFF0B6B74),
    onPrimary = Color(0xFFFFFFFF),
    primaryContainer = Color(0xFFC7F0F4),
    onPrimaryContainer = Color(0xFF06363B),
    secondary = Color(0xFF586268),
    onSecondary = Color(0xFFFFFFFF),
    secondaryContainer = Color(0xFFDCE6EA),
    onSecondaryContainer = Color(0xFF202A2F),
    tertiary = Color(0xFF6A5E15),
    onTertiary = Color(0xFFFFFFFF),
    tertiaryContainer = Color(0xFFF4E58A),
    onTertiaryContainer = Color(0xFF211C00),
    background = Color(0xFFFAFCFC),
    onBackground = Color(0xFF171D1F),
    surface = Color(0xFFFAFCFC),
    onSurface = Color(0xFF171D1F),
    surfaceVariant = Color(0xFFE0E4E7),
    onSurfaceVariant = Color(0xFF42484B),
    outline = Color(0xFF70787C),
)

private val AetherLinkDarkColors: ColorScheme = darkColorScheme(
    primary = Color(0xFF7BD2DD),
    onPrimary = Color(0xFF00363D),
    primaryContainer = Color(0xFF00515A),
    onPrimaryContainer = Color(0xFFC7F0F4),
    secondary = Color(0xFFC0CAD0),
    onSecondary = Color(0xFF2B3337),
    secondaryContainer = Color(0xFF424B50),
    onSecondaryContainer = Color(0xFFDCE6EA),
    tertiary = Color(0xFFD7C96F),
    onTertiary = Color(0xFF393000),
    tertiaryContainer = Color(0xFF514700),
    onTertiaryContainer = Color(0xFFF4E58A),
    background = Color(0xFF101416),
    onBackground = Color(0xFFE0E3E5),
    surface = Color(0xFF101416),
    onSurface = Color(0xFFE0E3E5),
    surfaceVariant = Color(0xFF42484B),
    onSurfaceVariant = Color(0xFFC0C8CC),
    outline = Color(0xFF8A9296),
)

private fun startPairingQrScanner(
    context: Context,
    onResult: (String) -> Unit,
    onFailure: (String?) -> Unit,
) {
    val options = GmsBarcodeScannerOptions.Builder()
        .setBarcodeFormats(Barcode.FORMAT_QR_CODE)
        .build()
    val scanner = GmsBarcodeScanning.getClient(context, options)

    scanner.startScan()
        .addOnSuccessListener { barcode ->
            val rawValue = barcode.rawValue
            if (rawValue.isNullOrBlank()) {
                onFailure(context.getString(R.string.error_qr_empty_detail))
            } else {
                onResult(rawValue)
            }
        }
        .addOnCanceledListener {
            // User intentionally dismissed the scanner. Keep the current pairing state.
        }
        .addOnFailureListener { error ->
            onFailure(error.message)
        }
}

private enum class AppTab(@param:StringRes val labelRes: Int) {
    Pairing(R.string.tab_pairing),
    Status(R.string.tab_status),
    Models(R.string.tab_models),
    Chat(R.string.tab_chat),
    Settings(R.string.tab_settings);

    @Composable
    fun icon() = when (this) {
        Pairing -> Icons.Filled.Link
        Status -> Icons.Filled.Sync
        Models -> Icons.Filled.Storage
        Chat -> Icons.AutoMirrored.Filled.Chat
        Settings -> Icons.Filled.Settings
    }
}
