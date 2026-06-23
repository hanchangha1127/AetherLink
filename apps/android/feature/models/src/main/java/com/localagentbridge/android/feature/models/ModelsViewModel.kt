package com.localagentbridge.android.feature.models

import androidx.lifecycle.ViewModel
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.flow.update

class ModelsViewModel : ViewModel() {
    private val mutableState = MutableStateFlow(ModelsUiState())
    val state: StateFlow<ModelsUiState> = mutableState.asStateFlow()

    fun loadStubModels() {
        mutableState.update {
            val models = listOf(
                ModelRow(id = "llama3.1:8b", name = "llama3.1:8b"),
                ModelRow(id = "qwen2.5:7b", name = "qwen2.5:7b"),
            )
            it.copy(models = models, selectedModelId = it.selectedModelId ?: models.first().id, error = null)
        }
    }

    fun selectModel(id: String) {
        mutableState.update { it.copy(selectedModelId = id) }
    }
}

