package com.localagentbridge.android.ui

import android.content.ClipData
import android.text.format.Formatter
import android.widget.Toast
import androidx.annotation.StringRes
import com.localagentbridge.android.isAetherLinkPairingQrCandidateValue
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ColumnScope
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.IntrinsicSize
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.WindowInsets
import androidx.compose.foundation.layout.fillMaxHeight
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.heightIn
import androidx.compose.foundation.layout.ime
import androidx.compose.foundation.layout.navigationBarsPadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.selection.selectable
import androidx.compose.foundation.selection.selectableGroup
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Archive
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.ContentCopy
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DeleteSweep
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.KeyboardArrowDown
import androidx.compose.material.icons.filled.KeyboardArrowUp
import androidx.compose.material.icons.filled.Link
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Unarchive
import androidx.compose.material3.AlertDialog
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.FilledIconButton
import androidx.compose.material3.FilledTonalIconButton
import androidx.compose.material3.HorizontalDivider
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.OutlinedCard
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.RadioButton
import androidx.compose.material3.Surface
import androidx.compose.material3.Switch
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.derivedStateOf
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.runtime.staticCompositionLocalOf
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.hapticfeedback.HapticFeedback
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.ClipEntry
import androidx.compose.ui.platform.LocalClipboard
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.res.pluralStringResource
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.semantics.Role
import androidx.compose.ui.semantics.LiveRegionMode
import androidx.compose.ui.semantics.clearAndSetSemantics
import androidx.compose.ui.semantics.contentDescription
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.onLongClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import com.localagentbridge.android.R
import com.localagentbridge.android.core.pairing.isEligibleRemoteRelayHost
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.runtime.RuntimeAppLanguage
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeActiveRouteKind
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeDiscoveredRuntime
import com.localagentbridge.android.runtime.RuntimeMemoryEntry
import com.localagentbridge.android.runtime.RuntimeMessageAttachment
import com.localagentbridge.android.runtime.RuntimeModel
import com.localagentbridge.android.runtime.RuntimePendingAttachment
import com.localagentbridge.android.runtime.RuntimeProviderStatus
import com.localagentbridge.android.runtime.RuntimeTrustedRuntime
import com.localagentbridge.android.runtime.RuntimeUiError
import com.localagentbridge.android.runtime.RuntimeUiState
import com.localagentbridge.android.runtime.isChatModel
import com.localagentbridge.android.runtime.isEmbeddingModel
import com.localagentbridge.android.runtime.supportsImageInput
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import java.util.Locale

private const val COPY_SUCCESS_ANNOUNCEMENT_DURATION_MS = 1_800L

private data class CopySuccessAnnouncement(
    val id: Int,
    val message: String,
)

private val LocalCopySuccessAnnouncer = staticCompositionLocalOf<(String) -> Unit> { {} }

internal enum class AetherLinkInteractionFeedback {
    PrimaryAction,
    SelectionChange,
    Toggle,
    Destructive,
    Clipboard,
}

internal fun aetherLinkHapticFeedbackType(feedback: AetherLinkInteractionFeedback): HapticFeedbackType {
    return when (feedback) {
        AetherLinkInteractionFeedback.PrimaryAction,
        AetherLinkInteractionFeedback.SelectionChange,
        AetherLinkInteractionFeedback.Toggle,
        -> HapticFeedbackType.TextHandleMove
        AetherLinkInteractionFeedback.Destructive,
        AetherLinkInteractionFeedback.Clipboard,
        -> HapticFeedbackType.LongPress
    }
}

internal fun shouldPerformSelectionChangeHaptic(selected: Boolean): Boolean = !selected

private fun HapticFeedback.performAetherLinkFeedback(feedback: AetherLinkInteractionFeedback) {
    performHapticFeedback(aetherLinkHapticFeedbackType(feedback))
}

@Composable
private fun QrPairingPanel(
    state: RuntimeUiState,
    onScanPairingQr: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.42f),
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        Column(
            modifier = Modifier.padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp),
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Surface(
                    modifier = Modifier.size(40.dp),
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.72f),
                    contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                ) {
                    Box(contentAlignment = Alignment.Center) {
                        Icon(
                            imageVector = Icons.Filled.Link,
                            contentDescription = null,
                            modifier = Modifier.size(20.dp),
                        )
                    }
                }
                Text(
                    text = stringResource(R.string.qr_pairing_title),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Text(
                text = stringResource(R.string.qr_pairing_detail),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 4,
                overflow = TextOverflow.Ellipsis,
            )
            val scanQrStateDescription = if (state.isConnecting) {
                stringResource(R.string.scan_qr_state_connecting)
            } else {
                stringResource(R.string.scan_qr_state_ready)
            }
            val scanQrActionLabel = if (state.isPairingAwaitingRoute) {
                stringResource(R.string.route_notice_action_scan_qr)
            } else {
                stringResource(R.string.scan_qr)
            }
            Button(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onScanPairingQr()
                },
                enabled = !state.isConnecting,
                modifier = Modifier
                    .fillMaxWidth()
                    .height(54.dp)
                    .semantics {
                        stateDescription = scanQrStateDescription
                    },
            ) {
                Icon(
                    Icons.Filled.Link,
                    contentDescription = null,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = scanQrActionLabel
                )
            }
            RouteRefreshSavedNotice(state = state)
            Text(
                text = stringResource(R.string.qr_pairing_security_note),
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.82f),
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun ManualPairingPayloadDialog(
    onDismiss: () -> Unit,
    onSubmit: (String) -> Unit,
) {
    var payload by rememberSaveable { mutableStateOf("") }
    val sanitizedPayload = usableManualPairingPayload(payload)
    val payloadStateDescription = stringResource(
        manualPairingPayloadStateDescriptionRes(payload, sanitizedPayload),
    )
    val payloadInputAccessibilityLabel = stringResource(R.string.manual_qr_payload_input_accessibility)
    val payloadSubmitAccessibilityLabel = stringResource(R.string.manual_qr_payload_submit_accessibility)
    val payloadCancelAccessibilityLabel = stringResource(R.string.manual_qr_payload_cancel_accessibility)
    val payloadIsInvalid = payload.isNotBlank() && sanitizedPayload == null
    val hapticFeedback = LocalHapticFeedback.current

    AlertDialog(
        onDismissRequest = onDismiss,
        title = {
            Text(stringResource(R.string.manual_qr_payload_title))
        },
        text = {
            Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                Text(
                    text = stringResource(R.string.manual_qr_payload_detail),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
                OutlinedTextField(
                    value = payload,
                    onValueChange = { payload = it },
                    label = { Text(stringResource(R.string.manual_qr_payload_label)) },
                    minLines = 3,
                    maxLines = 6,
                    isError = payloadIsInvalid,
                    supportingText = {
                        Text(payloadStateDescription)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            contentDescription = payloadInputAccessibilityLabel
                            stateDescription = payloadStateDescription
                        },
                )
            }
        },
        confirmButton = {
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    sanitizedPayload?.let(onSubmit)
                },
                enabled = sanitizedPayload != null,
                modifier = Modifier.semantics {
                    contentDescription = payloadSubmitAccessibilityLabel
                    stateDescription = payloadStateDescription
                    onClick(label = payloadSubmitAccessibilityLabel, action = null)
                },
            ) {
                Text(stringResource(R.string.manual_qr_payload_submit))
            }
        },
        dismissButton = {
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                    onDismiss()
                },
                modifier = Modifier.semantics {
                    contentDescription = payloadCancelAccessibilityLabel
                    onClick(label = payloadCancelAccessibilityLabel, action = null)
                },
            ) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@StringRes
private fun manualPairingPayloadStateDescriptionRes(
    payload: String,
    sanitizedPayload: String?,
): Int {
    return when {
        payload.isBlank() -> R.string.manual_qr_payload_state_empty
        sanitizedPayload == null -> R.string.manual_qr_payload_state_invalid
        else -> R.string.manual_qr_payload_state_ready
    }
}

internal fun usableManualPairingPayload(rawValue: String): String? {
    return rawValue.trim().takeIf { it.isAetherLinkPairingQrCandidateValue() }
}

@Composable
private fun RouteRefreshSavedNotice(state: RuntimeUiState) {
    val runtimeName = state.routeRefreshNoticeRuntimeName
        ?.takeIf { it.isNotBlank() }
        ?: return
    val notice = stringResource(R.string.route_refresh_notice, runtimeName)

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = notice
                liveRegion = LiveRegionMode.Polite
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.primaryContainer.copy(alpha = 0.58f),
        contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Filled.CheckCircle,
                contentDescription = null,
                modifier = Modifier.size(18.dp),
            )
            Text(
                text = notice,
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Medium,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun PendingPairingRouteStatus(state: RuntimeUiState) {
    val runtimeName = state.pendingPairingRuntimeName
        ?.takeIf { it.isNotBlank() }
        ?: stringResource(R.string.trusted_runtime)
    val pendingTitle = stringResource(R.string.pending_pairing_route_title)
    val pendingDetail = stringResource(R.string.pending_pairing_route_detail, runtimeName)
    val pendingAccessibilitySummary = stringResource(
        R.string.pending_pairing_route_accessibility_summary,
        runtimeName,
    )

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = pendingAccessibilitySummary
                liveRegion = LiveRegionMode.Polite
            },
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.secondaryContainer,
    ) {
        Row(
            modifier = Modifier.padding(14.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(
                Icons.Filled.Search,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onSecondaryContainer,
                modifier = Modifier.size(22.dp),
            )
            Column(
                verticalArrangement = Arrangement.spacedBy(4.dp),
                modifier = Modifier.weight(1f),
            ) {
                Text(
                    text = pendingTitle,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                )
                Text(
                    text = pendingDetail,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.onSecondaryContainer,
                )
                if (state.isDiscovering) {
                    LinearProgressIndicator(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(top = 6.dp),
                    )
                }
            }
        }
    }
}

@Composable
private fun PairingConnectButton(
    state: RuntimeUiState,
    onConnect: () -> Unit,
    onScanLatestQr: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val action = pairingConnectPrimaryAction(state)
    val connectStateDescription = pairingConnectButtonStateDescription(state, action)
    val actionLabel = pairingConnectButtonLabel(state, action)

    Button(
        onClick = {
            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
            when (action) {
                RouteNoticePrimaryAction.ScanLatestQr -> onScanLatestQr()
                RouteNoticePrimaryAction.Connect,
                null -> onConnect()
            }
        },
        enabled = state.trustedRuntime != null && !state.isConnecting,
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                stateDescription = connectStateDescription
            },
    ) {
        Icon(
            Icons.Filled.Link,
            contentDescription = null,
        )
        Spacer(Modifier.width(8.dp))
        Text(actionLabel)
    }
}

@Composable
private fun pairingConnectButtonStateDescription(
    state: RuntimeUiState,
    action: RouteNoticePrimaryAction?,
): String {
    return when {
        state.isConnecting -> stringResource(R.string.connect_runtime_state_connecting)
        action == RouteNoticePrimaryAction.ScanLatestQr -> stringResource(R.string.scan_latest_qr_state_ready)
        else -> stringResource(R.string.connect_runtime_state_ready)
    }
}

@Composable
private fun pairingConnectButtonLabel(
    state: RuntimeUiState,
    action: RouteNoticePrimaryAction?,
): String {
    return when (action) {
        RouteNoticePrimaryAction.ScanLatestQr -> stringResource(routeNoticeActionLabelRes(action))
        RouteNoticePrimaryAction.Connect,
        null -> connectRuntimeActionLabel(state)
    }
}

internal fun pairingConnectPrimaryAction(state: RuntimeUiState): RouteNoticePrimaryAction? {
    return when {
        state.isConnecting || state.isConnected -> null
        state.trustedRuntime == null -> null
        runtimeRouteNotice(state, state.trustedRuntime)?.action == RouteNoticePrimaryAction.ScanLatestQr ->
            RouteNoticePrimaryAction.ScanLatestQr
        routeNoticePrimaryAction(state) == RouteNoticePrimaryAction.ScanLatestQr ->
            RouteNoticePrimaryAction.ScanLatestQr
        else -> RouteNoticePrimaryAction.Connect
    }
}

@Composable
private fun connectRuntimeActionLabel(state: RuntimeUiState): String {
    return stringResource(connectRuntimeActionLabelRes(state))
}

@StringRes
internal fun connectRuntimeActionLabelRes(state: RuntimeUiState): Int {
    return if (state.isConnecting) {
        R.string.connecting
    } else if (state.trustedRuntime.hasUsableRelayRoute()) {
        R.string.connect_remote_route
    } else {
        R.string.connect_runtime
    }
}

@Composable
fun ConnectionStatusScreen(
    state: RuntimeUiState,
    onConnect: (() -> Unit)? = null,
    onRefreshHealth: () -> Unit,
    onDisconnect: () -> Unit,
    onScanLatestQr: (() -> Unit)? = null,
    modifier: Modifier = Modifier,
) {
    ScreenList(modifier) {
        item {
            ScreenHeader(
                title = R.string.status_title,
                subtitle = R.string.status_subtitle,
            )
        }
        item {
            ConnectionStatusPanel(
                state = state,
                onConnect = onConnect,
                onScanLatestQr = onScanLatestQr,
            )
        }
        item {
            ConnectionStatusActions(
                state = state,
                onRefreshHealth = onRefreshHealth,
                onDisconnect = onDisconnect,
            )
        }
        item { RouteRefreshSavedNotice(state = state) }
        item {
            ErrorText(
                error = state.error,
                routeAction = routeNoticePrimaryAction(state),
                onConnect = onConnect,
                onScanLatestQr = onScanLatestQr,
            )
        }
    }
}

@Composable
private fun ConnectionStatusPanel(
    state: RuntimeUiState,
    onConnect: (() -> Unit)? = null,
    onScanLatestQr: (() -> Unit)? = null,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            ConnectionStatusHero(state = state)
            StatusLine(
                label = stringResource(R.string.runtime),
                value = runtimeStatusLabel(state.runtimeStatus),
            )
            if (state.isPairingAwaitingRoute) {
                StatusLine(
                    label = stringResource(R.string.pairing_title),
                    value = stringResource(
                        R.string.pending_pairing_route_status,
                        state.pendingPairingRuntimeName
                            ?.takeIf { it.isNotBlank() }
                            ?: stringResource(R.string.trusted_runtime),
                    ),
                )
            }
            StatusLine(
                label = stringResource(R.string.backend),
                value = backendStatusLabel(state.backendAvailable),
            )
            StatusLine(
                label = stringResource(R.string.providers),
                value = providerStatusSummary(state),
            )
            ProviderStatusRows(providers = state.providerStatuses)
            RuntimeRouteNotice(
                state = state,
                onConnect = onConnect,
                onScanLatestQr = onScanLatestQr,
            )
            StatusLine(
                label = stringResource(R.string.connected),
                value = if (state.isConnected) stringResource(R.string.yes) else stringResource(R.string.no),
            )
            StatusLine(
                label = stringResource(R.string.auto_reconnect),
                value = if (state.trustedRuntimeAutoReconnectEnabled) {
                    stringResource(R.string.yes)
                } else {
                    stringResource(R.string.no)
                },
            )
            if (state.trustedRuntime != null && !state.trustedRuntimeAutoReconnectEnabled && !state.isConnected) {
                Text(
                    text = stringResource(R.string.auto_reconnect_paused),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
        }
    }
}

@Composable
private fun ConnectionStatusHero(state: RuntimeUiState) {
    val trustedRuntimeName = state.trustedRuntime?.name?.takeIf { it.isNotBlank() }
    val pendingRuntimeName = state.pendingPairingRuntimeName?.takeIf { it.isNotBlank() }
    val runtimeName = trustedRuntimeName
        ?: pendingRuntimeName
        ?: stringResource(R.string.trusted_runtime)

    val isTrustedConnection = state.isConnected && state.trustedRuntime != null
    val needsPairing = state.trustedRuntime == null && !state.isConnected
    val hasRelayRoute = state.trustedRuntime.hasUsableRelayRoute()
    val needsRoute = state.trustedRuntime != null &&
        state.trustedRuntime.endpointHint == null &&
        !hasRelayRoute &&
        !state.isConnected

    val title = stringResource(connectionStatusHeroTitleRes(state))
    val detail = stringResource(connectionStatusHeroDetailRes(state), runtimeName)
    val accessibilitySummary = stringResource(R.string.status_hero_accessibility_summary, title, detail)
    val icon = when {
        isTrustedConnection -> Icons.Filled.CheckCircle
        state.isConnecting -> Icons.Filled.Refresh
        state.isPairingAwaitingRoute || needsRoute || needsPairing -> Icons.Filled.Error
        else -> Icons.Filled.Link
    }
    val containerColor = when {
        isTrustedConnection -> MaterialTheme.colorScheme.primaryContainer
        state.isPairingAwaitingRoute || needsRoute || needsPairing -> MaterialTheme.colorScheme.errorContainer
        else -> MaterialTheme.colorScheme.surfaceVariant
    }
    val contentColor = when {
        isTrustedConnection -> MaterialTheme.colorScheme.onPrimaryContainer
        state.isPairingAwaitingRoute || needsRoute || needsPairing -> MaterialTheme.colorScheme.onErrorContainer
        else -> MaterialTheme.colorScheme.onSurfaceVariant
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = accessibilitySummary
            },
        shape = RoundedCornerShape(16.dp),
        color = containerColor,
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = contentColor,
                modifier = Modifier.size(22.dp),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(3.dp),
            ) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = contentColor,
                )
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = contentColor,
                )
            }
        }
    }
}

@StringRes
internal fun connectionStatusHeroTitleRes(state: RuntimeUiState): Int {
    val isTrustedConnection = state.isConnected && state.trustedRuntime != null
    val needsPairing = state.trustedRuntime == null && !state.isConnected
    val hasRelayRoute = state.trustedRuntime.hasUsableRelayRoute()
    val needsRoute = state.trustedRuntime != null &&
        state.trustedRuntime.endpointHint == null &&
        !hasRelayRoute &&
        !state.isConnected
    val hasSavedRelayRoute = hasRelayRoute && !state.isConnected
    val hasSavedRoute = state.trustedRuntime != null &&
        (state.trustedRuntime.endpointHint != null || hasRelayRoute) &&
        !state.isConnected

    return when {
        isTrustedConnection -> R.string.status_connected_trusted_title
        state.isConnected -> R.string.status_connected_diagnostics_title
        state.isConnecting -> R.string.status_connecting_trusted_title
        state.isPairingAwaitingRoute || needsRoute -> R.string.status_route_needed_title
        needsPairing -> R.string.status_pairing_needed_title
        hasSavedRelayRoute -> R.string.status_relay_ready_title
        hasSavedRoute -> R.string.status_connect_ready_title
        else -> R.string.status_disconnected
    }
}

@StringRes
internal fun connectionStatusHeroDetailRes(state: RuntimeUiState): Int {
    val isTrustedConnection = state.isConnected && state.trustedRuntime != null
    val needsPairing = state.trustedRuntime == null && !state.isConnected
    val hasRelayRoute = state.trustedRuntime.hasUsableRelayRoute()
    val needsRoute = state.trustedRuntime != null &&
        state.trustedRuntime.endpointHint == null &&
        !hasRelayRoute &&
        !state.isConnected
    val hasSavedRelayRoute = hasRelayRoute && !state.isConnected
    val hasSavedRoute = state.trustedRuntime != null &&
        (state.trustedRuntime.endpointHint != null || hasRelayRoute) &&
        !state.isConnected

    return when {
        isTrustedConnection -> R.string.status_connected_trusted_detail
        state.isConnected -> R.string.status_connected_diagnostics_detail
        state.isConnecting -> R.string.status_connecting_trusted_detail
        state.isPairingAwaitingRoute -> R.string.pending_pairing_route_detail
        needsRoute -> R.string.status_route_needed_detail
        needsPairing -> R.string.status_pairing_needed_detail
        hasSavedRelayRoute -> R.string.status_relay_ready_detail
        hasSavedRoute -> R.string.status_connect_ready_detail
        else -> R.string.status_disconnected_summary
    }
}

internal fun RuntimeTrustedRuntime?.hasRelayRouteMaterial(): Boolean {
    val host = this?.relayHost?.takeIf { it.isNotBlank() } ?: return false
    return isEligibleRemoteRelayHost(host, relayScope) &&
        relayPort != null &&
        relayPort in 1..65535 &&
        !relayId.isNullOrBlank() &&
        !relaySecret.isNullOrBlank() &&
        relayExpiresAtEpochMillis != null &&
        relayExpiresAtEpochMillis > 0L &&
        !relayNonce.isNullOrBlank()
}

internal fun RuntimeTrustedRuntime?.hasUsableRelayRoute(): Boolean {
    return hasRelayRouteMaterial() && !isRelayRouteExpired()
}

private fun RuntimeTrustedRuntime?.hasUnusableRelayRouteHint(): Boolean {
    val runtime = this ?: return false
    val hasAnyRelayField = !runtime.relayHost.isNullOrBlank() ||
        runtime.relayPort != null ||
        !runtime.relayId.isNullOrBlank() ||
        !runtime.relaySecret.isNullOrBlank() ||
        runtime.relayExpiresAtEpochMillis != null ||
        !runtime.relayNonce.isNullOrBlank()
    return hasAnyRelayField && !runtime.hasRelayRouteMaterial()
}

