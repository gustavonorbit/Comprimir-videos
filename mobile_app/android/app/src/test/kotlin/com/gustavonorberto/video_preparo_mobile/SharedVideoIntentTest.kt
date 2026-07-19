package com.gustavonorberto.video_preparo_mobile

import android.content.Intent
import android.net.Uri
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class SharedVideoIntentTest {

    @Test
    fun `extrai uri de intent de compartilhamento de video valida`() {
        val videoUri = Uri.parse("content://media/external/video/media/9")
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "video/mp4"
            putExtra(Intent.EXTRA_STREAM, videoUri)
        }

        assertEquals(videoUri, SharedVideoIntent.extractVideoUri(intent))
    }

    @Test
    fun `ignora intent que nao e ACTION_SEND`() {
        val intent = Intent(Intent.ACTION_VIEW).apply {
            type = "video/mp4"
            putExtra(Intent.EXTRA_STREAM, Uri.parse("content://media/external/video/media/9"))
        }

        assertNull(SharedVideoIntent.extractVideoUri(intent))
    }

    @Test
    fun `ignora intent sem tipo de video`() {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "image/png"
            putExtra(Intent.EXTRA_STREAM, Uri.parse("content://media/external/images/media/9"))
        }

        assertNull(SharedVideoIntent.extractVideoUri(intent))
    }

    @Test
    fun `ignora intent de video sem stream anexado`() {
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "video/mp4"
        }

        assertNull(SharedVideoIntent.extractVideoUri(intent))
    }

    @Test
    fun `ignora intent nula`() {
        assertNull(SharedVideoIntent.extractVideoUri(null))
    }

    @Test
    fun `intent marcada como consumida nao e reprocessada`() {
        val videoUri = Uri.parse("content://media/external/video/media/9")
        val intent = Intent(Intent.ACTION_SEND).apply {
            type = "video/mp4"
            putExtra(Intent.EXTRA_STREAM, videoUri)
        }

        assertEquals(videoUri, SharedVideoIntent.extractVideoUri(intent))

        SharedVideoIntent.markConsumed(intent)

        // Simula a Activity sendo recriada (rotacao, dobra do aparelho) com a mesma
        // Intent, sem que uma nova Intent seja entregue via onNewIntent.
        assertNull(SharedVideoIntent.extractVideoUri(intent))
    }
}
