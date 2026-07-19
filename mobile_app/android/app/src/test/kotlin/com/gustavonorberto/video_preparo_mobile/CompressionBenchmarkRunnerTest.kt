package com.gustavonorberto.video_preparo_mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Teste de contrato puro da ferramenta de benchmark. O caminho completo do runner usa
 * MediaExtractor/Transformer/MediaCodec e deve ser validado no aparelho real, porque o ambiente de
 * unit test JVM/Robolectric nao representa os encoders do Galaxy Z Fold 6 e pode travar em APIs
 * nativas de midia.
 */
class CompressionBenchmarkRunnerTest {

    @Test
    fun `modos do benchmark mantem labels esperados para o MethodChannel`() {
        assertEquals("vbr_atual", CompressionBenchmarkRunner.Mode.VBR_ATUAL.label)
        assertEquals("cq_conservador", CompressionBenchmarkRunner.Mode.CQ_CONSERVADOR.label)
        assertEquals("cq_agressivo", CompressionBenchmarkRunner.Mode.CQ_AGRESSIVO.label)
        assertEquals("cq_extremo", CompressionBenchmarkRunner.Mode.CQ_EXTREMO.label)
    }

    @Test
    fun `modo vbr de controle nao possui fracao cq`() {
        assertNull(CompressionBenchmarkRunner.Mode.VBR_ATUAL.qualityFraction)
    }

    @Test
    fun `modos cq usam fracoes ordenadas dentro da faixa normalizada`() {
        val conservador = CompressionBenchmarkRunner.Mode.CQ_CONSERVADOR.qualityFraction
        val agressivo = CompressionBenchmarkRunner.Mode.CQ_AGRESSIVO.qualityFraction
        val extremo = CompressionBenchmarkRunner.Mode.CQ_EXTREMO.qualityFraction

        assertTrue(conservador != null && conservador in 0.0..1.0)
        assertTrue(agressivo != null && agressivo in 0.0..1.0)
        assertTrue(extremo != null && extremo in 0.0..1.0)
        assertTrue(conservador!! > agressivo!!)
        assertTrue(agressivo > extremo!!)
    }
}