internal fun RuntimeTrustedRuntime?.hasRelayRouteWithoutSecret(): Boolean {
    val runtime = this ?: return false
    val host = runtime.relayHost?.takeIf { it.isNotBlank() } ?: return false
    return isEligibleRemoteRelayHost(host, runtime.relayScope) &&
        runtime.relayPort != null &&
        runtime.relayPort in 1..65535 &&
        !runtime.relayId.isNullOrBlank() &&
        runtime.relaySecret.isNullOrBlank()
}

@Composable
private fun RuntimeRouteNotice(
    state: RuntimeUiState,
    onConnect: (() -> Unit)?,
    onScanLatestQr: (() -> Unit)?,
) {
    val trustedRuntime = state.trustedRuntime
    val notice = runtimeRouteNotice(state, trustedRuntime) ?: return
    val hapticFeedback = LocalHapticFeedback.current
    val action = notice.action
    val actionHandler = when (action) {
        RouteNoticePrimaryAction.Connect -> onConnect
        RouteNoticePrimaryAction.ScanLatestQr -> onScanLatestQr
        null -> null
    }
    val actionLabel = action?.let { stringResource(routeNoticeActionLabelRes(it)) }
    val title = stringResource(R.string.route_notice_title)
    val statusDescription = stringResource(notice.statusRes)
    val detailDescription = stringResource(notice.detailRes)
    val recoverySteps = routeNoticeRecoverySteps(notice)
    val accessibilitySummary = if (recoverySteps == null) {
        stringResource(
            R.string.route_notice_accessibility_summary,
            title,
            statusDescription,
            detailDescription,
        )
    } else {
        stringResource(
            R.string.route_notice_accessibility_summary_with_steps,
            title,
            statusDescription,
            detailDescription,
            recoverySteps,
        )
    }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = accessibilitySummary
                stateDescription = statusDescription
            }
            .let { base ->
                if (actionHandler == null) {
                    base
                } else {
                    base.clickable(
                        role = Role.Button,
                        onClickLabel = actionLabel,
                    ) {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        actionHandler()
                    }
                }
            },
        shape = RoundedCornerShape(14.dp),
        color = notice.containerColor(),
        contentColor = notice.contentColor(),
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(
                imageVector = notice.icon,
                contentDescription = null,
                modifier = Modifier.size(20.dp),
                tint = notice.contentColor(),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = title,
                        modifier = Modifier.weight(1f),
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = notice.contentColor(),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    RouteNoticeStatusPill(notice)
                }
                Text(
                    text = detailDescription,
                    style = MaterialTheme.typography.bodySmall,
                    color = notice.contentColor(),
                )
                if (recoverySteps != null) {
                    Text(
                        text = recoverySteps,
                        style = MaterialTheme.typography.bodySmall,
                        color = notice.contentColor().copy(alpha = 0.82f),
                    )
                }
                if (actionLabel != null && actionHandler != null) {
                    Text(
                        text = actionLabel,
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        color = notice.contentColor(),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun routeNoticeRecoverySteps(notice: RuntimeRouteNoticeState): String? {
    if (notice.tone != RuntimeRouteNoticeTone.Warning) return null
    if (notice.action != RouteNoticePrimaryAction.ScanLatestQr) return null
    return stringResource(R.string.route_notice_recovery_steps)
}

@Composable
private fun RouteNoticeStatusPill(notice: RuntimeRouteNoticeState) {
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = notice.contentColor().copy(alpha = 0.10f),
        contentColor = notice.contentColor(),
    ) {
        Text(
            text = stringResource(notice.statusRes),
            modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
            style = MaterialTheme.typography.labelSmall,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
    }
}

internal data class RuntimeRouteNoticeState(
    @param:StringRes val statusRes: Int,
    @param:StringRes val detailRes: Int,
    val tone: RuntimeRouteNoticeTone,
    val icon: androidx.compose.ui.graphics.vector.ImageVector,
    val action: RouteNoticePrimaryAction? = null,
)

internal enum class RuntimeRouteNoticeTone {
    Neutral,
    Ready,
    Warning,
}

internal enum class RouteNoticePrimaryAction {
    Connect,
    ScanLatestQr,
}

@StringRes
internal fun routeNoticeActionLabelRes(action: RouteNoticePrimaryAction): Int {
    return when (action) {
        RouteNoticePrimaryAction.Connect -> R.string.connect_remote_route
        RouteNoticePrimaryAction.ScanLatestQr -> R.string.route_notice_action_scan_qr
    }
}

internal fun routeNoticePrimaryAction(state: RuntimeUiState): RouteNoticePrimaryAction? {
    if (state.isConnected || state.isConnecting) return null
    val trustedRuntime = state.trustedRuntime ?: return RouteNoticePrimaryAction.ScanLatestQr
    if (state.isPairingAwaitingRoute) return RouteNoticePrimaryAction.ScanLatestQr
    if (state.error?.isRouteAvailabilityNotice() == true) {
        return if (
            state.error.code in QR_REFRESH_EMPTY_CHAT_ERROR_CODES ||
            state.error.diagnosticCode in QR_REFRESH_EMPTY_CHAT_DIAGNOSTIC_CODES
        ) {
            RouteNoticePrimaryAction.ScanLatestQr
        } else if (hasConnectableTrustedRuntimeRoute(state, trustedRuntime)) {
            RouteNoticePrimaryAction.Connect
        } else {
            RouteNoticePrimaryAction.ScanLatestQr
        }
    }
    if (!hasConnectableTrustedRuntimeRoute(state, trustedRuntime)) return RouteNoticePrimaryAction.ScanLatestQr
    return RouteNoticePrimaryAction.Connect
}

internal fun hasConnectableTrustedRuntimeRoute(
    state: RuntimeUiState,
    trustedRuntime: RuntimeTrustedRuntime? = state.trustedRuntime,
): Boolean {
    trustedRuntime ?: return false
    if (trustedRuntime.hasUsableRelayRoute()) return true
    if (trustedRuntime.endpointHint != null) return true
    return state.runtimeEndpointSource != RuntimeEndpointSource.Manual && state.runtimeHost.isNotBlank()
}

@Composable
private fun RuntimeRouteNoticeState.containerColor() = when (tone) {
    RuntimeRouteNoticeTone.Ready -> MaterialTheme.colorScheme.primaryContainer
    RuntimeRouteNoticeTone.Warning -> MaterialTheme.colorScheme.errorContainer
    RuntimeRouteNoticeTone.Neutral -> MaterialTheme.colorScheme.surfaceVariant
}

@Composable
private fun RuntimeRouteNoticeState.contentColor() = when (tone) {
    RuntimeRouteNoticeTone.Ready -> MaterialTheme.colorScheme.onPrimaryContainer
    RuntimeRouteNoticeTone.Warning -> MaterialTheme.colorScheme.onErrorContainer
    RuntimeRouteNoticeTone.Neutral -> MaterialTheme.colorScheme.onSurfaceVariant
}

internal fun runtimeRouteNotice(
    state: RuntimeUiState,
    trustedRuntime: RuntimeTrustedRuntime?,
): RuntimeRouteNoticeState? {
    if (trustedRuntime == null && !state.isConnected && !state.isPairingAwaitingRoute) return null
    if (state.isConnected) {
        when (state.activeRouteKind) {
            RuntimeActiveRouteKind.Relay -> return RuntimeRouteNoticeState(
                statusRes = R.string.route_notice_status_connected,
                detailRes = R.string.route_notice_relay_active,
                tone = RuntimeRouteNoticeTone.Ready,
                icon = Icons.Filled.CheckCircle,
            )
            RuntimeActiveRouteKind.PeerToPeer -> return RuntimeRouteNoticeState(
                statusRes = R.string.route_notice_status_connected,
                detailRes = R.string.route_notice_p2p_active,
                tone = RuntimeRouteNoticeTone.Ready,
                icon = Icons.Filled.CheckCircle,
            )
            RuntimeActiveRouteKind.DirectTcp, null -> Unit
        }
        return when (state.runtimeEndpointSource) {
            RuntimeEndpointSource.BonjourDiscovery,
            RuntimeEndpointSource.PairingQr,
            RuntimeEndpointSource.TrustedLastKnown -> RuntimeRouteNoticeState(
                statusRes = R.string.route_notice_status_connected,
                detailRes = R.string.route_notice_local_route,
                tone = RuntimeRouteNoticeTone.Ready,
                icon = Icons.Filled.CheckCircle,
            )
            RuntimeEndpointSource.UsbReverse,
            RuntimeEndpointSource.Emulator,
            RuntimeEndpointSource.Manual -> RuntimeRouteNoticeState(
                statusRes = R.string.route_notice_status_diagnostics,
                detailRes = R.string.route_notice_development_route,
                tone = RuntimeRouteNoticeTone.Neutral,
                icon = Icons.Filled.Link,
            )
        }
    }
    state.error?.takeIf { it.requiresLatestQrRouteNotice() }?.let { routeError ->
        return RuntimeRouteNoticeState(
            statusRes = R.string.route_notice_status_refresh_needed,
            detailRes = routeAvailabilityCompactLabelRes(routeError),
            tone = RuntimeRouteNoticeTone.Warning,
            icon = Icons.Filled.Error,
            action = RouteNoticePrimaryAction.ScanLatestQr,
        )
    }
    if (trustedRuntime.hasRelayRouteWithoutSecret()) {
        return RuntimeRouteNoticeState(
            statusRes = R.string.route_notice_status_refresh_needed,
            detailRes = R.string.route_notice_relay_without_secret,
            tone = RuntimeRouteNoticeTone.Warning,
            icon = Icons.Filled.Error,
            action = RouteNoticePrimaryAction.ScanLatestQr,
        )
    }
    if (trustedRuntime.hasUnusableRelayRouteHint()) {
        return RuntimeRouteNoticeState(
            statusRes = R.string.route_notice_status_refresh_needed,
            detailRes = R.string.route_notice_relay_unusable,
            tone = RuntimeRouteNoticeTone.Warning,
            icon = Icons.Filled.Error,
            action = RouteNoticePrimaryAction.ScanLatestQr,
        )
    }
    if (trustedRuntime.hasRelayRouteMaterial()) {
        return if (trustedRuntime.isRelayRouteExpired()) {
            RuntimeRouteNoticeState(
                statusRes = R.string.route_notice_status_refresh_needed,
                detailRes = R.string.route_notice_relay_expired,
                tone = RuntimeRouteNoticeTone.Warning,
                icon = Icons.Filled.Error,
                action = RouteNoticePrimaryAction.ScanLatestQr,
            )
        } else {
            RuntimeRouteNoticeState(
                statusRes = R.string.route_notice_status_saved_connection,
                detailRes = R.string.route_notice_relay_encrypted,
                tone = RuntimeRouteNoticeTone.Neutral,
                icon = Icons.Filled.Link,
                action = routeNoticePrimaryAction(state),
            )
        }
    }
    if (state.runtimeEndpointSource == RuntimeEndpointSource.BonjourDiscovery) {
        return RuntimeRouteNoticeState(
            statusRes = R.string.route_notice_status_nearby,
            detailRes = R.string.route_notice_local_route,
            tone = RuntimeRouteNoticeTone.Ready,
            icon = Icons.Filled.CheckCircle,
        )
    }
    if (state.runtimeEndpointSource != RuntimeEndpointSource.Manual && state.runtimeHost.isNotBlank()) {
        return RuntimeRouteNoticeState(
            statusRes = R.string.route_notice_status_diagnostics,
            detailRes = R.string.route_notice_development_route,
            tone = RuntimeRouteNoticeTone.Neutral,
            icon = Icons.Filled.Link,
            action = routeNoticePrimaryAction(state),
        )
    }
    return RuntimeRouteNoticeState(
        statusRes = R.string.route_notice_status_scan_qr,
        detailRes = R.string.route_notice_remote_pending,
        tone = RuntimeRouteNoticeTone.Neutral,
        icon = Icons.Filled.Search,
        action = RouteNoticePrimaryAction.ScanLatestQr,
    )
}

private fun RuntimeTrustedRuntime?.relayRouteExpiresAtMillis(): Long? {
    val expiresAt = this?.relayExpiresAtEpochMillis ?: return null
    return expiresAt.takeIf { it > 0L && it != Long.MAX_VALUE }
}

private fun RuntimeTrustedRuntime?.isRelayRouteExpired(
    nowEpochMillis: Long = System.currentTimeMillis(),
): Boolean {
    val expiresAt = relayRouteExpiresAtMillis() ?: return false
    return expiresAt <= nowEpochMillis
}

@Composable
private fun ConnectionStatusActions(
    state: RuntimeUiState,
    onRefreshHealth: () -> Unit,
    onDisconnect: () -> Unit,
) {
    if (!state.isConnected) return

    val hapticFeedback = LocalHapticFeedback.current
    val refreshHealthStateDescription = stringResource(R.string.refresh_health_state_ready)
    val disconnectStateDescription = stringResource(R.string.disconnect_runtime_state_ready)

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(
            onClick = {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                onRefreshHealth()
            },
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    stateDescription = refreshHealthStateDescription
                },
        ) {
            Icon(
                Icons.Filled.Refresh,
                contentDescription = null,
            )
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.refresh_health))
        }
        OutlinedButton(
            onClick = {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                onDisconnect()
            },
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    stateDescription = disconnectStateDescription
                },
        ) {
            Icon(
                Icons.Filled.Close,
                contentDescription = null,
            )
            Spacer(Modifier.width(8.dp))
            Text(stringResource(R.string.disconnect))
        }
    }
}

@Composable
private fun ProviderStatusRows(providers: List<RuntimeProviderStatus>) {
    if (providers.isEmpty()) return

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        providers.forEachIndexed { index, provider ->
            ProviderStatusRow(provider = provider)
            if (index != providers.lastIndex) {
                HorizontalDivider()
            }
        }
    }
}

@Composable
private fun ProviderStatusRow(provider: RuntimeProviderStatus) {
    val statusText = if (provider.available) {
        stringResource(R.string.provider_status_ready)
    } else {
        stringResource(R.string.provider_status_unavailable)
    }
    val icon = if (provider.available) Icons.Filled.CheckCircle else Icons.Filled.Error
    val tint = if (provider.available) {
        MaterialTheme.colorScheme.primary
    } else {
        MaterialTheme.colorScheme.error
    }
    val diagnosticMessage = providerDiagnosticMessage(provider)
    val diagnosticCode = providerDiagnosticCode(provider)
    val hasDiagnostics = providerDiagnosticsVisible(provider)
    val detailText = providerStatusDetail(provider)
    val retryableHint = if (provider.retryable == true) {
        stringResource(R.string.provider_retryable_hint)
    } else {
        null
    }
    val rowAccessibilitySummary = if (retryableHint != null) {
        stringResource(
            R.string.provider_status_row_summary_retryable,
            provider.name,
            statusText,
            detailText,
            retryableHint,
        )
    } else {
        stringResource(
            R.string.provider_status_row_summary,
            provider.name,
            statusText,
            detailText,
        )
    }
    var diagnosticsExpanded by rememberSaveable(provider.id) { mutableStateOf(false) }
    val diagnosticsStateDescription = stringResource(
        if (diagnosticsExpanded) {
            R.string.section_state_expanded
        } else {
            R.string.section_state_collapsed
        },
    )
    val diagnosticsContentDescription = stringResource(
        if (diagnosticsExpanded) {
            R.string.provider_hide_diagnostics_for
        } else {
            R.string.provider_show_diagnostics_for
        },
        provider.name,
    )
    val hapticFeedback = LocalHapticFeedback.current

    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = tint,
            modifier = Modifier.size(20.dp),
        )
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics(mergeDescendants = true) {
                        contentDescription = rowAccessibilitySummary
                    },
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically,
                ) {
                    Text(
                        text = provider.name,
                        style = MaterialTheme.typography.bodyLarge,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                    Spacer(Modifier.width(12.dp))
                    Text(
                        text = statusText,
                        style = MaterialTheme.typography.labelMedium,
                        color = tint,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                Text(
                    text = detailText,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
                if (retryableHint != null) {
                    Text(
                        text = retryableHint,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            if (hasDiagnostics) {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                        diagnosticsExpanded = !diagnosticsExpanded
                    },
                    modifier = Modifier.semantics {
                        contentDescription = diagnosticsContentDescription
                        stateDescription = diagnosticsStateDescription
                    },
                    contentPadding = PaddingValues(horizontal = 0.dp, vertical = 4.dp),
                ) {
                    Icon(
                        imageVector = if (diagnosticsExpanded) {
                            Icons.Filled.KeyboardArrowUp
                        } else {
                            Icons.Filled.KeyboardArrowDown
                        },
                        contentDescription = null,
                    )
                    Spacer(Modifier.width(4.dp))
                    Text(
                        text = stringResource(
                            if (diagnosticsExpanded) {
                                R.string.provider_hide_diagnostics
                            } else {
                                R.string.provider_show_diagnostics
                            }
                        )
                    )
                }
                if (diagnosticsExpanded) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .background(
                                color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.42f),
                                shape = RoundedCornerShape(8.dp),
                            )
                            .padding(10.dp),
                        verticalArrangement = Arrangement.spacedBy(4.dp),
                    ) {
                        diagnosticMessage?.let { message ->
                            Text(
                                text = stringResource(R.string.provider_host_detail, message),
                                style = MaterialTheme.typography.bodySmall,
                                color = MaterialTheme.colorScheme.secondary,
                            )
                        }
                        diagnosticCode?.let { code ->
                            Text(
                                text = stringResource(R.string.provider_error_code, code),
                                style = MaterialTheme.typography.labelSmall,
                                color = MaterialTheme.colorScheme.secondary,
                            )
                        }
                    }
                }
            }
        }
    }
}

@Composable
fun ChatScreen(
    state: RuntimeUiState,
    onInputChange: (String) -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
    onConnect: () -> Unit,
    onScanPairingQr: () -> Unit,
    onRefreshHealth: () -> Unit,
    onAttachFiles: () -> Unit,
    onRemoveAttachment: (String) -> Unit,
    onSuggestionClick: (String) -> Unit,
    onScanLatestQr: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val listState = rememberLazyListState()
    val hapticFeedback = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()
    val hasSendableContent = chatComposerHasSendableContent(state)
    val hasUnsupportedImageAttachment = chatComposerHasUnsupportedImageAttachment(state)
    val canEditComposer = chatComposerCanEdit(state)
    val canSend = chatComposerCanSend(state)
    val jumpToLatestStateDescription = stringResource(R.string.jump_to_latest_state_ready)
    val density = LocalDensity.current
    val keyboardDockPadding = if (WindowInsets.ime.getBottom(density) > 0) 64.dp else 0.dp
    val composerDockSpace = 166.dp
    var previousMessageCount by rememberSaveable { mutableStateOf(0) }
    var copyAnnouncement by remember { mutableStateOf<CopySuccessAnnouncement?>(null) }
    var copyAnnouncementId by remember { mutableStateOf(0) }
    val announceCopySuccess: (String) -> Unit = { message ->
        copyAnnouncementId += 1
        copyAnnouncement = CopySuccessAnnouncement(
            id = copyAnnouncementId,
            message = message,
        )
    }
    val showJumpToLatest by remember(state.messages.size) {
        derivedStateOf {
            shouldShowJumpToLatestChatButton(
                lastVisibleItemIndex = listState.layoutInfo.visibleItemsInfo.lastOrNull()?.index,
                totalItemsCount = listState.layoutInfo.totalItemsCount.takeIf { it > 0 } ?: state.messages.size,
            )
        }
    }

    LaunchedEffect(
        state.messages.size,
        state.messages.lastOrNull()?.content,
        state.messages.lastOrNull()?.reasoning,
        state.isStreaming,
    ) {
        if (state.messages.isNotEmpty()) {
            val layoutInfo = listState.layoutInfo
            val lastVisibleItemIndex = layoutInfo.visibleItemsInfo.lastOrNull()?.index
            val totalItemsCount = layoutInfo.totalItemsCount.takeIf { it > 0 } ?: state.messages.size
            val messageCountChanged = previousMessageCount != state.messages.size
            val newUserMessageAdded = newUserMessageAddedSince(
                previousMessageCount = previousMessageCount,
                messages = state.messages,
                isStreaming = state.isStreaming,
            )
            if (
                shouldAutoScrollChat(
                    lastVisibleItemIndex = lastVisibleItemIndex,
                    totalItemsCount = totalItemsCount,
                    messageCountChanged = messageCountChanged,
                    newUserMessageAdded = newUserMessageAdded,
                )
            ) {
                listState.animateScrollToItem(state.messages.lastIndex)
            }
        }
        previousMessageCount = state.messages.size
    }

    copyAnnouncement?.let { announcement ->
        LaunchedEffect(announcement.id) {
            delay(COPY_SUCCESS_ANNOUNCEMENT_DURATION_MS)
            if (copyAnnouncement?.id == announcement.id) {
                copyAnnouncement = null
            }
        }
    }

    CompositionLocalProvider(LocalCopySuccessAnnouncer provides announceCopySuccess) {
        Box(
            modifier = modifier
                .fillMaxSize()
                .padding(horizontal = 12.dp, vertical = 6.dp),
        ) {
        if (state.messages.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(bottom = composerDockSpace),
                contentAlignment = Alignment.Center,
            ) {
                if (shouldShowChatEmptyState(state)) {
                    ChatEmptyState(
                        state = state,
                        onConnect = onConnect,
                        onScanPairingQr = onScanPairingQr,
                    )
                }
            }
        } else {
            LazyColumn(
                state = listState,
                modifier = Modifier
                    .align(Alignment.TopCenter)
                    .widthIn(max = 840.dp)
                    .fillMaxWidth()
                    .fillMaxHeight()
                    .testTag(CHAT_MESSAGE_LIST_TEST_TAG),
                verticalArrangement = Arrangement.spacedBy(20.dp),
                contentPadding = PaddingValues(
                    start = 4.dp,
                    top = 16.dp,
                    end = 4.dp,
                    bottom = composerDockSpace + 12.dp,
                ),
            ) {
                items(
                    items = state.messages,
                    key = { message -> message.id },
                ) { message ->
                    val isLatestAssistant = message.role == "assistant" &&
                        message.id == state.messages.lastAssistantMessageId()
                    ChatMessageRow(
                        message = message,
                        isStreaming = state.isStreaming &&
                            message.role == "assistant" &&
                            message.id == state.messages.lastOrNull()?.id,
                        showSuggestions = shouldShowAssistantSuggestionsForMessage(state, message),
                        isLoadingSuggestions = isLatestAssistant && state.isLoadingSuggestions,
                        onSuggestionClick = onSuggestionClick,
                    )
                }
            }
        }
        if (showJumpToLatest) {
            FilledTonalIconButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    scope.launch {
                        listState.animateScrollToItem(state.messages.lastIndex)
                    }
                },
                modifier = Modifier
                    .align(Alignment.BottomCenter)
                    .padding(bottom = composerDockSpace + keyboardDockPadding + 18.dp)
                    .size(40.dp)
                    .semantics {
                        stateDescription = jumpToLatestStateDescription
                    },
            ) {
                Icon(
                    imageVector = Icons.Filled.KeyboardArrowDown,
                    contentDescription = stringResource(R.string.content_desc_jump_to_latest),
                )
            }
        }
        Column(
            modifier = Modifier
                .align(Alignment.BottomCenter)
                .widthIn(max = 840.dp)
                .fillMaxWidth()
                .navigationBarsPadding()
                .padding(bottom = keyboardDockPadding),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            BackendReadinessBanner(
                state = state,
                onRefreshHealth = onRefreshHealth,
            )
            RouteRefreshSavedNotice(state = state)
            if (shouldShowChatBottomError(state)) {
                ErrorText(
                    error = state.error,
                    routeAction = routeNoticePrimaryAction(state),
                    onConnect = onConnect,
                    onScanLatestQr = onScanLatestQr,
                )
            }
            ChatComposer(
                value = state.chatInput,
                attachments = state.pendingAttachments,
                enabled = canEditComposer,
                imageAttachmentsSupported = !hasUnsupportedImageAttachment,
                canSend = canSend,
                hasSendableContent = hasSendableContent,
                isStreaming = state.isStreaming,
                hint = chatInputHint(state),
                onInputChange = onInputChange,
                onAttachFiles = onAttachFiles,
                onRemoveAttachment = onRemoveAttachment,
                onSend = onSend,
                onCancel = onCancel,
            )
        }
        copyAnnouncement?.let { announcement ->
            CopySuccessLiveRegion(message = announcement.message)
        }
    }
}

}

