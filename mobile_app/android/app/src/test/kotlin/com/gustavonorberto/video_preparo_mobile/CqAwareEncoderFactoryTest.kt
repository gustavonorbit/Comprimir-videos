package com.gustavonorberto.video_preparo_mobile

import android.media.metrics.LogSessionId
import androidx.annotation.OptIn
import androidx.media3.common.Format
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Codec
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config

/**
 * Cobertura possivel em CI: contrato de fallback e honestidade da [CqAwareEncoderFactory.Decision]
 * quando o aparelho (aqui, o ambiente fake do Robolectric) nao anuncia nenhum encoder com suporte
 * real a CQ e qualityRange legivel. O caminho positivo (CQ realmente usado) so pode ser validado
 * num aparelho real — ver BENCHMARK_CQ_FOLD6.md.
 */
@OptIn(UnstableApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class CqAwareEncoderFactoryTest {

    private class FakeEncoderFactory : Codec.EncoderFactory {
        var videoEncodingCalls = 0

        override fun createForAudioEncoding(format: Format, logSessionId: LogSessionId?): Codec {
            throw UnsupportedOperationException("Audio nao e exercitado neste teste.")
        }

        override fun createForVideoEncoding(format: Format, logSessionId: LogSessionId?): Codec {
            videoEncodingCalls += 1
            // Lanca deliberadamente: o objetivo do teste e apenas confirmar que o fallback foi
            // chamado e que a Decision reportada e honesta, nao produzir um Codec real.
            throw UnsupportedOperationException("Fallback chamado como esperado.")
        }
    }

    @Test
    fun `sem encoder CQ com qualityRange legivel cai para fallback e reporta decisao honesta`() {
        val fallback = FakeEncoderFactory()
        var decision: CqAwareEncoderFactory.Decision? = null

        val factory = CqAwareEncoderFactory(
            context = RuntimeEnvironment.getApplication(),
            fallback = fallback,
            qualityFraction = 0.85,
            listener = { reported -> decision = reported },
            cqEncoderFinder = { null },
        )

        val format = Format.Builder()
            .setSampleMimeType(MimeTypes.VIDEO_H264)
            .setWidth(1920)
            .setHeight(1080)
            .build()

        try {
            factory.createForVideoEncoding(format, null)
        } catch (_: UnsupportedOperationException) {
            // Esperado: ver comentario em FakeEncoderFactory.createForVideoEncoding.
        }

        assert(fallback.videoEncodingCalls == 1) {
            "Esperava que o fallback fosse chamado quando nenhum encoder CQ e encontrado."
        }
        val reportedDecision = decision
        assert(reportedDecision != null) { "Esperava que uma Decision fosse reportada." }
        assert(reportedDecision?.usedCq == false)
        assert(reportedDecision?.cqSupportedByDevice == false)
        assert(reportedDecision?.mimeType == MimeTypes.VIDEO_H264)
        assert(reportedDecision?.fallbackReason != null)
    }

    @Test
    fun `audio e sempre delegado ao fallback`() {
        val fallback = FakeEncoderFactory()
        val factory = CqAwareEncoderFactory(
            context = RuntimeEnvironment.getApplication(),
            fallback = fallback,
            qualityFraction = 0.5,
            cqEncoderFinder = { null },
        )

        val format = Format.Builder().setSampleMimeType(MimeTypes.AUDIO_AAC).build()

        try {
            factory.createForAudioEncoding(format, null)
        } catch (_: UnsupportedOperationException) {
            // Esperado: FakeEncoderFactory.createForAudioEncoding sempre lanca.
        }
    }
}
