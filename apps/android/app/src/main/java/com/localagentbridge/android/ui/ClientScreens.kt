package com.localagentbridge.android.ui

import android.content.ClipData
import android.text.format.Formatter
import android.widget.Toast
import androidx.annotation.StringRes
import com.localagentbridge.android.isAetherLinkPairingQrCandidateValue
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
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
import androidx.compose.foundation.layout.FlowRowScope
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
import androidx.compose.foundation.lazy.itemsIndexed
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
import androidx.compose.material.icons.filled.Edit
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
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
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
import androidx.compose.ui.semantics.disabled
import androidx.compose.ui.semantics.heading
import androidx.compose.ui.semantics.liveRegion
import androidx.compose.ui.semantics.onClick
import androidx.compose.ui.semantics.onLongClick
import androidx.compose.ui.semantics.semantics
import androidx.compose.ui.semantics.stateDescription
import androidx.compose.ui.text.AnnotatedString
import androidx.compose.ui.text.SpanStyle
import androidx.compose.ui.text.buildAnnotatedString
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.style.TextDecoration
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.text.withStyle
import androidx.compose.ui.unit.dp
import com.localagentbridge.android.R
import com.localagentbridge.android.core.pairing.isAllowedRemoteRelayScope
import com.localagentbridge.android.core.pairing.isEligibleRemoteRelayHost
import com.localagentbridge.android.core.transport.RuntimeEndpointSource
import com.localagentbridge.android.runtime.APP_LANGUAGE_SOURCE_DEFAULT
import com.localagentbridge.android.runtime.APP_LANGUAGE_SOURCE_IN_APP
import com.localagentbridge.android.runtime.APP_LANGUAGE_SOURCE_SYSTEM
import com.localagentbridge.android.runtime.RuntimeAppLanguage
import com.localagentbridge.android.runtime.RuntimeAppTheme
import com.localagentbridge.android.runtime.RuntimeActiveRouteKind
import com.localagentbridge.android.runtime.MAX_PENDING_ATTACHMENTS
import com.localagentbridge.android.runtime.RuntimeChatMessage
import com.localagentbridge.android.runtime.RuntimeChatSession
import com.localagentbridge.android.runtime.RuntimeDiscoveredRuntime
import com.localagentbridge.android.runtime.RuntimeMemoryEntry
import com.localagentbridge.android.runtime.RuntimeMemorySummaryDraft
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
        modifier = Modifier
            .fillMaxWidth()
            .testTag(SETTINGS_QR_PAIRING_PANEL_TEST_TAG),
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
                    modifier = Modifier.semantics {
                        heading()
                    },
                )
            }
            Text(
                text = stringResource(R.string.qr_pairing_detail),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
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
                    .heightIn(min = 54.dp)
                    .testTag(SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG)
                    .semantics {
                        stateDescription = scanQrStateDescription
                        onClick(label = scanQrActionLabel, action = null)
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
                onClick(label = actionLabel, action = null)
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
    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(CONNECTION_STATUS_PANEL_TEST_TAG),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            ConnectionStatusHero(state = state)
            StatusLine(
                label = stringResource(R.string.runtime),
                value = runtimeStatusLabel(state.runtimeStatus),
                tagKey = CONNECTION_STATUS_RUNTIME_LINE_KEY,
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
                    tagKey = CONNECTION_STATUS_PAIRING_LINE_KEY,
                )
            }
            StatusLine(
                label = stringResource(R.string.backend),
                value = backendStatusLabel(state.backendAvailable),
                tagKey = CONNECTION_STATUS_BACKEND_LINE_KEY,
            )
            StatusLine(
                label = stringResource(R.string.providers),
                value = providerStatusSummary(state),
                tagKey = CONNECTION_STATUS_PROVIDERS_LINE_KEY,
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
                tagKey = CONNECTION_STATUS_CONNECTED_LINE_KEY,
            )
            StatusLine(
                label = stringResource(R.string.auto_reconnect),
                value = if (state.trustedRuntimeAutoReconnectEnabled) {
                    stringResource(R.string.yes)
                } else {
                    stringResource(R.string.no)
                },
                tagKey = CONNECTION_STATUS_AUTO_RECONNECT_LINE_KEY,
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
    val hasConnectableRoute = hasConnectableTrustedRuntimeRoute(state)
    val needsRoute = state.trustedRuntime != null && !hasConnectableRoute && !state.isConnected

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
            .testTag(CONNECTION_STATUS_HERO_TEST_TAG)
            .semantics(mergeDescendants = true) {
                contentDescription = accessibilitySummary
            },
        shape = RoundedCornerShape(16.dp),
        color = containerColor,
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .testTag(CONNECTION_STATUS_HERO_ROW_TEST_TAG)
                .padding(horizontal = 14.dp, vertical = 12.dp),
            horizontalArrangement = Arrangement.spacedBy(10.dp),
            verticalAlignment = Alignment.Top,
        ) {
            Icon(
                imageVector = icon,
                contentDescription = null,
                tint = contentColor,
                modifier = Modifier
                    .size(22.dp)
                    .testTag(CONNECTION_STATUS_HERO_ICON_TEST_TAG),
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
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.testTag(CONNECTION_STATUS_HERO_TITLE_TEST_TAG),
                )
                Text(
                    text = detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = contentColor,
                    modifier = Modifier.testTag(CONNECTION_STATUS_HERO_DETAIL_TEST_TAG),
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
    val hasConnectableRoute = hasConnectableTrustedRuntimeRoute(state)
    val needsRoute = state.trustedRuntime != null && !hasConnectableRoute && !state.isConnected
    val hasSavedRelayRoute = hasRelayRoute && !state.isConnected
    val hasSavedRoute = hasConnectableRoute && !state.isConnected

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
    val hasConnectableRoute = hasConnectableTrustedRuntimeRoute(state)
    val needsRoute = state.trustedRuntime != null && !hasConnectableRoute && !state.isConnected
    val hasSavedRelayRoute = hasRelayRoute && !state.isConnected
    val hasSavedRoute = hasConnectableRoute && !state.isConnected

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
    return isAllowedRemoteRelayScope(relayScope) &&
        isEligibleRemoteRelayHost(host, relayScope) &&
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
    return isAllowedRemoteRelayScope(runtime.relayScope) &&
        isEligibleRemoteRelayHost(host, runtime.relayScope) &&
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
    val endpointHint = trustedRuntime.endpointHint
    if (endpointHint != null && endpointHint.source != RuntimeEndpointSource.TrustedLastKnown) return true
    return state.runtimeEndpointSource.isCurrentDirectRouteCandidate() && state.runtimeHost.isNotBlank()
}

private fun RuntimeEndpointSource.isCurrentDirectRouteCandidate(): Boolean {
    return this != RuntimeEndpointSource.Manual && this != RuntimeEndpointSource.TrustedLastKnown
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
    if (state.runtimeEndpointSource.isCurrentDirectRouteCandidate() && state.runtimeHost.isNotBlank()) {
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
    val refreshHealthActionLabel = stringResource(R.string.refresh_health)
    val disconnectActionLabel = stringResource(R.string.disconnect)
    val actionsEnabled = !state.isConnecting
    val connectedActionDisabledState = stringResource(R.string.connect_runtime_state_connecting)
    val refreshHealthStateDescription = if (actionsEnabled) {
        stringResource(R.string.refresh_health_state_ready)
    } else {
        connectedActionDisabledState
    }
    val disconnectStateDescription = if (actionsEnabled) {
        stringResource(R.string.disconnect_runtime_state_ready)
    } else {
        connectedActionDisabledState
    }

    Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
        Button(
            onClick = {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                onRefreshHealth()
            },
            enabled = actionsEnabled,
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    stateDescription = refreshHealthStateDescription
                    onClick(label = refreshHealthActionLabel, action = null)
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
            enabled = actionsEnabled,
            modifier = Modifier
                .fillMaxWidth()
                .semantics {
                    stateDescription = disconnectStateDescription
                    onClick(label = disconnectActionLabel, action = null)
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
    val providerLabel = runtimeProviderDisplayName(providerStatusDisplayNameSource(provider))
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
            providerLabel,
            statusText,
            detailText,
            retryableHint,
        )
    } else {
        stringResource(
            R.string.provider_status_row_summary,
            providerLabel,
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
        providerLabel,
    )
    val hapticFeedback = LocalHapticFeedback.current

    Row(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(providerStatusRowTestTag(provider.id)),
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
                    .testTag(providerStatusHeaderTestTag(provider.id))
                    .semantics(mergeDescendants = true) {
                        contentDescription = rowAccessibilitySummary
                    },
                verticalArrangement = Arrangement.spacedBy(4.dp),
            ) {
                Text(
                    text = providerLabel,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.Medium,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Surface(
                    modifier = Modifier.testTag(providerStatusStatusTestTag(provider.id)),
                    shape = RoundedCornerShape(999.dp),
                    color = tint.copy(alpha = 0.10f),
                    contentColor = tint,
                ) {
                    Text(
                        text = statusText,
                        modifier = Modifier.padding(horizontal = 8.dp, vertical = 3.dp),
                        style = MaterialTheme.typography.labelMedium,
                        color = tint,
                        fontWeight = FontWeight.SemiBold,
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
                    modifier = Modifier
                        .testTag(providerStatusDiagnosticsButtonTestTag(provider.id))
                        .semantics {
                            contentDescription = diagnosticsContentDescription
                            stateDescription = diagnosticsStateDescription
                            onClick(label = diagnosticsContentDescription, action = null)
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
                        ),
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
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
                            .testTag(providerStatusDiagnosticsPanelTestTag(provider.id))
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
    onClearDraft: () -> Unit = { onInputChange("") },
    onSend: () -> Unit,
    onCancel: () -> Unit,
    onConnect: () -> Unit,
    onScanPairingQr: () -> Unit,
    onRefreshHealth: () -> Unit,
    onAttachFiles: () -> Unit,
    onRemoveAttachment: (String) -> Unit,
    onScanLatestQr: () -> Unit,
    onRegenerateLatestResponse: () -> Unit = {},
    onReuseLatestUserMessage: () -> Unit = {},
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
    val jumpToLatestActionLabel = stringResource(R.string.content_desc_jump_to_latest)
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
                if (state.isLoadingActiveChatMessages) {
                    ChatMessagesLoadingState()
                } else if (shouldShowChatEmptyState(state)) {
                    ChatEmptyState(
                        state = state,
                        onConnect = onConnect,
                        onScanPairingQr = onScanPairingQr,
                        onScanLatestQr = onScanLatestQr,
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
                verticalArrangement = Arrangement.spacedBy(0.dp),
                contentPadding = PaddingValues(
                    start = 4.dp,
                    top = 16.dp,
                    end = 4.dp,
                    bottom = composerDockSpace + 12.dp,
                ),
            ) {
                itemsIndexed(
                    items = state.messages,
                    key = { _, message -> message.id },
                ) { index, message ->
                    val isLatestAssistant = message.role == "assistant" &&
                        message.id == state.messages.lastAssistantMessageId()
                    val isLatestUser = message.role == "user" &&
                        message.id == state.messages.lastUserMessageId()
                    if (index > 0) {
                        Spacer(
                            modifier = Modifier.height(
                                chatTranscriptMessageGap(
                                    previousRole = state.messages[index - 1].role,
                                    currentRole = message.role,
                                ),
                            ),
                        )
                    }
                    ChatMessageRow(
                        message = message,
                        isStreaming = state.isStreaming &&
                            message.role == "assistant" &&
                            message.id == state.messages.lastOrNull()?.id,
                        showRegenerateAction = isLatestAssistant &&
                            message.content.isNotBlank() &&
                            !state.isStreaming &&
                            !state.isLoadingActiveChatMessages,
                        showReuseAction = isLatestUser &&
                            message.content.isNotBlank() &&
                            message.attachments.isEmpty() &&
                            !state.isStreaming &&
                            !state.isLoadingActiveChatMessages,
                        onRegenerateLatestResponse = onRegenerateLatestResponse,
                        onReuseLatestUserMessage = onReuseLatestUserMessage,
                        modifier = Modifier.testTag(chatMessageRowTestTag(message.id)),
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
                    .testTag(CHAT_JUMP_TO_LATEST_TEST_TAG)
                    .semantics {
                        stateDescription = jumpToLatestStateDescription
                        onClick(label = jumpToLatestActionLabel, action = null)
                    },
            ) {
                Icon(
                    imageVector = Icons.Filled.KeyboardArrowDown,
                    contentDescription = jumpToLatestActionLabel,
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
                onClearDraft = onClearDraft,
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
private fun ChatMessagesLoadingState() {
    val loadingText = stringResource(R.string.loading_chat_messages)
    Column(
        modifier = Modifier
            .widthIn(max = 280.dp)
            .semantics {
                contentDescription = loadingText
                liveRegion = LiveRegionMode.Polite
            },
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(14.dp),
    ) {
        LinearProgressIndicator(modifier = Modifier.fillMaxWidth())
        Text(
            text = loadingText,
            style = MaterialTheme.typography.bodyMedium,
            color = MaterialTheme.colorScheme.onSurfaceVariant,
            textAlign = TextAlign.Center,
        )
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
    val refreshHealthActionLabel = stringResource(R.string.refresh_health)

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(CHAT_BACKEND_READINESS_BANNER_TEST_TAG)
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
                        modifier = Modifier.testTag(CHAT_BACKEND_READINESS_TITLE_TEST_TAG),
                    )
                    Text(
                        text = detail,
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        modifier = Modifier.testTag(CHAT_BACKEND_READINESS_DETAIL_TEST_TAG),
                    )
                }
            }
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onRefreshHealth()
                },
                modifier = Modifier
                    .testTag(CHAT_BACKEND_READINESS_REFRESH_TEST_TAG)
                    .semantics {
                        stateDescription = refreshHealthStateDescription
                        onClick(label = refreshHealthActionLabel, action = null)
                    },
            ) {
                Icon(
                    imageVector = Icons.Filled.Refresh,
                    contentDescription = null,
                )
                Spacer(Modifier.width(8.dp))
                Text(
                    text = stringResource(R.string.refresh_health),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
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
    onFollowSystemLanguage: () -> Unit = {},
    onSetTheme: (RuntimeAppTheme) -> Unit,
    onSelectEmbeddingModel: (String?) -> Unit,
    onAddMemoryEntry: (String) -> Unit,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
    onApproveMemorySummaryDraft: (String) -> Unit = {},
    onDismissMemorySummaryDraft: (String) -> Unit = {},
    onRefreshMemory: () -> Unit = {},
    onRefreshChatHistory: (String?) -> Unit = {},
    onOpenChatSession: (String) -> Unit = {},
    onRenameChatSession: (String) -> Unit = {},
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
                selectedLanguageSource = state.selectedLanguageSource,
                onSetLanguageTag = onSetLanguageTag,
                onFollowSystemLanguage = onFollowSystemLanguage,
                selectedTheme = state.selectedTheme,
                onSetTheme = onSetTheme,
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
                    summaryDrafts = state.memorySummaryDrafts,
                    approvingSummaryDraftIds = state.approvingMemorySummaryDraftIds,
                    dismissingSummaryDraftIds = state.dismissingMemorySummaryDraftIds,
                    actionsEnabled = memoryActionsEnabled(state),
                    actionsDisabledReasonRes = memoryLockNoticeTextRes(
                        state = state,
                        hasEntries = state.memoryEntries.isNotEmpty(),
                    ),
                    onAddMemoryEntry = onAddMemoryEntry,
                    onRemoveMemoryEntry = onRemoveMemoryEntry,
                    onSetMemoryEntryEnabled = onSetMemoryEntryEnabled,
                    onApproveMemorySummaryDraft = onApproveMemorySummaryDraft,
                    onDismissMemorySummaryDraft = onDismissMemorySummaryDraft,
                    onRefreshMemory = onRefreshMemory,
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
                    activeChatSessionId = state.activeChatSessionId,
                    models = state.models,
                    isActionEnabled = !state.isStreaming,
                    canRefreshChatHistory = chatHistoryRefreshEnabled(state),
                    refreshStateDescriptionRes = chatHistoryRefreshStateDescriptionRes(state),
                    onRefreshChatHistory = onRefreshChatHistory,
                    onOpenChatSession = onOpenChatSession,
                    onRenameChatSession = onRenameChatSession,
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
internal fun AutoReconnectSettingRow(
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
    val autoReconnectDisabledStateDescription = stringResource(
        R.string.auto_reconnect_state_pair_first,
    )
    val autoReconnectActionLabel = stringResource(
        if (enabled) {
            R.string.setting_action_disable_named
        } else {
            R.string.setting_action_enable_named
        },
        autoReconnectContentDescription,
    )
    val autoReconnectModifier = if (canChange) {
        Modifier.semantics {
            contentDescription = autoReconnectContentDescription
            stateDescription = autoReconnectStateDescription
            onClick(label = autoReconnectActionLabel) {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                onSetAutoReconnectEnabled(!enabled)
                true
            }
        }
    } else {
        Modifier.clearAndSetSemantics {
            contentDescription = autoReconnectContentDescription
            stateDescription = autoReconnectDisabledStateDescription
            disabled()
        }
    }

    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(AUTO_RECONNECT_CARD_TEST_TAG),
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .testTag(AUTO_RECONNECT_ROW_TEST_TAG)
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
                    modifier = Modifier.testTag(AUTO_RECONNECT_TITLE_TEST_TAG),
                )
                Text(
                    text = stringResource(R.string.auto_reconnect_detail),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.testTag(AUTO_RECONNECT_DETAIL_TEST_TAG),
                )
            }
            Box(modifier = Modifier.testTag(AUTO_RECONNECT_SWITCH_TEST_TAG)) {
                Switch(
                    checked = enabled,
                    onCheckedChange = { checked ->
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                        onSetAutoReconnectEnabled(checked)
                    },
                    enabled = canChange,
                    modifier = autoReconnectModifier,
                )
            }
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
            modifier = Modifier.semantics {
                heading()
            },
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
        modifier = Modifier
            .fillMaxWidth()
            .testTag(settingsExpandableSectionTestTag(title)),
        verticalArrangement = Arrangement.spacedBy(12.dp),
    ) {
        HorizontalDivider()
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .testTag(settingsExpandableSectionHeaderTestTag(title))
                .clickable(
                    role = Role.Button,
                    onClickLabel = toggleActionLabel,
                    onClick = { toggleExpanded() },
                )
                .semantics(mergeDescendants = true) {
                    heading()
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
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.testTag(settingsExpandableSectionTitleTestTag(title)),
                )
                Text(
                    text = stringResource(subtitle),
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.testTag(settingsExpandableSectionSubtitleTestTag(title)),
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
                    modifier = Modifier.testTag(settingsExpandableSectionActionTestTag(title)),
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
        val forgetTrustedRuntimeConfirmMessage = stringResource(
            R.string.forget_trusted_runtime_confirm_message,
            trustedRuntime.name,
        )
        val confirmForgetActionContentDescription = stringResource(
            R.string.forget_trusted_runtime_confirm_action_named,
            trustedRuntime.name,
        )
        val cancelForgetActionContentDescription = stringResource(
            R.string.forget_trusted_runtime_cancel_action_named,
            trustedRuntime.name,
        )
        AlertDialog(
            onDismissRequest = { showForgetConfirmation = false },
            title = { Text(stringResource(R.string.forget_trusted_runtime_confirm_title)) },
            text = {
                Text(
                    text = forgetTrustedRuntimeConfirmMessage,
                    modifier = Modifier.semantics {
                        contentDescription = forgetTrustedRuntimeConfirmMessage
                    },
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                        showForgetConfirmation = false
                        onForgetTrustedRuntime()
                    },
                    modifier = Modifier.semantics {
                        contentDescription = confirmForgetActionContentDescription
                        onClick(label = confirmForgetActionContentDescription, action = null)
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
                    modifier = Modifier.semantics {
                        contentDescription = cancelForgetActionContentDescription
                        onClick(label = cancelForgetActionContentDescription, action = null)
                    },
                ) {
                    Text(stringResource(R.string.cancel))
                }
            },
        )
    }

    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(SETTINGS_TRUSTED_RUNTIME_PANEL_TEST_TAG),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(SETTINGS_TRUSTED_RUNTIME_HEADER_TEST_TAG),
                verticalAlignment = Alignment.CenterVertically,
            ) {
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
                    modifier = Modifier.testTag(SETTINGS_TRUSTED_RUNTIME_ICON_TEST_TAG),
                )
                Spacer(Modifier.width(8.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = stringResource(R.string.trusted_runtime),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.secondary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.testTag(SETTINGS_TRUSTED_RUNTIME_LABEL_TEST_TAG),
                    )
                    Text(
                        text = state.trustedRuntime?.name ?: stringResource(R.string.no_trusted_runtime),
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.testTag(SETTINGS_TRUSTED_RUNTIME_NAME_TEST_TAG),
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
                        .testTag(SETTINGS_TRUSTED_RUNTIME_FORGET_ACTION_TEST_TAG)
                        .semantics {
                            forgetTrustedRuntimeContentDescription?.let {
                                contentDescription = it
                                onClick(label = it, action = null)
                            }
                        },
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(
                        text = stringResource(R.string.forget),
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            } ?: Text(
                text = stringResource(R.string.trusted_runtime_detail),
                color = MaterialTheme.colorScheme.secondary,
                style = MaterialTheme.typography.bodyMedium,
                modifier = Modifier.testTag(SETTINGS_TRUSTED_RUNTIME_EMPTY_DETAIL_TEST_TAG),
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
                val manualQrPayloadOpenAccessibilityLabel =
                    stringResource(R.string.manual_qr_payload_open_accessibility)
                OutlinedButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        showManualPayloadDialog = true
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            contentDescription = manualQrPayloadOpenAccessibilityLabel
                            onClick(label = manualQrPayloadOpenAccessibilityLabel, action = null)
                        },
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
    val startDiscoveryActionLabel = if (state.isDiscovering) {
        stringResource(R.string.discovering_runtimes)
    } else {
        stringResource(R.string.discover_runtimes)
    }
    val stopDiscoveryActionLabel = stringResource(R.string.stop)

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
                            onClick(label = startDiscoveryActionLabel, action = null)
                        },
                ) {
                    Icon(Icons.Filled.Refresh, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(startDiscoveryActionLabel)
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
                            onClick(label = stopDiscoveryActionLabel, action = null)
                        },
                ) {
                    Icon(Icons.Filled.Close, contentDescription = null)
                    Spacer(Modifier.width(8.dp))
                    Text(stopDiscoveryActionLabel)
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
internal fun DiscoveredRuntimeRow(
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
        modifier = Modifier
            .fillMaxWidth()
            .testTag(discoveredRuntimeRowTestTag(peer.serviceName)),
        colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.surfaceVariant),
        shape = RoundedCornerShape(8.dp),
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
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
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
            if (canUseDiscoveredRoute) {
                TextButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        onUse(peer)
                    },
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(discoveredRuntimeActionTestTag(peer.serviceName))
                        .semantics {
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
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag(discoveredRuntimeStatusTestTag(peer.serviceName))
                        .semantics {
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
    onScanLatestQr: () -> Unit,
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
                heading()
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
                        ChatEmptyPrimaryAction.ScanQr -> {
                            if (preferQrRouteRefresh) {
                                onScanLatestQr()
                            } else {
                                onScanPairingQr()
                            }
                        }
                    }
                },
                enabled = !state.isConnecting,
                modifier = Modifier.semantics {
                    stateDescription = primaryActionStateDescription
                    onClick(label = primaryActionLabel, action = null)
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
    showRegenerateAction: Boolean,
    showReuseAction: Boolean,
    onRegenerateLatestResponse: () -> Unit,
    onReuseLatestUserMessage: () -> Unit,
    modifier: Modifier = Modifier,
) {
    val isUser = message.role == "user"
    val hapticFeedback = LocalHapticFeedback.current
    val roleLabel = stringResource(
        if (isUser) {
            R.string.role_user
        } else {
            R.string.role_assistant
        },
    )
    var attachmentAccessibilitySummary: String? = null
    if (message.content.isBlank() && message.attachments.isNotEmpty()) {
        val attachmentLabels = mutableListOf<String>()
        message.attachments.forEach { attachment ->
            attachmentLabels += attachmentAccessibilityDescription(attachment)
        }
        attachmentAccessibilitySummary = attachmentLabels.joinToString(separator = ". ")
    }
    val messageAccessibilitySummary = when {
        message.content.isNotBlank() -> {
            stringResource(R.string.chat_message_accessibility_summary, roleLabel, message.content)
        }
        attachmentAccessibilitySummary != null -> {
            stringResource(R.string.chat_message_accessibility_summary, roleLabel, attachmentAccessibilitySummary)
        }
        else -> null
    }
    val isAttachmentOnlyMessage = message.content.isBlank() && message.attachments.isNotEmpty()
    val showVisibleCopyAction = shouldShowVisibleMessageCopyAction(message.content)
    val copyMessageActionLabel = stringResource(R.string.copy_message)
    Row(
        modifier = modifier.fillMaxWidth(),
        horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
    ) {
        if (isUser) {
            Column(
                modifier = Modifier.widthIn(max = 548.dp),
                horizontalAlignment = Alignment.End,
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                val userMessageModifier = if (isAttachmentOnlyMessage && messageAccessibilitySummary != null) {
                    Modifier.semantics {
                        contentDescription = messageAccessibilitySummary
                    }
                } else {
                    Modifier
                }
                Column(
                    modifier = userMessageModifier,
                    horizontalAlignment = Alignment.End,
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Surface(
                        modifier = Modifier
                            .copyOnLongPress(message.content)
                            .then(
                                if (!isAttachmentOnlyMessage && messageAccessibilitySummary != null) {
                                    Modifier.semantics {
                                        contentDescription = messageAccessibilitySummary
                                    }
                                } else {
                                    Modifier
                                },
                            ),
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
                        messageId = message.id,
                        attachments = message.attachments,
                        horizontalAlignment = Alignment.End,
                    )
                }
                if (showVisibleCopyAction || showReuseAction) {
                    MessageActionRow(
                        messageId = message.id,
                        horizontalAlignment = Alignment.End,
                    ) {
                        if (showVisibleCopyAction) {
                            MessageCopyButton(
                                textToCopy = message.content,
                                copyActionLabel = copyMessageActionLabel,
                            )
                        }
                        if (showReuseAction) {
                            val reuseActionLabel = stringResource(R.string.reuse_message)
                            val reuseActionStateDescription =
                                stringResource(R.string.reuse_message_state_ready)
                            IconButton(
                                onClick = {
                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                    onReuseLatestUserMessage()
                                },
                                modifier = Modifier
                                    .size(36.dp)
                                    .semantics {
                                        contentDescription = reuseActionLabel
                                        stateDescription = reuseActionStateDescription
                                        onClick(label = reuseActionLabel, action = null)
                                    },
                            ) {
                                Icon(
                                    imageVector = Icons.Filled.Edit,
                                    contentDescription = null,
                                    modifier = Modifier.size(18.dp),
                                )
                            }
                        }
                    }
                }
            }
        } else {
            AssistantMessage(
                message = message,
                isStreaming = isStreaming,
                messageAccessibilitySummary = messageAccessibilitySummary,
                showVisibleCopyAction = showVisibleCopyAction,
                copyMessageActionLabel = copyMessageActionLabel,
                showRegenerateAction = showRegenerateAction,
                onRegenerateLatestResponse = onRegenerateLatestResponse,
            )
        }
    }
}

@Composable
private fun AssistantMessage(
    message: RuntimeChatMessage,
    isStreaming: Boolean,
    messageAccessibilitySummary: String?,
    showVisibleCopyAction: Boolean,
    copyMessageActionLabel: String,
    showRegenerateAction: Boolean,
    onRegenerateLatestResponse: () -> Unit,
) {
    val hasReasoning = message.reasoning.isNotBlank()
    val hapticFeedback = LocalHapticFeedback.current
    var isReasoningExpanded by rememberSaveable(message.id) {
        mutableStateOf(false)
    }
    val showTyping = assistantShowsTypingPlaceholder(message, isStreaming)
    val assistantTypingText = stringResource(R.string.assistant_typing)
    val assistantRoleLabel = stringResource(R.string.role_assistant)
    val isAttachmentOnlyMessage = message.content.isBlank() && message.attachments.isNotEmpty() && !showTyping

    Column(
        modifier = Modifier
            .widthIn(max = 720.dp)
            .fillMaxWidth()
            .then(
                if (isAttachmentOnlyMessage && messageAccessibilitySummary != null) {
                    Modifier.semantics {
                        contentDescription = messageAccessibilitySummary
                    }
                } else {
                    Modifier
                },
            ),
        verticalArrangement = Arrangement.spacedBy(10.dp),
    ) {
        if (hasReasoning) {
            AssistantReasoning(
                reasoning = message.reasoning,
                expanded = isReasoningExpanded,
                announceUpdates = isStreaming && message.isReasoningOpen,
                onExpandedChange = {
                    isReasoningExpanded = it
                },
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
            if (messageAccessibilitySummary != null && !showTyping) {
                contentModifier = contentModifier.semantics {
                    contentDescription = messageAccessibilitySummary
                    if (isStreaming) {
                        liveRegion = LiveRegionMode.Polite
                    }
                }
            }
            Row(
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.Top,
            ) {
                AssistantIdentityMarker(roleLabel = assistantRoleLabel)
                Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    MessageContent(
                        content = visibleContent,
                        textColor = MaterialTheme.colorScheme.onSurface,
                        modifier = contentModifier,
                    )
                    if ((showVisibleCopyAction && !showTyping) || showRegenerateAction) {
                        MessageActionRow(
                            messageId = message.id,
                            horizontalAlignment = Alignment.Start,
                        ) {
                            if (showVisibleCopyAction && !showTyping) {
                                MessageCopyButton(
                                    textToCopy = message.content,
                                    copyActionLabel = copyMessageActionLabel,
                                )
                            }
                            if (showRegenerateAction) {
                                val regenerateActionLabel = stringResource(R.string.regenerate_response)
                                val regenerateActionStateDescription =
                                    stringResource(R.string.regenerate_response_state_ready)
                                IconButton(
                                    onClick = {
                                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                        onRegenerateLatestResponse()
                                    },
                                    modifier = Modifier
                                        .size(36.dp)
                                        .semantics {
                                            contentDescription = regenerateActionLabel
                                            stateDescription = regenerateActionStateDescription
                                            onClick(label = regenerateActionLabel, action = null)
                                        },
                                ) {
                                    Icon(
                                        imageVector = Icons.Filled.Refresh,
                                        contentDescription = null,
                                        modifier = Modifier.size(18.dp),
                                    )
                                }
                            }
                        }
                    }
                }
            }
        }
        ReadOnlyAttachmentChips(
            messageId = message.id,
            attachments = message.attachments,
            horizontalAlignment = Alignment.Start,
        )
        if (showTyping) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(CHAT_STREAMING_PROGRESS_TEST_TAG),
            ) {
                StreamingProgressIndicator(
                    modifier = Modifier
                        .fillMaxWidth(),
                )
            }
        }
    }
}

@Composable
private fun StreamingProgressIndicator(modifier: Modifier = Modifier) {
    val transition = rememberInfiniteTransition()
    val offsetFraction by transition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(durationMillis = 1200, easing = LinearEasing),
        ),
    )
    val activeColor = MaterialTheme.colorScheme.primary
    val trackColor = MaterialTheme.colorScheme.primary.copy(alpha = 0.18f)

    Canvas(
        modifier = modifier
            .height(4.dp)
            .clearAndSetSemantics {},
    ) {
        val radius = CornerRadius(size.height / 2f, size.height / 2f)
        drawRoundRect(
            color = trackColor,
            topLeft = Offset.Zero,
            size = size,
            cornerRadius = radius,
        )
        val segmentWidth = size.width * 0.36f
        val segmentStart = (size.width + segmentWidth) * offsetFraction - segmentWidth
        drawRoundRect(
            color = activeColor,
            topLeft = Offset(segmentStart, 0f),
            size = Size(segmentWidth, size.height),
            cornerRadius = radius,
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MessageActionRow(
    messageId: String,
    horizontalAlignment: Alignment.Horizontal,
    content: @Composable FlowRowScope.() -> Unit,
) {
    FlowRow(
        modifier = Modifier.testTag(chatMessageActionsTestTag(messageId)),
        horizontalArrangement = Arrangement.spacedBy(4.dp, horizontalAlignment),
        verticalArrangement = Arrangement.spacedBy(2.dp),
        itemVerticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

@Composable
private fun AssistantIdentityMarker(roleLabel: String) {
    Box(
        modifier = Modifier
            .padding(top = 1.dp)
            .size(28.dp)
            .background(
                color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.82f),
                shape = RoundedCornerShape(999.dp),
            )
            .semantics(mergeDescendants = true) {
                contentDescription = roleLabel
            }
            .testTag(ASSISTANT_IDENTITY_MARKER_TEST_TAG),
        contentAlignment = Alignment.Center,
    ) {
        Text(
            text = stringResource(R.string.role_assistant_initial),
            color = MaterialTheme.colorScheme.onSecondaryContainer,
            style = MaterialTheme.typography.labelMedium,
            fontWeight = FontWeight.SemiBold,
            maxLines = 1,
            overflow = TextOverflow.Clip,
            textAlign = TextAlign.Center,
        )
    }
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
                    MessageText(
                        text = part.text,
                        textColor = textColor,
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

private fun shouldShowVisibleMessageCopyAction(content: String): Boolean {
    return content.isNotBlank() && parseMessageContent(content).none { it is MessageContentPart.Code }
}

@Composable
private fun MessageText(
    text: String,
    textColor: androidx.compose.ui.graphics.Color,
) {
    val blocks = remember(text) { parseMessageTextBlocks(text) }
    Column(
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        blocks.forEach { block ->
            when (block) {
                is MessageTextBlock.Heading -> {
                    Text(
                        text = markdownInlineText(block.text, textColor),
                        modifier = Modifier.semantics { heading() },
                        style = when (block.level) {
                            1 -> MaterialTheme.typography.titleMedium
                            2 -> MaterialTheme.typography.titleSmall
                            else -> MaterialTheme.typography.bodyLarge
                        },
                        fontWeight = FontWeight.SemiBold,
                        color = textColor,
                    )
                }
                is MessageTextBlock.Paragraph -> {
                    Text(
                        text = markdownInlineText(block.text, textColor),
                        style = MaterialTheme.typography.bodyLarge,
                        color = textColor,
                    )
                }
                is MessageTextBlock.ListItem -> {
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(8.dp),
                    ) {
                        Text(
                            text = block.marker,
                            style = MaterialTheme.typography.bodyLarge,
                            color = textColor.copy(alpha = 0.68f),
                            modifier = Modifier.widthIn(min = 20.dp),
                        )
                        Text(
                            text = markdownInlineText(block.text, textColor),
                            style = MaterialTheme.typography.bodyLarge,
                            color = textColor,
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
                is MessageTextBlock.Quote -> {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .height(IntrinsicSize.Min)
                            .semantics(mergeDescendants = true) {},
                        horizontalArrangement = Arrangement.spacedBy(10.dp),
                    ) {
                        Box(
                            modifier = Modifier
                                .width(3.dp)
                                .fillMaxHeight()
                                .heightIn(min = 24.dp)
                                .background(
                                    color = MaterialTheme.colorScheme.secondary.copy(alpha = 0.28f),
                                    shape = RoundedCornerShape(2.dp),
                                ),
                        )
                        Text(
                            text = markdownInlineText(block.text, textColor),
                            style = MaterialTheme.typography.bodyMedium,
                            color = textColor.copy(alpha = 0.78f),
                            modifier = Modifier.weight(1f),
                        )
                    }
                }
                is MessageTextBlock.Table -> {
                    MarkdownTable(
                        table = block,
                        textColor = textColor,
                    )
                }
                MessageTextBlock.Separator -> {
                    HorizontalDivider(
                        modifier = Modifier.padding(vertical = 2.dp),
                        color = textColor.copy(alpha = 0.16f),
                    )
                }
            }
        }
    }
}

@Composable
private fun MarkdownTable(
    table: MessageTextBlock.Table,
    textColor: androidx.compose.ui.graphics.Color,
) {
    val scrollState = rememberScrollState()
    val columnCount = table.headers.size.coerceAtLeast(0)
    val rowCount = table.rows.size.coerceAtLeast(0)
    val columnCountText = pluralStringResource(
        R.plurals.markdown_table_column_count,
        columnCount,
        columnCount,
    )
    val rowCountText = pluralStringResource(
        R.plurals.markdown_table_row_count,
        rowCount,
        rowCount,
    )
    val tableAccessibilitySummary = stringResource(
        R.string.markdown_table_accessibility_summary,
        columnCountText,
        rowCountText,
    )
    Box(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(CHAT_MARKDOWN_TABLE_TEST_TAG)
            .semantics {
                contentDescription = tableAccessibilitySummary
            }
            .horizontalScroll(scrollState),
    ) {
        Surface(
            modifier = Modifier.testTag(CHAT_MARKDOWN_TABLE_SURFACE_TEST_TAG),
            shape = RoundedCornerShape(10.dp),
            color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.36f),
            contentColor = textColor,
        ) {
            Column {
                MarkdownTableRow(
                    cells = table.headers,
                    textColor = textColor,
                    isHeader = true,
                )
                table.rows.forEachIndexed { index, row ->
                    HorizontalDivider(color = textColor.copy(alpha = 0.12f))
                    MarkdownTableRow(
                        cells = row,
                        textColor = textColor,
                        isHeader = false,
                        isAlternate = index % 2 == 1,
                    )
                }
            }
        }
    }
}

@Composable
private fun MarkdownTableRow(
    cells: List<String>,
    textColor: androidx.compose.ui.graphics.Color,
    isHeader: Boolean,
    isAlternate: Boolean = false,
) {
    Row(
        modifier = Modifier.background(
            color = when {
                isHeader -> MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.58f)
                isAlternate -> MaterialTheme.colorScheme.surface.copy(alpha = 0.30f)
                else -> androidx.compose.ui.graphics.Color.Transparent
            },
        ),
    ) {
        cells.forEachIndexed { index, cell ->
            MarkdownTableCell(
                text = cell,
                textColor = textColor,
                isHeader = isHeader,
            )
            if (index != cells.lastIndex) {
                Box(
                    modifier = Modifier
                        .width(1.dp)
                        .heightIn(min = 42.dp)
                        .background(textColor.copy(alpha = 0.10f)),
                )
            }
        }
    }
}

@Composable
private fun MarkdownTableCell(
    text: String,
    textColor: androidx.compose.ui.graphics.Color,
    isHeader: Boolean,
) {
    Text(
        text = markdownInlineText(text, textColor),
        style = if (isHeader) {
            MaterialTheme.typography.labelMedium
        } else {
            MaterialTheme.typography.bodySmall
        },
        fontWeight = if (isHeader) FontWeight.SemiBold else FontWeight.Normal,
        color = if (isHeader) textColor else textColor.copy(alpha = 0.88f),
        maxLines = 4,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier
            .width(MARKDOWN_TABLE_CELL_WIDTH_DP.dp)
            .padding(horizontal = 10.dp, vertical = 9.dp),
    )
}

@Composable
private fun markdownInlineText(
    text: String,
    textColor: androidx.compose.ui.graphics.Color,
): AnnotatedString {
    val codeBackground = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f)
    val linkColor = MaterialTheme.colorScheme.primary
    return remember(text, textColor, codeBackground, linkColor) {
        buildAnnotatedString {
            appendMarkdownInline(
                source = text,
                textColor = textColor,
                codeBackground = codeBackground,
                linkColor = linkColor,
            )
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
    val codeLineCount = if (code.isBlank()) {
        0
    } else {
        code.lines().size
    }
    val lineCountText = pluralStringResource(
        R.plurals.code_block_line_count,
        codeLineCount,
        codeLineCount,
    )
    val languageText = trimmedLanguage.ifBlank {
        stringResource(R.string.code_block_language_unspecified)
    }
    val codeBlockAccessibilitySummary = stringResource(
        R.string.code_block_accessibility_summary,
        languageText,
        lineCountText,
    )
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(CHAT_CODE_BLOCK_TEST_TAG)
            .semantics {
                contentDescription = codeBlockAccessibilitySummary
            },
        shape = RoundedCornerShape(10.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.72f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(CHAT_CODE_BLOCK_HEADER_TEST_TAG),
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
                        modifier = Modifier
                            .weight(1f)
                            .testTag(CHAT_CODE_BLOCK_LANGUAGE_TEST_TAG),
                    )
                } else {
                    Spacer(modifier = Modifier.weight(1f))
                }
                if (code.isNotBlank()) {
                    MessageCopyButton(
                        textToCopy = code,
                        copyActionLabel = copyCodeBlockLabel,
                        modifier = Modifier.testTag(CHAT_CODE_BLOCK_COPY_ACTION_TEST_TAG),
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
                    .testTag(CHAT_CODE_BLOCK_TEXT_TEST_TAG)
                    .horizontalScroll(rememberScrollState()),
            )
        }
    }
}

@Composable
private fun MessageCopyButton(
    textToCopy: String,
    copyActionLabel: String,
    modifier: Modifier = Modifier,
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
                clipboard.setClipEntry(ClipEntry(ClipData.newPlainText(copyActionLabel, textToCopy)))
                announceCopySuccess(copiedMessage)
                Toast.makeText(context, copiedMessage, Toast.LENGTH_SHORT).show()
            }
        },
        enabled = textToCopy.isNotBlank(),
        contentPadding = PaddingValues(horizontal = 8.dp, vertical = 2.dp),
        modifier = modifier.semantics {
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
            clipboard.setClipEntry(ClipEntry(ClipData.newPlainText(copyActionLabel, textToCopy)))
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

internal sealed interface MessageTextBlock {
    data class Heading(val level: Int, val text: String) : MessageTextBlock
    data class Paragraph(val text: String) : MessageTextBlock
    data class ListItem(val marker: String, val text: String) : MessageTextBlock
    data class Quote(val text: String) : MessageTextBlock
    data class Table(val headers: List<String>, val rows: List<List<String>>) : MessageTextBlock
    data object Separator : MessageTextBlock
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

internal fun parseMessageTextBlocks(text: String): List<MessageTextBlock> {
    val blocks = mutableListOf<MessageTextBlock>()
    val paragraphLines = mutableListOf<String>()
    val headingPattern = Regex("^\\s*(#{1,3})\\s+(.+)$")
    val listPattern = Regex("^\\s*(?:([-*])|(\\d{1,3})[.)])\\s+(.+)$")
    val quotePattern = Regex("^\\s*>\\s?(.+)$")
    val lines = text.lineSequence().toList()

    fun flushParagraph() {
        val paragraph = paragraphLines
            .joinToString(separator = "\n")
            .trim()
        if (paragraph.isNotBlank()) {
            blocks += MessageTextBlock.Paragraph(paragraph)
        }
        paragraphLines.clear()
    }

    var index = 0
    while (index < lines.size) {
        val table = parseMarkdownTableAt(lines, index)
        if (table != null) {
            flushParagraph()
            blocks += table.block
            index = table.nextIndex
            continue
        }

        val line = lines[index]
        val headingMatch = headingPattern.matchEntire(line)
        val match = listPattern.matchEntire(line)
        val quoteMatch = quotePattern.matchEntire(line)
        when {
            line.isMarkdownSeparator() -> {
                flushParagraph()
                blocks += MessageTextBlock.Separator
            }
            headingMatch != null -> {
                flushParagraph()
                blocks += MessageTextBlock.Heading(
                    level = headingMatch.groupValues[1].length,
                    text = headingMatch.groupValues[2].trim(),
                )
            }
            match != null -> {
                flushParagraph()
                val orderedNumber = match.groupValues[2]
                val marker = if (orderedNumber.isNotBlank()) "$orderedNumber." else "\u2022"
                blocks += MessageTextBlock.ListItem(
                    marker = marker,
                    text = match.groupValues[3].trim(),
                )
            }
            quoteMatch != null -> {
                flushParagraph()
                blocks += MessageTextBlock.Quote(quoteMatch.groupValues[1].trim())
            }
            line.isBlank() -> flushParagraph()
            else -> paragraphLines += line.trimEnd()
        }
        index += 1
    }
    flushParagraph()

    return blocks.ifEmpty { listOf(MessageTextBlock.Paragraph(text.trim())) }
}

private data class ParsedMarkdownTable(
    val block: MessageTextBlock.Table,
    val nextIndex: Int,
)

private fun parseMarkdownTableAt(
    lines: List<String>,
    startIndex: Int,
): ParsedMarkdownTable? {
    if (startIndex + 1 >= lines.size) return null

    val headerCells = parseMarkdownTableCells(lines[startIndex]) ?: return null
    val separatorCells = parseMarkdownTableCells(lines[startIndex + 1]) ?: return null
    if (!separatorCells.all { it.isMarkdownTableSeparatorCell() }) return null
    if (headerCells.size < 2 || headerCells.all { it.isBlank() }) return null

    val rows = mutableListOf<List<String>>()
    var cursor = startIndex + 2
    while (cursor < lines.size) {
        val rowCells = parseMarkdownTableCells(lines[cursor]) ?: break
        if (rowCells.all { it.isMarkdownTableSeparatorCell() }) break
        rows += rowCells
        cursor += 1
    }

    val columnCount = maxOf(
        headerCells.size,
        rows.maxOfOrNull { it.size } ?: 0,
    )
    if (columnCount < 2) return null

    return ParsedMarkdownTable(
        block = MessageTextBlock.Table(
            headers = headerCells.normalizedMarkdownTableRow(columnCount),
            rows = rows.map { it.normalizedMarkdownTableRow(columnCount) },
        ),
        nextIndex = cursor,
    )
}

private fun parseMarkdownTableCells(line: String): List<String>? {
    val trimmed = line.trim()
    if (!trimmed.contains("|")) return null
    val body = trimmed
        .removePrefix("|")
        .removeSuffix("|")
    val cells = body.split("|").map { it.trim() }
    return cells.takeIf { it.size >= 2 }
}

private fun String.isMarkdownTableSeparatorCell(): Boolean {
    return matches(Regex(":?-{3,}:?"))
}

private fun List<String>.normalizedMarkdownTableRow(columnCount: Int): List<String> {
    return take(columnCount) + List((columnCount - size).coerceAtLeast(0)) { "" }
}

private fun String.isMarkdownSeparator(): Boolean {
    val compact = trim().filterNot { it.isWhitespace() }
    return compact.length >= 3 && compact.all { it == compact.first() } && compact.first() in "-*_"
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

private fun AnnotatedString.Builder.appendMarkdownInline(
    source: String,
    textColor: androidx.compose.ui.graphics.Color,
    codeBackground: androidx.compose.ui.graphics.Color,
    linkColor: androidx.compose.ui.graphics.Color,
) {
    var index = 0
    while (index < source.length) {
        when {
            source[index] == '`' -> {
                val end = source.indexOf('`', startIndex = index + 1)
                if (end > index + 1) {
                    withStyle(
                        SpanStyle(
                            color = textColor,
                            background = codeBackground,
                            fontFamily = FontFamily.Monospace,
                        ),
                    ) {
                        append(source.substring(index + 1, end))
                    }
                    index = end + 1
                } else {
                    append(source[index])
                    index += 1
                }
            }
            source.startsWith("**", startIndex = index) -> {
                val end = source.indexOf("**", startIndex = index + 2)
                if (end > index + 2) {
                    withStyle(SpanStyle(fontWeight = FontWeight.SemiBold)) {
                        append(source.substring(index + 2, end))
                    }
                    index = end + 2
                } else {
                    append(source[index])
                    index += 1
                }
            }
            source[index] == '[' -> {
                val labelEnd = source.indexOf("](", startIndex = index + 1)
                val urlEnd = if (labelEnd > index + 1) {
                    source.indexOf(')', startIndex = labelEnd + 2)
                } else {
                    -1
                }
                if (labelEnd > index + 1 && urlEnd > labelEnd + 2) {
                    withStyle(
                        SpanStyle(
                            color = linkColor,
                            textDecoration = TextDecoration.Underline,
                        ),
                    ) {
                        append(source.substring(index + 1, labelEnd))
                    }
                    index = urlEnd + 1
                } else {
                    append(source[index])
                    index += 1
                }
            }
            else -> {
                append(source[index])
                index += 1
            }
        }
    }
}

private fun List<RuntimeChatMessage>.lastAssistantMessageId(): String? {
    return lastOrNull { it.role == "assistant" }?.id
}

private fun List<RuntimeChatMessage>.lastUserMessageId(): String? {
    return lastOrNull { it.role == "user" }?.id
}

@Composable
private fun AssistantReasoning(
    reasoning: String,
    expanded: Boolean,
    announceUpdates: Boolean,
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
        when {
            !isExpandable -> R.string.assistant_reasoning_state_shown
            expanded -> R.string.section_state_expanded
            else -> R.string.section_state_collapsed
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
                if (announceUpdates) {
                    liveRegion = LiveRegionMode.Polite
                }
            }
            .clickable(
                role = Role.Button,
                onClickLabel = toggleLabel,
                onClick = toggleExpanded,
            )
    } else {
        Modifier.semantics(mergeDescendants = true) {
            contentDescription = accessibilitySummary
            if (announceUpdates) {
                liveRegion = LiveRegionMode.Polite
            }
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
internal const val CHAT_COMPOSER_CONTAINER_CORNER_RADIUS_DP = 28
internal const val CHAT_COMPOSER_CONTAINER_ALPHA = 0.98f
internal const val MARKDOWN_TABLE_CELL_WIDTH_DP = 152
internal const val DEVELOPER_DIAGNOSTICS_TOGGLE_ROW_TAG = "developer-diagnostics-toggle-row"
internal const val DEVELOPER_DIAGNOSTICS_SWITCH_DISABLED_TAG = "developer-diagnostics-switch-disabled"
internal const val DEVELOPER_DIAGNOSTICS_SWITCH_ENABLED_TAG = "developer-diagnostics-switch-enabled"
internal const val SETTINGS_CHAT_HISTORY_SEARCH_TEST_TAG = "aetherlink_settings_chat_history_search"
internal const val SETTINGS_CHAT_HISTORY_BULK_EXPANDER_TEST_TAG = "settings_chat_history_bulk_expander"
internal const val SETTINGS_CHAT_HISTORY_BULK_EXPANDER_LABEL_TEST_TAG =
    "settings_chat_history_bulk_expander_label"
internal const val SETTINGS_CHAT_HISTORY_BULK_DETAIL_TEST_TAG = "settings_chat_history_bulk_detail"
internal const val SETTINGS_CHAT_HISTORY_BULK_ARCHIVE_ACTION_TEST_TAG =
    "settings_chat_history_bulk_archive_action"
internal const val SETTINGS_CHAT_HISTORY_BULK_ARCHIVE_LABEL_TEST_TAG =
    "settings_chat_history_bulk_archive_label"
internal const val SETTINGS_CHAT_HISTORY_BULK_DELETE_ACTION_TEST_TAG =
    "settings_chat_history_bulk_delete_action"
internal const val SETTINGS_CHAT_HISTORY_BULK_DELETE_LABEL_TEST_TAG =
    "settings_chat_history_bulk_delete_label"

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
    onClearDraft: () -> Unit,
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
    val attachmentLimitReached = attachments.size >= MAX_PENDING_ATTACHMENTS
    val attachedFilesStateDescription = if (attachments.isNotEmpty()) {
        pluralStringResource(
            R.plurals.attach_files_state_count,
            attachments.size,
            attachments.size,
            MAX_PENDING_ATTACHMENTS,
        )
    } else {
        null
    }
    val readyStateDescription = attachedFilesStateDescription?.let { attachmentState ->
        stringResource(R.string.chat_hint_ready_with_attachments, attachmentState)
    } ?: stringResource(R.string.chat_hint_ready)
    val composerStateDescription = when {
        hint.isNotBlank() -> hint
        hasSendableContent -> readyStateDescription
        else -> stringResource(R.string.chat_hint_enter_message)
    }
    val sendStateDescription = composerStateDescription
    val sendActionLabel = stringResource(R.string.content_desc_send)
    val cancelGenerationStateDescription = stringResource(R.string.cancel_generation_state_ready)
    val cancelGenerationActionLabel = stringResource(R.string.content_desc_cancel_generation)
    val attachFilesActionLabel = stringResource(R.string.content_desc_attach_files)
    val clearDraftActionLabel = stringResource(R.string.clear_draft)
    val clearDraftStateDescription = stringResource(R.string.clear_draft_state_ready)
    val canAttachFiles = enabled && !attachmentLimitReached
    val canClearDraft = enabled && (value.isNotBlank() || attachments.isNotEmpty()) && !isStreaming
    val attachFilesStateDescription = when {
        !enabled && hint.isNotBlank() -> hint
        !enabled -> stringResource(R.string.attach_files_state_unavailable)
        attachmentLimitReached -> stringResource(
            R.string.attach_files_state_limit_reached,
            attachments.size,
            MAX_PENDING_ATTACHMENTS,
        )
        attachments.isNotEmpty() -> attachedFilesStateDescription.orEmpty()
        enabled -> stringResource(R.string.attach_files_state_ready)
        else -> stringResource(R.string.attach_files_state_unavailable)
    }
    Surface(
        modifier = modifier
            .fillMaxWidth()
            .testTag(CHAT_COMPOSER_CONTAINER_TEST_TAG),
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
                    .heightIn(min = 42.dp)
                    .testTag(CHAT_COMPOSER_CONTROLS_ROW_TEST_TAG),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.Bottom,
            ) {
                FilledTonalIconButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        onAttachFiles()
                    },
                    enabled = canAttachFiles,
                    modifier = Modifier
                        .size(40.dp)
                        .testTag(CHAT_COMPOSER_ATTACH_ACTION_TEST_TAG)
                        .semantics {
                            stateDescription = attachFilesStateDescription
                            onClick(label = attachFilesActionLabel) {
                                if (canAttachFiles) {
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
                        .testTag(CHAT_COMPOSER_INPUT_TEST_TAG)
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
                if (canClearDraft) {
                    IconButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onClearDraft()
                        },
                        modifier = Modifier
                            .size(40.dp)
                            .testTag(CHAT_COMPOSER_CLEAR_DRAFT_ACTION_TEST_TAG)
                            .semantics {
                                contentDescription = clearDraftActionLabel
                                stateDescription = clearDraftStateDescription
                                onClick(label = clearDraftActionLabel) {
                                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                    onClearDraft()
                                    true
                                }
                            },
                    ) {
                        Icon(
                            Icons.Filled.Close,
                            contentDescription = null,
                        )
                    }
                }
                if (isStreaming) {
                    FilledIconButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Destructive)
                            onCancel()
                        },
                        enabled = true,
                        modifier = Modifier
                            .size(40.dp)
                            .testTag(CHAT_COMPOSER_CANCEL_ACTION_TEST_TAG)
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
                            .testTag(CHAT_COMPOSER_SEND_ACTION_TEST_TAG)
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
            .testTag(CHAT_COMPOSER_STATUS_TEST_TAG)
            .semantics(mergeDescendants = true) {
                liveRegion = LiveRegionMode.Polite
                contentDescription = text
            }
            .padding(horizontal = 2.dp),
        horizontalArrangement = Arrangement.spacedBy(7.dp),
        verticalAlignment = Alignment.CenterVertically,
    ) {
        Surface(
            modifier = Modifier
                .size(6.dp)
                .testTag(CHAT_COMPOSER_STATUS_DOT_TEST_TAG),
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
            modifier = Modifier
                .weight(1f)
                .testTag(CHAT_COMPOSER_STATUS_TEXT_TEST_TAG),
        )
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ReadOnlyAttachmentChips(
    messageId: String,
    attachments: List<RuntimeMessageAttachment>,
    horizontalAlignment: Alignment.Horizontal,
) {
    if (attachments.isEmpty()) return

    FlowRow(
        modifier = Modifier
            .widthIn(max = 548.dp)
            .fillMaxWidth()
            .testTag(readOnlyAttachmentChipsTestTag(messageId)),
        horizontalArrangement = Arrangement.spacedBy(8.dp, horizontalAlignment),
        verticalArrangement = Arrangement.spacedBy(6.dp),
        itemVerticalAlignment = Alignment.CenterVertically,
    ) {
        attachments.forEach { attachment ->
            ReadOnlyAttachmentChip(attachment = attachment)
        }
    }
}

@Composable
private fun ReadOnlyAttachmentChip(attachment: RuntimeMessageAttachment) {
    val attachmentTypeDescription = attachmentTypeLabel(attachment.type)
    val attachmentContentDescription = attachmentAccessibilityDescription(attachment)
    Surface(
        modifier = Modifier.widthIn(max = READ_ONLY_ATTACHMENT_CHIP_MAX_WIDTH_DP.dp),
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
private fun attachmentAccessibilityDescription(attachment: RuntimeMessageAttachment): String {
    val attachmentTypeDescription = attachmentTypeLabel(attachment.type)
    return stringResource(
        R.string.content_desc_attachment_chip,
        attachment.name,
        attachmentTypeDescription,
    )
}

@Composable
private fun attachmentTypeLabel(type: String): String {
    return if (type == "image") {
        stringResource(R.string.attachment_type_image)
    } else {
        stringResource(R.string.attachment_type_document)
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun AttachmentChips(
    attachments: List<RuntimePendingAttachment>,
    enabled: Boolean,
    disabledActionStateDescription: String?,
    imageAttachmentsSupported: Boolean,
    onRemoveAttachment: (String) -> Unit,
) {
    if (attachments.isEmpty()) return

    FlowRow(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(PENDING_ATTACHMENT_CHIPS_TEST_TAG),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
        itemVerticalAlignment = Alignment.CenterVertically,
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
        modifier = Modifier
            .widthIn(max = PENDING_ATTACHMENT_CHIP_MAX_WIDTH_DP.dp)
            .testTag(pendingAttachmentChipTestTag(attachment.id)),
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
    val title = stringResource(R.string.companion_only_title)
    val detail = stringResource(R.string.companion_only_detail)
    val summary = "$title. $detail"
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = summary
                liveRegion = LiveRegionMode.Polite
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.primaryContainer,
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
            Text(
                text = detail,
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onPrimaryContainer,
            )
        }
    }
}

@Composable
private fun AppPreferencesPanel(
    selectedLanguageTag: String,
    selectedLanguageSource: String,
    onSetLanguageTag: (String) -> Unit,
    onFollowSystemLanguage: () -> Unit,
    selectedTheme: RuntimeAppTheme,
    onSetTheme: (RuntimeAppTheme) -> Unit,
) {
    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(SETTINGS_PREFERENCES_PANEL_TEST_TAG),
    ) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                text = stringResource(R.string.preferences_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.semantics {
                    heading()
                },
            )
            AppearancePreferenceSelector(
                selectedTheme = selectedTheme,
                onSetTheme = onSetTheme,
            )
            LanguagePreferenceSelector(
                selectedLanguageTag = selectedLanguageTag,
                selectedLanguageSource = selectedLanguageSource,
                onSetLanguageTag = onSetLanguageTag,
                onFollowSystemLanguage = onFollowSystemLanguage,
            )
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
        modifier = Modifier
            .testTag(SETTINGS_APPEARANCE_GROUP_TEST_TAG)
            .selectableGroup(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text = groupLabel,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
            modifier = Modifier
                .semantics {
                    heading()
                }
                .testTag(SETTINGS_APPEARANCE_GROUP_LABEL_TEST_TAG),
        )
        options.forEach { (theme, labelRes) ->
            val selected = theme == selectedTheme
            val optionLabel = stringResource(labelRes)
            val optionDetail = if (theme == RuntimeAppTheme.System) {
                stringResource(R.string.appearance_system_detail)
            } else {
                null
            }
            val optionAccessibilitySummary = if (optionDetail == null) {
                stringResource(
                    R.string.preference_option_accessibility_summary,
                    groupLabel,
                    optionLabel,
                )
            } else {
                stringResource(
                    R.string.preference_option_accessibility_summary_with_detail,
                    groupLabel,
                    optionLabel,
                    optionDetail,
                )
            }
            val optionSelectActionLabel = stringResource(
                R.string.preference_option_action_select,
                optionAccessibilitySummary,
            )
            val selectTheme = {
                if (shouldPerformSelectionChangeHaptic(selected)) {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                }
                onSetTheme(theme)
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(appearancePreferenceOptionRowTestTag(theme))
                    .selectable(
                        selected = selected,
                        role = Role.RadioButton,
                        onClick = selectTheme,
                    )
                    .selectedPreferenceOptionState(
                        selected = selected,
                        selectedStateDescription = selectedStateDescription,
                        contentDescription = optionAccessibilitySummary,
                    )
                    .semantics {
                        onClick(label = optionSelectActionLabel) {
                            selectTheme()
                            true
                        }
                    }
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                RadioButton(
                    selected = selected,
                    onClick = null,
                    modifier = Modifier.testTag(appearancePreferenceOptionRadioTestTag(theme)),
                )
                Column(
                    modifier = Modifier.weight(1f),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text(
                        text = optionLabel,
                        style = MaterialTheme.typography.bodyMedium,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.testTag(appearancePreferenceOptionLabelTestTag(theme)),
                    )
                    if (optionDetail != null) {
                        Text(
                            text = optionDetail,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.secondary,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.testTag(appearancePreferenceOptionDetailTestTag(theme)),
                        )
                    }
                }
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
internal fun EmbeddingModelPanel(
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
    val modelRefreshActionLabel = if (state.isLoadingModels) {
        stringResource(R.string.loading_models)
    } else {
        stringResource(R.string.load_models)
    }
    val canChangeEmbeddingModel = !state.isStreaming

    OutlinedCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(EMBEDDING_MODEL_PANEL_TEST_TAG),
    ) {
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
                        modifier = Modifier.semantics {
                            heading()
                        },
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
                enabled = canChangeEmbeddingModel,
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
                enabled = state.isConnected && !state.isLoadingModels && canChangeEmbeddingModel,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        stateDescription = modelRefreshStateDescription
                        onClick(label = modelRefreshActionLabel, action = null)
                    },
            ) {
                Icon(Icons.Filled.Refresh, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(
                    text = modelRefreshActionLabel,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            when {
                !state.isConnected -> EmptyState(
                    text = stringResource(R.string.embedding_model_connect_first),
                    announceChanges = true,
                )
                embeddingModels.isEmpty() -> EmptyState(
                    text = stringResource(R.string.embedding_model_empty),
                    announceChanges = true,
                )
                else -> Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    embeddingModels.forEach { model ->
                        EmbeddingModelRow(
                            model = model,
                            selected = model.id == state.selectedEmbeddingModelId,
                            enabled = canChangeEmbeddingModel,
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
        state.isStreaming -> stringResource(R.string.model_picker_state_wait_for_stream)
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
            .testTag(SAVED_EMBEDDING_MODEL_ROW_TEST_TAG)
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
                    modifier = Modifier.testTag(SAVED_EMBEDDING_MODEL_LABEL_TEST_TAG),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                if (detail != null) {
                    Text(
                        text = detail,
                        modifier = Modifier.testTag(SAVED_EMBEDDING_MODEL_DETAIL_TEST_TAG),
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
    enabled: Boolean,
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
        enabled = enabled,
        modifier = selectedEmbeddingModelRowModifier(
            selected = selected,
            enabled = enabled,
            contentDescription = accessibilitySummary,
        ).testTag(EMBEDDING_MODEL_NONE_ROW_TEST_TAG),
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
                    modifier = Modifier.testTag(EMBEDDING_MODEL_NONE_LABEL_TEST_TAG),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = detail,
                    modifier = Modifier.testTag(EMBEDDING_MODEL_NONE_DETAIL_TEST_TAG),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
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
    enabled: Boolean,
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
    val rowEnabled = enabled && model.installed
    val rowDisabledStateDescription = when {
        !enabled -> stringResource(R.string.model_picker_state_wait_for_stream)
        !model.installed -> stringResource(R.string.embedding_model_state_install_before_selecting)
        else -> null
    }
    OutlinedButton(
        onClick = {
            if (shouldPerformSelectionChangeHaptic(selected)) {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
            }
            onSelectEmbeddingModel(model.id)
        },
        enabled = rowEnabled,
        modifier = selectedEmbeddingModelRowModifier(
            selected = selected,
            enabled = rowEnabled,
            contentDescription = accessibilitySummary,
            disabledStateDescription = rowDisabledStateDescription,
        ).testTag(embeddingModelRowTestTag(model.id)),
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
                    modifier = Modifier.testTag(embeddingModelRowNameTestTag(model.id)),
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = modelStatusText,
                    modifier = Modifier.testTag(embeddingModelRowStatusTestTag(model.id)),
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
        }
    }
}

@Composable
private fun selectedEmbeddingModelRowModifier(
    selected: Boolean,
    enabled: Boolean,
    contentDescription: String,
    disabledStateDescription: String? = null,
): Modifier {
    val selectedStateDescription = stringResource(R.string.selection_state_selected)
    val resolvedDisabledStateDescription = disabledStateDescription
        ?: stringResource(R.string.model_picker_state_wait_for_stream)
    return Modifier
        .fillMaxWidth()
        .semantics {
            this.contentDescription = contentDescription
            if (!enabled) {
                stateDescription = resolvedDisabledStateDescription
            } else if (selected) {
                stateDescription = selectedStateDescription
            }
        }
}

@Composable
private fun LanguagePreferenceSelector(
    selectedLanguageTag: String,
    selectedLanguageSource: String,
    onSetLanguageTag: (String) -> Unit,
    onFollowSystemLanguage: () -> Unit,
) {
    val hapticFeedback = LocalHapticFeedback.current
    val options = appLanguagePreferenceOptions()
    val selectedStateDescription = stringResource(R.string.selection_state_selected)
    val groupLabel = stringResource(R.string.language_title)
    val systemSelected = appLanguagePreferenceSystemOptionSelected(selectedLanguageSource)
    val systemOptionLabel = stringResource(R.string.language_follow_system)
    val systemOptionDetail = stringResource(R.string.language_follow_system_detail)
    val systemOptionAccessibilitySummary = stringResource(
        R.string.preference_option_accessibility_summary_with_detail,
        groupLabel,
        systemOptionLabel,
        systemOptionDetail,
    )
    val systemOptionSelectActionLabel = stringResource(
        R.string.preference_option_action_select,
        systemOptionAccessibilitySummary,
    )
    val selectSystemLanguage = {
        if (shouldPerformSelectionChangeHaptic(systemSelected)) {
            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
        }
        onFollowSystemLanguage()
    }

    Column(
        modifier = Modifier
            .testTag(SETTINGS_LANGUAGE_GROUP_TEST_TAG)
            .selectableGroup(),
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        Text(
            text = groupLabel,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
            modifier = Modifier
                .semantics {
                    heading()
                }
                .testTag(SETTINGS_LANGUAGE_GROUP_LABEL_TEST_TAG),
        )
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .testTag(languagePreferenceOptionRowTestTag(APP_LANGUAGE_SOURCE_SYSTEM))
                .selectable(
                    selected = systemSelected,
                    role = Role.RadioButton,
                    onClick = selectSystemLanguage,
                )
                .selectedPreferenceOptionState(
                    selected = systemSelected,
                    selectedStateDescription = selectedStateDescription,
                    contentDescription = systemOptionAccessibilitySummary,
                )
                .semantics {
                    onClick(label = systemOptionSelectActionLabel) {
                        selectSystemLanguage()
                        true
                    }
                }
                .padding(vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            RadioButton(
                selected = systemSelected,
                onClick = null,
                modifier = Modifier.testTag(languagePreferenceOptionRadioTestTag(APP_LANGUAGE_SOURCE_SYSTEM)),
            )
            Column(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(2.dp),
            ) {
                Text(
                    text = systemOptionLabel,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.testTag(languagePreferenceOptionLabelTestTag(APP_LANGUAGE_SOURCE_SYSTEM)),
                )
                Text(
                    text = systemOptionDetail,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier.testTag(languagePreferenceOptionDetailTestTag(APP_LANGUAGE_SOURCE_SYSTEM)),
                )
            }
        }
        options.forEach { (language, labelRes) ->
            val selected = appLanguagePreferenceFixedOptionSelected(
                selectedLanguageTag = selectedLanguageTag,
                selectedLanguageSource = selectedLanguageSource,
                language = language,
            )
            val optionLabel = stringResource(labelRes)
            val optionAccessibilitySummary = stringResource(
                R.string.preference_option_accessibility_summary,
                groupLabel,
                optionLabel,
            )
            val optionSelectActionLabel = stringResource(
                R.string.preference_option_action_select,
                optionAccessibilitySummary,
            )
            val selectLanguage = {
                if (shouldPerformSelectionChangeHaptic(selected)) {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.SelectionChange)
                }
                onSetLanguageTag(language.languageTag)
            }
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(languagePreferenceOptionRowTestTag(language.languageTag))
                    .selectable(
                        selected = selected,
                        role = Role.RadioButton,
                        onClick = selectLanguage,
                    )
                    .selectedPreferenceOptionState(
                        selected = selected,
                        selectedStateDescription = selectedStateDescription,
                        contentDescription = optionAccessibilitySummary,
                    )
                    .semantics {
                        onClick(label = optionSelectActionLabel) {
                            selectLanguage()
                            true
                        }
                    }
                    .padding(vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp),
            ) {
                RadioButton(
                    selected = selected,
                    onClick = null,
                    modifier = Modifier.testTag(languagePreferenceOptionRadioTestTag(language.languageTag)),
                )
                Text(
                    text = optionLabel,
                    style = MaterialTheme.typography.bodyMedium,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    modifier = Modifier
                        .weight(1f)
                        .testTag(languagePreferenceOptionLabelTestTag(language.languageTag)),
                )
            }
        }
    }
}

internal fun appLanguagePreferenceSystemOptionSelected(selectedLanguageSource: String?): Boolean {
    return when (selectedLanguageSource?.trim()) {
        APP_LANGUAGE_SOURCE_IN_APP -> false
        APP_LANGUAGE_SOURCE_DEFAULT,
        APP_LANGUAGE_SOURCE_SYSTEM,
        null,
        "" -> true
        else -> true
    }
}

internal fun appLanguagePreferenceFixedOptionSelected(
    selectedLanguageTag: String,
    selectedLanguageSource: String?,
    language: RuntimeAppLanguage,
): Boolean {
    return !appLanguagePreferenceSystemOptionSelected(selectedLanguageSource) &&
        appLanguagePreferenceOptionSelected(selectedLanguageTag, language)
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
internal fun ChatHistorySettingsPanel(
    activeSessions: List<RuntimeChatSession>,
    archivedSessions: List<RuntimeChatSession>,
    activeChatSessionId: String?,
    models: List<RuntimeModel>,
    isActionEnabled: Boolean,
    canRefreshChatHistory: Boolean,
    @StringRes refreshStateDescriptionRes: Int,
    onRefreshChatHistory: (String?) -> Unit,
    onOpenChatSession: (String) -> Unit,
    onRenameChatSession: (String) -> Unit,
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
        models = models,
    )
    val filteredArchivedSessions = filterChatHistorySessions(
        sessions = archivedSessions,
        query = chatSearchQuery,
        untitledTitle = untitledTitle,
        models = models,
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
    val archiveAllActionLabel = stringResource(R.string.archive_all_chats)
    val canPermanentlyDeleteArchived = chatHistoryPermanentDeleteArchivedEnabled(
        isActionEnabled = isActionEnabled,
        archivedSessionCount = archivedSessions.size,
    )
    val deleteArchivedStateDescription = chatHistoryDeleteArchivedStateDescription(
        isActionEnabled = isActionEnabled,
        archivedSessionCount = archivedSessions.size,
    )
    val deleteArchivedActionLabel = stringResource(R.string.permanently_delete_archived_chats)
    val refreshChatHistoryContentDescription = stringResource(R.string.chat_history_refresh)
    val refreshChatHistoryStateDescription = stringResource(refreshStateDescriptionRes)
    val normalizedChatSearchQuery = chatSearchQuery.trim().ifBlank { null }
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
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End,
            ) {
                ChatHistoryRefreshButton(
                    canRefreshChatHistory = canRefreshChatHistory,
                    refreshContentDescription = refreshChatHistoryContentDescription,
                    refreshStateDescription = refreshChatHistoryStateDescription,
                    onRefreshChatHistory = { onRefreshChatHistory(normalizedChatSearchQuery) },
                    hapticFeedback = hapticFeedback,
                )
            }
            ChatHistorySummary(
                activeCount = activeSessions.size,
                archivedCount = archivedSessions.size,
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
            if (hasSearchQuery) {
                ChatHistorySearchResultSummary(
                    query = chatSearchQuery.trim(),
                    activeCount = filteredActiveSessions.size,
                    archivedCount = filteredArchivedSessions.size,
                )
            }
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
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .heightIn(min = 48.dp)
                        .testTag(SETTINGS_CHAT_HISTORY_BULK_EXPANDER_TEST_TAG),
                ) {
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
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier
                                .weight(1f)
                                .testTag(SETTINGS_CHAT_HISTORY_BULK_EXPANDER_LABEL_TEST_TAG),
                        )
                    }
                }
                if (showBulkActions) {
                    Text(
                        text = stringResource(R.string.chat_history_bulk_actions_detail),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.secondary,
                        modifier = Modifier.testTag(SETTINGS_CHAT_HISTORY_BULK_DETAIL_TEST_TAG),
                    )
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 88.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                bulkArchiveConfirmStep.value = 1
                            },
                            enabled = canArchiveAll,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 88.dp)
                                .semantics {
                                    stateDescription = archiveAllStateDescription
                                    onClick(label = archiveAllActionLabel, action = null)
                                },
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(SETTINGS_CHAT_HISTORY_BULK_ARCHIVE_ACTION_TEST_TAG),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(Icons.Filled.Archive, contentDescription = null)
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    text = archiveAllActionLabel,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier
                                        .weight(1f)
                                        .testTag(SETTINGS_CHAT_HISTORY_BULK_ARCHIVE_LABEL_TEST_TAG),
                                )
                            }
                        }
                    }
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .heightIn(min = 88.dp)
                    ) {
                        OutlinedButton(
                            onClick = {
                                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                                bulkDeleteConfirmStep.value = 1
                            },
                            enabled = canPermanentlyDeleteArchived,
                            modifier = Modifier
                                .fillMaxWidth()
                                .heightIn(min = 88.dp)
                                .semantics {
                                    stateDescription = deleteArchivedStateDescription
                                    onClick(label = deleteArchivedActionLabel, action = null)
                                },
                        ) {
                            Row(
                                modifier = Modifier
                                    .fillMaxWidth()
                                    .testTag(SETTINGS_CHAT_HISTORY_BULK_DELETE_ACTION_TEST_TAG),
                                verticalAlignment = Alignment.CenterVertically,
                            ) {
                                Icon(Icons.Filled.DeleteSweep, contentDescription = null)
                                Spacer(Modifier.width(8.dp))
                                Text(
                                    text = deleteArchivedActionLabel,
                                    maxLines = 2,
                                    overflow = TextOverflow.Ellipsis,
                                    modifier = Modifier
                                        .weight(1f)
                                        .testTag(SETTINGS_CHAT_HISTORY_BULK_DELETE_LABEL_TEST_TAG),
                                )
                            }
                        }
                    }
                }
            }
            if (hasSearchQuery && !hasFilteredResults) {
                val noSearchResultsText = stringResource(R.string.no_chat_search_results)
                Text(
                    text = noSearchResultsText,
                    style = MaterialTheme.typography.bodyMedium,
                    color = MaterialTheme.colorScheme.secondary,
                    modifier = Modifier.semantics {
                        liveRegion = LiveRegionMode.Polite
                    },
                )
            }
            if (filteredActiveSessions.isNotEmpty()) {
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    filteredActiveSessions.forEach { session ->
                        ChatHistorySettingsRow(
                            session = session,
                            models = models,
                            selected = session.id == activeChatSessionId,
                            isActionEnabled = isActionEnabled,
                            showSearchMetadata = hasSearchQuery,
                            onOpenChatSession = onOpenChatSession,
                            onRenameChatSession = onRenameChatSession,
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
                            models = models,
                            selected = false,
                            isActionEnabled = isActionEnabled,
                            showSearchMetadata = hasSearchQuery,
                            onOpenChatSession = onOpenChatSession,
                            onRenameChatSession = onRenameChatSession,
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
    models: List<RuntimeModel> = emptyList(),
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
            chatHistorySessionModelDisplayName(session = session, models = models),
            session.modelId,
            session.lastEvent,
            session.lastFinishReason,
            session.lastErrorCode,
            session.searchSnippet,
            session.searchMatchedFields.joinToString(" "),
        ).joinToString(separator = " ").lowercase(Locale.ROOT)
        terms.all(searchableText::contains)
    }
}

internal fun chatHistorySessionModelDisplayName(
    session: RuntimeChatSession,
    models: List<RuntimeModel>,
): String? {
    val modelId = session.modelId
        ?.trim()
        ?.takeIf(String::isNotBlank)
        ?: return null
    return models
        .firstOrNull { it.id == modelId }
        ?.name
        ?.trim()
        ?.takeIf(String::isNotBlank)
        ?: savedRuntimeModelDisplayName(modelId).takeIf(String::isNotBlank)
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

internal fun chatHistoryRefreshEnabled(state: RuntimeUiState): Boolean {
    return state.isConnected && !state.isStreaming
}

@StringRes
internal fun chatHistoryRefreshStateDescriptionRes(state: RuntimeUiState): Int {
    return when {
        state.isStreaming -> R.string.chat_history_action_state_wait_for_stream
        state.isConnected -> R.string.chat_history_refresh_state_ready
        else -> R.string.chat_history_refresh_state_connect_first
    }
}

@Composable
private fun ChatHistoryRefreshButton(
    canRefreshChatHistory: Boolean,
    refreshContentDescription: String,
    refreshStateDescription: String,
    onRefreshChatHistory: () -> Unit,
    hapticFeedback: HapticFeedback,
) {
    IconButton(
        onClick = {
            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
            onRefreshChatHistory()
        },
        enabled = canRefreshChatHistory,
        modifier = Modifier.semantics {
            contentDescription = refreshContentDescription
            stateDescription = refreshStateDescription
            onClick(label = refreshContentDescription, action = null)
        },
    ) {
        Icon(Icons.Filled.Refresh, contentDescription = null)
    }
}

@Composable
private fun ChatHistorySettingsRow(
    session: RuntimeChatSession,
    models: List<RuntimeModel>,
    selected: Boolean,
    isActionEnabled: Boolean,
    showSearchMetadata: Boolean,
    onOpenChatSession: (String) -> Unit,
    onRenameChatSession: (String) -> Unit,
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
    val modelName = chatHistorySessionModelDisplayName(session = session, models = models)
    val modelText = modelName?.let { name ->
        stringResource(R.string.chat_session_model_value, name)
    }
    val searchSnippet = if (showSearchMetadata) {
        session.searchSnippet?.trim()?.takeIf(String::isNotBlank)
    } else {
        null
    }
    val searchMetadata = runtimeSearchMetadataText(
        session = session,
        showSearchMetadata = showSearchMetadata,
    )
    val baseRowAccessibilitySummary = when {
        selected && modelText != null -> stringResource(
            R.string.chat_session_row_summary_selected_with_model,
            title,
            statusText,
            modelText,
        )
        selected -> stringResource(R.string.chat_session_row_summary_selected, title, statusText)
        modelText != null -> stringResource(R.string.chat_session_row_summary_with_model, title, statusText, modelText)
        else -> stringResource(R.string.chat_session_row_summary, title, statusText)
    }
    val searchAccessibilitySummary = listOfNotNull(searchMetadata, searchSnippet)
        .joinToString(separator = " ")
        .takeIf(String::isNotBlank)
    val rowAccessibilitySummary = searchAccessibilitySummary
        ?.let { "$baseRowAccessibilitySummary $it" }
        ?: baseRowAccessibilitySummary
    val renameActionContentDescription = stringResource(R.string.rename_chat_named, title)
    val archiveActionContentDescription = stringResource(R.string.archive_chat_named, title)
    val openActionContentDescription = stringResource(R.string.open_chat_named, title)
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
                        .testTag(settingsChatHistoryRowContentTestTag(session.id))
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
                    if (selected) {
                        Surface(
                            shape = RoundedCornerShape(6.dp),
                            color = MaterialTheme.colorScheme.primaryContainer,
                            contentColor = MaterialTheme.colorScheme.onPrimaryContainer,
                        ) {
                            Text(
                                text = stringResource(R.string.selection_state_selected),
                                modifier = Modifier.padding(horizontal = 8.dp, vertical = 2.dp),
                                style = MaterialTheme.typography.labelSmall,
                                maxLines = 1,
                                overflow = TextOverflow.Ellipsis,
                            )
                        }
                    }
                    Text(
                        text = statusText,
                        style = MaterialTheme.typography.labelSmall,
                        color = statusColor,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                    )
                    if (modelText != null) {
                        Text(
                            text = modelText,
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    if (searchMetadata != null) {
                        Text(
                            text = searchMetadata,
                            modifier = Modifier.testTag(settingsChatHistorySearchMetadataTestTag(session.id)),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.primary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    if (searchSnippet != null) {
                        Text(
                            text = searchSnippet,
                            modifier = Modifier.testTag(settingsChatHistorySearchSnippetTestTag(session.id)),
                            style = MaterialTheme.typography.labelSmall,
                            color = MaterialTheme.colorScheme.onSurfaceVariant,
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
            }
            ChatHistorySettingsActionRow(sessionId = session.id) {
                if (isArchived) {
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onRestoreChatSession(session.id)
                        },
                        enabled = isActionEnabled,
                        modifier = Modifier
                            .widthIn(min = 124.dp)
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
                            maxLines = 2,
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
                            .widthIn(min = 124.dp)
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
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                } else {
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onOpenChatSession(session.id)
                        },
                        enabled = isActionEnabled,
                        modifier = Modifier
                            .widthIn(min = 124.dp)
                            .semantics {
                                contentDescription = openActionContentDescription
                                onClick(label = openActionContentDescription, action = null)
                                chatHistoryActionStateDescription?.let { stateDescription = it }
                            },
                    ) {
                        Icon(Icons.Filled.Link, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = stringResource(R.string.open_chat),
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                    OutlinedButton(
                        onClick = {
                            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                            onArchiveChatSession(session.id)
                        },
                        enabled = isActionEnabled,
                        modifier = Modifier
                            .widthIn(min = 124.dp)
                            .semantics {
                                contentDescription = archiveActionContentDescription
                                onClick(label = archiveActionContentDescription, action = null)
                                chatHistoryActionStateDescription?.let { stateDescription = it }
                            },
                    ) {
                        Icon(Icons.Filled.Archive, contentDescription = null)
                        Spacer(Modifier.width(6.dp))
                        Text(
                            text = stringResource(R.string.archive_chat),
                            maxLines = 2,
                            overflow = TextOverflow.Ellipsis,
                        )
                    }
                }
                IconButton(
                    onClick = {
                        hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                        onRenameChatSession(session.id)
                    },
                    enabled = isActionEnabled,
                    modifier = Modifier.semantics {
                        contentDescription = renameActionContentDescription
                        onClick(label = renameActionContentDescription, action = null)
                        chatHistoryActionStateDescription?.let { stateDescription = it }
                    },
                ) {
                    Icon(Icons.Filled.Edit, contentDescription = null)
                }
            }
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun ChatHistorySettingsActionRow(
    sessionId: String,
    content: @Composable FlowRowScope.() -> Unit,
) {
    FlowRow(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(settingsChatHistoryActionsTestTag(sessionId)),
        horizontalArrangement = Arrangement.spacedBy(8.dp),
        verticalArrangement = Arrangement.spacedBy(6.dp),
        itemVerticalAlignment = Alignment.CenterVertically,
        content = content,
    )
}

@Composable
private fun runtimeSearchMetadataText(
    session: RuntimeChatSession,
    showSearchMetadata: Boolean,
): String? {
    if (!showSearchMetadata) return null
    val rankText = session.searchRank
        ?.takeIf { it > 0 }
        ?.let { stringResource(R.string.chat_search_match_rank, it) }
    val fieldText = session.searchMatchedFields
        .mapNotNull { runtimeSearchFieldLabel(it) }
        .distinct()
        .take(3)
        .joinToString(", ")
        .takeIf(String::isNotBlank)
    return when {
        rankText != null && fieldText != null -> stringResource(
            R.string.chat_search_match_metadata,
            rankText,
            fieldText,
        )
        rankText != null -> rankText
        fieldText != null -> stringResource(R.string.chat_search_match_fields, fieldText)
        else -> null
    }
}

@Composable
private fun runtimeSearchFieldLabel(field: String): String? {
    return when (field.trim().lowercase(Locale.ROOT)) {
        "title" -> stringResource(R.string.chat_search_field_title)
        "session_id" -> stringResource(R.string.chat_search_field_session)
        "model" -> stringResource(R.string.chat_search_field_model)
        "status",
        "last_event",
        "last_finish_reason",
        -> stringResource(R.string.chat_search_field_status)
        "last_error_code" -> stringResource(R.string.chat_search_field_error)
        "transcript" -> stringResource(R.string.chat_search_field_transcript)
        "reasoning" -> stringResource(R.string.chat_search_field_reasoning)
        "attachment" -> stringResource(R.string.chat_search_field_attachment)
        else -> null
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
    val cancelActionContentDescription = stringResource(
        R.string.confirmation_cancel_action_named,
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
                modifier = Modifier.semantics {
                    contentDescription = cancelActionContentDescription
                    onClick(label = cancelActionContentDescription, action = null)
                },
            ) {
                Text(stringResource(R.string.cancel))
            }
        },
    )
}

@Composable
internal fun MemoryPanel(
    entries: List<RuntimeMemoryEntry>,
    summaryDrafts: List<RuntimeMemorySummaryDraft> = emptyList(),
    approvingSummaryDraftIds: Set<String> = emptySet(),
    dismissingSummaryDraftIds: Set<String> = emptySet(),
    actionsEnabled: Boolean,
    @StringRes actionsDisabledReasonRes: Int = memoryLockNoticeTextRes(hasEntries = entries.isNotEmpty()),
    onAddMemoryEntry: (String) -> Unit,
    onRemoveMemoryEntry: (String) -> Unit,
    onSetMemoryEntryEnabled: (String, Boolean) -> Unit,
    onApproveMemorySummaryDraft: (String) -> Unit = {},
    onDismissMemorySummaryDraft: (String) -> Unit = {},
    onRefreshMemory: () -> Unit,
    showHeader: Boolean = true,
) {
    val draft = rememberSaveable { mutableStateOf("") }
    val showAddedMemoryNotice = rememberSaveable { mutableStateOf(false) }
    val canAdd = actionsEnabled && draft.value.isNotBlank()
    val hapticFeedback = LocalHapticFeedback.current
    val actionsDisabledReason = stringResource(actionsDisabledReasonRes)
    val memoryAddedNotice = stringResource(R.string.memory_added)
    val memoryAddStateDescription = when {
        !actionsEnabled -> actionsDisabledReason
        draft.value.isBlank() -> stringResource(R.string.memory_add_state_enter_memory)
        else -> stringResource(R.string.memory_add_state_ready)
    }
    val memoryRefreshContentDescription = stringResource(R.string.memory_refresh)
    val memoryAddContentDescription = stringResource(R.string.memory_add_label)
    val memoryAddActionLabel = stringResource(R.string.memory_add)
    val pausedMemoryCount = entries.count { !it.enabled }
    val memorySummary = stringResource(
        R.string.memory_summary,
        pluralStringResource(
            R.plurals.memory_saved_count,
            entries.size,
            entries.size,
        ),
        pluralStringResource(
            R.plurals.memory_paused_count,
            pausedMemoryCount,
            pausedMemoryCount,
        ),
    )

    OutlinedCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier.padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (showHeader) {
                MemoryPanelHeader(
                    actionsEnabled = actionsEnabled,
                    actionsDisabledReason = actionsDisabledReason,
                    memoryRefreshContentDescription = memoryRefreshContentDescription,
                    onRefreshMemory = onRefreshMemory,
                    hapticFeedback = hapticFeedback,
                )
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                ) {
                    MemoryRefreshButton(
                        actionsEnabled = actionsEnabled,
                        actionsDisabledReason = actionsDisabledReason,
                        memoryRefreshContentDescription = memoryRefreshContentDescription,
                        onRefreshMemory = onRefreshMemory,
                        hapticFeedback = hapticFeedback,
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
                        text = actionsDisabledReason,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                        style = MaterialTheme.typography.bodySmall,
                    )
                }
            }
            OutlinedTextField(
                value = draft.value,
                onValueChange = {
                    draft.value = it
                    showAddedMemoryNotice.value = false
                },
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
                    showAddedMemoryNotice.value = true
                },
                enabled = canAdd,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        stateDescription = memoryAddStateDescription
                        onClick(label = memoryAddActionLabel, action = null)
                    },
            ) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(memoryAddActionLabel)
            }
            if (actionsEnabled && showAddedMemoryNotice.value) {
                Surface(
                    modifier = Modifier
                        .fillMaxWidth()
                        .semantics {
                            contentDescription = memoryAddedNotice
                            liveRegion = LiveRegionMode.Polite
                        },
                    shape = RoundedCornerShape(8.dp),
                    color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f),
                    contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
                ) {
                    Text(
                        text = memoryAddedNotice,
                        modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Medium,
                    )
                }
            }
            if (entries.isEmpty()) {
                EmptyState(
                    text = if (!actionsEnabled && actionsDisabledReasonRes == R.string.memory_action_state_wait_for_stream) {
                        actionsDisabledReason
                    } else {
                        stringResource(memoryEmptyStateTextRes(actionsEnabled = actionsEnabled))
                    },
                    announceChanges = true,
                )
            } else {
                MemorySummary(summary = memorySummary)
                Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    entries.forEach { entry ->
                        MemoryEntryRow(
                            entry = entry,
                            actionsEnabled = actionsEnabled,
                            disabledActionStateDescription = if (actionsEnabled) null else actionsDisabledReason,
                            onRemoveMemoryEntry = onRemoveMemoryEntry,
                            onSetMemoryEntryEnabled = onSetMemoryEntryEnabled,
                        )
                    }
                }
            }
            if (summaryDrafts.isNotEmpty()) {
                MemorySummaryDraftsSection(
                    drafts = summaryDrafts,
                    approvingDraftIds = approvingSummaryDraftIds,
                    dismissingDraftIds = dismissingSummaryDraftIds,
                    actionsEnabled = actionsEnabled,
                    disabledActionStateDescription = if (actionsEnabled) null else actionsDisabledReason,
                    onApproveMemorySummaryDraft = onApproveMemorySummaryDraft,
                    onDismissMemorySummaryDraft = onDismissMemorySummaryDraft,
                    hapticFeedback = hapticFeedback,
                )
            }
        }
    }
}

@Composable
private fun MemorySummary(summary: String) {
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = summary
                liveRegion = LiveRegionMode.Polite
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.secondaryContainer.copy(alpha = 0.55f),
        contentColor = MaterialTheme.colorScheme.onSecondaryContainer,
    ) {
        Text(
            text = summary,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 10.dp),
            style = MaterialTheme.typography.bodySmall,
            fontWeight = FontWeight.Medium,
        )
    }
}

@Composable
private fun MemorySummaryDraftsSection(
    drafts: List<RuntimeMemorySummaryDraft>,
    approvingDraftIds: Set<String>,
    dismissingDraftIds: Set<String>,
    actionsEnabled: Boolean,
    disabledActionStateDescription: String?,
    onApproveMemorySummaryDraft: (String) -> Unit,
    onDismissMemorySummaryDraft: (String) -> Unit,
    hapticFeedback: HapticFeedback,
) {
    val sectionTitle = stringResource(R.string.memory_summary_drafts_title)
    val countSummary = pluralStringResource(
        R.plurals.memory_summary_drafts_count,
        drafts.size,
        drafts.size,
    )
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .semantics {
                contentDescription = countSummary
                liveRegion = LiveRegionMode.Polite
            },
        verticalArrangement = Arrangement.spacedBy(8.dp),
    ) {
        HorizontalDivider()
        Text(
            text = sectionTitle,
            style = MaterialTheme.typography.titleSmall,
            fontWeight = FontWeight.SemiBold,
            modifier = Modifier.semantics { heading() },
        )
        Text(
            text = countSummary,
            style = MaterialTheme.typography.bodySmall,
            color = MaterialTheme.colorScheme.secondary,
        )
        drafts.forEach { draft ->
            MemorySummaryDraftRow(
                draft = draft,
                approving = draft.id in approvingDraftIds,
                dismissing = draft.id in dismissingDraftIds,
                actionsEnabled = actionsEnabled,
                disabledActionStateDescription = disabledActionStateDescription,
                onApproveMemorySummaryDraft = onApproveMemorySummaryDraft,
                onDismissMemorySummaryDraft = onDismissMemorySummaryDraft,
                hapticFeedback = hapticFeedback,
            )
        }
    }
}

@OptIn(ExperimentalLayoutApi::class)
@Composable
private fun MemorySummaryDraftRow(
    draft: RuntimeMemorySummaryDraft,
    approving: Boolean,
    dismissing: Boolean,
    actionsEnabled: Boolean,
    disabledActionStateDescription: String?,
    onApproveMemorySummaryDraft: (String) -> Unit,
    onDismissMemorySummaryDraft: (String) -> Unit,
    hapticFeedback: HapticFeedback,
) {
    val untitledChatTitle = stringResource(R.string.untitled_chat)
    val title = draft.session.title.takeIf { it.isNotBlank() } ?: untitledChatTitle
    val sourceCount = pluralStringResource(
        R.plurals.memory_summary_draft_source_count,
        draft.sourcePointers.size,
        draft.sourcePointers.size,
    )
    val sourceRange = draft.sourceRange.takeIf { it.isNotBlank() }
    val approveLabel = stringResource(R.string.memory_summary_draft_approve)
    val approvingLabel = stringResource(R.string.memory_summary_draft_approving)
    val approveContentDescription = stringResource(R.string.memory_summary_draft_approve_named, title)
    val approveStateDescription = when {
        approving -> approvingLabel
        dismissing -> stringResource(R.string.memory_summary_draft_dismissing)
        !actionsEnabled -> disabledActionStateDescription
        else -> stringResource(R.string.memory_summary_draft_approve_state_ready)
    }
    val dismissLabel = stringResource(R.string.memory_summary_draft_dismiss)
    val dismissingLabel = stringResource(R.string.memory_summary_draft_dismissing)
    val dismissContentDescription = stringResource(R.string.memory_summary_draft_dismiss_named, title)
    val dismissStateDescription = when {
        dismissing -> dismissingLabel
        approving -> approvingLabel
        !actionsEnabled -> disabledActionStateDescription
        else -> stringResource(R.string.memory_summary_draft_dismiss_state_ready)
    }
    val rowSummary = stringResource(
        R.string.memory_summary_draft_row_summary,
        title,
        sourceCount,
        sourceRange ?: "",
        draft.summaryPreview,
    )
    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(memorySummaryDraftRowTestTag(draft.id))
            .semantics {
                contentDescription = rowSummary
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.55f),
        contentColor = MaterialTheme.colorScheme.onSurfaceVariant,
    ) {
        Column(
            modifier = Modifier.padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.SemiBold,
            )
            FlowRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(memorySummaryDraftMetadataTestTag(draft.id)),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalArrangement = Arrangement.spacedBy(2.dp),
                itemVerticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = sourceCount,
                    style = MaterialTheme.typography.labelMedium,
                    color = MaterialTheme.colorScheme.secondary,
                )
                sourceRange?.let {
                    Text(
                        text = stringResource(R.string.memory_summary_draft_source_range, it),
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.secondary,
                    )
                }
            }
            Text(
                text = stringResource(R.string.memory_summary_draft_preview_label),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
            Text(
                text = draft.summaryPreview,
                style = MaterialTheme.typography.bodyMedium,
            )
            draft.sourcePointers.take(2).forEach { pointer ->
                val roleLabel = stringResource(
                    if (pointer.role == "user") {
                        R.string.role_user
                    } else {
                        R.string.role_assistant
                    },
                )
                Text(
                    text = stringResource(R.string.memory_summary_draft_source_excerpt, roleLabel, pointer.excerpt),
                    style = MaterialTheme.typography.bodySmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 2,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            Button(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
                    onApproveMemorySummaryDraft(draft.id)
                },
                enabled = actionsEnabled && !approving && !dismissing,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        contentDescription = approveContentDescription
                        approveStateDescription?.let { stateDescription = it }
                        onClick(label = approveContentDescription, action = null)
                    },
            ) {
                Icon(Icons.Filled.Add, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (approving) approvingLabel else approveLabel)
            }
            OutlinedButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                    onDismissMemorySummaryDraft(draft.id)
                },
                enabled = actionsEnabled && !approving && !dismissing,
                modifier = Modifier
                    .fillMaxWidth()
                    .semantics {
                        contentDescription = dismissContentDescription
                        dismissStateDescription?.let { stateDescription = it }
                        onClick(label = dismissContentDescription, action = null)
                    },
            ) {
                Icon(Icons.Filled.Close, contentDescription = null)
                Spacer(Modifier.width(8.dp))
                Text(if (dismissing) dismissingLabel else dismissLabel)
            }
        }
    }
}

@Composable
private fun MemoryPanelHeader(
    actionsEnabled: Boolean,
    actionsDisabledReason: String,
    memoryRefreshContentDescription: String,
    onRefreshMemory: () -> Unit,
    hapticFeedback: HapticFeedback,
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        horizontalArrangement = Arrangement.spacedBy(12.dp),
        verticalAlignment = Alignment.Top,
    ) {
        Column(
            modifier = Modifier.weight(1f),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = stringResource(R.string.memory_title),
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.SemiBold,
                modifier = Modifier.semantics {
                    heading()
                },
            )
            Text(
                text = stringResource(R.string.memory_subtitle),
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.secondary,
            )
        }
        MemoryRefreshButton(
            actionsEnabled = actionsEnabled,
            actionsDisabledReason = actionsDisabledReason,
            memoryRefreshContentDescription = memoryRefreshContentDescription,
            onRefreshMemory = onRefreshMemory,
            hapticFeedback = hapticFeedback,
        )
    }
}

@Composable
private fun MemoryRefreshButton(
    actionsEnabled: Boolean,
    actionsDisabledReason: String,
    memoryRefreshContentDescription: String,
    onRefreshMemory: () -> Unit,
    hapticFeedback: HapticFeedback,
) {
    val memoryRefreshReadyStateDescription = stringResource(R.string.memory_refresh_state_ready)
    IconButton(
        onClick = {
            hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.PrimaryAction)
            onRefreshMemory()
        },
        enabled = actionsEnabled,
        modifier = Modifier.semantics {
            contentDescription = memoryRefreshContentDescription
            stateDescription = if (actionsEnabled) {
                memoryRefreshReadyStateDescription
            } else {
                actionsDisabledReason
            }
            onClick(label = memoryRefreshContentDescription, action = null)
        },
    ) {
        Icon(Icons.Filled.Refresh, contentDescription = null)
    }
}

@Composable
internal fun MemoryEntryRow(
    entry: RuntimeMemoryEntry,
    actionsEnabled: Boolean,
    disabledActionStateDescription: String?,
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
    val memoryRemoveCancelContentDescription = stringResource(
        R.string.confirmation_cancel_action_named,
        memoryRemoveContentDescription,
    )
    val memoryActionStateDescription = disabledActionStateDescription ?: memoryStateDescription

    if (showDeleteConfirmation.value) {
        AlertDialog(
            onDismissRequest = {
                showDeleteConfirmation.value = false
            },
            title = {
                Text(stringResource(R.string.memory_remove_confirm_title))
            },
            text = {
                Text(stringResource(R.string.memory_remove_confirm_message, memoryActionLabel))
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
                        disabledActionStateDescription?.let { stateDescription = it }
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
                    modifier = Modifier.semantics {
                        contentDescription = memoryRemoveCancelContentDescription
                        onClick(label = memoryRemoveCancelContentDescription, action = null)
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
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp),
        ) {
            Text(
                text = entry.content,
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(MEMORY_ENTRY_CONTENT_TEST_TAG),
                style = MaterialTheme.typography.bodyMedium,
                color = if (entry.enabled) {
                    MaterialTheme.colorScheme.onSurfaceVariant
                } else {
                    MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.58f)
                },
            )
            MemoryEntrySourceReview(
                entry = entry,
                memoryActionLabel = memoryActionLabel,
            )
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(MEMORY_ENTRY_ACTIONS_TEST_TAG),
                horizontalArrangement = Arrangement.spacedBy(10.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = stringResource(
                        if (entry.enabled) {
                            R.string.memory_enabled
                        } else {
                            R.string.memory_paused
                        },
                    ),
                    modifier = Modifier.weight(1f),
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
                        stateDescription = memoryActionStateDescription
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
                            disabledActionStateDescription?.let { stateDescription = it }
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
}

@Composable
private fun MemoryEntrySourceReview(
    entry: RuntimeMemoryEntry,
    memoryActionLabel: String,
) {
    val source = entry.source ?: return
    if (source.sourcePointers.isEmpty()) return

    val hapticFeedback = LocalHapticFeedback.current
    val expanded = rememberSaveable(entry.id, "source") { mutableStateOf(false) }
    val untitledChatTitle = stringResource(R.string.untitled_chat)
    val sourceTitle = source.session.title.takeIf { it.isNotBlank() } ?: untitledChatTitle
    val sourceOrigin = stringResource(R.string.memory_source_from_chat, sourceTitle)
    val sourceCount = pluralStringResource(
        R.plurals.memory_summary_draft_source_count,
        source.sourcePointers.size,
        source.sourcePointers.size,
    )
    val sourceRange = source.sourceRange.takeIf { it.isNotBlank() }?.let {
        stringResource(R.string.memory_summary_draft_source_range, it)
    }
    val sourceSummary = stringResource(
        R.string.memory_source_summary,
        sourceOrigin,
        sourceCount,
        sourceRange ?: "",
    )
    val showSource = stringResource(R.string.memory_source_show)
    val hideSource = stringResource(R.string.memory_source_hide)
    val showSourceNamed = stringResource(R.string.memory_source_show_named, memoryActionLabel)
    val hideSourceNamed = stringResource(R.string.memory_source_hide_named, memoryActionLabel)
    val sourceStateDescription = stringResource(
        if (expanded.value) {
            R.string.section_state_expanded
        } else {
            R.string.section_state_collapsed
        },
    )
    val toggleLabel = if (expanded.value) hideSource else showSource
    val toggleContentDescription = if (expanded.value) hideSourceNamed else showSourceNamed

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(MEMORY_ENTRY_SOURCE_TEST_TAG)
            .semantics {
                contentDescription = sourceSummary
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.surface.copy(alpha = 0.72f),
        contentColor = MaterialTheme.colorScheme.onSurface,
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 10.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(6.dp),
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Text(
                    text = sourceOrigin,
                    modifier = Modifier.weight(1f),
                    style = MaterialTheme.typography.labelMedium,
                    fontWeight = FontWeight.SemiBold,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
                Text(
                    text = sourceCount,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                )
            }
            sourceRange?.let {
                Text(
                    text = it,
                    style = MaterialTheme.typography.labelSmall,
                    color = MaterialTheme.colorScheme.secondary,
                )
            }
            TextButton(
                onClick = {
                    hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                    expanded.value = !expanded.value
                },
                modifier = Modifier.semantics {
                    contentDescription = toggleContentDescription
                    stateDescription = sourceStateDescription
                    onClick(label = toggleLabel, action = null)
                },
            ) {
                Icon(
                    imageVector = if (expanded.value) {
                        Icons.Filled.KeyboardArrowUp
                    } else {
                        Icons.Filled.KeyboardArrowDown
                    },
                    contentDescription = null,
                )
                Spacer(Modifier.width(6.dp))
                Text(toggleLabel)
            }
            if (expanded.value) {
                source.sourcePointers.take(2).forEach { pointer ->
                    val roleLabel = stringResource(
                        if (pointer.role == "user") {
                            R.string.role_user
                        } else {
                            R.string.role_assistant
                        },
                    )
                    Text(
                        text = stringResource(R.string.memory_summary_draft_source_excerpt, roleLabel, pointer.excerpt),
                        style = MaterialTheme.typography.bodySmall,
                        color = MaterialTheme.colorScheme.secondary,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
            }
        }
    }
}

internal const val MEMORY_ACTION_LABEL_MAX_CHARS = 80
internal const val AUTO_RECONNECT_CARD_TEST_TAG = "auto_reconnect_card"
internal const val AUTO_RECONNECT_ROW_TEST_TAG = "auto_reconnect_row"
internal const val AUTO_RECONNECT_TITLE_TEST_TAG = "auto_reconnect_title"
internal const val AUTO_RECONNECT_DETAIL_TEST_TAG = "auto_reconnect_detail"
internal const val AUTO_RECONNECT_SWITCH_TEST_TAG = "auto_reconnect_switch"
internal const val CONNECTION_STATUS_PANEL_TEST_TAG = "connection_status_panel"
internal const val CONNECTION_STATUS_HERO_TEST_TAG = "connection_status_hero"
internal const val CONNECTION_STATUS_HERO_ROW_TEST_TAG = "connection_status_hero_row"
internal const val CONNECTION_STATUS_HERO_ICON_TEST_TAG = "connection_status_hero_icon"
internal const val CONNECTION_STATUS_HERO_TITLE_TEST_TAG = "connection_status_hero_title"
internal const val CONNECTION_STATUS_HERO_DETAIL_TEST_TAG = "connection_status_hero_detail"
internal const val CONNECTION_STATUS_LINE_TEST_TAG_PREFIX = "connection_status_line_"
internal const val CONNECTION_STATUS_LINE_LABEL_TEST_TAG_PREFIX = "connection_status_line_label_"
internal const val CONNECTION_STATUS_LINE_VALUE_TEST_TAG_PREFIX = "connection_status_line_value_"
internal const val CONNECTION_STATUS_RUNTIME_LINE_KEY = "runtime"
internal const val CONNECTION_STATUS_PAIRING_LINE_KEY = "pairing"
internal const val CONNECTION_STATUS_BACKEND_LINE_KEY = "backend"
internal const val CONNECTION_STATUS_PROVIDERS_LINE_KEY = "providers"
internal const val CONNECTION_STATUS_CONNECTED_LINE_KEY = "connected"
internal const val CONNECTION_STATUS_AUTO_RECONNECT_LINE_KEY = "auto_reconnect"
internal const val SETTINGS_PREFERENCES_PANEL_TEST_TAG = "settings_preferences_panel"
internal const val SETTINGS_APPEARANCE_GROUP_TEST_TAG = "settings_appearance_group"
internal const val SETTINGS_APPEARANCE_GROUP_LABEL_TEST_TAG = "settings_appearance_group_label"
internal const val SETTINGS_LANGUAGE_GROUP_TEST_TAG = "settings_language_group"
internal const val SETTINGS_LANGUAGE_GROUP_LABEL_TEST_TAG = "settings_language_group_label"
internal const val SETTINGS_APPEARANCE_OPTION_ROW_TEST_TAG_PREFIX = "settings_appearance_option_row_"
internal const val SETTINGS_APPEARANCE_OPTION_RADIO_TEST_TAG_PREFIX = "settings_appearance_option_radio_"
internal const val SETTINGS_APPEARANCE_OPTION_LABEL_TEST_TAG_PREFIX = "settings_appearance_option_label_"
internal const val SETTINGS_APPEARANCE_OPTION_DETAIL_TEST_TAG_PREFIX = "settings_appearance_option_detail_"
internal const val SETTINGS_LANGUAGE_OPTION_ROW_TEST_TAG_PREFIX = "settings_language_option_row_"
internal const val SETTINGS_LANGUAGE_OPTION_RADIO_TEST_TAG_PREFIX = "settings_language_option_radio_"
internal const val SETTINGS_LANGUAGE_OPTION_LABEL_TEST_TAG_PREFIX = "settings_language_option_label_"
internal const val SETTINGS_LANGUAGE_OPTION_DETAIL_TEST_TAG_PREFIX = "settings_language_option_detail_"
internal const val EMBEDDING_MODEL_PANEL_TEST_TAG = "embedding_model_panel"
internal const val EMBEDDING_MODEL_NONE_ROW_TEST_TAG = "embedding_model_none_row"
internal const val EMBEDDING_MODEL_NONE_LABEL_TEST_TAG = "embedding_model_none_label"
internal const val EMBEDDING_MODEL_NONE_DETAIL_TEST_TAG = "embedding_model_none_detail"
internal const val SAVED_EMBEDDING_MODEL_ROW_TEST_TAG = "saved_embedding_model_row"
internal const val SAVED_EMBEDDING_MODEL_LABEL_TEST_TAG = "saved_embedding_model_label"
internal const val SAVED_EMBEDDING_MODEL_DETAIL_TEST_TAG = "saved_embedding_model_detail"
internal const val MEMORY_ENTRY_CONTENT_TEST_TAG = "memory_entry_content"
internal const val MEMORY_ENTRY_ACTIONS_TEST_TAG = "memory_entry_actions"
internal const val MEMORY_ENTRY_SOURCE_TEST_TAG = "memory_entry_source"

internal fun appearancePreferenceOptionRowTestTag(theme: RuntimeAppTheme): String =
    "$SETTINGS_APPEARANCE_OPTION_ROW_TEST_TAG_PREFIX${settingsPreferenceTagKey(theme.name)}"

internal fun appearancePreferenceOptionRadioTestTag(theme: RuntimeAppTheme): String =
    "$SETTINGS_APPEARANCE_OPTION_RADIO_TEST_TAG_PREFIX${settingsPreferenceTagKey(theme.name)}"

internal fun appearancePreferenceOptionLabelTestTag(theme: RuntimeAppTheme): String =
    "$SETTINGS_APPEARANCE_OPTION_LABEL_TEST_TAG_PREFIX${settingsPreferenceTagKey(theme.name)}"

internal fun appearancePreferenceOptionDetailTestTag(theme: RuntimeAppTheme): String =
    "$SETTINGS_APPEARANCE_OPTION_DETAIL_TEST_TAG_PREFIX${settingsPreferenceTagKey(theme.name)}"

internal fun languagePreferenceOptionRowTestTag(languageTag: String): String =
    "$SETTINGS_LANGUAGE_OPTION_ROW_TEST_TAG_PREFIX${settingsPreferenceTagKey(languageTag)}"

internal fun languagePreferenceOptionRadioTestTag(languageTag: String): String =
    "$SETTINGS_LANGUAGE_OPTION_RADIO_TEST_TAG_PREFIX${settingsPreferenceTagKey(languageTag)}"

internal fun languagePreferenceOptionLabelTestTag(languageTag: String): String =
    "$SETTINGS_LANGUAGE_OPTION_LABEL_TEST_TAG_PREFIX${settingsPreferenceTagKey(languageTag)}"

internal fun languagePreferenceOptionDetailTestTag(languageTag: String): String =
    "$SETTINGS_LANGUAGE_OPTION_DETAIL_TEST_TAG_PREFIX${settingsPreferenceTagKey(languageTag)}"

private fun settingsPreferenceTagKey(value: String): String =
    value.lowercase(Locale.ROOT).replace("-", "_")

internal fun embeddingModelRowTestTag(modelId: String): String =
    "embedding_model_row_$modelId"

internal fun embeddingModelRowNameTestTag(modelId: String): String =
    "embedding_model_row_name_$modelId"

internal fun embeddingModelRowStatusTestTag(modelId: String): String =
    "embedding_model_row_status_$modelId"

internal fun memorySummaryDraftRowTestTag(draftId: String): String =
    "memory_summary_draft_row_$draftId"

internal fun memorySummaryDraftMetadataTestTag(draftId: String): String =
    "memory_summary_draft_metadata_$draftId"

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
private fun StatusLine(
    label: String,
    value: String,
    tagKey: String? = null,
) {
    val lineModifier = tagKey?.let { Modifier.testTag(connectionStatusLineTestTag(it)) } ?: Modifier
    val labelModifier = tagKey?.let { Modifier.testTag(connectionStatusLineLabelTestTag(it)) } ?: Modifier
    val valueModifier = tagKey?.let { Modifier.testTag(connectionStatusLineValueTestTag(it)) } ?: Modifier

    Column(
        modifier = lineModifier.fillMaxWidth(),
        verticalArrangement = Arrangement.spacedBy(4.dp),
    ) {
        Text(
            text = label,
            style = MaterialTheme.typography.labelMedium,
            color = MaterialTheme.colorScheme.secondary,
            maxLines = 1,
            overflow = TextOverflow.Ellipsis,
            modifier = labelModifier,
        )
        Text(
            text = value,
            style = MaterialTheme.typography.bodyLarge,
            fontWeight = FontWeight.Medium,
            maxLines = 2,
            overflow = TextOverflow.Ellipsis,
            modifier = valueModifier,
        )
        HorizontalDivider()
    }
}

@Composable
private fun ChatHistorySearchResultSummary(
    query: String,
    activeCount: Int,
    archivedCount: Int,
) {
    val safeActiveCount = activeCount.coerceAtLeast(0)
    val safeArchivedCount = archivedCount.coerceAtLeast(0)
    val activeText = pluralStringResource(
        R.plurals.chat_history_active_count,
        safeActiveCount,
        safeActiveCount,
    )
    val archivedText = pluralStringResource(
        R.plurals.chat_history_archived_count,
        safeArchivedCount,
        safeArchivedCount,
    )
    val resultText = stringResource(
        R.string.chat_history_search_result_summary,
        query,
        activeText,
        archivedText,
    )

    Text(
        text = resultText,
        style = MaterialTheme.typography.bodySmall,
        color = MaterialTheme.colorScheme.secondary,
        modifier = Modifier
            .testTag(SETTINGS_CHAT_HISTORY_SEARCH_RESULT_SUMMARY_TEST_TAG)
            .semantics {
                contentDescription = resultText
                liveRegion = LiveRegionMode.Polite
            },
    )
}

@Composable
private fun ChatHistorySummary(
    activeCount: Int,
    archivedCount: Int,
) {
    val safeActiveCount = activeCount.coerceAtLeast(0)
    val safeArchivedCount = archivedCount.coerceAtLeast(0)
    val savedCount = safeActiveCount + safeArchivedCount
    val savedText = pluralStringResource(
        R.plurals.chat_history_saved_count,
        savedCount,
        savedCount,
    )
    val activeText = pluralStringResource(
        R.plurals.chat_history_active_count,
        safeActiveCount,
        safeActiveCount,
    )
    val archivedText = pluralStringResource(
        R.plurals.chat_history_archived_count,
        safeArchivedCount,
        safeArchivedCount,
    )
    val detailText = stringResource(
        R.string.chat_history_summary_detail,
        activeText,
        archivedText,
    )
    val accessibilitySummary = stringResource(
        R.string.chat_history_summary_accessibility,
        savedText,
        detailText,
    )

    Surface(
        modifier = Modifier
            .fillMaxWidth()
            .semantics(mergeDescendants = true) {
                contentDescription = accessibilitySummary
            },
        shape = RoundedCornerShape(16.dp),
        color = MaterialTheme.colorScheme.surfaceVariant.copy(alpha = 0.58f),
    ) {
        Column(
            modifier = Modifier.padding(horizontal = 14.dp, vertical = 12.dp),
            verticalArrangement = Arrangement.spacedBy(4.dp),
        ) {
            Text(
                text = stringResource(R.string.chat_history_summary_title),
                style = MaterialTheme.typography.labelMedium,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = savedText,
                style = MaterialTheme.typography.titleSmall,
                fontWeight = FontWeight.SemiBold,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
            )
            Text(
                text = detailText,
                style = MaterialTheme.typography.bodySmall,
                color = MaterialTheme.colorScheme.secondary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis,
            )
        }
    }
}

@Composable
private fun EmptyState(
    text: String,
    announceChanges: Boolean = false,
) {
    val stateModifier = if (announceChanges) {
        Modifier.semantics(mergeDescendants = true) {
            contentDescription = text
            liveRegion = LiveRegionMode.Polite
        }
    } else {
        Modifier
    }
    Surface(
        modifier = stateModifier.fillMaxWidth(),
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
            .testTag(CHAT_RUNTIME_ERROR_BANNER_TEST_TAG)
            .semantics {
                contentDescription = accessibilitySummary
                liveRegion = LiveRegionMode.Polite
            },
        shape = RoundedCornerShape(8.dp),
        color = MaterialTheme.colorScheme.errorContainer,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(12.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp),
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(CHAT_RUNTIME_ERROR_ROW_TEST_TAG),
                verticalAlignment = Alignment.CenterVertically,
            ) {
                Icon(
                    Icons.Filled.Error,
                    contentDescription = null,
                    tint = MaterialTheme.colorScheme.onErrorContainer,
                    modifier = Modifier.testTag(CHAT_RUNTIME_ERROR_ICON_TEST_TAG),
                )
                Spacer(Modifier.width(8.dp))
                Column(
                    modifier = Modifier
                        .weight(1f)
                        .testTag(CHAT_RUNTIME_ERROR_TEXT_COLUMN_TEST_TAG),
                    verticalArrangement = Arrangement.spacedBy(2.dp),
                ) {
                    Text(
                        text = errorTitle,
                        style = MaterialTheme.typography.labelMedium,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.testTag(CHAT_RUNTIME_ERROR_TITLE_TEST_TAG),
                    )
                    Text(
                        text = errorLabel,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.testTag(CHAT_RUNTIME_ERROR_MESSAGE_TEST_TAG),
                    )
                    detailLabel?.let { detail ->
                        Text(
                            text = detail,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.testTag(CHAT_RUNTIME_ERROR_DETAIL_TEST_TAG),
                        )
                    }
                    diagnosticLabel?.let { diagnostic ->
                        Text(
                            text = diagnostic,
                            style = MaterialTheme.typography.bodySmall,
                            color = MaterialTheme.colorScheme.onErrorContainer,
                            maxLines = 3,
                            overflow = TextOverflow.Ellipsis,
                            modifier = Modifier.testTag(CHAT_RUNTIME_ERROR_DIAGNOSTIC_TEST_TAG),
                        )
                    }
                }
            }
            runtimeTechnicalDiagnosticsReport(
                error = error,
                codeLabel = stringResource(R.string.runtime_error_diagnostics_code),
                diagnosticCodeLabel = stringResource(R.string.runtime_error_diagnostics_diagnostic_code),
                technicalDetailLabel = stringResource(R.string.runtime_error_diagnostics_technical_detail),
            )?.let { report ->
                ErrorTechnicalDiagnostics(report = report)
            }
        }
    }
}

@Composable
private fun ErrorTechnicalDiagnostics(report: String) {
    var expanded by rememberSaveable(report) { mutableStateOf(false) }
    val hapticFeedback = LocalHapticFeedback.current
    val title = stringResource(R.string.runtime_error_technical_details)
    val stateDescriptionText = stringResource(
        if (expanded) {
            R.string.section_state_expanded
        } else {
            R.string.section_state_collapsed
        }
    )
    val toggleLabel = stringResource(
        if (expanded) {
            R.string.runtime_error_hide_technical_details
        } else {
            R.string.runtime_error_show_technical_details
        }
    )

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(CHAT_RUNTIME_ERROR_TECHNICAL_TEST_TAG),
        verticalArrangement = Arrangement.spacedBy(6.dp),
    ) {
        TextButton(
            onClick = {
                hapticFeedback.performAetherLinkFeedback(AetherLinkInteractionFeedback.Toggle)
                expanded = !expanded
            },
            contentPadding = PaddingValues(horizontal = 0.dp, vertical = 0.dp),
            modifier = Modifier
                .fillMaxWidth()
                .testTag(CHAT_RUNTIME_ERROR_TECHNICAL_TOGGLE_TEST_TAG)
                .semantics {
                    contentDescription = title
                    stateDescription = stateDescriptionText
                    onClick(label = toggleLabel, action = null)
                },
        ) {
            Text(
                text = title,
                color = MaterialTheme.colorScheme.onErrorContainer,
                maxLines = 1,
                overflow = TextOverflow.Ellipsis,
                modifier = Modifier
                    .weight(1f)
                    .testTag(CHAT_RUNTIME_ERROR_TECHNICAL_TOGGLE_LABEL_TEST_TAG),
            )
            Icon(
                imageVector = if (expanded) {
                    Icons.Filled.KeyboardArrowUp
                } else {
                    Icons.Filled.KeyboardArrowDown
                },
                contentDescription = null,
                tint = MaterialTheme.colorScheme.onErrorContainer,
                modifier = Modifier
                    .size(18.dp)
                    .testTag(CHAT_RUNTIME_ERROR_TECHNICAL_TOGGLE_ICON_TEST_TAG),
            )
        }
        if (expanded) {
            Surface(
                modifier = Modifier
                    .fillMaxWidth()
                    .testTag(CHAT_RUNTIME_ERROR_TECHNICAL_PANEL_TEST_TAG),
                shape = RoundedCornerShape(8.dp),
                color = MaterialTheme.colorScheme.surface.copy(alpha = 0.38f),
                contentColor = MaterialTheme.colorScheme.onErrorContainer,
            ) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(10.dp),
                    verticalArrangement = Arrangement.spacedBy(6.dp),
                ) {
                    Row(
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag(CHAT_RUNTIME_ERROR_TECHNICAL_ACTIONS_TEST_TAG),
                        horizontalArrangement = Arrangement.End,
                    ) {
                        MessageCopyButton(
                            textToCopy = report,
                            copyActionLabel = stringResource(R.string.runtime_error_copy_diagnostics),
                        )
                    }
                    Text(
                        text = report,
                        style = MaterialTheme.typography.bodySmall,
                        fontFamily = FontFamily.Monospace,
                        color = MaterialTheme.colorScheme.onErrorContainer,
                        maxLines = 8,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier
                            .fillMaxWidth()
                            .testTag(CHAT_RUNTIME_ERROR_TECHNICAL_REPORT_TEST_TAG),
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

    Box(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(ROUTE_AVAILABILITY_NOTICE_TEST_TAG),
    ) {
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
            Column(
                modifier = Modifier.padding(horizontal = 12.dp, vertical = 7.dp),
                verticalArrangement = Arrangement.spacedBy(5.dp),
            ) {
                Row(
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
                        modifier = Modifier
                            .weight(1f)
                            .testTag(ROUTE_AVAILABILITY_NOTICE_BODY_TEST_TAG),
                        color = MaterialTheme.colorScheme.onSurfaceVariant.copy(alpha = 0.86f),
                        style = MaterialTheme.typography.bodySmall,
                        fontWeight = FontWeight.Medium,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
                if (actionLabel != null && actionHandler != null) {
                    Text(
                        text = actionLabel,
                        modifier = Modifier
                            .align(Alignment.End)
                            .testTag(ROUTE_AVAILABILITY_NOTICE_ACTION_TEST_TAG),
                        color = MaterialTheme.colorScheme.primary,
                        style = MaterialTheme.typography.labelMedium,
                        fontWeight = FontWeight.SemiBold,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis,
                    )
                }
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
        "route_diagnostic_relay_unreachable_from_device" -> R.string.route_diagnostic_relay_unreachable_from_device
        "route_diagnostic_relay_failed" -> R.string.route_diagnostic_relay_failed
        "route_diagnostic_relay_auth_failed" -> R.string.route_diagnostic_relay_auth_failed
        "route_diagnostic_remote_route_expired" -> R.string.route_diagnostic_remote_route_expired
        "route_diagnostic_direct_qr_rejected" -> R.string.route_diagnostic_direct_qr_rejected
        "route_diagnostic_relay_qr_unreachable" -> R.string.route_diagnostic_relay_qr_unreachable
        else -> when {
            error.code == "remote_route_unreachable_from_device" -> R.string.error_remote_route_unreachable_from_device
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
    "remote_route_unreachable_from_device",
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
    "route_diagnostic_relay_unreachable_from_device",
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
    "route_diagnostic_relay_unreachable_from_device",
    "route_diagnostic_relay_failed",
    "route_diagnostic_relay_auth_failed",
    "route_diagnostic_remote_route_expired",
    "route_diagnostic_direct_qr_rejected",
    "route_diagnostic_relay_qr_unreachable",
)

private val QR_REFRESH_EMPTY_CHAT_ERROR_CODES = setOf(
    "remote_routes_unavailable",
    "remote_route_unreachable_from_device",
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

internal fun chatTranscriptMessageGap(previousRole: String, currentRole: String) =
    if (previousRole == currentRole) 10.dp else 22.dp

internal fun chatMessageRowTestTag(messageId: String): String = "$CHAT_MESSAGE_ROW_TEST_TAG_PREFIX$messageId"

internal fun chatMessageActionsTestTag(messageId: String): String = "$CHAT_MESSAGE_ACTIONS_TEST_TAG_PREFIX$messageId"

internal fun readOnlyAttachmentChipsTestTag(messageId: String): String =
    "$READ_ONLY_ATTACHMENT_CHIPS_TEST_TAG_PREFIX$messageId"

internal fun pendingAttachmentChipTestTag(attachmentId: String): String =
    "$PENDING_ATTACHMENT_CHIP_TEST_TAG_PREFIX$attachmentId"

internal fun settingsChatHistoryActionsTestTag(sessionId: String): String =
    "$SETTINGS_CHAT_HISTORY_ACTIONS_TEST_TAG_PREFIX$sessionId"

internal fun settingsChatHistoryRowContentTestTag(sessionId: String): String =
    "$SETTINGS_CHAT_HISTORY_ROW_CONTENT_TEST_TAG_PREFIX$sessionId"

internal fun settingsChatHistorySearchMetadataTestTag(sessionId: String): String =
    "$SETTINGS_CHAT_HISTORY_SEARCH_METADATA_TEST_TAG_PREFIX$sessionId"

internal fun settingsChatHistorySearchSnippetTestTag(sessionId: String): String =
    "$SETTINGS_CHAT_HISTORY_SEARCH_SNIPPET_TEST_TAG_PREFIX$sessionId"

internal fun discoveredRuntimeRowTestTag(serviceName: String): String =
    "$DISCOVERED_RUNTIME_ROW_TEST_TAG_PREFIX$serviceName"

internal fun discoveredRuntimeActionTestTag(serviceName: String): String =
    "$DISCOVERED_RUNTIME_ACTION_TEST_TAG_PREFIX$serviceName"

internal fun discoveredRuntimeStatusTestTag(serviceName: String): String =
    "$DISCOVERED_RUNTIME_STATUS_TEST_TAG_PREFIX$serviceName"

internal fun providerStatusRowTestTag(providerId: String): String =
    "$PROVIDER_STATUS_ROW_TEST_TAG_PREFIX$providerId"

internal fun providerStatusHeaderTestTag(providerId: String): String =
    "$PROVIDER_STATUS_HEADER_TEST_TAG_PREFIX$providerId"

internal fun providerStatusStatusTestTag(providerId: String): String =
    "$PROVIDER_STATUS_STATUS_TEST_TAG_PREFIX$providerId"

internal fun providerStatusDiagnosticsButtonTestTag(providerId: String): String =
    "$PROVIDER_STATUS_DIAGNOSTICS_BUTTON_TEST_TAG_PREFIX$providerId"

internal fun providerStatusDiagnosticsPanelTestTag(providerId: String): String =
    "$PROVIDER_STATUS_DIAGNOSTICS_PANEL_TEST_TAG_PREFIX$providerId"

internal fun connectionStatusLineTestTag(key: String): String =
    "$CONNECTION_STATUS_LINE_TEST_TAG_PREFIX$key"

internal fun connectionStatusLineLabelTestTag(key: String): String =
    "$CONNECTION_STATUS_LINE_LABEL_TEST_TAG_PREFIX$key"

internal fun connectionStatusLineValueTestTag(key: String): String =
    "$CONNECTION_STATUS_LINE_VALUE_TEST_TAG_PREFIX$key"

internal const val CHAT_MESSAGE_LIST_TEST_TAG = "aetherlink_chat_message_list"
internal const val CHAT_JUMP_TO_LATEST_TEST_TAG = "aetherlink_chat_jump_to_latest"
internal const val CHAT_STREAMING_PROGRESS_TEST_TAG = "aetherlink_chat_streaming_progress"
internal const val CHAT_BACKEND_READINESS_BANNER_TEST_TAG = "aetherlink_chat_backend_readiness_banner"
internal const val CHAT_BACKEND_READINESS_TITLE_TEST_TAG = "aetherlink_chat_backend_readiness_title"
internal const val CHAT_BACKEND_READINESS_DETAIL_TEST_TAG = "aetherlink_chat_backend_readiness_detail"
internal const val CHAT_BACKEND_READINESS_REFRESH_TEST_TAG = "aetherlink_chat_backend_readiness_refresh"
internal const val CHAT_RUNTIME_ERROR_BANNER_TEST_TAG = "aetherlink_chat_runtime_error_banner"
internal const val CHAT_RUNTIME_ERROR_ROW_TEST_TAG = "aetherlink_chat_runtime_error_row"
internal const val CHAT_RUNTIME_ERROR_ICON_TEST_TAG = "aetherlink_chat_runtime_error_icon"
internal const val CHAT_RUNTIME_ERROR_TEXT_COLUMN_TEST_TAG = "aetherlink_chat_runtime_error_text_column"
internal const val CHAT_RUNTIME_ERROR_TITLE_TEST_TAG = "aetherlink_chat_runtime_error_title"
internal const val CHAT_RUNTIME_ERROR_MESSAGE_TEST_TAG = "aetherlink_chat_runtime_error_message"
internal const val CHAT_RUNTIME_ERROR_DETAIL_TEST_TAG = "aetherlink_chat_runtime_error_detail"
internal const val CHAT_RUNTIME_ERROR_DIAGNOSTIC_TEST_TAG = "aetherlink_chat_runtime_error_diagnostic"
internal const val CHAT_RUNTIME_ERROR_TECHNICAL_TEST_TAG = "aetherlink_chat_runtime_error_technical"
internal const val CHAT_RUNTIME_ERROR_TECHNICAL_TOGGLE_TEST_TAG =
    "aetherlink_chat_runtime_error_technical_toggle"
internal const val CHAT_RUNTIME_ERROR_TECHNICAL_TOGGLE_LABEL_TEST_TAG =
    "aetherlink_chat_runtime_error_technical_toggle_label"
internal const val CHAT_RUNTIME_ERROR_TECHNICAL_TOGGLE_ICON_TEST_TAG =
    "aetherlink_chat_runtime_error_technical_toggle_icon"
internal const val CHAT_RUNTIME_ERROR_TECHNICAL_PANEL_TEST_TAG =
    "aetherlink_chat_runtime_error_technical_panel"
internal const val CHAT_RUNTIME_ERROR_TECHNICAL_ACTIONS_TEST_TAG =
    "aetherlink_chat_runtime_error_technical_actions"
internal const val CHAT_RUNTIME_ERROR_TECHNICAL_REPORT_TEST_TAG =
    "aetherlink_chat_runtime_error_technical_report"
internal const val CHAT_MARKDOWN_TABLE_TEST_TAG = "aetherlink_chat_markdown_table"
internal const val CHAT_MARKDOWN_TABLE_SURFACE_TEST_TAG = "aetherlink_chat_markdown_table_surface"
internal const val CHAT_CODE_BLOCK_TEST_TAG = "aetherlink_chat_code_block"
internal const val CHAT_CODE_BLOCK_HEADER_TEST_TAG = "aetherlink_chat_code_block_header"
internal const val CHAT_CODE_BLOCK_LANGUAGE_TEST_TAG = "aetherlink_chat_code_block_language"
internal const val CHAT_CODE_BLOCK_COPY_ACTION_TEST_TAG = "aetherlink_chat_code_block_copy_action"
internal const val CHAT_CODE_BLOCK_TEXT_TEST_TAG = "aetherlink_chat_code_block_text"
internal const val CHAT_MESSAGE_ROW_TEST_TAG_PREFIX = "aetherlink_chat_message_row_"
internal const val CHAT_MESSAGE_ACTIONS_TEST_TAG_PREFIX = "aetherlink_chat_message_actions_"
internal const val READ_ONLY_ATTACHMENT_CHIP_MAX_WIDTH_DP = 210
internal const val READ_ONLY_ATTACHMENT_CHIPS_TEST_TAG_PREFIX = "aetherlink_read_only_attachment_chips_"
internal const val PENDING_ATTACHMENT_CHIP_MAX_WIDTH_DP = 244
internal const val PENDING_ATTACHMENT_CHIPS_TEST_TAG = "aetherlink_pending_attachment_chips"
internal const val PENDING_ATTACHMENT_CHIP_TEST_TAG_PREFIX = "aetherlink_pending_attachment_chip_"
internal const val SETTINGS_QR_PAIRING_PANEL_TEST_TAG = "aetherlink_settings_qr_pairing_panel"
internal const val SETTINGS_QR_PAIRING_SCAN_BUTTON_TEST_TAG = "aetherlink_settings_qr_pairing_scan_button"
internal const val SETTINGS_TRUSTED_RUNTIME_PANEL_TEST_TAG = "aetherlink_settings_trusted_runtime_panel"
internal const val SETTINGS_TRUSTED_RUNTIME_HEADER_TEST_TAG = "aetherlink_settings_trusted_runtime_header"
internal const val SETTINGS_TRUSTED_RUNTIME_ICON_TEST_TAG = "aetherlink_settings_trusted_runtime_icon"
internal const val SETTINGS_TRUSTED_RUNTIME_LABEL_TEST_TAG = "aetherlink_settings_trusted_runtime_label"
internal const val SETTINGS_TRUSTED_RUNTIME_NAME_TEST_TAG = "aetherlink_settings_trusted_runtime_name"
internal const val SETTINGS_TRUSTED_RUNTIME_FORGET_ACTION_TEST_TAG =
    "aetherlink_settings_trusted_runtime_forget_action"
internal const val SETTINGS_TRUSTED_RUNTIME_EMPTY_DETAIL_TEST_TAG =
    "aetherlink_settings_trusted_runtime_empty_detail"
internal const val SETTINGS_EXPANDABLE_SECTION_TEST_TAG_PREFIX = "aetherlink_settings_section_"
internal const val SETTINGS_EXPANDABLE_SECTION_HEADER_TEST_TAG_PREFIX = "aetherlink_settings_section_header_"
internal const val SETTINGS_EXPANDABLE_SECTION_TITLE_TEST_TAG_PREFIX = "aetherlink_settings_section_title_"
internal const val SETTINGS_EXPANDABLE_SECTION_SUBTITLE_TEST_TAG_PREFIX = "aetherlink_settings_section_subtitle_"
internal const val SETTINGS_EXPANDABLE_SECTION_ACTION_TEST_TAG_PREFIX = "aetherlink_settings_section_action_"
internal const val SETTINGS_CHAT_HISTORY_ACTIONS_TEST_TAG_PREFIX = "aetherlink_settings_chat_history_actions_"
internal const val SETTINGS_CHAT_HISTORY_SEARCH_RESULT_SUMMARY_TEST_TAG =
    "aetherlink_settings_chat_history_search_result_summary"
internal const val SETTINGS_CHAT_HISTORY_ROW_CONTENT_TEST_TAG_PREFIX =
    "aetherlink_settings_chat_history_row_content_"
internal const val SETTINGS_CHAT_HISTORY_SEARCH_METADATA_TEST_TAG_PREFIX =
    "aetherlink_settings_chat_history_search_metadata_"
internal const val SETTINGS_CHAT_HISTORY_SEARCH_SNIPPET_TEST_TAG_PREFIX =
    "aetherlink_settings_chat_history_search_snippet_"
internal const val DISCOVERED_RUNTIME_ROW_TEST_TAG_PREFIX = "aetherlink_discovered_runtime_row_"
internal const val DISCOVERED_RUNTIME_ACTION_TEST_TAG_PREFIX = "aetherlink_discovered_runtime_action_"
internal const val DISCOVERED_RUNTIME_STATUS_TEST_TAG_PREFIX = "aetherlink_discovered_runtime_status_"
internal const val PROVIDER_STATUS_ROW_TEST_TAG_PREFIX = "aetherlink_provider_status_row_"
internal const val PROVIDER_STATUS_HEADER_TEST_TAG_PREFIX = "aetherlink_provider_status_header_"
internal const val PROVIDER_STATUS_STATUS_TEST_TAG_PREFIX = "aetherlink_provider_status_status_"
internal const val PROVIDER_STATUS_DIAGNOSTICS_BUTTON_TEST_TAG_PREFIX =
    "aetherlink_provider_status_diagnostics_button_"
internal const val PROVIDER_STATUS_DIAGNOSTICS_PANEL_TEST_TAG_PREFIX =
    "aetherlink_provider_status_diagnostics_panel_"
internal const val ROUTE_AVAILABILITY_NOTICE_TEST_TAG = "aetherlink_route_availability_notice"
internal const val ROUTE_AVAILABILITY_NOTICE_BODY_TEST_TAG = "aetherlink_route_availability_notice_body"
internal const val ROUTE_AVAILABILITY_NOTICE_ACTION_TEST_TAG = "aetherlink_route_availability_notice_action"
internal const val ASSISTANT_IDENTITY_MARKER_TEST_TAG = "aetherlink_assistant_identity_marker"
internal const val CHAT_COMPOSER_CONTAINER_TEST_TAG = "aetherlink_chat_composer_container"
internal const val CHAT_COMPOSER_CONTROLS_ROW_TEST_TAG = "aetherlink_chat_composer_controls_row"
internal const val CHAT_COMPOSER_ATTACH_ACTION_TEST_TAG = "aetherlink_chat_composer_attach_action"
internal const val CHAT_COMPOSER_INPUT_TEST_TAG = "aetherlink_chat_composer_input"
internal const val CHAT_COMPOSER_CLEAR_DRAFT_ACTION_TEST_TAG = "aetherlink_chat_composer_clear_draft_action"
internal const val CHAT_COMPOSER_SEND_ACTION_TEST_TAG = "aetherlink_chat_composer_send_action"
internal const val CHAT_COMPOSER_CANCEL_ACTION_TEST_TAG = "aetherlink_chat_composer_cancel_action"
internal const val CHAT_COMPOSER_STATUS_TEST_TAG = "aetherlink_chat_composer_status"
internal const val CHAT_COMPOSER_STATUS_DOT_TEST_TAG = "aetherlink_chat_composer_status_dot"
internal const val CHAT_COMPOSER_STATUS_TEXT_TEST_TAG = "aetherlink_chat_composer_status_text"

internal fun settingsExpandableSectionTestTag(@StringRes title: Int): String =
    "$SETTINGS_EXPANDABLE_SECTION_TEST_TAG_PREFIX${settingsExpandableSectionTagKey(title)}"

internal fun settingsExpandableSectionHeaderTestTag(@StringRes title: Int): String =
    "$SETTINGS_EXPANDABLE_SECTION_HEADER_TEST_TAG_PREFIX${settingsExpandableSectionTagKey(title)}"

internal fun settingsExpandableSectionTitleTestTag(@StringRes title: Int): String =
    "$SETTINGS_EXPANDABLE_SECTION_TITLE_TEST_TAG_PREFIX${settingsExpandableSectionTagKey(title)}"

internal fun settingsExpandableSectionSubtitleTestTag(@StringRes title: Int): String =
    "$SETTINGS_EXPANDABLE_SECTION_SUBTITLE_TEST_TAG_PREFIX${settingsExpandableSectionTagKey(title)}"

internal fun settingsExpandableSectionActionTestTag(@StringRes title: Int): String =
    "$SETTINGS_EXPANDABLE_SECTION_ACTION_TEST_TAG_PREFIX${settingsExpandableSectionTagKey(title)}"

private fun settingsExpandableSectionTagKey(@StringRes title: Int): String {
    return when (title) {
        R.string.pairing_title -> "pairing"
        R.string.status_title -> "status"
        R.string.advanced_connection -> "advanced_connection"
        R.string.embedding_model_title -> "embedding_model"
        R.string.memory_title -> "memory"
        R.string.chat_history_settings_title -> "chat_history"
        else -> "unknown_$title"
    }
}

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
        !state.isLoadingActiveChatMessages &&
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
        state.isLoadingActiveChatMessages -> R.string.chat_hint_loading_chat
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
            error?.diagnosticCode == "route_diagnostic_relay_unreachable_from_device" ||
                error?.code == "remote_route_unreachable_from_device"
        ) -> R.string.route_diagnostic_relay_unreachable_from_device
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
        state.selectedModelId == null -> R.string.empty_chat_no_model_header_hint
        selectedModelIsMissingFromRuntime(state) -> R.string.selected_model_unavailable
        !selectedModelIsUsable(state) -> R.string.chat_hint_install_model
        else -> R.string.empty_chat_no_model
    }
}

internal fun shouldScanLatestQrFromEmptyChat(state: RuntimeUiState): Boolean {
    if (state.isConnected || state.trustedRuntime == null) return false
    if (!hasConnectableTrustedRuntimeRoute(state)) return true
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
    return state.isConnected && state.trustedRuntime != null && !state.isStreaming
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
internal fun memoryLockNoticeTextRes(state: RuntimeUiState, hasEntries: Boolean): Int {
    return if (state.isStreaming) {
        R.string.memory_action_state_wait_for_stream
    } else {
        memoryLockNoticeTextRes(hasEntries = hasEntries)
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

@Composable
private fun runtimeErrorLabel(error: RuntimeUiError): String {
    return when (error.code) {
        "invalid_endpoint" -> stringResource(R.string.error_invalid_endpoint)
        "connection_failed" -> stringResource(R.string.error_connection_failed)
        "no_route" -> stringResource(R.string.error_no_runtime_route)
        "no_connectable_route" -> stringResource(R.string.error_no_connectable_runtime_route)
        "remote_routes_unavailable" -> stringResource(R.string.error_remote_routes_unavailable)
        "remote_route_unreachable_from_device" -> stringResource(R.string.error_remote_route_unreachable_from_device)
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
        "chat_history_loading" -> stringResource(R.string.error_chat_history_loading)
        "chat_history_load_failed" -> stringResource(R.string.error_chat_history_load_failed)
        "chat_session_not_found" -> stringResource(R.string.error_chat_session_not_found)
        "chat_session_must_be_archived_before_delete" -> stringResource(R.string.error_chat_session_must_be_archived_before_delete)
        "chat_session_sync_failed" -> stringResource(R.string.error_chat_session_sync_failed)
        "chat_history_runtime_required" -> stringResource(R.string.error_chat_history_runtime_required)
        "memory_runtime_required" -> stringResource(R.string.error_memory_runtime_required)
        "memory_load_failed" -> stringResource(R.string.error_memory_load_failed)
        "memory_summary_drafts_load_failed" -> stringResource(R.string.error_memory_summary_drafts_load_failed)
        "memory_summary_draft_approval_failed" -> stringResource(R.string.error_memory_summary_draft_approval_failed)
        "memory_summary_draft_dismiss_failed" -> stringResource(R.string.error_memory_summary_draft_dismiss_failed)
        "runtime_error" -> stringResource(R.string.error_runtime_error)
        "send_failed" -> stringResource(R.string.error_send_failed)
        "regenerate_unavailable" -> stringResource(R.string.error_regenerate_unavailable)
        "regenerate_attachment_context_unavailable" -> stringResource(R.string.error_regenerate_attachment_context_unavailable)
        "reuse_message_unavailable" -> stringResource(R.string.error_reuse_message_unavailable)
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
    if (error.code !in USER_VISIBLE_ERROR_DETAIL_CODES) return null
    return error.detail
        ?.trim()
        ?.takeUnless { it.containsBackendEndpointMaterial() }
        ?.takeIf { it.isNotEmpty() }
}

internal fun runtimeTechnicalDiagnosticsReport(
    error: RuntimeUiError,
    codeLabel: String = "code",
    diagnosticCodeLabel: String = "diagnostic_code",
    technicalDetailLabel: String = "technical_detail",
): String? {
    val code = error.code
        .trim()
        .takeIf { it.matches(PROVIDER_DIAGNOSTIC_CODE_PATTERN) }
    val diagnosticCode = error.diagnosticCode
        ?.trim()
        ?.takeIf { it.matches(PROVIDER_DIAGNOSTIC_CODE_PATTERN) }
    val technicalDetail = error.technicalDetail
        ?.redactBackendEndpointMaterial()
        ?.takeIf { it.isNotBlank() }

    val lines = buildList {
        code?.let { add("$codeLabel: $it") }
        diagnosticCode?.let { add("$diagnosticCodeLabel: $it") }
        technicalDetail?.let { add("$technicalDetailLabel: $it") }
    }
    return lines.takeIf { it.isNotEmpty() }?.joinToString(separator = "\n")
}

private val USER_VISIBLE_ERROR_DETAIL_CODES = setOf(
    "attachment_too_large",
    "attachment_read_failed",
)

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

private fun String.redactBackendEndpointMaterial(): String {
    return BACKEND_ENDPOINT_DETAIL_PATTERNS
        .fold(trim()) { redacted, pattern ->
            pattern.replace(redacted) { match ->
                val leading = match.value.takeWhile { it.isWhitespace() || it in "{,;?&" }
                "$leading[redacted]"
            }
        }
        .replace(Regex("\\s+"), " ")
        .trim()
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
        "route_diagnostic_relay_unreachable_from_device" ->
            stringResource(R.string.route_diagnostic_relay_unreachable_from_device)
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
    val providerLabel = runtimeProviderDisplayName(providerStatusDisplayNameSource(provider))
    if (provider.available) {
        return stringResource(R.string.provider_status_ready_detail, providerLabel)
    }
    return when (provider.id.normalizedProviderStatusId()) {
        "ollama" -> stringResource(R.string.provider_ollama_unavailable_hint)
        "lm_studio", "lmstudio" -> stringResource(R.string.provider_lm_studio_unavailable_hint)
        else -> stringResource(R.string.provider_unavailable_hint, providerLabel)
    }
}

private fun providerStatusDisplayNameSource(provider: RuntimeProviderStatus): String {
    val normalizedId = provider.id.normalizedProviderStatusId()
    return if (normalizedId in knownProviderStatusIds) {
        provider.id
    } else {
        provider.name.ifBlank { provider.id }
    }
}

private fun String.normalizedProviderStatusId(): String =
    trim()
        .lowercase(Locale.US)
        .replace('-', '_')
        .replace(' ', '_')

private val knownProviderStatusIds = setOf(
    "ollama",
    "lm_studio",
    "lmstudio",
    "companion_runtime",
    "local_runtime",
    "runtime",
)

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
