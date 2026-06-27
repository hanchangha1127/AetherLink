package com.localagentbridge.android.runtime

import android.content.Context
import androidx.test.core.app.ApplicationProvider
import com.localagentbridge.android.R
import org.junit.Assert.assertEquals
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Config
import androidx.test.ext.junit.runners.AndroidJUnit4

@RunWith(AndroidJUnit4::class)
@Config(sdk = [35])
class RuntimeAttachmentPromptResourceTest {
    @Test
    fun attachmentOnlyPromptHeaderUsesLocalizedAndroidResources() {
        val context = ApplicationProvider.getApplicationContext<Context>()

        assertEquals(
            "Analyze attached input:",
            context.getString(R.string.attachment_only_prompt_header),
        )
        assertEquals(
            "Analyze attached input:",
            attachmentOnlyPromptHeader(context, RuntimeAppLanguage.English.languageTag),
        )
        assertEquals(
            "첨부한 입력을 분석하세요:",
            attachmentOnlyPromptHeader(context, RuntimeAppLanguage.Korean.languageTag),
        )
        assertEquals(
            "添付された入力を分析してください:",
            attachmentOnlyPromptHeader(context, RuntimeAppLanguage.Japanese.languageTag),
        )
        assertEquals(
            "请分析附加输入：",
            attachmentOnlyPromptHeader(context, RuntimeAppLanguage.SimplifiedChinese.languageTag),
        )
        assertEquals(
            "Analysez les éléments joints :",
            attachmentOnlyPromptHeader(context, RuntimeAppLanguage.French.languageTag),
        )
        assertEquals(
            "Analyze attached input:",
            attachmentOnlyPromptHeader(context, ""),
        )
    }
}
