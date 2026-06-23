package com.localagentbridge.android.feature.models

data class ModelRow(
    val id: String,
    val name: String,
    val sizeBytes: Long? = null,
)

data class ModelsUiState(
    val models: List<ModelRow> = emptyList(),
    val selectedModelId: String? = null,
    val isLoading: Boolean = false,
    val error: String? = null,
)

