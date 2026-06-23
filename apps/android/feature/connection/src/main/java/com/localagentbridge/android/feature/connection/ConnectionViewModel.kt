package com.localagentbridge.android.feature.connection

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.localagentbridge.android.core.transport.DiscoveredMac
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update
import kotlinx.coroutines.launch

class ConnectionViewModel : ViewModel() {
    private val mutableState = MutableStateFlow(ConnectionUiState())
    val state: StateFlow<ConnectionUiState> = mutableState.asStateFlow()

    fun startStubDiscovery() {
        viewModelScope.launch {
            mutableState.update {
	                it.copy(
	                    isDiscovering = false,
	                    discoveredMacs = listOf(DiscoveredMac("AetherLink Mac", "discovered.local", 43170)),
	                    statusCode = "discovery_ready",
	                    statusDetail = null,
	                    errorCode = null,
	                )
	            }
        }
    }

	    fun selectMac(mac: DiscoveredMac) {
	        mutableState.update {
	            it.copy(
	                selectedMac = mac,
	                statusCode = "selected",
	                statusDetail = mac.serviceName,
	                errorCode = null,
	            )
	        }
	    }

    fun updatePairingCode(code: String) {
        mutableState.update { it.copy(pairingCode = code.filter(Char::isDigit).take(6)) }
    }

    fun pairSelectedMac() {
        val selected = state.value.selectedMac
        val code = state.value.pairingCode
        mutableState.update {
	            when {
	                selected == null -> it.copy(errorCode = "select_mac_first")
	                code.length != 6 -> it.copy(errorCode = "invalid_pairing_code")
	                else -> it.copy(
	                    statusCode = "paired",
	                    statusDetail = selected.serviceName,
	                    errorCode = null,
	                )
	            }
	        }
    }
}