@Composable
private fun CopySuccessLiveRegion(message: String) {
    Box(
        modifier = Modifier
            .size(1.dp)
            .semantics {
                liveRegion = LiveRegionMode.Polite
                contentDescription = message
            },
    )
}

@Composable
private fun BackendReadinessBanner(
    state: RuntimeUiState,
    onRefreshHealth: () -> Unit,
) {
    if (!state.isConnected || state.backendAvailable != false) return

    val hapticFeedback = LocalHapticFeedback.current
    val unavailableProviders = state.providerStatuses.filter { provider -> !provider.available }
    val title = stringResource(R.string.chat_backend_unavailable_title)
    val detail = unavailableProviders
        .firstOrNull()
        ?.let { provider -> providerStatusDetail(provider) }
        ?: stringResource(R.string.chat_backend_unavailable_detail)
    val accessibilitySummary = stringResource(
        R.string.chat_backend_unavailable_summary,
        title,
        detail,
    )
    val refreshHealthStateDescription = stringResource(R.string.refresh_health_state_ready)

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = accessibilitySummary
                liveRegion = LiveRegionMode.Polite
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.errorContainer,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.Top,
            ) {
                Icon(
                    imageVector = Icons.Filled.Error,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onErrorContainer,
                )
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                    Text(
                        text = detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
            }
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onRefreshHealth()
                },
                modifier = Modifier.semantics {
                    stateDescription = refreshHealthStateDescription
                },
            ) {
                Icon(
                    imageVector = Icons.Filled.Refresh,
                    contentDescription = null,
                )
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.refresh_health))
            }
        }
    }
}

@Composable
fun SettingsScreen(
    state: RuntimeUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onUseUsbReverse: () -> Unit,
    onUseEmulator: () -> Unit,
    onStartDiscovery: () -> Unit,
    onStopDiscovery: () -> Unit,
    onUseDiscoveredRuntime: (RuntimeDiscoveredRuntime) -> Unit,
    onForgetTrustedRuntime: () -> Unit,
    onScanPairingQr: () -> Unit,
    onSubmitPairingPayload: (String) -> Unit,
    onConnect: () -> Unit,
    onRefreshHealth: () -> Unit,
    onRequestModels: () -> Unit,
    onDisconnect: () -> Unit,
    onSetAutoReconnectEnabled: (Boolean) -> Unit,
    onSetLanguageTag: (String) -> Unit,
    onSetTheme: (RuntimeAppTheme) -> Unit,
    onSelectEmbeddingModel: (String?) -> Unit,
    onAddMemoryEntry: (String) -> Unit,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
    onArchiveChatSession: (String) -> Unit,
    onRestoreChatSession: (String) -> Unit,
    onPermanentlyDeleteChatSession: (String) -> Unit,
    onArchiveAllChatSessions: () -> Unit,
    onPermanentlyDeleteArchivedChatSessions: () -> Unit,
    showDeveloperDiagnostics: Boolean,
    modifier: Modifier = Modifier,
) {
    ScreenList(modifier) {
        if (settingsScreenShowsGenericHeader(state)) {
            item {
                ScreenHeader(
                    title = R.string.settings_title,
                    subtitle = R.string.settings_subtitle,
                )
            }
        }
        if (state.trustedRuntime == null) {
            item {
                FirstRunLanguagePreferencePanel(
                    selectedLanguageTag = state.selectedLanguageTag,
                    onSetLanguageTag = onSetLanguageTag,
                )
            }
        }
        item {
            SettingsExpandableSection(
                title = settingsPrimaryConnectionSectionTitleRes(state),
                subtitle = settingsPrimaryConnectionSectionSubtitleRes(state),
                initiallyExpanded = settingsPrimaryConnectionSectionInitiallyExpanded(state),
                expandWhenKey = settingsPrimaryConnectionSectionExpansionKey(state),
            ) {
                QrPairingPanel(
                    state = state,
                    onScanPairingQr = onScanPairingQr,
                )
                CompanionOnlyPanel()
                if (state.isPairingAwaitingRoute) {
                    PendingPairingRouteStatus(state = state)
                }
                TrustedRuntimePanel(
                    state = state,
                    onForgetTrustedRuntime = onForgetTrustedRuntime,
                )
                if (settingsShowsPairingConnectButton(state)) {
                    PairingConnectButton(
                        state = state,
                        onConnect = onConnect,
                        onScanLatestQr = onScanPairingQr,
                    )
                }
                if (state.trustedRuntime == null) {
                    EmptyState(text = stringResource(R.string.connect_requires_pairing))
                }
                ConnectionStatusPanel(
                    state = state,
                    onConnect = onConnect,
                    onScanLatestQr = onScanPairingQr,
                )
                ConnectionStatusActions(
                    state = state,
                    onRefreshHealth = onRefreshHealth,
                    onDisconnect = onDisconnect,
                )
                AutoReconnectSettingRow(
                    enabled = state.trustedRuntimeAutoReconnectEnabled,
                    canChange = state.trustedRuntime != null,
                    onSetAutoReconnectEnabled = onSetAutoReconnectEnabled,
                )
            }
        }
        item {
            AppPreferencesPanel(
                selectedLanguageTag = state.selectedLanguageTag,
                onSetLanguageTag = onSetLanguageTag,
                selectedTheme = state.selectedTheme,
                onSetTheme = onSetTheme,
                showLanguageSelector = state.trustedRuntime != null,
            )
        }
        if (settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics)) {
            item {
                SettingsExpandableSection(
                    title = R.string.advanced_connection,
                    subtitle = R.string.advanced_connection_detail,
                ) {
                    DiscoveryPanel(
                        state = state,
                        onStartDiscovery = onStartDiscovery,
                        onStopDiscovery = onStopDiscovery,
                        onUseDiscoveredRuntime = onUseDiscoveredRuntime,
                    )
                    DeveloperDiagnosticsPanel(
                        state = state,
                        onHostChange = onHostChange,
                        onPortChange = onPortChange,
                        onUseUsbReverse = onUseUsbReverse,
                        onUseEmulator = onUseEmulator,
                        onSubmitPairingPayload = onSubmitPairingPayload,
                    )
                }
            }
        }
        item {
            SettingsExpandableSection(
                title = R.string.embedding_model_title,
                subtitle = R.string.embedding_model_subtitle,
                initiallyExpanded = settingsLowerPrioritySectionInitiallyExpanded(),
            ) {
                EmbeddingModelPanel(
                    state = state,
                    onRequestModels = onRequestModels,
                    onSelectEmbeddingModel = onSelectEmbeddingModel,
                    showHeader = false,
                )
            }
        }
        item {
            SettingsExpandableSection(
                title = R.string.memory_title,
                subtitle = R.string.memory_subtitle,
                initiallyExpanded = settingsLowerPrioritySectionInitiallyExpanded(),
            ) {
                MemoryPanel(
                    entries = state.memoryEntries,
                    actionsEnabled = memoryActionsEnabled(state),
                    onAddMemoryEntry = onAddMemoryEntry,
                    onRemoveMemoryEntry = onRemoveMemoryEntry,
                    onSetMemoryEntryEnabled = onSetMemoryEntryEnabled,
                    showHeader = false,
                )
            }
        }
        item {
            SettingsExpandableSection(
                title = R.string.chat_history_settings_title,
                subtitle = R.string.chat_history_settings_subtitle,
                initiallyExpanded = settingsLowerPrioritySectionInitiallyExpanded(),
            ) {
                ChatHistorySettingsPanel(
                    activeSessions = state.chatSessions,
                    archivedSessions = state.archivedChatSessions,
                    isActionEnabled = !state.isStreaming,
                    onArchiveChatSession = onArchiveChatSession,
                    onRestoreChatSession = onRestoreChatSession,
                    onPermanentlyDeleteChatSession = onPermanentlyDeleteChatSession,
                    onArchiveAllChatSessions = onArchiveAllChatSessions,
                    onPermanentlyDeleteArchivedChatSessions = onPermanentlyDeleteArchivedChatSessions,
                    showHeader = false,
                )
            }
        }
        item {
            ErrorText(
                error = state.error,
                routeAction = routeNoticePrimaryAction(state),
                onConnect = onConnect,
                onScanLatestQr = onScanPairingQr,
            )
        }
    }
}

internal fun settingsScreenShowsGenericHeader(state: RuntimeUiState): Boolean {
    return state.trustedRuntime != null && !state.isPairingAwaitingRoute
}

@StringRes
internal fun settingsPrimaryConnectionSectionTitleRes(state: RuntimeUiState): Int {
    return if (settingsScreenShowsGenericHeader(state)) {
        R.string.status_title
    } else {
        R.string.pairing_title
    }
}

@StringRes
internal fun settingsPrimaryConnectionSectionSubtitleRes(state: RuntimeUiState): Int {
    return if (settingsScreenShowsGenericHeader(state)) {
        R.string.status_subtitle
    } else {
        R.string.pairing_subtitle
    }
}

internal fun settingsPrimaryConnectionSectionInitiallyExpanded(state: RuntimeUiState): Boolean {
    return !state.isConnected ||
        state.trustedRuntime == null ||
        state.isPairingAwaitingRoute
}

internal fun settingsPrimaryConnectionSectionExpansionKey(state: RuntimeUiState): String {
    return when {
        state.trustedRuntime == null -> "pairing-required"
        state.isPairingAwaitingRoute -> "pairing-route:${state.pendingPairingRuntimeName.orEmpty()}"
        else -> "trusted:${state.trustedRuntime.deviceId}"
    }
}

internal fun settingsShowsPairingConnectButton(state: RuntimeUiState): Boolean {
    return !state.isConnected && state.trustedRuntime != null
}

internal fun settingsSectionExpandedStateDescriptionRes(): Int = R.string.section_state_expanded

internal fun settingsSectionCollapsedStateDescriptionRes(): Int = R.string.section_state_collapsed

internal fun settingsLowerPrioritySectionInitiallyExpanded(): Boolean = false

internal fun settingsScreenShowsTroubleshootingSection(showDeveloperDiagnostics: Boolean): Boolean {
    return showDeveloperDiagnostics
}

@Composable
private fun AutoReconnectSettingRow(
    enabled: Boolean,
    canChange: Boolean,
    onSetAutoReconnectEnabled: (Boolean) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val autoReconnectContentDescription = stringResource(R.string.auto_reconnect)
    val autoReconnectStateDescription = stringResource(
        if (enabled) {
            R.string.setting_state_on
        } else {
            R.string.setting_state_off
        },
    )
    val autoReconnectActionLabel = stringResource(
        if (enabled) {
            R.string.setting_action_disable_named
        } else {
            R.string.setting_action_enable_named
        },
        autoReconnectContentDescription,
    )

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = stringResource(R.string.auto_reconnect),
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                )
                Text(
                    text = stringResource(R.string.auto_reconnect_detail),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            Switch(
                checked = enabled,
                onCheckedChange = { checked ->
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                    onSetAutoReconnectEnabled(checked)
                },
                enabled = canChange,
                modifier = Modifier.semantics {
                    contentDescription = autoReconnectContentDescription
                    stateDescription = autoReconnectStateDescription
                    onClick(label = autoReconnectActionLabel) {
                        if (!canChange) {
                            false
                        } else {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                            onSetAutoReconnectEnabled(!enabled)
                            true
                        }
                    }
                },
            )
        }
    }
}

@Composable
private fun ScreenList(
    modifier: Modifier,
    content: androidx.compose.foundation.lazy.LazyListScope.() -> Unit,
) {
    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .padding(horizontal = 20.dp, vertical = 16.dp),
        verticalArrangement = Arrangement.spacedBy(14.dp),
        contentPadding = PaddingValues(bottom = 24.dp),
        content = content,
    )
}

@Composable
private fun ScreenHeader(
    @StringRes title: Int,
    @StringRes subtitle: Int? = null,
) {
    Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
        Text(
            text = stringResource(title),
            style = MaterialTheme.typography.headlineSmall,
            fontWeight = FontWeight.SemiBold,
        )
        subtitle?.let {
            Text(
                text = stringResource(it),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
    }
}

@Composable
private fun SettingsExpandableSection(
    @StringRes title: Int,
    @StringRes subtitle: Int,
    initiallyExpanded: Boolean = false,
    expandWhenKey: String? = null,
    content: @Composable ColumnScope.() -> Unit,
) {
    val isExpanded = rememberSaveable { mutableStateOf(initiallyExpanded) }
    val hapticFeedback = LocalHapticFeedback.current
    LaunchedEffect(expandWhenKey, initiallyExpanded) {
        if (initiallyExpanded) {
            isExpanded.value = true
        }
    }
    val toggleExpanded = {
        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
        isExpanded.value = !isExpanded.value
    }
    val toggleStateDescription = stringResource(
        if (isExpanded.value) {
            settingsSectionExpandedStateDescriptionRes()
        } else {
            settingsSectionCollapsedStateDescriptionRes()
        },
    )
    val toggleActionLabel = stringResource(
        if (isExpanded.value) {
            R.string.collapse_section
        } else {
            R.string.expand_section
        },
    )

    Column(
        modifier = Modifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        HorizontalDivider()
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable(
                    role = Role.Button,
                    onClickLabel = toggleActionLabel,
                    onClick = { toggleExpanded() },
                )
                .semantics(mergeDescendants = true) {
                    stateDescription = toggleStateDescription
                }
                .padding(vertical = 4.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = stringResource(title),
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Medium,
                )
                Text(
                    text = stringResource(subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            Spacer(Modifier.width(12.dp))
            FilledTonalIconButton(
                onClick = { toggleExpanded() },
                modifier = Modifier.clearAndSetSemantics {},
            ) {
                Icon(
                    imageVector = if (isExpanded.value) {
                        Icons.Filled.KeyboardArrowUp
                    } else {
                        Icons.Filled.KeyboardArrowDown
                    },
                    contentDescription = null,
                )
            }
        }
        if (isExpanded.value) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(12.dp),
            ) {
                Column(
                    modifier = Modifier.fillMaxWidth(),
                    verticalArrangement = Arrangement.spacedBy(12.dp),
                    content = content,
                )
            }
        }
    }
}

@Composable
private fun TrustedRuntimePanel(
    state: RuntimeUiState,
    onForgetTrustedRuntime: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    var showForgetConfirmation by rememberSaveable { mutableStateOf(false) }
    val trustedRuntime = state.trustedRuntime
    val forgetTrustedRuntimeContentDescription = trustedRuntime?.let { runtime ->
        stringResource(R.string.forget_trusted_runtime_named, runtime.name)
    }

    if (trustedRuntime != null && showForgetConfirmation) {
        AlertDialog(
            onDismissRequest = { showForgetConfirmation = false },
            title = { Text(stringResource(R.string.forget_trusted_runtime_confirm_title)) },
            text = { Text(stringResource(R.string.forget_trusted_runtime_confirm_message)) },
            confirmButton = {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                        showForgetConfirmation = false
                        onForgetTrustedRuntime()
                    },
                ) {
                    Text(stringResource(R.string.forget_trusted_runtime_confirm_action))
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                        showForgetConfirmation = false
                    },
                ) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(
                    imageVector = if (state.trustedRuntime != null) Icons.Filled.CheckCircle else Icons.Filled.Link,
                    contentDescription = if (state.trustedRuntime != null) {
                        stringResource(R.string.trusted_runtime)
                    } else {
                        stringResource(R.string.no_trusted_runtime)
                    },
                    tint = if (state.trustedRuntime != null) {
                        MaterialTheme.colorScheme.primary
                    } else {
                        MaterialTheme.colorScheme.secondary
                    },
                )
                Spacer(Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.trusted_runtime),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                    Text(
                        text = state.trustedRuntime?.name ?: stringResource(R.string.no_trusted_runtime),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            state.trustedRuntime?.let {
                OutlinedButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        showForgetConfirmation = true
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            forgetTrustedRuntimeContentDescription?.let { contentDescription = it }
                        },
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.forget))
                }
            } ?: Text(
                text = stringResource(R.string.trusted_runtime_detail),
                color = MaterialTheme.colorScheme.secondary,
                style = MaterialTheme.typography.bodyMedium,
            )
        }
    }
}

@Composable
private fun DeveloperDiagnosticsPanel(
    state: RuntimeUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onUseUsbReverse: () -> Unit,
    onUseEmulator: () -> Unit,
    onSubmitPairingPayload: (String) -> Unit,
) {
    val isEnabled = rememberSaveable { mutableStateOf(false) }
    var showManualPayloadDialog by rememberSaveable { mutableStateOf(false) }
    val hapticFeedback = LocalHapticFeedback.current
    val diagnosticsContentDescription = stringResource(R.string.developer_routes_title)
    val toggleDeveloperDiagnostics = {
        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
        isEnabled.value = !isEnabled.value
    }
    val diagnosticsStateDescription = stringResource(
        if (isEnabled.value) {
            R.string.setting_state_on
        } else {
            R.string.setting_state_off
        },
    )
    val diagnosticsActionLabel = stringResource(
        if (isEnabled.value) {
            R.string.setting_action_disable_named
        } else {
            R.string.setting_action_enable_named
        },
        diagnosticsContentDescription,
    )

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(DEVELOPER_DIAGNOSTICS_TOGGLE_ROW_TAG)
                    .clickable(
                        role = Role.Switch,
                        onClickLabel = diagnosticsActionLabel,
                    ) {
                        toggleDeveloperDiagnostics()
                    },
                horizontalArrangement = Arrangement.spacedBy(12.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = stringResource(R.string.developer_routes_title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                    )
                    Text(
                        text = stringResource(R.string.developer_routes_detail),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
                Switch(
                    modifier = Modifier
                        .testTag(
                            if (isEnabled.value) {
                                DEVELOPER_DIAGNOSTICS_SWITCH_ENABLED_TAG
                            } else {
                                DEVELOPER_DIAGNOSTICS_SWITCH_DISABLED_TAG
                            },
                        )
                        .semantics {
                            contentDescription = diagnosticsContentDescription
                            stateDescription = diagnosticsStateDescription
                            onClick(label = diagnosticsActionLabel) {
                                toggleDeveloperDiagnostics()
                                true
                            }
                        },
                    checked = isEnabled.value,
                    onCheckedChange = { checked ->
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                        isEnabled.value = checked
                    },
                )
            }
            if (isEnabled.value) {
                OutlinedButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        showManualPayloadDialog = true
                    },
                    modifier = Modifier.fillMaxWidth(),
                ) {
                    Icon(
                        Icons.Filled.ContentCopy,
                        contentDescription = null,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.enter_qr_payload))
                }
                EndpointPanel(
                    state = state,
                    onHostChange = onHostChange,
                    onPortChange = onPortChange,
                    onUseUsbReverse = onUseUsbReverse,
                    onUseEmulator = onUseEmulator,
                    title = R.string.runtime_endpoint,
                )
            }
        }
    }

    if (showManualPayloadDialog) {
        ManualPairingPayloadDialog(
            onDismiss = { showManualPayloadDialog = false },
            onSubmit = { rawValue ->
                showManualPayloadDialog = false
                onSubmitPairingPayload(rawValue)
            },
        )
    }
}

