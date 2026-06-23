package com.localagentbridge.android.feature.connection

import com.localagentbridge.android.core.transport.DiscoveredMac

data class ConnectionUiState(
    val isDiscovering: Boolean = false,
    val discoveredMacs: List<DiscoveredMac> = emptyList(),
    val selectedMac: DiscoveredMac? = null,
    val pairingCode: String = "",
    val statusCode: String = "not_connected",
    val statusDetail: String? = null,
    val errorCode: String? = null,
)