@Composable
private fun EndpointPanel(
    state: RuntimeUiState,
    onHostChange: (String) -> Unit,
    onPortChange: (String) -> Unit,
    onUseUsbReverse: () -> Unit,
    onUseEmulator: () -> Unit,
    @StringRes title: Int = R.string.advanced_connection,
) {
    val isExpanded = rememberSaveable { mutableStateOf(false) }
    val hapticFeedback = LocalHapticFeedback.current
    val toggleExpanded = {
        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
        isExpanded.value = !isExpanded.value
    }
    val toggleContentDescription = stringResource(title)
    val toggleStateDescription = stringResource(
        if (isExpanded.value) {
            settingsSectionExpandedStateDescriptionRes()
        } else {
            settingsSectionCollapsedStateDescriptionRes()
        },
    )
    val toggleActionLabel = stringResource(
        if (isExpanded.value) {
            R.string.hide_advanced_connection
        } else {
            R.string.show_advanced_connection
        },
    )

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable(
                        role = Role.Button,
                        onClickLabel = toggleActionLabel,
                        onClick = { toggleExpanded() },
                    )
                    .semantics(mergeDescendants = true) {
                        contentDescription = toggleContentDescription
                        stateDescription = toggleStateDescription
                    },
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(4.dp),
                ) {
                    Text(
                        text = stringResource(title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                    )
                    Text(
                        text = stringResource(R.string.advanced_connection_detail),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
                Spacer(Modifier.width(12.dp))
                FilledTonalIconButton(
                    onClick = { toggleExpanded() },
                    modifier = Modifier.clearAndSetSemantics {},
                ) {
                    Icon(
                        imageVector = if (isExpanded.value) {
                            Icons.Filled.KeyboardArrowUp
                        } else {
                            Icons.Filled.KeyboardArrowDown
                        },
                        contentDescription = null,
                    )
                }
            }
            if (isExpanded.value) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onUseUsbReverse()
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(
                            Icons.Filled.Link,
                            contentDescription = null,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.usb_reverse))
                    }
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onUseEmulator()
                        },
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Icon(
                            Icons.Filled.Settings,
                            contentDescription = null,
                        )
                        Spacer(Modifier.width(8.dp))
                        Text(stringResource(R.string.emulator))
                    }
                }
                OutlinedTextField(
                    value = state.runtimeHost,
                    onValueChange = onHostChange,
                    label = { Text(stringResource(R.string.runtime_host)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
                OutlinedTextField(
                    value = state.runtimePort,
                    onValueChange = onPortChange,
                    label = { Text(stringResource(R.string.runtime_port)) },
                    keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                )
            }
        }
    }
}

@Composable
private fun DiscoveryPanel(
    state: RuntimeUiState,
    onStartDiscovery: () -> Unit,
    onStopDiscovery: () -> Unit,
    onUseDiscoveredRuntime: (RuntimeDiscoveredRuntime) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val startDiscoveryStateDescription = stringResource(
        if (state.isDiscovering) {
            R.string.discover_runtimes_state_running
        } else {
            R.string.discover_runtimes_state_ready
        },
    )
    val stopDiscoveryStateDescription = stringResource(
        if (state.isDiscovering) {
            R.string.stop_discovery_state_ready
        } else {
            R.string.stop_discovery_state_idle
        },
    )

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.discovered_runtimes),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Medium,
            )
            Text(
                text = stringResource(R.string.discovery_detail),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Button(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        onStartDiscovery()
                    },
                    enabled = !state.isDiscovering,
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            stateDescription = startDiscoveryStateDescription
                        },
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = if (state.isDiscovering) {
                            stringResource(R.string.discovering_runtimes)
                        } else {
                            stringResource(R.string.discover_runtimes)
                        },
                    )
                }
                OutlinedButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                        onStopDiscovery()
                    },
                    enabled = state.isDiscovering,
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            stateDescription = stopDiscoveryStateDescription
                        },
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(stringResource(R.string.stop))
                }
            }
            if (state.isDiscovering) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            if (state.discoveredRuntimes.isEmpty()) {
                EmptyState(text = stringResource(R.string.no_discovered_runtimes))
            } else {
                LazyColumn(
                    modifier = Modifier.heightIn(max = 220.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp),
                ) {
                    items(state.discoveredRuntimes) { peer ->
                        DiscoveredRuntimeRow(
                            peer = peer,
                            trustedRuntime = state.trustedRuntime,
                            onUse = onUseDiscoveredRuntime,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun DiscoveredRuntimeRow(
    peer: RuntimeDiscoveredRuntime,
    trustedRuntime: RuntimeTrustedRuntime?,
    onUse: (RuntimeDiscoveredRuntime) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val identityStatus = peer.identityStatus(trustedRuntime)
    val hasAdvertisedIdentity = peer.hasAdvertisedIdentity()
    val canUseDiscoveredRoute = discoveredRuntimeSelectable(peer, trustedRuntime)
    val identityStatusLabel = stringResource(identityStatus.labelRes(hasAdvertisedIdentity))
    val routeUnavailableLabel = stringResource(identityStatus.routeUnavailableLabelRes())
    val routeUnavailableSummary = stringResource(
        R.string.discovered_runtime_unavailable_summary,
        peer.serviceName,
        identityStatusLabel,
        routeUnavailableLabel,
    )
    val discoveredRuntimeActionContentDescription = stringResource(
        R.string.use_trusted_connection_named,
        peer.serviceName,
    )

    Card(
        modifier = Modifier.fillMaxWidth(),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(8.dp),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = peer.serviceName,
                    style = MaterialTheme.typography.titleSmall,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = stringResource(R.string.runtime_route_local_discovery),
                    color = MaterialTheme.colorScheme.secondary,
                    style = MaterialTheme.typography.bodySmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = identityStatusLabel,
                    color = when (identityStatus) {
                        DiscoveredRuntimeIdentityStatus.TrustedMatch -> MaterialTheme.colorScheme.primary
                        DiscoveredRuntimeIdentityStatus.DifferentTrustedRuntime -> MaterialTheme.colorScheme.error
                        DiscoveredRuntimeIdentityStatus.Unknown -> MaterialTheme.colorScheme.secondary
                    },
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            if (canUseDiscoveredRoute) {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        onUse(peer)
                    },
                    modifier = Modifier.semantics {
                        contentDescription = discoveredRuntimeActionContentDescription
                    },
                ) {
                    Text(stringResource(discoveredRuntimeActionLabelRes(peer, trustedRuntime)))
                }
            } else {
                Text(
                    text = routeUnavailableLabel,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.semantics {
                        contentDescription = routeUnavailableSummary
                    },
                )
            }
        }
    }
}

private enum class DiscoveredRuntimeIdentityStatus {
    TrustedMatch,
    Unknown,
    DifferentTrustedRuntime;

    @StringRes
    fun labelRes(hasAdvertisedIdentity: Boolean): Int = when (this) {
        TrustedMatch -> R.string.discovery_identity_trusted_match
        Unknown -> if (hasAdvertisedIdentity) {
            R.string.discovery_identity_unknown
        } else {
            R.string.discovery_identity_not_advertised
        }
        DifferentTrustedRuntime -> R.string.discovery_identity_different_trusted_runtime
    }
}

private fun DiscoveredRuntimeIdentityStatus.routeUnavailableLabelRes(): Int = when (this) {
    DiscoveredRuntimeIdentityStatus.TrustedMatch -> R.string.use_trusted_connection
    DiscoveredRuntimeIdentityStatus.Unknown -> R.string.discovery_route_qr_required
    DiscoveredRuntimeIdentityStatus.DifferentTrustedRuntime -> R.string.discovery_route_not_trusted
}

@StringRes
internal fun discoveredRuntimeActionLabelRes(
    peer: RuntimeDiscoveredRuntime,
    trustedRuntime: RuntimeTrustedRuntime?,
): Int {
    return if (discoveredRuntimeSelectable(peer, trustedRuntime)) {
        R.string.use_trusted_connection
    } else {
        peer.identityStatus(trustedRuntime).routeUnavailableLabelRes()
    }
}

internal fun discoveredRuntimeSelectable(
    peer: RuntimeDiscoveredRuntime,
    trustedRuntime: RuntimeTrustedRuntime?,
): Boolean {
    return peer.identityStatus(trustedRuntime) == DiscoveredRuntimeIdentityStatus.TrustedMatch
}

private fun RuntimeDiscoveredRuntime.identityStatus(trustedRuntime: RuntimeTrustedRuntime?): DiscoveredRuntimeIdentityStatus {
    val discoveredRouteToken = routeToken.normalizedIdentityValue()
    val discoveredDeviceId = deviceId.normalizedIdentityValue()
    val discoveredFingerprint = fingerprint.normalizedIdentityValue()

    if (discoveredRouteToken == null && discoveredDeviceId == null && discoveredFingerprint == null) {
        return DiscoveredRuntimeIdentityStatus.Unknown
    }
    if (trustedRuntime == null) {
        return DiscoveredRuntimeIdentityStatus.Unknown
    }

    val trustedRouteToken = trustedRuntime.routeToken.normalizedIdentityValue()
    val trustedDeviceId = trustedRuntime.deviceId.normalizedIdentityValue()
    val trustedFingerprint = trustedRuntime.fingerprint.normalizedIdentityValue()
    val routeTokenMatches = discoveredRouteToken != null && discoveredRouteToken == trustedRouteToken
    val deviceIdMatches = discoveredDeviceId != null && discoveredDeviceId == trustedDeviceId
    val fingerprintMatches = discoveredFingerprint != null && discoveredFingerprint == trustedFingerprint
    val routeTokenDiffers = discoveredRouteToken != null &&
        trustedRouteToken != null &&
        discoveredRouteToken != trustedRouteToken
    val deviceIdDiffers = discoveredDeviceId != null && trustedDeviceId != null && discoveredDeviceId != trustedDeviceId
    val fingerprintDiffers = discoveredFingerprint != null &&
        trustedFingerprint != null &&
        discoveredFingerprint != trustedFingerprint

    return when {
        routeTokenMatches -> DiscoveredRuntimeIdentityStatus.TrustedMatch
        routeTokenDiffers -> DiscoveredRuntimeIdentityStatus.DifferentTrustedRuntime
        (deviceIdMatches || fingerprintMatches) && !routeTokenDiffers && !fingerprintDiffers && !deviceIdDiffers -> {
            DiscoveredRuntimeIdentityStatus.TrustedMatch
        }
        deviceIdDiffers || fingerprintDiffers -> DiscoveredRuntimeIdentityStatus.DifferentTrustedRuntime
        else -> DiscoveredRuntimeIdentityStatus.Unknown
    }
}

private fun RuntimeDiscoveredRuntime.hasAdvertisedIdentity(): Boolean =
    routeToken.normalizedIdentityValue() != null ||
        deviceId.normalizedIdentityValue() != null ||
        fingerprint.normalizedIdentityValue() != null

private fun String?.normalizedIdentityValue(): String? = this?.trim()?.takeUnless { it.isEmpty() }

@Composable
private fun ChatEmptyState(
    state: RuntimeUiState,
    onConnect: () -> Unit,
    onScanPairingQr: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val preferQrRouteRefresh = shouldScanLatestQrFromEmptyChat(state)
    val primaryAction = chatEmptyPrimaryAction(state)
    val emptyTitle = chatEmptyTitle(state, preferQrRouteRefresh)
    val emptyBody = chatEmptyText(state, preferQrRouteRefresh)
    val emptyAccessibilitySummary = stringResource(
        R.string.chat_empty_state_accessibility_summary,
        emptyTitle,
        emptyBody,
    )
    val statusIcon = when {
        !state.isConnected -> Icons.Filled.Link
        state.isStreaming -> Icons.Filled.Refresh
        selectedModelIsUsable(state) -> Icons.Filled.CheckCircle
        else -> Icons.Filled.Search
    }

    Column(
        modifier = Modifier
            .widthIn(max = 460.dp)
            .fillMaxWidth()
            .padding(horizontal = 20.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        horizontalAlignment = Alignment.CenterHorizontally,
    ) {
        Icon(
            imageVector = statusIcon,
            contentDescription = null,
            tint = MaterialTheme.colorScheme.secondary.copy(alpha = 0.78f),
            modifier = Modifier.size(30.dp),
        )
        Column(
            modifier = Modifier.semantics(mergeDescendants = true) {
                contentDescription = emptyAccessibilitySummary
                if (preferQrRouteRefresh) {
                    liveRegion = LiveRegionMode.Polite
                }
            },
            verticalArrangement = Arrangement.spacedBy(4.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
        ) {
            Text(
                text = emptyTitle,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                textAlign = TextAlign.Center,
            )
            Text(
                text = emptyBody,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
                textAlign = TextAlign.Center,
            )
        }
        if (state.isStreaming) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
        if (primaryAction != null) {
            val primaryActionStateDescription = chatEmptyPrimaryActionStateDescription(state, primaryAction)
            val primaryActionLabel = when (primaryAction) {
                ChatEmptyPrimaryAction.Connect -> connectRuntimeActionLabel(state)
                ChatEmptyPrimaryAction.ScanQr -> stringResource(chatEmptyScanActionLabelRes(state))
            }
            Button(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    when (primaryAction) {
                        ChatEmptyPrimaryAction.Connect -> onConnect()
                        ChatEmptyPrimaryAction.ScanQr -> onScanPairingQr()
                    }
                },
                enabled = !state.isConnecting,
                modifier = Modifier.semantics {
                    stateDescription = primaryActionStateDescription
                },
            ) {
                Icon(Icons.Filled.Link, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(
                    text = primaryActionLabel,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun quickModelStatus(model: RuntimeModel, installing: Boolean): String {
    return when {
        installing -> stringResource(R.string.installing_model)
        !model.installed -> stringResource(R.string.model_not_installed)
        model.running -> stringResource(R.string.model_running)
        else -> stringResource(R.string.model_installed)
    }
}

@Composable
private fun ChatMessageRow(
    message: RuntimeChatMessage,
    isStreaming: Boolean,
    showSuggestions: Boolean,
    isLoadingSuggestions: Boolean,
    onSuggestionClick: (String) -> Unit,
) {
    val isUser = message.role == "user"
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        if (isUser) {
            Column(
                modifier = Modifier.widthIn(max = 548.dp),
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Surface(
                    modifier = Modifier.copyOnLongPress(message.content),
                    shape = RoundedCornerShape(
                        topStart = 18.dp,
                        topEnd = 6.dp,
                        bottomStart = 18.dp,
                        bottomEnd = 18.dp,
                    ),
                    color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
                    contentColor = MaterialTheme.colorScheme.onSurface,
                ) {
                    MessageContent(
                        content = message.content,
                        textColor = MaterialTheme.colorScheme.onSurface,
                        modifier = Modifier.padding(horizontal = 15.dp, vertical = 10.dp),
                    )
                }
                ReadOnlyAttachmentChips(
                    attachments = message.attachments,
                )
            }
        } else {
            AssistantMessage(
                message = message,
                isStreaming = isStreaming,
                showSuggestions = showSuggestions,
                isLoadingSuggestions = isLoadingSuggestions,
                onSuggestionClick = onSuggestionClick,
            )
        }
    }
}

@Composable
private fun AssistantMessage(
    message: RuntimeChatMessage,
    isStreaming: Boolean,
    showSuggestions: Boolean,
    isLoadingSuggestions: Boolean,
    onSuggestionClick: (String) -> Unit,
) {
    val hasReasoning = message.reasoning.isNotBlank()
    var isReasoningExpanded by rememberSaveable(message.id) { mutableStateOf(false) }
    val showTyping = assistantShowsTypingPlaceholder(message, isStreaming)
    val assistantTypingText = stringResource(R.string.assistant_typing)

    Column(
        modifier = Modifier
            .widthIn(max = 720.dp)
            .fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (hasReasoning) {
            AssistantReasoning(
                reasoning = message.reasoning,
                expanded = isReasoningExpanded,
                onExpandedChange = { isReasoningExpanded = it },
            )
        }
        if (message.content.isNotBlank() || showTyping) {
            val visibleContent = if (showTyping && message.content.isBlank()) {
                assistantTypingText
            } else {
                message.content
            }
            var contentModifier = Modifier.padding(horizontal = 2.dp)
            if (showTyping) {
                contentModifier = contentModifier.semantics {
                    liveRegion = LiveRegionMode.Polite
                    contentDescription = assistantTypingText
                }
            }
            contentModifier = contentModifier.copyOnLongPress(message.content)
            MessageContent(
                content = visibleContent,
                textColor = MaterialTheme.colorScheme.onSurface,
                modifier = contentModifier,
            )
        }
        ReadOnlyAttachmentChips(
            attachments = message.attachments,
        )
        if (showTyping) {
            LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        }
        if (showSuggestions) {
            SuggestedQuestions(
                suggestions = message.suggestions,
                isLoading = isLoadingSuggestions,
                onSuggestionClick = onSuggestionClick,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun SuggestedQuestions(
    suggestions: List<String>,
    isLoading: Boolean,
    onSuggestionClick: (String) -> Unit,
) {
    val visibleSuggestions = normalizedSuggestedQuestions(suggestions)
    if (visibleSuggestions.isEmpty() && !isLoading) return

    val hapticFeedback = LocalHapticFeedback.current
    val generatingSuggestionsText = stringResource(R.string.generating_suggestions)
    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Text(
            text = stringResource(R.string.suggested_next_questions),
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
        )
        if (isLoading && visibleSuggestions.isEmpty()) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        liveRegion = LiveRegionMode.Polite
                        contentDescription = generatingSuggestionsText
                    },
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                LinearProgressIndicator(modifier = Modifier.weight(1f))
                Text(
                    text = generatingSuggestionsText,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
        if (visibleSuggestions.isNotEmpty()) {
            FlowRow(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                visibleSuggestions.forEach { suggestion ->
                    SuggestedQuestionChip(
                        text = suggestion,
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onSuggestionClick(suggestion)
                        },
                    )
                }
            }
        }
    }
}

@Composable
private fun SuggestedQuestionChip(
    text: String,
    onClick: () -> Unit,
) {
    val suggestionContentDescription = stringResource(R.string.content_desc_suggested_question, text)
    val suggestionClickLabel = stringResource(R.string.action_use_suggested_question)
    Surface(
        modifier = Modifier
            .widthIn(min = 120.dp, max = 360.dp)
            .clickable(
                onClickLabel = suggestionClickLabel,
                role = Role.Button,
                onClick = onClick,
            )
            .semantics {
                contentDescription = suggestionContentDescription
            },
        shape = RoundedCornerShape(18.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.58f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Text(
            text = text,
            style = MaterialTheme.typography.bodySmall,
            maxLines = SUGGESTED_QUESTION_MAX_LINES,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp),
        )
    }
}

internal fun suggestedQuestionMaxLines(): Int = SUGGESTED_QUESTION_MAX_LINES

internal fun normalizedSuggestedQuestions(
    suggestions: List<String>,
    maxItems: Int = SUGGESTED_QUESTION_MAX_ITEMS,
): List<String> {
    val seen = linkedSetOf<String>()
    return suggestions
        .asSequence()
        .map { suggestion ->
            suggestion.trim().replace(Regex("\\s+"), " ")
        }
        .filter { it.isNotBlank() }
        .filter { seen.add(it.lowercase(Locale.ROOT)) }
        .take(maxItems)
        .toList()
}

@Composable
private fun MessageContent(
    content: String,
    textColor: androidx.compose.ui.graphics.Color,
    modifier: Modifier = Modifier,
) {
    val parts = parseMessageContent(content)
    val codeBlockCount = parts.count { it is MessageContentPart.Code }
    var codeBlockIndex = 0

    Column(
        modifier = modifier,
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        parts.forEach { part ->
            when (part) {
                is MessageContentPart.Text -> {
                    Text(
                        text = part.text,
                        style = MaterialTheme.typography.bodyLarge,
                        color = textColor,
                    )
                }
                is MessageContentPart.Code -> {
                    codeBlockIndex += 1
                    CodeBlock(
                        code = part.code,
                        language = part.language,
                        index = codeBlockIndex,
                        count = codeBlockCount,
                    )
                }
            }
        }
    }
}

@Composable
private fun CodeBlock(
    code: String,
    language: String?,
    index: Int,
    count: Int,
) {
    val trimmedLanguage = language?.trim().orEmpty()
    val copyCodeBlockLabel = when {
        count <= 1 -> stringResource(R.string.copy_code_block)
        trimmedLanguage.isNotBlank() -> stringResource(R.string.copy_code_block_named, trimmedLanguage, index)
        else -> stringResource(R.string.copy_code_block_numbered, index)
    }
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                if (language != null) {
                    Text(
                        text = language,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.weight(1f),
                    )
                } else {
                    Spacer(modifier = Modifier.weight(1f))
                }
                if (code.isNotBlank()) {
                    MessageCopyButton(
                        textToCopy = code,
                        copyActionLabel = copyCodeBlockLabel,
                    )
                }
            }
            Text(
                text = code,
                style = MaterialTheme.typography.bodySmall,
                fontFamily = FontFamily.Monospace,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
                softWrap = false,
                modifier = Modifier
                    .fillMaxWidth()
                    .horizontalScroll(rememberScrollState()),
            )
        }
    }
}

@Composable
private fun MessageCopyButton(
    textToCopy: String,
    copyActionLabel: String,
) {
    val clipboard = LocalClipboard.current
    val context = LocalContext.current
    val hapticFeedback = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()
    val copiedMessage = stringResource(R.string.message_copied)
    val announceCopySuccess = LocalCopySuccessAnnouncer.current

    TextButton(
        onClick = {
            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Clipboard)
            scope.launch {
                clipboard.setClipEntry(ClipEntry(ClipData.newPlainText("AetherLink", textToCopy)))
                announceCopySuccess(copiedMessage)
                Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()
            }
        },
        enabled = textToCopy.isNotBlank(),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
        modifier = Modifier.semantics {
            contentDescription = copyActionLabel
            onClick(label = copyActionLabel, action = null)
        },
    ) {
        Icon(
            imageVector = Icons.Filled.ContentCopy,
            contentDescription = null,
            modifier = Modifier.size(16.dp),
        )
    }
}

@Composable
private fun Modifier.copyOnLongPress(textToCopy: String): Modifier {
    if (textToCopy.isBlank()) return this

    val clipboard = LocalClipboard.current
    val context = LocalContext.current
    val hapticFeedback = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()
    val copiedMessage = stringResource(R.string.message_copied)
    val copyActionLabel = stringResource(R.string.copy_message)
    val announceCopySuccess = LocalCopySuccessAnnouncer.current
    val copyAction = {
        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Clipboard)
        scope.launch {
            clipboard.setClipEntry(ClipEntry(ClipData.newPlainText("AetherLink", textToCopy)))
            announceCopySuccess(copiedMessage)
            Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()
        }
        Unit
    }

    return this
        .pointerInput(textToCopy, copiedMessage) {
            detectTapGestures(onLongPress = { copyAction() })
        }
        .semantics {
            onLongClick(label = copyActionLabel) {
                copyAction()
                true
            }
        }
}

internal sealed interface MessageContentPart {
    data class Text(val text: String) : MessageContentPart
    data class Code(val language: String?, val code: String) : MessageContentPart
}

internal fun parseMessageContent(content: String): List<MessageContentPart> {
    val parts = mutableListOf<MessageContentPart>()
    var cursor = 0

    while (cursor < content.length) {
        val fenceStart = content.indexOf("```", startIndex = cursor)
        if (fenceStart == -1) {
            addTextPart(parts, content.substring(cursor))
            break
        }

        addTextPart(parts, content.substring(cursor, fenceStart))

        val languageStart = fenceStart + 3
        val languageEnd = content.indexOf('\n', startIndex = languageStart)
        if (languageEnd == -1) {
            addTextPart(parts, content.substring(fenceStart))
            break
        }

        val language = content
            .substring(languageStart, languageEnd)
            .trim()
            .takeIf { it.isNotEmpty() }
        val codeStart = languageEnd + 1
        val fenceEnd = content.indexOf("```", startIndex = codeStart)

        if (fenceEnd == -1) {
            parts += MessageContentPart.Code(
                language = language,
                code = content.substring(codeStart).trimEnd('\n'),
            )
            break
        }

        parts += MessageContentPart.Code(
            language = language,
            code = content.substring(codeStart, fenceEnd).trimEnd('\n'),
        )
        cursor = fenceEnd + 3
        if (cursor < content.length && content[cursor] == '\n') {
            cursor += 1
        }
    }

    return parts.ifEmpty { listOf(MessageContentPart.Text(content)) }
}

private fun addTextPart(
    parts: MutableList<MessageContentPart>,
    text: String,
) {
    val trimmed = text.trim('\n')
    if (trimmed.isNotBlank()) {
        parts += MessageContentPart.Text(trimmed)
    }
}

private fun List<RuntimeChatMessage>.lastAssistantMessageId(): String? {
    return lastOrNull { it.role == "assistant" }?.id
}

@Composable
private fun AssistantReasoning(
    reasoning: String,
    expanded: Boolean,
    onExpandedChange: (Boolean) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val displayPolicy = reasoningDisplayPolicy(
        reasoning = reasoning,
        expanded = expanded,
    )
    val isExpandable = displayPolicy.expandable
    val reasoningLabel = stringResource(R.string.assistant_reasoning_label)
    val toggleLabel = stringResource(
        if (expanded) {
            R.string.assistant_reasoning_hide
        } else {
            R.string.assistant_reasoning_show
        }
    )
    val stateDescriptionText = stringResource(
        if (expanded) {
            R.string.section_state_expanded
        } else {
            R.string.section_state_collapsed
        }
    )
    val accessibilitySummary = stringResource(
        R.string.assistant_reasoning_summary,
        reasoningLabel,
        stateDescriptionText,
        displayPolicy.text.replace(Regex("\\s+"), " "),
    )
    val toggleExpanded = {
        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
        onExpandedChange(!expanded)
    }
    val rowModifier = if (isExpandable) {
        Modifier
            .semantics(mergeDescendants = true) {
                contentDescription = accessibilitySummary
                stateDescription = stateDescriptionText
            }
            .clickable(
                role = Role.Button,
                onClickLabel = toggleLabel,
                onClick = toggleExpanded,
            )
    } else {
        Modifier.semantics(mergeDescendants = true) {
            contentDescription = accessibilitySummary
        }
    }

    Row(
        modifier = rowModifier
            .fillMaxWidth()
            .height(IntrinsicSize.Min)
            .padding(horizontal = 2.dp, vertical = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        Box(
            modifier = Modifier
                .fillMaxHeight()
                .width(2.dp)
                .background(
                    color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.16f),
                    shape = RoundedCornerShape(1.dp),
                ),
        )
        Column(
            modifier = Modifier
                .weight(1f)
                .padding(vertical = 2.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = reasoningLabel,
                    style = MaterialTheme.typography.labelSmall,
                    fontWeight = FontWeight.Medium,
                    color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.56f),
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.weight(1f),
                )
                if (isExpandable) {
                    Row(
                        horizontalArrangement = Arrangement.spacedBy(2.dp),
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f, fill = false),
                    ) {
                        Text(
                            text = toggleLabel,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.56f),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                        Icon(
                            imageVector = if (expanded) {
                                Icons.Filled.KeyboardArrowUp
                            } else {
                                Icons.Filled.KeyboardArrowDown
                            },
                            contentDescription = null,
                            tint = MaterialTheme.colorScheme.secondary.copy(alpha = 0.56f),
                            modifier = Modifier.size(17.dp),
                        )
                    }
                }
            }
            Text(
                text = displayPolicy.text,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = displayPolicy.contentAlpha),
                maxLines = displayPolicy.maxLines,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

internal data class ReasoningDisplayPolicy(
    val text: String,
    val contentAlpha: Float,
    val maxLines: Int,
    val expandable: Boolean,
)

internal fun reasoningDisplayPolicy(
    reasoning: String,
    expanded: Boolean,
): ReasoningDisplayPolicy {
    val expandable = reasoningNeedsExpansion(reasoning)
    val isExpanded = expanded && expandable
    return ReasoningDisplayPolicy(
        text = if (isExpanded) reasoning.trim() else reasoningPreview(reasoning),
        contentAlpha = if (isExpanded) REASONING_EXPANDED_ALPHA else REASONING_COLLAPSED_ALPHA,
        maxLines = if (isExpanded) Int.MAX_VALUE else REASONING_PREVIEW_MAX_LINES,
        expandable = expandable,
    )
}

internal fun assistantShowsTypingPlaceholder(
    message: RuntimeChatMessage,
    isStreaming: Boolean,
): Boolean {
    return isStreaming && message.content.isBlank() && !message.isReasoningOpen
}

internal fun reasoningPreview(
    reasoning: String,
    maxLines: Int = REASONING_PREVIEW_MAX_LINES,
    maxCharacters: Int = REASONING_PREVIEW_MAX_CHARS,
): String {
    val previewLines = reasoning
        .trim()
        .lineSequence()
        .map { it.trim().replace(Regex("\\s+"), " ") }
        .filter { it.isNotBlank() }
        .take(maxLines)
        .toList()
    return previewLines
        .joinToString(separator = "\n")
        .ifBlank { reasoning.trim().replace(Regex("\\s+"), " ") }
        .cappedReasoningPreview(maxCharacters)
}

internal fun reasoningNeedsExpansion(
    reasoning: String,
    maxLines: Int = REASONING_PREVIEW_MAX_LINES,
): Boolean {
    val full = reasoning.trim().replace(Regex("\\s+"), " ")
    if (full.isBlank()) return false
    val normalizedLines = reasoning
        .trim()
        .lineSequence()
        .map { it.trim().replace(Regex("\\s+"), " ") }
        .filter { it.isNotBlank() }
        .toList()
    return normalizedLines.size > maxLines ||
        full.length > REASONING_SINGLE_PARAGRAPH_PREVIEW_CHARS
}

internal const val REASONING_PREVIEW_MAX_LINES = 3
internal const val REASONING_PREVIEW_MAX_CHARS = 180
internal const val REASONING_COLLAPSED_ALPHA = 0.42f
internal const val REASONING_EXPANDED_ALPHA = 0.58f
private const val REASONING_SINGLE_PARAGRAPH_PREVIEW_CHARS = REASONING_PREVIEW_MAX_CHARS
internal const val SUGGESTED_QUESTION_MAX_ITEMS = 4
private const val SUGGESTED_QUESTION_MAX_LINES = 2
internal const val CHAT_COMPOSER_CONTAINER_CORNER_RADIUS_DP = 28
internal const val CHAT_COMPOSER_CONTAINER_ALPHA = 0.98f
internal const val DEVELOPER_DIAGNOSTICS_TOGGLE_ROW_TAG = "developer-diagnostics-toggle-row"
internal const val DEVELOPER_DIAGNOSTICS_SWITCH_DISABLED_TAG = "developer-diagnostics-switch-disabled"
internal const val DEVELOPER_DIAGNOSTICS_SWITCH_ENABLED_TAG = "developer-diagnostics-switch-enabled"
internal const val SETTINGS_CHAT_HISTORY_SEARCH_TEST_TAG = "aetherlink_settings_chat_history_search"

private fun String.cappedReasoningPreview(maxCharacters: Int): String {
    val trimmed = trim()
    if (trimmed.length <= maxCharacters) return trimmed
    return trimmed.take(maxCharacters).trimEnd() + "..."
}

internal fun chatComposerInputContentDescriptionRes(): Int = R.string.message

internal fun chatComposerVisualPlaceholderRes(): Int? = null

internal fun chatEmptyStaticPromptRes(): Int? = null

@Composable
private fun ChatComposer(
    value: String,
    attachments: List<RuntimePendingAttachment>,
    enabled: Boolean,
    imageAttachmentsSupported: Boolean,
    canSend: Boolean,
    hasSendableContent: Boolean,
    isStreaming: Boolean,
    hint: String,
    onInputChange: (String) -> Unit,
    onAttachFiles: () -> Unit,
    onRemoveAttachment: (String) -> Unit,
    onSend: () -> Unit,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val showComposerWarning = !imageAttachmentsSupported && attachments.any { it.type == "image" }
    val showComposerStatus = chatComposerShouldShowStatus(
        enabled = enabled,
        isStreaming = isStreaming,
        hint = hint,
        hasWarning = showComposerWarning,
    )
    val inputContentDescription = stringResource(chatComposerInputContentDescriptionRes())
    val composerStateDescription = when {
        hint.isNotBlank() -> hint
        hasSendableContent -> stringResource(R.string.chat_hint_ready)
        else -> stringResource(R.string.chat_hint_enter_message)
    }
    val sendStateDescription = composerStateDescription
    val sendActionLabel = stringResource(R.string.content_desc_send)
    val cancelGenerationStateDescription = stringResource(R.string.cancel_generation_state_ready)
    val cancelGenerationActionLabel = stringResource(R.string.content_desc_cancel_generation)
    val attachFilesActionLabel = stringResource(R.string.content_desc_attach_files)
    val attachFilesStateDescription = when {
        enabled -> stringResource(R.string.attach_files_state_ready)
        hint.isNotBlank() -> hint
        else -> stringResource(R.string.attach_files_state_unavailable)
    }
    Surface(
        modifier = modifier.fillMaxWidth(),
        shape = RoundedCornerShape(CHAT_COMPOSER_CONTAINER_CORNER_RADIUS_DP.dp),
        tonalElevation = 1.dp,
        shadowElevation = 2.dp,
        color = MaterialTheme.colorScheme.surface.copy(alpha = CHAT_COMPOSER_CONTAINER_ALPHA),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            if (isStreaming) {
                LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
            }
            AttachmentChips(
                attachments = attachments,
                enabled = enabled,
                disabledActionStateDescription = attachFilesStateDescription.takeUnless { enabled },
                imageAttachmentsSupported = imageAttachmentsSupported,
                onRemoveAttachment = onRemoveAttachment,
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .heightIn(min = 42.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.Bottom,
            ) {
                FilledTonalIconButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        onAttachFiles()
                    },
                    enabled = enabled,
                    modifier = Modifier
                        .size(40.dp)
                        .semantics {
                            stateDescription = attachFilesStateDescription
                            onClick(label = attachFilesActionLabel) {
                                if (enabled) {
                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                    onAttachFiles()
                                    true
                                } else {
                                    false
                                }
                            }
                        },
                ) {
                    Icon(
                        Icons.Filled.Add,
                        contentDescription = attachFilesActionLabel,
                    )
                }
                BasicTextField(
                    value = value,
                    onValueChange = onInputChange,
                    enabled = enabled,
                    singleLine = false,
                    minLines = 1,
                    maxLines = 6,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(
                        onSend = {
                            if (canSend) {
                                hapticFeedback.performAetherLinkFeedback(
                                    AetherLinkInteractionFeedback.PrimaryAction,
                                )
                                onSend()
                            }
                        },
                    ),
                    textStyle = MaterialTheme.typography.bodyLarge.copy(
                        color = if (enabled) {
                            MaterialTheme.colorScheme.onSurface
                        } else {
                            MaterialTheme.colorScheme.onSurfaceVariant
                        },
                    ),
                    modifier = Modifier
                        .weight(1f)
                        .heightIn(min = 40.dp, max = 136.dp)
                        .semantics {
                            contentDescription = inputContentDescription
                            stateDescription = composerStateDescription
                        },
                    decorationBox = { innerTextField ->
                        Box(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(horizontal = 2.dp, vertical = 9.dp),
                            contentAlignment = Alignment.TopStart,
                        ) {
                            innerTextField()
                        }
                    },
                )
                if (isStreaming) {
                    FilledIconButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                            onCancel()
                        },
                        enabled = true,
                        modifier = Modifier
                            .size(40.dp)
                            .semantics {
                                stateDescription = cancelGenerationStateDescription
                                onClick(label = cancelGenerationActionLabel) {
                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                                    onCancel()
                                    true
                                }
                            },
                    ) {
                        Icon(
                            Icons.Filled.Close,
                            contentDescription = cancelGenerationActionLabel,
                        )
                    }
                } else {
                    FilledIconButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onSend()
                        },
                        enabled = canSend,
                        modifier = Modifier
                            .size(40.dp)
                            .semantics {
                                stateDescription = sendStateDescription
                                onClick(label = sendActionLabel) {
                                    if (canSend) {
                                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                        onSend()
                                        true
                                    } else {
                                        false
                                    }
                                }
                            },
                    ) {
                        Icon(
                            Icons.AutoMirrored.Filled.Send,
                            contentDescription = sendActionLabel,
                        )
                    }
                }
            }
            if (showComposerStatus) {
                ComposerStatus(
                    text = hint,
                    isReady = canSend,
                    isWarning = showComposerWarning,
                )
            }
        }
    }
}

@Composable
private fun ComposerStatus(
    text: String,
    isReady: Boolean,
    isWarning: Boolean,
) {
    val statusColor = when {
        isWarning -> MaterialTheme.colorScheme.error
        isReady -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.secondary
    }

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                liveRegion = LiveRegionMode.Polite
                contentDescription = text
            }
            .padding(horizontal = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            modifier = Modifier.size(6.dp),
            shape = RoundedCornerShape(999.dp),
            color = statusColor,
            content = {},
        )
        Text(
            text = text,
            style = MaterialTheme.typography.labelSmall,
            color = statusColor,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = Modifier.weight(1f),
        )
    }
}

@Composable
private fun ReadOnlyAttachmentChips(
    attachments: List<RuntimeMessageAttachment>,
) {
    if (attachments.isEmpty()) return

    Row(
        modifier = Modifier
            .widthIn(max = 548.dp)
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        attachments.forEach { attachment ->
            ReadOnlyAttachmentChip(attachment = attachment)
        }
    }
}

@Composable
private fun ReadOnlyAttachmentChip(attachment: RuntimeMessageAttachment) {
    val attachmentTypeDescription = attachmentTypeLabel(attachment.type)
    val attachmentContentDescription = stringResource(
        R.string.content_desc_attachment_chip,
        attachment.name,
        attachmentTypeDescription,
    )
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.62f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Column(
            modifier = Modifier
                .padding(horizontal = 11.dp, vertical = 6.dp)
                .semantics {
                    contentDescription = attachmentContentDescription
                    stateDescription = attachmentTypeDescription
                },
            verticalArrangement = Arrangement.spacedBy(1.dp),
        ) {
            Text(
                text = attachment.name,
                style = MaterialTheme.typography.labelMedium,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = attachmentTypeDescription,
                style = MaterialTheme.typography.labelSmall,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun attachmentTypeLabel(type: String): String {
    return if (type == "image") {
        stringResource(R.string.attachment_type_image)
    } else {
        stringResource(R.string.attachment_type_document)
    }
}

@Composable
private fun AttachmentChips(
    attachments: List<RuntimePendingAttachment>,
    enabled: Boolean,
    disabledActionStateDescription: String?,
    imageAttachmentsSupported: Boolean,
    onRemoveAttachment: (String) -> Unit,
) {
    if (attachments.isEmpty()) return

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .horizontalScroll(rememberScrollState()),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        attachments.forEach { attachment ->
            AttachmentChip(
                attachment = attachment,
                enabled = enabled,
                disabledActionStateDescription = disabledActionStateDescription,
                imageAttachmentsSupported = imageAttachmentsSupported,
                onRemoveAttachment = onRemoveAttachment,
            )
        }
    }
}

@Composable
private fun AttachmentChip(
    attachment: RuntimePendingAttachment,
    enabled: Boolean,
    disabledActionStateDescription: String?,
    imageAttachmentsSupported: Boolean,
    onRemoveAttachment: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val isUnsupportedImage = attachment.type == "image" && !imageAttachmentsSupported
    val metadata = attachmentMetadataLabel(attachment)
    val attachmentStateDescription = if (isUnsupportedImage) {
        stringResource(R.string.attachment_requires_vision_model)
    } else {
        metadata
    }
    val attachmentContentDescription = stringResource(
        R.string.content_desc_attachment_chip,
        attachment.name,
        attachmentStateDescription,
    )
    val removeAttachmentActionLabel = stringResource(R.string.content_desc_remove_attachment, attachment.name)
    Surface(
        shape = RoundedCornerShape(999.dp),
        color = if (isUnsupportedImage) {
            MaterialTheme.colorScheme.errorContainer
        } else {
            MaterialTheme.colorScheme.secondaryContainer
        },
        contentColor = if (isUnsupportedImage) {
            MaterialTheme.colorScheme.onErrorContainer
        } else {
            MaterialTheme.colorScheme.onSecondaryContainer
        },
    ) {
        Row(
            modifier = Modifier.padding(start = 12.dp, end = 4.dp, top = 4.dp, bottom = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Column(
                modifier = Modifier
                    .widthIn(max = 190.dp)
                    .semantics {
                        contentDescription = attachmentContentDescription
                        stateDescription = attachmentStateDescription
                    },
                verticalArrangement = Arrangement.spacedBy(1.dp),
            ) {
                Text(
                    text = attachment.name,
                    style = MaterialTheme.typography.labelMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = if (isUnsupportedImage) {
                        stringResource(R.string.attachment_requires_vision_model)
                    } else {
                        metadata
                    },
                    style = MaterialTheme.typography.labelSmall,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            IconButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                    onRemoveAttachment(attachment.id)
                },
                enabled = enabled,
                modifier = Modifier
                    .size(28.dp)
                    .semantics {
                        onClick(label = removeAttachmentActionLabel) {
                            if (enabled) {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                                onRemoveAttachment(attachment.id)
                                true
                            } else {
                                false
                            }
                        }
                        if (!enabled && disabledActionStateDescription != null) {
                            stateDescription = disabledActionStateDescription
                        }
                    },
            ) {
                Icon(
                    Icons.Filled.Close,
                    contentDescription = removeAttachmentActionLabel,
                    modifier = Modifier.size(18.dp),
                )
            }
        }
    }
}

@Composable
private fun attachmentMetadataLabel(attachment: RuntimePendingAttachment): String {
    val context = LocalContext.current
    val typeLabel = if (attachment.type == "image") {
        stringResource(R.string.attachment_type_image)
    } else {
        stringResource(R.string.attachment_type_document)
    }
    val sizeLabel = if (attachment.sizeBytes > 0L) {
        Formatter.formatFileSize(context, attachment.sizeBytes)
    } else {
        ""
    }
    return if (sizeLabel.isBlank()) {
        typeLabel
    } else {
        stringResource(R.string.attachment_metadata_with_size, typeLabel, sizeLabel)
    }
}

@Composable
private fun CompanionOnlyPanel() {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = stringResource(R.string.companion_only_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
            Text(
                text = stringResource(R.string.companion_only_detail),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
    }
}

@Composable
private fun FirstRunLanguagePreferencePanel(
    selectedLanguageTag: String,
    onSetLanguageTag: (String) -> Unit,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            LanguagePreferenceSelector(
                selectedLanguageTag = selectedLanguageTag,
                onSetLanguageTag = onSetLanguageTag,
            )
        }
    }
}

@Composable
private fun AppPreferencesPanel(
    selectedLanguageTag: String,
    onSetLanguageTag: (String) -> Unit,
    selectedTheme: RuntimeAppTheme,
    onSetTheme: (RuntimeAppTheme) -> Unit,
    showLanguageSelector: Boolean = true,
) {
    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.preferences_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
            )
            AppearancePreferenceSelector(
                selectedTheme = selectedTheme,
                onSetTheme = onSetTheme,
            )
            if (showLanguageSelector) {
                LanguagePreferenceSelector(
                    selectedLanguageTag = selectedLanguageTag,
                    onSetLanguageTag = onSetLanguageTag,
                )
            }
        }
    }
}

@Composable
private fun AppearancePreferenceSelector(
    selectedTheme: RuntimeAppTheme,
    onSetTheme: (RuntimeAppTheme) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val options = appThemePreferenceOptions()
    val selectedStateDescription = stringResource(R.string.selection_state_selected)
    val groupLabel = stringResource(R.string.appearance_title)

    Column(
        modifier = Modifier.selectableGroup(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text = groupLabel,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
        )
        options.forEach { (theme, labelRes) ->
            val selected = theme == selectedTheme
            val optionLabel = stringResource(labelRes)
            val optionAccessibilitySummary = stringResource(
                R.string.preference_option_accessibility_summary,
                groupLabel,
                optionLabel,
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .selectable(
                        selected = selected,
                        role = Role.RadioButton,
                    ) {
                        if (shouldPerformSelectionChangeHaptic(selected)) {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                        }
                        onSetTheme(theme)
                    }
                    .selectedPreferenceOptionState(
                        selected = selected,
                        selectedStateDescription = selectedStateDescription,
                        contentDescription = optionAccessibilitySummary,
                    )
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                RadioButton(
                    selected = selected,
                    onClick = null,
                )
                Text(
                    text = optionLabel,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

internal fun appThemePreferenceOptions(): List<Pair<RuntimeAppTheme, Int>> {
    return listOf(
        RuntimeAppTheme.System to R.string.appearance_system,
        RuntimeAppTheme.Light to R.string.appearance_light,
        RuntimeAppTheme.Dark to R.string.appearance_dark,
    )
}

private fun Modifier.selectedPreferenceOptionState(
    selected: Boolean,
    selectedStateDescription: String,
    contentDescription: String,
): Modifier {
    return semantics {
        this.contentDescription = contentDescription
        if (selected) {
            stateDescription = selectedStateDescription
        }
    }
}

@Composable
private fun EmbeddingModelPanel(
    state: RuntimeUiState,
    onRequestModels: () -> Unit,
    onSelectEmbeddingModel: (String?) -> Unit,
    showHeader: Boolean = true,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val embeddingModels = state.models
        .filter { it.isEmbeddingModel() }
        .sortedWith(compareBy<RuntimeModel> { !it.installed }.thenBy { it.name.lowercase() })
    val selectedEmbeddingModel = embeddingModels.firstOrNull { it.id == state.selectedEmbeddingModelId }
    val selectedEmbeddingModelUnavailable =
        state.selectedEmbeddingModelId != null && selectedEmbeddingModel == null
    val selectedEmbeddingModelLabel = selectedEmbeddingModel?.name
        ?: state.selectedEmbeddingModelId?.let(::savedRuntimeModelDisplayName)
        ?: stringResource(R.string.model_none)
    val selectedEmbeddingModelRecoveryMessage = when {
        !selectedEmbeddingModelUnavailable -> null
        state.isLoadingModels -> stringResource(R.string.selected_embedding_model_restoring)
        state.isConnected -> stringResource(R.string.selected_embedding_model_unavailable)
        else -> stringResource(R.string.selected_embedding_model_restoring)
    }
    val modelRefreshStateDescription = modelRefreshButtonStateDescription(state)

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (showHeader) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = stringResource(R.string.embedding_model_title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = stringResource(R.string.embedding_model_subtitle),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            StatusLine(
                label = stringResource(R.string.selected_embedding_model),
                value = selectedEmbeddingModelLabel,
            )
            if (selectedEmbeddingModelRecoveryMessage != null) {
                Text(
                    text = selectedEmbeddingModelRecoveryMessage,
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            EmbeddingModelNoneRow(
                selected = state.selectedEmbeddingModelId == null,
                onSelectEmbeddingModel = onSelectEmbeddingModel,
            )
            if (selectedEmbeddingModelUnavailable) {
                SavedEmbeddingModelRow(
                    modelName = selectedEmbeddingModelLabel,
                    detail = selectedEmbeddingModelRecoveryMessage,
                )
            }
            Button(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onRequestModels()
                },
                enabled = state.isConnected && !state.isLoadingModels,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        stateDescription = modelRefreshStateDescription
                    },
            ) {
                Icon(Icons.Filled.Refresh, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(
                    text = if (state.isLoadingModels) {
                        stringResource(R.string.loading_models)
                    } else {
                        stringResource(R.string.load_models)
                    },
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            when {
                !state.isConnected -> EmptyState(text = stringResource(R.string.embedding_model_connect_first))
                embeddingModels.isEmpty() -> EmptyState(text = stringResource(R.string.embedding_model_empty))
                else -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    embeddingModels.forEach { model ->
                        EmbeddingModelRow(
                            model = model,
                            selected = model.id == state.selectedEmbeddingModelId,
                            onSelectEmbeddingModel = onSelectEmbeddingModel,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun modelRefreshButtonStateDescription(state: RuntimeUiState): String {
    return when {
        state.isLoadingModels -> stringResource(R.string.model_refresh_state_loading)
        state.isConnected -> stringResource(R.string.model_refresh_state_ready)
        else -> stringResource(R.string.model_refresh_state_connect_first)
    }
}

@Composable
private fun SavedEmbeddingModelRow(
    modelName: String,
    detail: String?,
) {
    val accessibilitySummary = detail?.let {
        stringResource(R.string.saved_embedding_model_row_summary, modelName, it)
    } ?: modelName
    val selectedStateDescription = stringResource(R.string.selection_state_selected)
    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = accessibilitySummary
                stateDescription = selectedStateDescription
            },
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = Icons.Filled.CheckCircle,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.primary,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = modelName,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                if (detail != null) {
                    Text(
                        text = detail,
                        style = MaterialTheme.typography.labelSmall,
                        color = MaterialTheme.colorScheme.secondary,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

@Composable
private fun EmbeddingModelNoneRow(
    selected: Boolean,
    onSelectEmbeddingModel: (String?) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val modelName = stringResource(R.string.model_none)
    val detail = stringResource(R.string.embedding_model_none_detail)
    val accessibilitySummary = stringResource(
        if (selected) {
            R.string.embedding_model_none_row_summary_selected
        } else {
            R.string.embedding_model_none_row_summary
        },
        modelName,
        detail,
    )
    OutlinedButton(
        onClick = {
            if (shouldPerformSelectionChangeHaptic(selected)) {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
            }
            onSelectEmbeddingModel(null)
        },
        modifier = selectedEmbeddingModelRowModifier(
            selected = selected,
            contentDescription = accessibilitySummary,
        ),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = if (selected) Icons.Filled.CheckCircle else Icons.Filled.Close,
                contentDescription = null,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = modelName,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = detail,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun EmbeddingModelRow(
    model: RuntimeModel,
    selected: Boolean,
    onSelectEmbeddingModel: (String?) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val modelStatusText = stringResource(
        R.string.model_status_value,
        runtimeProviderDisplayName(model.provider),
        quickModelStatus(model = model, installing = false),
    )
    val accessibilitySummary = stringResource(
        if (selected) {
            R.string.embedding_model_row_summary_selected
        } else {
            R.string.embedding_model_row_summary
        },
        model.name,
        modelStatusText,
    )
    OutlinedButton(
        onClick = {
            if (shouldPerformSelectionChangeHaptic(selected)) {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
            }
            onSelectEmbeddingModel(model.id)
        },
        enabled = model.installed,
        modifier = selectedEmbeddingModelRowModifier(
            selected = selected,
            contentDescription = accessibilitySummary,
        ),
        contentPadding = PaddingValues(horizontal = 12.dp, vertical = 10.dp),
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                imageVector = if (selected) Icons.Filled.CheckCircle else Icons.Filled.Search,
                contentDescription = null,
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = model.name,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = modelStatusText,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun selectedEmbeddingModelRowModifier(
    selected: Boolean,
    contentDescription: String,
): Modifier {
    val selectedStateDescription = stringResource(R.string.selection_state_selected)
    return Modifier
        .fillMaxWidth()
        .semantics {
            this.contentDescription = contentDescription
            if (selected) {
                stateDescription = selectedStateDescription
            }
        }
}

@Composable
private fun LanguagePreferenceSelector(
    selectedLanguageTag: String,
    onSetLanguageTag: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val options = appLanguagePreferenceOptions()
    val selectedStateDescription = stringResource(R.string.selection_state_selected)
    val groupLabel = stringResource(R.string.language_title)

    Column(
        modifier = Modifier.selectableGroup(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text = groupLabel,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
        )
        options.forEach { (language, labelRes) ->
            val selected = appLanguagePreferenceOptionSelected(selectedLanguageTag, language)
            val optionLabel = stringResource(labelRes)
            val optionAccessibilitySummary = stringResource(
                R.string.preference_option_accessibility_summary,
                groupLabel,
                optionLabel,
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .selectable(
                        selected = selected,
                        role = Role.RadioButton,
                    ) {
                        if (shouldPerformSelectionChangeHaptic(selected)) {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                        }
                        onSetLanguageTag(language.languageTag)
                    }
                    .selectedPreferenceOptionState(
                        selected = selected,
                        selectedStateDescription = selectedStateDescription,
                        contentDescription = optionAccessibilitySummary,
                    )
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                RadioButton(
                    selected = selected,
                    onClick = null,
                )
                Text(
                    text = optionLabel,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

internal fun appLanguagePreferenceOptionSelected(
    selectedLanguageTag: String,
    language: RuntimeAppLanguage,
): Boolean {
    return RuntimeAppLanguage.normalizeLanguageTag(selectedLanguageTag) == language.languageTag
}

internal fun appLanguagePreferenceOptions(): List<Pair<RuntimeAppLanguage, Int>> {
    return listOf(
        RuntimeAppLanguage.English to R.string.language_english,
        RuntimeAppLanguage.Korean to R.string.language_korean,
        RuntimeAppLanguage.Japanese to R.string.language_japanese,
        RuntimeAppLanguage.SimplifiedChinese to R.string.language_simplified_chinese,
        RuntimeAppLanguage.French to R.string.language_french,
    )
}

@Composable
private fun ChatHistorySettingsPanel(
    activeSessions: List<RuntimeChatSession>,
    archivedSessions: List<RuntimeChatSession>,
    isActionEnabled: Boolean,
    onArchiveChatSession: (String) -> Unit,
    onRestoreChatSession: (String) -> Unit,
    onPermanentlyDeleteChatSession: (String) -> Unit,
    onArchiveAllChatSessions: () -> Unit,
    onPermanentlyDeleteArchivedChatSessions: () -> Unit,
    showHeader: Boolean = true,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val bulkArchiveConfirmStep = rememberSaveable { mutableStateOf(0) }
    val bulkDeleteConfirmStep = rememberSaveable { mutableStateOf(0) }
    var showBulkActions by rememberSaveable { mutableStateOf(false) }
    var chatSearchQuery by rememberSaveable { mutableStateOf("") }
    val untitledTitle = stringResource(R.string.untitled_chat)
    val filteredActiveSessions = filterChatHistorySessions(
        sessions = activeSessions,
        query = chatSearchQuery,
        untitledTitle = untitledTitle,
    )
    val filteredArchivedSessions = filterChatHistorySessions(
        sessions = archivedSessions,
        query = chatSearchQuery,
        untitledTitle = untitledTitle,
    )
    val hasSearchQuery = chatSearchQuery.trim().isNotEmpty()
    val chatSearchClearContentDescription = stringResource(
        R.string.clear_chat_search_named,
        chatSearchQuery.trim().ifBlank { chatSearchQuery },
    )
    val hasFilteredResults = filteredActiveSessions.isNotEmpty() || filteredArchivedSessions.isNotEmpty()
    val canArchiveAll = chatHistoryArchiveAllEnabled(
        isActionEnabled = isActionEnabled,
        activeSessionCount = activeSessions.size,
    )
    val archiveAllStateDescription = chatHistoryArchiveAllStateDescription(
        isActionEnabled = isActionEnabled,
        activeSessionCount = activeSessions.size,
    )
    val canPermanentlyDeleteArchived = chatHistoryPermanentDeleteArchivedEnabled(
        isActionEnabled = isActionEnabled,
        archivedSessionCount = archivedSessions.size,
    )
    val deleteArchivedStateDescription = chatHistoryDeleteArchivedStateDescription(
        isActionEnabled = isActionEnabled,
        archivedSessionCount = archivedSessions.size,
    )
    val hasBulkActions = chatHistoryBulkActionsAvailable(
        activeSessionCount = activeSessions.size,
        archivedSessionCount = archivedSessions.size,
    )

    TwoStepConfirmationDialog(
        step = bulkArchiveConfirmStep.value,
        titleRes = R.string.archive_all_chats,
        accessibilitySubject = stringResource(R.string.archive_all_chats),
        firstMessage = stringResource(R.string.archive_all_chats_confirm_first),
        secondMessage = stringResource(R.string.archive_all_chats_confirm_second),
        confirmRes = R.string.archive,
        enabled = canArchiveAll,
        onStepChange = { bulkArchiveConfirmStep.value = it },
        onConfirm = onArchiveAllChatSessions,
    )
    TwoStepConfirmationDialog(
        step = bulkDeleteConfirmStep.value,
        titleRes = R.string.permanently_delete_archived_chats,
        accessibilitySubject = stringResource(R.string.permanently_delete_archived_chats),
        firstMessage = stringResource(R.string.delete_archived_chats_confirm_first),
        secondMessage = stringResource(R.string.delete_archived_chats_confirm_second),
        confirmRes = R.string.permanently_delete,
        enabled = canPermanentlyDeleteArchived,
        onStepChange = { bulkDeleteConfirmStep.value = it },
        onConfirm = onPermanentlyDeleteArchivedChatSessions,
    )

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (showHeader) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = stringResource(R.string.chat_history_settings_title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = stringResource(R.string.chat_history_settings_subtitle),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            StatusLine(
                label = stringResource(R.string.previous_chats),
                value = activeSessions.size.toString(),
            )
            StatusLine(
                label = stringResource(R.string.archived_chats),
                value = archivedSessions.size.toString(),
            )
            OutlinedTextField(
                value = chatSearchQuery,
                onValueChange = { chatSearchQuery = it },
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(SETTINGS_CHAT_HISTORY_SEARCH_TEST_TAG),
                singleLine = true,
                label = { Text(stringResource(R.string.chat_search_label)) },
                leadingIcon = {
                    Icon(
                        imageVector = Icons.Filled.Search,
                        contentDescription = null,
                    )
                },
                trailingIcon = {
                    if (chatSearchQuery.isNotEmpty()) {
                        IconButton(
                            onClick = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                chatSearchQuery = ""
                            },
                            modifier = Modifier.semantics {
                                contentDescription = chatSearchClearContentDescription
                                onClick(label = chatSearchClearContentDescription, action = null)
                            },
                        ) {
                            Icon(
                                imageVector = Icons.Filled.Close,
                                contentDescription = null,
                            )
                        }
                    }
                },
            )
            if (hasBulkActions) {
                val bulkActionsStateDescription = stringResource(
                    if (showBulkActions) {
                        R.string.section_state_expanded
                    } else {
                        R.string.section_state_collapsed
                    },
                )
                val bulkActionsClickLabel = stringResource(
                    if (showBulkActions) {
                        R.string.collapse_section
                    } else {
                        R.string.expand_section
                    },
                )
                OutlinedButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                        showBulkActions = !showBulkActions
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            stateDescription = bulkActionsStateDescription
                            onClick(label = bulkActionsClickLabel, action = null)
                        },
                ) {
                    Icon(
                        imageVector = if (showBulkActions) {
                            Icons.Filled.KeyboardArrowUp
                        } else {
                            Icons.Filled.KeyboardArrowDown
                        },
                        contentDescription = null,
                    )
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = stringResource(R.string.chat_history_bulk_actions_title),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (showBulkActions) {
                    Text(
                        text = stringResource(R.string.chat_history_bulk_actions_detail),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            bulkArchiveConfirmStep.value = 1
                        },
                        enabled = canArchiveAll,
                        modifier = Modifier
                            .fillMaxWidth()
                            .semantics {
                                stateDescription = archiveAllStateDescription
                            },
                    ) {
                        Icon(Icons.Filled.Archive, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = stringResource(R.string.archive_all_chats),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            bulkDeleteConfirmStep.value = 1
                        },
                        enabled = canPermanentlyDeleteArchived,
                        modifier = Modifier
                            .fillMaxWidth()
                            .semantics {
                                stateDescription = deleteArchivedStateDescription
                            },
                    ) {
                        Icon(Icons.Filled.DeleteSweep, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = stringResource(R.string.permanently_delete_archived_chats),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
            if (hasSearchQuery && !hasFilteredResults) {
                Text(
                    text = stringResource(R.string.no_chat_search_results),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            if (filteredActiveSessions.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    filteredActiveSessions.forEach { session ->
                        ChatHistorySettingsRow(
                            session = session,
                            isActionEnabled = isActionEnabled,
                            onArchiveChatSession = onArchiveChatSession,
                            onRestoreChatSession = onRestoreChatSession,
                            onPermanentlyDeleteChatSession = onPermanentlyDeleteChatSession,
                        )
                    }
                }
            }
            if (filteredArchivedSessions.isNotEmpty()) {
                HorizontalDivider()
                Text(
                    text = stringResource(R.string.archived_chats),
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    filteredArchivedSessions.forEach { session ->
                        ChatHistorySettingsRow(
                            session = session,
                            isActionEnabled = isActionEnabled,
                            onArchiveChatSession = onArchiveChatSession,
                            onRestoreChatSession = onRestoreChatSession,
                            onPermanentlyDeleteChatSession = onPermanentlyDeleteChatSession,
                        )
                    }
                }
            }
        }
    }
}

internal fun filterChatHistorySessions(
    sessions: List<RuntimeChatSession>,
    query: String,
    untitledTitle: String,
): List<RuntimeChatSession> {
    val terms = query
        .trim()
        .lowercase(Locale.ROOT)
        .split(Regex("\\s+"))
        .filter { it.isNotBlank() }
    if (terms.isEmpty()) return sessions
    return sessions.filter { session ->
        val searchableText = listOfNotNull(
            session.localizedTitle(untitledTitle),
            session.modelId,
            session.lastEvent,
            session.lastFinishReason,
            session.lastErrorCode,
        ).joinToString(separator = " ").lowercase(Locale.ROOT)
        terms.all(searchableText::contains)
    }
}

internal fun chatHistoryArchiveAllEnabled(
    isActionEnabled: Boolean,
    activeSessionCount: Int,
): Boolean {
    return isActionEnabled && activeSessionCount > 0
}

@Composable
private fun chatHistoryArchiveAllStateDescription(
    isActionEnabled: Boolean,
    activeSessionCount: Int,
): String {
    return when {
        !isActionEnabled -> stringResource(R.string.archive_all_chats_state_wait_for_stream)
        activeSessionCount <= 0 -> stringResource(R.string.archive_all_chats_state_no_active)
        else -> stringResource(R.string.archive_all_chats_state_ready)
    }
}

internal fun chatHistoryPermanentDeleteArchivedEnabled(
    isActionEnabled: Boolean,
    archivedSessionCount: Int,
): Boolean {
    return isActionEnabled && archivedSessionCount > 0
}

@Composable
private fun chatHistoryDeleteArchivedStateDescription(
    isActionEnabled: Boolean,
    archivedSessionCount: Int,
): String {
    return when {
        !isActionEnabled -> stringResource(R.string.delete_archived_chats_state_wait_for_stream)
        archivedSessionCount <= 0 -> stringResource(R.string.delete_archived_chats_state_no_archived)
        else -> stringResource(R.string.delete_archived_chats_state_ready)
    }
}

internal fun chatHistoryBulkActionsAvailable(
    activeSessionCount: Int,
    archivedSessionCount: Int,
): Boolean {
    return activeSessionCount > 0 || archivedSessionCount > 0
}

@Composable
private fun ChatHistorySettingsRow(
    session: RuntimeChatSession,
    isActionEnabled: Boolean,
    onArchiveChatSession: (String) -> Unit,
    onRestoreChatSession: (String) -> Unit,
    onPermanentlyDeleteChatSession: (String) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val deleteConfirmStep = rememberSaveable(session.id) { mutableStateOf(0) }
    val isArchived = session.archivedAtMillis != null
    val title = session.localizedTitle(stringResource(R.string.untitled_chat))
    val statusRes = chatHistorySessionStatusRes(session)
    val baseStatusText = if (isArchived) {
        stringResource(R.string.archived_chat)
    } else {
        pluralStringResource(
            R.plurals.chat_message_count,
            session.messageCount,
            session.messageCount,
        )
    }
    val statusText = statusRes?.let { status ->
        stringResource(R.string.chat_session_status_value, baseStatusText, stringResource(status))
    } ?: baseStatusText
    val rowAccessibilitySummary = stringResource(R.string.chat_session_row_summary, title, statusText)
    val archiveActionContentDescription = stringResource(R.string.archive_chat_named, title)
    val restoreActionContentDescription = stringResource(R.string.restore_chat_named, title)
    val permanentlyDeleteActionContentDescription =
        stringResource(R.string.permanently_delete_chat_named, title)
    val chatHistoryActionStateDescription = if (!isActionEnabled) {
        stringResource(R.string.chat_history_action_state_wait_for_stream)
    } else {
        null
    }
    val statusColor = when (statusRes) {
        R.string.chat_session_status_failed -> MaterialTheme.colorScheme.error
        R.string.chat_session_status_in_progress -> MaterialTheme.colorScheme.primary
        else -> MaterialTheme.colorScheme.secondary
    }
    val canPermanentlyDelete = chatHistoryPermanentDeleteChatEnabled(
        isActionEnabled = isActionEnabled,
        isArchived = isArchived,
    )

    TwoStepConfirmationDialog(
        step = deleteConfirmStep.value,
        titleRes = R.string.permanently_delete_chat,
        accessibilitySubject = permanentlyDeleteActionContentDescription,
        firstMessage = stringResource(R.string.permanently_delete_chat_confirm_first, title),
        secondMessage = stringResource(R.string.permanently_delete_chat_confirm_second, title),
        confirmRes = R.string.permanently_delete,
        enabled = canPermanentlyDelete,
        onStepChange = { deleteConfirmStep.value = it },
        onConfirm = { onPermanentlyDeleteChatSession(session.id) },
    )

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .semantics {
                            contentDescription = rowAccessibilitySummary
                        },
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.bodyMedium,
                        fontWeight = FontWeight.Medium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    Text(
                        text = statusText,
                        style = MaterialTheme.typography.labelSmall,
                        color = statusColor,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                if (isArchived) {
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onRestoreChatSession(session.id)
                        },
                        enabled = isActionEnabled,
                        modifier = Modifier
                            .weight(1f)
                            .semantics {
                                contentDescription = restoreActionContentDescription
                                onClick(label = restoreActionContentDescription, action = null)
                                chatHistoryActionStateDescription?.let { stateDescription = it }
                            },
                    ) {
                        Icon(Icons.Filled.Unarchive, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = stringResource(R.string.restore_chat),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            deleteConfirmStep.value = 1
                        },
                        enabled = isActionEnabled,
                        modifier = Modifier
                            .weight(1f)
                            .semantics {
                                contentDescription = permanentlyDeleteActionContentDescription
                                onClick(label = permanentlyDeleteActionContentDescription, action = null)
                                chatHistoryActionStateDescription?.let { stateDescription = it }
                            },
                    ) {
                        Icon(Icons.Filled.Delete, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = stringResource(R.string.permanently_delete),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                } else {
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onArchiveChatSession(session.id)
                        },
                        enabled = isActionEnabled,
                        modifier = Modifier
                            .fillMaxWidth()
                            .semantics {
                                contentDescription = archiveActionContentDescription
                                onClick(label = archiveActionContentDescription, action = null)
                                chatHistoryActionStateDescription?.let { stateDescription = it }
                            },
                    ) {
                        Icon(Icons.Filled.Archive, contentDescription = null)
                        Spacer(Modifier.width(8.dp))
                        Text(
                            text = stringResource(R.string.archive_chat),
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
        }
    }
}

@StringRes
internal fun chatHistorySessionStatusRes(session: RuntimeChatSession): Int? {
    val errorCode = session.lastErrorCode?.trim()
    if (!errorCode.isNullOrBlank()) {
        return R.string.chat_session_status_failed
    }

    val finishReason = session.lastFinishReason?.trim()?.lowercase(Locale.ROOT)
    when (finishReason) {
        "cancel", "cancelled", "canceled" -> return R.string.chat_session_status_cancelled
        "error", "failed", "failure" -> return R.string.chat_session_status_failed
    }
    if (!finishReason.isNullOrBlank()) {
        return R.string.chat_session_status_completed
    }

    return when (session.lastEvent?.trim()?.lowercase(Locale.ROOT)) {
        "chat.error", "error", "failed", "failure" -> R.string.chat_session_status_failed
        "chat.cancel", "chat.cancelled", "chat.canceled", "cancelled", "canceled" ->
            R.string.chat_session_status_cancelled
        "chat.done", "done", "completed" -> R.string.chat_session_status_completed
        "chat.send",
        "chat.sent",
        "chat.request",
        "chat.requested",
        "chat.start",
        "chat.started",
        "chat.delta",
        "chat.reasoning_delta",
        "chat.thinking_delta",
        "streaming" -> R.string.chat_session_status_in_progress
        else -> null
    }
}

private fun RuntimeChatSession.localizedTitle(untitledTitle: String): String {
    val cleanTitle = title.trim()
    return if (cleanTitle.isBlank() || cleanTitle == LEGACY_DEFAULT_CHAT_TITLE) {
        untitledTitle
    } else {
        cleanTitle
    }
}

private const val LEGACY_DEFAULT_CHAT_TITLE = "New chat"

internal fun chatHistoryPermanentDeleteChatEnabled(
    isActionEnabled: Boolean,
    isArchived: Boolean,
): Boolean {
    return isActionEnabled && isArchived
}

@Composable
private fun TwoStepConfirmationDialog(
    step: Int,
    @StringRes titleRes: Int,
    accessibilitySubject: String,
    firstMessage: String,
    secondMessage: String,
    @StringRes confirmRes: Int,
    enabled: Boolean = true,
    onStepChange: (Int) -> Unit,
    onConfirm: () -> Unit,
) {
    if (step == 0) return
    val hapticFeedback = LocalHapticFeedback.current
    val confirmActionContentDescription = stringResource(
        if (step == 1) {
            R.string.confirmation_continue_action_named
        } else {
            R.string.confirmation_final_action_named
        },
        accessibilitySubject,
    )

    AlertDialog(
        onDismissRequest = { onStepChange(0) },
        title = { Text(stringResource(titleRes)) },
        text = { Text(if (step == 1) firstMessage else secondMessage) },
        confirmButton = {
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(
                        if (step == 1) {
                            AetherLinkInteractionFeedback.PrimaryAction
                        } else {
                            AetherLinkInteractionFeedback.Destructive
                        },
                    )
                    if (step == 1) {
                        onStepChange(2)
                    } else {
                        onStepChange(0)
                        onConfirm()
                    }
                },
                enabled = enabled,
                modifier = Modifier.semantics {
                    contentDescription = confirmActionContentDescription
                    onClick(label = confirmActionContentDescription, action = null)
                },
            ) {
                Text(
                    text = if (step == 1) {
                        stringResource(R.string.continue_action)
                    } else {
                        stringResource(confirmRes)
                    },
                )
            }
        },
        dismissButton = {
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                    onStepChange(0)
                },
            ) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@Composable
private fun MemoryPanel(
    entries: List<RuntimeMemoryEntry>,
    actionsEnabled: Boolean,
    onAddMemoryEntry: (String) -> Unit,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
    showHeader: Boolean = true,
) {
    val draft = rememberSaveable { mutableStateOf("") }
    val canAdd = actionsEnabled && draft.value.isNotBlank()
    val hapticFeedback = LocalHapticFeedback.current
    val memoryAddStateDescription = when {
        !actionsEnabled -> stringResource(memoryLockNoticeTextRes(hasEntries = entries.isNotEmpty()))
        draft.value.isBlank() -> stringResource(R.string.memory_add_state_enter_memory)
        else -> stringResource(R.string.memory_add_state_ready)
    }
    val memoryAddContentDescription = stringResource(R.string.memory_add_label)

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (showHeader) {
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(
                        text = stringResource(R.string.memory_title),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.SemiBold,
                    )
                    Text(
                        text = stringResource(R.string.memory_subtitle),
                        style = MaterialTheme.typography.bodyMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            if (!actionsEnabled) {
                Surface(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.surfaceVariant,
                    contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
                ) {
                    Text(
                        text = stringResource(memoryLockNoticeTextRes(hasEntries = entries.isNotEmpty())),
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            OutlinedTextField(
                value = draft.value,
                onValueChange = { draft.value = it },
                label = { Text(stringResource(R.string.memory_add_label)) },
                placeholder = { Text(stringResource(R.string.memory_add_placeholder)) },
                enabled = actionsEnabled,
                minLines = 2,
                maxLines = 4,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        contentDescription = memoryAddContentDescription
                        stateDescription = memoryAddStateDescription
                    },
            )
            Button(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onAddMemoryEntry(draft.value)
                    draft.value = ""
                },
                enabled = canAdd,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        stateDescription = memoryAddStateDescription
                    },
            ) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(stringResource(R.string.memory_add))
            }
            if (entries.isEmpty()) {
                EmptyState(text = stringResource(memoryEmptyStateTextRes(actionsEnabled = actionsEnabled)))
            } else {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    entries.forEach { entry ->
                        MemoryEntryRow(
                            entry = entry,
                            actionsEnabled = actionsEnabled,
                            onRemoveMemoryEntry = onRemoveMemoryEntry,
                            onSetMemoryEntryEnabled = onSetMemoryEntryEnabled,
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun MemoryEntryRow(
    entry: RuntimeMemoryEntry,
    actionsEnabled: Boolean,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val showDeleteConfirmation = rememberSaveable(entry.id) { mutableStateOf(false) }
    val memoryActionLabel = memoryAccessibilityActionLabel(
        content = entry.content,
        fallback = stringResource(R.string.memory_title),
    )
    val memoryStateDescription = stringResource(
        if (entry.enabled) {
            R.string.memory_enabled
        } else {
            R.string.memory_paused
        },
    )
    val memoryToggleContentDescription = stringResource(
        if (entry.enabled) {
            R.string.memory_pause_named
        } else {
            R.string.memory_enable_named
        },
        memoryActionLabel,
    )
    val memoryRemoveContentDescription = stringResource(R.string.memory_remove_named, memoryActionLabel)

    if (showDeleteConfirmation.value) {
        AlertDialog(
            onDismissRequest = {
                showDeleteConfirmation.value = false
            },
            title = {
                Text(stringResource(R.string.memory_remove_confirm_title))
            },
            text = {
                Text(stringResource(R.string.memory_remove_confirm_message))
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                        showDeleteConfirmation.value = false
                        onRemoveMemoryEntry(entry.id)
                    },
                    enabled = actionsEnabled,
                    modifier = Modifier.semantics {
                        contentDescription = memoryRemoveContentDescription
                        onClick(label = memoryRemoveContentDescription, action = null)
                    },
                ) {
                    Text(stringResource(R.string.delete))
                }
            },
            dismissButton = {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                        showDeleteConfirmation.value = false
                    },
                ) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Text(
                text = entry.content,
                modifier = Modifier.weight(1f),
                style = MaterialTheme.typography.bodyMedium,
                color = if (entry.enabled) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.58f)
                },
            )
            Text(
                text = stringResource(
                    if (entry.enabled) {
                        R.string.memory_enabled
                    } else {
                        R.string.memory_paused
                    },
                ),
                style = MaterialTheme.typography.labelSmall,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Switch(
                checked = entry.enabled,
                onCheckedChange = { enabled ->
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                    onSetMemoryEntryEnabled(entry.id, enabled)
                },
                enabled = actionsEnabled,
                modifier = Modifier.semantics {
                    contentDescription = memoryToggleContentDescription
                    stateDescription = memoryStateDescription
                    onClick(label = memoryToggleContentDescription, action = null)
                },
            )
            FilledTonalIconButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    showDeleteConfirmation.value = true
                },
                enabled = actionsEnabled,
                modifier = Modifier
                    .size(40.dp)
                    .semantics {
                        contentDescription = memoryRemoveContentDescription
                        onClick(label = memoryRemoveContentDescription, action = null)
                    },
            ) {
                Icon(
                    imageVector = Icons.Filled.Delete,
                    contentDescription = null,
                )
            }
        }
    }
}

internal const val MEMORY_ACTION_LABEL_MAX_CHARS = 80

private fun memoryAccessibilityActionLabel(
    content: String,
    fallback: String,
    maxCharacters: Int = MEMORY_ACTION_LABEL_MAX_CHARS,
): String {
    val normalized = content
        .trim()
        .replace(Regex("\\s+"), " ")
    val label = normalized.ifBlank { fallback }
    if (label.length <= maxCharacters) return label
    return label.take(maxCharacters).trimEnd() + "..."
}

@Composable
private fun StatusLine(label: String, value: String) {
    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Medium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
        )
        HorizontalDivider()
    }
}

@Composable
private fun EmptyState(text: String) {
    Surface(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant,
    ) {
        Text(
            text = text,
            modifier = Modifier.padding(16.dp),
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.secondary,
        )
    }
}

@Composable
private fun ErrorText(
    error: RuntimeUiError?,
    routeAction: RouteNoticePrimaryAction? = null,
    onConnect: (() -> Unit)? = null,
    onScanLatestQr: (() -> Unit)? = null,
) {
    if (error == null) return

    if (error.isRouteAvailabilityNotice()) {
        RouteAvailabilityNotice(
            error = error,
            action = routeAction,
            onConnect = onConnect,
            onScanLatestQr = onScanLatestQr,
        )
        return
    }

    val errorTitle = stringResource(R.string.error_title)
    val errorLabel = runtimeErrorLabel(error)
    val detailText = runtimeVisibleErrorDetail(error) ?: runtimeErrorDetailLabel(error)
    val detailLabel = detailText?.let { detail -> stringResource(R.string.error_detail, detail) }
    val diagnosticLabel = runtimeErrorDiagnosticLabel(error)
    val accessibilityBody = listOfNotNull(errorLabel, detailLabel, diagnosticLabel)
        .joinToString(" ")
    val accessibilitySummary = stringResource(
        R.string.error_accessibility_summary,
        errorTitle,
        accessibilityBody,
    )

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .clearAndSetSemantics {
                contentDescription = accessibilitySummary
                liveRegion = LiveRegionMode.Polite
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.errorContainer,
    ) {
        Row(
            modifier = Modifier.padding(12.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Filled.Error,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onErrorContainer,
            )
            Spacer(Modifier.width(8.dp))
            Column {
                Text(
                    text = errorTitle,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
                Text(
                    text = errorLabel,
                    color = MaterialTheme.colorScheme.onErrorContainer,
                )
                detailLabel?.let { detail ->
                    Text(
                        text = detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
                diagnosticLabel?.let { diagnostic ->
                    Text(
                        text = diagnostic,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                    )
                }
            }
        }
    }
}

@Composable
private fun RouteAvailabilityNotice(
    error: RuntimeUiError,
    action: RouteNoticePrimaryAction?,
    onConnect: (() -> Unit)?,
    onScanLatestQr: (() -> Unit)?,
) {
    val body = routeAvailabilityCompactLabel(error)
    val title = stringResource(R.string.route_notice_title)
    val statusDescription = stringResource(R.string.route_notice_status_refresh_needed)
    val accessibilitySummary = stringResource(
        R.string.route_notice_accessibility_summary,
        title,
        statusDescription,
        body,
    )
    val hapticFeedback = LocalHapticFeedback.current
    val actionHandler = when (action) {
        RouteNoticePrimaryAction.Connect -> onConnect
        RouteNoticePrimaryAction.ScanLatestQr -> onScanLatestQr
        null -> null
    }
    val actionLabel = action?.let { stringResource(routeNoticeActionLabelRes(it)) }

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = accessibilitySummary
                stateDescription = statusDescription
                liveRegion = LiveRegionMode.Polite
            }
            .let { base ->
                if (actionHandler == null) {
                    base
                } else {
                    base.clickable(
                        role = Role.Button,
                        onClickLabel = actionLabel,
                    ) {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        actionHandler()
                    }
                }
            },
        shape = RoundedCornerShape(24.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.56f),
    ) {
        Row(
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp),
            verticalAlignment = Alignment.CenterVertically,
        ) {
            Icon(
                Icons.Filled.Link,
                contentDescription = null,
                tint = MaterialTheme.colorScheme.secondary,
                modifier = Modifier.size(16.dp),
            )
            Text(
                text = body,
                modifier = Modifier.weight(1f),
                color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.86f),
                style = MaterialTheme.typography.bodySmall,
                fontWeight = FontWeight.Medium,
                maxLines = 3,
                overflow = TextOverflow.Ellipsis,
            )
            if (actionLabel != null && actionHandler != null) {
                Text(
                    text = actionLabel,
                    color = MaterialTheme.colorScheme.primary,
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun routeAvailabilityCompactLabel(error: RuntimeUiError): String {
    return stringResource(routeAvailabilityCompactLabelRes(error))
}

@StringRes
internal fun routeAvailabilityCompactLabelRes(error: RuntimeUiError): Int {
    return when (error.diagnosticCode) {
        "route_diagnostic_relay_failed" -> R.string.route_diagnostic_relay_failed
        "route_diagnostic_relay_auth_failed" -> R.string.route_diagnostic_relay_auth_failed
        "route_diagnostic_remote_route_expired" -> R.string.route_diagnostic_remote_route_expired
        "route_diagnostic_direct_qr_rejected" -> R.string.route_diagnostic_direct_qr_rejected
        "route_diagnostic_relay_qr_unreachable" -> R.string.route_diagnostic_relay_qr_unreachable
        else -> when {
            error.code == "remote_route_unreachable" -> R.string.error_remote_route_unreachable
            error.code == "pairing_endpoint_unavailable" -> R.string.route_notice_pairing_endpoint_unavailable
            error.code == "remote_routes_unavailable" ||
                error.code == "remote_route_expired" ||
                error.code == "pairing_route_retrying" ||
                error.code == "pairing_direct_route_rejected" ||
                error.code == "pairing_relay_route_rejected" ||
                error.diagnosticCode in RELAY_ROUTE_NEEDED_DIAGNOSTIC_CODES ->
                R.string.route_notice_short_relay_needed
            else -> R.string.route_notice_short_unavailable
        }
    }
}

private fun RuntimeUiError.isRouteAvailabilityNotice(): Boolean {
    return code in ROUTE_AVAILABILITY_NOTICE_CODES || diagnosticCode in ROUTE_AVAILABILITY_DIAGNOSTIC_CODES
}

private val ROUTE_AVAILABILITY_NOTICE_CODES = setOf(
    "no_route",
    "no_connectable_route",
    "remote_routes_unavailable",
    "remote_route_unreachable",
    "remote_route_expired",
    "pairing_required",
    "authentication_required",
    "pairing_route_retrying",
    "pairing_endpoint_unavailable",
    "pairing_direct_route_rejected",
    "pairing_relay_route_rejected",
)

private val ROUTE_AVAILABILITY_DIAGNOSTIC_CODES = setOf(
    "route_diagnostic_local_missing_remote_pending",
    "route_diagnostic_direct_failed_remote_pending",
    "route_diagnostic_remote_pending",
    "route_diagnostic_relay_failed",
    "route_diagnostic_relay_auth_failed",
    "route_diagnostic_remote_route_expired",
    "route_diagnostic_direct_qr_rejected",
    "route_diagnostic_relay_qr_unreachable",
)

private val RELAY_ROUTE_NEEDED_DIAGNOSTIC_CODES = setOf(
    "route_diagnostic_local_missing_remote_pending",
    "route_diagnostic_direct_failed_remote_pending",
    "route_diagnostic_remote_pending",
    "route_diagnostic_relay_failed",
    "route_diagnostic_relay_auth_failed",
    "route_diagnostic_remote_route_expired",
    "route_diagnostic_direct_qr_rejected",
    "route_diagnostic_relay_qr_unreachable",
)

private val QR_REFRESH_EMPTY_CHAT_ERROR_CODES = setOf(
    "remote_routes_unavailable",
    "remote_route_unreachable",
    "remote_route_expired",
    "pairing_required",
    "authentication_required",
    "pairing_route_retrying",
    "pairing_endpoint_unavailable",
    "pairing_direct_route_rejected",
    "pairing_relay_route_rejected",
)

private val QR_REFRESH_EMPTY_CHAT_DIAGNOSTIC_CODES = RELAY_ROUTE_NEEDED_DIAGNOSTIC_CODES

private fun RuntimeUiError.requiresLatestQrRouteNotice(): Boolean {
    return code in QR_REFRESH_EMPTY_CHAT_ERROR_CODES ||
        diagnosticCode in QR_REFRESH_EMPTY_CHAT_DIAGNOSTIC_CODES
}

internal const val CHAT_MESSAGE_LIST_TEST_TAG = "aetherlink_chat_message_list"

private fun selectedModelIsUsable(state: RuntimeUiState): Boolean {
    val selectedId = state.selectedModelId ?: return false
    val selectedModel = state.models.firstOrNull { it.id == selectedId && it.isChatModel() }
    return selectedModel?.installed == true
}

private fun selectedModelIsMissingFromRuntime(state: RuntimeUiState): Boolean {
    val selectedId = state.selectedModelId ?: return false
    return state.models.none { it.id == selectedId && it.isChatModel() }
}

internal fun chatComposerHasSendableContent(state: RuntimeUiState): Boolean {
    return state.chatInput.isNotBlank() || state.pendingAttachments.isNotEmpty()
}

internal fun chatComposerHasUnsupportedImageAttachment(state: RuntimeUiState): Boolean {
    if (state.pendingAttachments.none { it.type == "image" }) return false
    val selectedId = state.selectedModelId ?: return false
    val selectedModel = state.models.firstOrNull { it.id == selectedId && it.isChatModel() }
    return selectedModel?.supportsImageInput() != true
}

internal fun chatComposerCanEdit(state: RuntimeUiState): Boolean {
    return state.isConnected &&
        state.trustedRuntime != null &&
        !state.isStreaming &&
        selectedModelIsUsable(state)
}

internal fun chatComposerCanSend(state: RuntimeUiState): Boolean {
    return chatComposerCanEdit(state) &&
        chatComposerHasSendableContent(state) &&
        !chatComposerHasUnsupportedImageAttachment(state)
}

internal fun chatComposerShouldShowStatus(
    enabled: Boolean,
    isStreaming: Boolean,
    hint: String,
    hasWarning: Boolean,
): Boolean {
    return !isStreaming &&
        hint.isNotBlank() &&
        (!enabled || hasWarning)
}

internal fun shouldAutoScrollChat(
    lastVisibleItemIndex: Int?,
    totalItemsCount: Int,
    messageCountChanged: Boolean,
    newUserMessageAdded: Boolean = false,
    nearBottomThreshold: Int = 1,
): Boolean {
    if (totalItemsCount <= 0) return false
    if (lastVisibleItemIndex == null) return true
    if (messageCountChanged && newUserMessageAdded) return true
    val latestItemIndex = totalItemsCount - 1
    return lastVisibleItemIndex >= latestItemIndex - nearBottomThreshold
}

internal fun newUserMessageAddedSince(
    previousMessageCount: Int,
    messages: List<RuntimeChatMessage>,
    isStreaming: Boolean,
): Boolean {
    if (!isStreaming || messages.isEmpty()) return false
    val startIndex = previousMessageCount.coerceIn(0, messages.size)
    if (startIndex == messages.size) return false
    return messages
        .drop(startIndex)
        .any { message -> message.role == "user" }
}

internal fun shouldShowJumpToLatestChatButton(
    lastVisibleItemIndex: Int?,
    totalItemsCount: Int,
    nearBottomThreshold: Int = 1,
): Boolean {
    if (lastVisibleItemIndex == null) return false
    return !shouldAutoScrollChat(
        lastVisibleItemIndex = lastVisibleItemIndex,
        totalItemsCount = totalItemsCount,
        messageCountChanged = false,
        nearBottomThreshold = nearBottomThreshold,
    )
}

@Composable
private fun chatInputHint(state: RuntimeUiState): String {
    return chatInputHintRes(state)?.let { stringResource(it) }.orEmpty()
}

@StringRes
internal fun chatInputHintRes(state: RuntimeUiState): Int? {
    return when {
        state.trustedRuntime == null -> R.string.chat_hint_pairing
        !state.isConnected && shouldScanLatestQrFromEmptyChat(state) -> R.string.chat_hint_scan_latest_qr
        !state.isConnected && !hasConnectableTrustedRuntimeRoute(state) -> R.string.chat_hint_scan_latest_qr
        !state.isConnected -> R.string.chat_hint_connect
        state.selectedModelId == null -> R.string.chat_hint_select_model
        selectedModelIsMissingFromRuntime(state) -> R.string.chat_hint_model_unavailable
        !selectedModelIsUsable(state) -> R.string.chat_hint_install_model
        chatComposerHasUnsupportedImageAttachment(state) -> R.string.chat_hint_select_vision_model
        state.isStreaming -> R.string.chat_hint_wait_for_stream
        else -> null
    }
}

@Composable
private fun chatEmptyTitle(state: RuntimeUiState, preferQrRouteRefresh: Boolean = false): String {
    return when {
        preferQrRouteRefresh -> stringResource(R.string.status_route_needed_title)
        state.trustedRuntime == null -> stringResource(R.string.empty_chat_pairing_title)
        !state.isConnected -> stringResource(R.string.empty_chat_disconnected_title)
        state.isStreaming -> stringResource(R.string.empty_chat_streaming_title)
        else -> stringResource(R.string.empty_chat_no_model_title)
    }
}

@Composable
private fun chatEmptyText(state: RuntimeUiState, preferQrRouteRefresh: Boolean = false): String {
    return stringResource(chatEmptyTextRes(state, preferQrRouteRefresh))
}

@StringRes
internal fun chatEmptyTextRes(state: RuntimeUiState, preferQrRouteRefresh: Boolean = false): Int {
    val error = state.error
    return when {
        preferQrRouteRefresh && (
            error?.diagnosticCode == "route_diagnostic_relay_failed" ||
                error?.code == "remote_route_unreachable"
        ) -> R.string.empty_chat_relay_route_unreachable
        preferQrRouteRefresh && (
            error?.diagnosticCode == "route_diagnostic_relay_qr_unreachable" ||
                error?.code == "pairing_relay_route_rejected"
        ) -> R.string.empty_chat_relay_qr_unreachable
        preferQrRouteRefresh && (
            error?.diagnosticCode == "route_diagnostic_relay_auth_failed" ||
                error?.code == "remote_route_auth_failed"
        ) -> R.string.route_diagnostic_relay_auth_failed
        preferQrRouteRefresh && (
            error?.diagnosticCode == "route_diagnostic_direct_qr_rejected" ||
                error?.code == "pairing_direct_route_rejected"
        ) -> R.string.route_diagnostic_direct_qr_rejected
        preferQrRouteRefresh && (
            error?.diagnosticCode == "route_diagnostic_remote_route_expired" ||
                error?.code == "remote_route_expired"
        ) -> R.string.route_diagnostic_remote_route_expired
        preferQrRouteRefresh && error?.code == "pairing_endpoint_unavailable" ->
            R.string.route_notice_pairing_endpoint_unavailable
        preferQrRouteRefresh -> R.string.route_notice_short_relay_needed
        state.trustedRuntime == null -> R.string.empty_chat_pairing
        !state.isConnected -> R.string.empty_chat_disconnected
        state.isStreaming -> R.string.empty_chat_streaming
        selectedModelIsMissingFromRuntime(state) -> R.string.selected_model_unavailable
        else -> R.string.empty_chat_no_model
    }
}

internal fun shouldScanLatestQrFromEmptyChat(state: RuntimeUiState): Boolean {
    if (state.isConnected || state.trustedRuntime == null) return false
    val error = state.error ?: return false
    return error.code in QR_REFRESH_EMPTY_CHAT_ERROR_CODES ||
        error.diagnosticCode in QR_REFRESH_EMPTY_CHAT_DIAGNOSTIC_CODES
}

internal fun shouldShowChatBottomError(state: RuntimeUiState): Boolean {
    return !(state.messages.isEmpty() && shouldScanLatestQrFromEmptyChat(state))
}

internal enum class ChatEmptyPrimaryAction {
    Connect,
    ScanQr,
}

@StringRes
internal fun chatEmptyScanActionLabelRes(state: RuntimeUiState): Int {
    return if (state.trustedRuntime == null) {
        R.string.scan_qr
    } else {
        R.string.route_notice_action_scan_qr
    }
}

@Composable
private fun chatEmptyPrimaryActionStateDescription(
    state: RuntimeUiState,
    primaryAction: ChatEmptyPrimaryAction,
): String {
    if (state.isConnecting) {
        return stringResource(R.string.connect_runtime_state_connecting)
    }
    return when (primaryAction) {
        ChatEmptyPrimaryAction.Connect -> stringResource(R.string.connect_runtime_state_ready)
        ChatEmptyPrimaryAction.ScanQr -> {
            if (state.trustedRuntime == null) {
                stringResource(R.string.scan_qr_state_ready)
            } else {
                stringResource(R.string.scan_latest_qr_state_ready)
            }
        }
    }
}

internal fun chatEmptyPrimaryAction(state: RuntimeUiState): ChatEmptyPrimaryAction? {
    if (state.messages.isNotEmpty() || state.isConnected) return null
    return when {
        shouldScanLatestQrFromEmptyChat(state) -> ChatEmptyPrimaryAction.ScanQr
        state.trustedRuntime == null -> ChatEmptyPrimaryAction.ScanQr
        else -> ChatEmptyPrimaryAction.Connect
    }
}

internal fun shouldShowChatEmptyState(state: RuntimeUiState): Boolean {
    if (state.messages.isNotEmpty()) return false
    if (shouldScanLatestQrFromEmptyChat(state)) return true
    if (!state.isConnected) return true
    if (state.isStreaming) return true
    if (!selectedModelIsUsable(state)) return true
    return false
}

internal fun memoryActionsEnabled(state: RuntimeUiState): Boolean {
    return state.isConnected && state.trustedRuntime != null
}

@StringRes
internal fun memoryLockNoticeTextRes(hasEntries: Boolean): Int {
    return if (hasEntries) {
        R.string.memory_read_only_notice
    } else {
        R.string.memory_connect_to_load
    }
}

@StringRes
internal fun memoryEmptyStateTextRes(actionsEnabled: Boolean): Int {
    return if (actionsEnabled) {
        R.string.memory_empty
    } else {
        R.string.memory_empty_disconnected
    }
}

internal fun shouldShowAssistantSuggestions(
    isLatestAssistant: Boolean,
    hasAssistantOutput: Boolean,
    isStreaming: Boolean,
    isLoadingSuggestions: Boolean,
    suggestions: List<String>,
): Boolean {
    if (!isLatestAssistant || !hasAssistantOutput || isStreaming) return false
    return normalizedSuggestedQuestions(suggestions).isNotEmpty() || isLoadingSuggestions
}

internal fun shouldShowAssistantSuggestionsForMessage(
    state: RuntimeUiState,
    message: RuntimeChatMessage,
): Boolean {
    val isLatestAssistant = message.role == "assistant" &&
        message.id == state.messages.lastAssistantMessageId()
    return shouldShowAssistantSuggestions(
        isLatestAssistant = isLatestAssistant,
        hasAssistantOutput = message.content.isNotBlank(),
        isStreaming = state.isStreaming,
        isLoadingSuggestions = state.isLoadingSuggestions,
        suggestions = message.suggestions,
    )
}

@Composable
private fun runtimeErrorLabel(error: RuntimeUiError): String {
    return when (error.code) {
        "invalid_endpoint" -> stringResource(R.string.error_invalid_endpoint)
        "connection_failed" -> stringResource(R.string.error_connection_failed)
        "no_route" -> stringResource(R.string.error_no_runtime_route)
        "no_connectable_route" -> stringResource(R.string.error_no_connectable_runtime_route)
        "remote_routes_unavailable" -> stringResource(R.string.error_remote_routes_unavailable)
        "remote_route_unreachable" -> stringResource(R.string.error_remote_route_unreachable)
        "remote_route_expired" -> stringResource(R.string.error_remote_route_expired)
        "discovery_failed" -> stringResource(R.string.error_discovery_failed)
        "invalid_pairing_qr" -> stringResource(R.string.error_invalid_pairing_qr)
        "pairing_route_retrying" -> stringResource(R.string.error_pairing_route_retrying)
        "pairing_endpoint_unavailable" -> stringResource(R.string.error_pairing_endpoint_unavailable)
        "pairing_direct_route_rejected" -> stringResource(R.string.error_pairing_direct_route_rejected)
        "pairing_relay_route_rejected" -> stringResource(R.string.error_pairing_relay_route_rejected)
        "qr_scan_failed" -> stringResource(R.string.error_qr_scan_failed)
        "pair_first" -> stringResource(R.string.error_pair_first)
        "pairing_required" -> stringResource(R.string.error_pairing_required)
        "pairing_rejected" -> stringResource(R.string.error_pairing_rejected)
        "runtime_identity_mismatch" -> stringResource(R.string.error_runtime_identity_mismatch)
        "runtime_authentication_failed" -> stringResource(R.string.error_runtime_authentication_failed)
        "authentication_required" -> stringResource(R.string.error_authentication_required)
        "authentication_failed" -> stringResource(R.string.error_authentication_failed)
        "device_identity_failed" -> stringResource(R.string.error_device_identity_failed)
        "select_model" -> stringResource(R.string.error_select_model)
        "select_chat_model" -> stringResource(R.string.error_select_chat_model)
        "select_embedding_model" -> stringResource(R.string.error_select_embedding_model)
        "connect_first" -> stringResource(R.string.error_connect_first)
        "receive_failed" -> stringResource(R.string.error_receive_failed)
        "remote_route_auth_failed" -> stringResource(R.string.error_remote_route_auth_failed)
        "generation_cancelled" -> stringResource(R.string.error_generation_cancelled)
        "generation_in_progress" -> stringResource(R.string.error_generation_in_progress)
        "chat_session_not_found" -> stringResource(R.string.error_chat_session_not_found)
        "chat_session_must_be_archived_before_delete" -> stringResource(R.string.error_chat_session_must_be_archived_before_delete)
        "chat_session_sync_failed" -> stringResource(R.string.error_chat_session_sync_failed)
        "chat_history_runtime_required" -> stringResource(R.string.error_chat_history_runtime_required)
        "memory_runtime_required" -> stringResource(R.string.error_memory_runtime_required)
        "runtime_error" -> stringResource(R.string.error_runtime_error)
        "send_failed" -> stringResource(R.string.error_send_failed)
        "invalid_payload" -> stringResource(R.string.error_invalid_payload)
        "install_model_first" -> stringResource(R.string.error_install_model_first)
        "model_install_failed" -> stringResource(R.string.error_model_install_failed)
        "attachment_too_large" -> stringResource(R.string.error_attachment_too_large)
        "attachment_read_failed" -> stringResource(R.string.error_attachment_read_failed)
        "attachment_limit_reached" -> stringResource(R.string.error_attachment_limit_reached)
        "select_vision_model" -> stringResource(R.string.error_select_vision_model)
        "unsupported_attachment" -> stringResource(R.string.error_unsupported_attachment)
        "unreadable_attachment" -> stringResource(R.string.error_unreadable_attachment)
        "ollama_auth_required" -> stringResource(R.string.error_ollama_auth_required)
        "backend_unavailable" -> stringResource(R.string.error_backend_unavailable)
        "generation_not_found" -> stringResource(R.string.error_generation_not_found)
        "transport_error" -> stringResource(R.string.error_transport_error)
        "internal_error" -> stringResource(R.string.error_internal_error)
        else -> stringResource(R.string.error_unknown)
    }
}

internal fun runtimeVisibleErrorDetail(error: RuntimeUiError): String? {
    return error.detail
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it.isNotEmpty() }
}

internal fun providerDiagnosticMessage(provider: RuntimeProviderStatus): String? {
    return provider.message
        .trim()
        .takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it.isNotEmpty() }
}

internal fun providerDiagnosticCode(provider: RuntimeProviderStatus): String? {
    return provider.code
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it.matches(PROVIDER_DIAGNOSTIC_CODE_PATTERN) }
}

internal fun providerDiagnosticsVisible(provider: RuntimeProviderStatus): Boolean {
    return providerDiagnosticMessage(provider) != null || providerDiagnosticCode(provider) != null
}

private fun String.containsBackendEndpointMaterial(): Boolean {
    return BACKEND_ENDPOINT_DETAIL_PATTERNS.any { pattern -> pattern.containsMatchIn(this) }
}

private val BACKEND_ENDPOINT_DETAIL_PATTERNS = listOf(
    Regex("https?://[^\\s,;)]+", RegexOption.IGNORE_CASE),
    Regex("\\b(?:[A-Za-z0-9.-]+|\\[[0-9A-Fa-f:]+])(?::)(?:11434|1234)\\b", RegexOption.IGNORE_CASE),
    Regex("\\b(?:Ollama|LM Studio)\\s+URL\\b", RegexOption.IGNORE_CASE),
    Regex("/(?:api/(?:tags|ps|pull|chat|show|v1)|v1/(?:models|chat|chat/completions))\\b", RegexOption.IGNORE_CASE),
    Regex(
        "(^|[\\s{,;?&])['\"]?(?:route[_-]?token|routeToken|discovery[_-]?token|discoveryToken|route[_-]?secret|routeSecret|relay[_-]?secret|relaySecret|remote[_-]?secret|remoteSecret|rendezvous[_-]?secret|rendezvousSecret|pairing[_-]?secret|pairingSecret|relay[_-]?id|relayId|remote[_-]?id|remoteId|route[_-]?id|routeId|rendezvous[_-]?id|rendezvousId|network[_-]?id|networkId|relay[_-]?nonce|relayNonce|remote[_-]?nonce|remoteNonce|route[_-]?nonce|routeNonce|rendezvous[_-]?nonce|rendezvousNonce|rt|rs|ri|rrn|rx)['\"]?\\s*[:=]\\s*['\"]?[^\\s'\",;})]+",
        RegexOption.IGNORE_CASE,
    ),
)

private val PROVIDER_DIAGNOSTIC_CODE_PATTERN = Regex("[A-Za-z][A-Za-z0-9_.-]{0,79}")

@Composable
private fun runtimeErrorDetailLabel(error: RuntimeUiError): String? {
    return when (error.code) {
        "qr_scan_failed" -> stringResource(R.string.error_qr_scanner_unavailable_detail)
        "ollama_auth_required" -> stringResource(R.string.error_ollama_auth_required_detail)
        else -> null
    }
}

@Composable
private fun runtimeErrorDiagnosticLabel(error: RuntimeUiError): String? {
    return when (error.diagnosticCode) {
        "route_diagnostic_local_missing_remote_pending" ->
            stringResource(R.string.route_diagnostic_local_missing_remote_pending)
        "route_diagnostic_direct_failed_remote_pending" ->
            stringResource(R.string.route_diagnostic_direct_failed_remote_pending)
        "route_diagnostic_remote_pending" ->
            stringResource(R.string.route_diagnostic_remote_pending)
        "route_diagnostic_relay_failed" ->
            stringResource(R.string.route_diagnostic_relay_failed)
        "route_diagnostic_relay_auth_failed" ->
            stringResource(R.string.route_diagnostic_relay_auth_failed)
        "route_diagnostic_remote_route_expired" ->
            stringResource(R.string.route_diagnostic_remote_route_expired)
        "route_diagnostic_direct_qr_rejected" ->
            stringResource(R.string.route_diagnostic_direct_qr_rejected)
        "route_diagnostic_relay_qr_unreachable" ->
            stringResource(R.string.route_diagnostic_relay_qr_unreachable)
        else -> null
    }
}

@Composable
private fun providerStatusSummary(state: RuntimeUiState): String {
    if (state.providerStatuses.isEmpty()) {
        return backendStatusLabel(state.backendAvailable)
    }
    val totalCount = state.providerStatuses.size
    val availableCount = state.providerStatuses.count { it.available }
    return when (availableCount) {
        totalCount -> stringResource(R.string.provider_status_summary_all_ready)
        0 -> stringResource(R.string.provider_status_summary_none_ready)
        else -> stringResource(
            R.string.provider_status_summary_mixed,
            availableCount,
            totalCount,
        )
    }
}

@Composable
private fun providerStatusDetail(provider: RuntimeProviderStatus): String {
    if (provider.available) {
        return stringResource(R.string.provider_status_ready_detail, provider.name)
    }
    return when (provider.id) {
        "ollama" -> stringResource(R.string.provider_ollama_unavailable_hint)
        "lm_studio" -> stringResource(R.string.provider_lm_studio_unavailable_hint)
        else -> stringResource(R.string.provider_unavailable_hint, provider.name)
    }
}

private fun savedRuntimeModelDisplayName(modelId: String): String {
    val trimmed = modelId.trim()
    if (trimmed.isEmpty()) return trimmed
    val providerPrefix = trimmed.substringBefore(':', missingDelimiterValue = "")
        .lowercase(Locale.US)
    return if (providerPrefix in modelDisplayProviderPrefixes && ':' in trimmed) {
        trimmed.substringAfter(':').takeIf { it.isNotBlank() } ?: trimmed
    } else {
        trimmed
    }
}

private val modelDisplayProviderPrefixes = setOf(
    "ollama",
    "lmstudio",
    "lm_studio",
    "companion",
    "runtime",
)

@Composable
private fun runtimeStatusLabel(status: String): String {
    return when (status.lowercase()) {
        "disconnected" -> stringResource(R.string.status_disconnected)
        "connecting" -> stringResource(R.string.status_connecting)
        "connected" -> stringResource(R.string.status_connected)
        "pairing" -> stringResource(R.string.status_pairing)
        "pairing_required" -> stringResource(R.string.status_pairing_required)
        "route_refreshed" -> stringResource(R.string.status_route_refreshed)
        "authenticated" -> stringResource(R.string.status_authenticated)
        "failed" -> stringResource(R.string.status_failed)
        "ok" -> stringResource(R.string.status_ok)
        else -> stringResource(R.string.status_unknown)
    }
}

@Composable
private fun backendStatusLabel(available: Boolean?): String {
    return when (available) {
        true -> stringResource(R.string.backend_available)
        false -> stringResource(R.string.backend_unavailable)
        null -> stringResource(R.string.status_unknown)
    }
}
