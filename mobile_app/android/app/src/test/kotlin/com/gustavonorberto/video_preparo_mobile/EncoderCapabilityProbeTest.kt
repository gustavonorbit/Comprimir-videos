package com.gustavonorberto.video_preparo_mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Teste de contrato sem consultar MediaCodecList. A disponibilidade real de CQ e a lista de
 * encoders dependem do hardware e devem ser coletadas no Galaxy Z Fold 6 pela tela debug.
 */
class EncoderCapabilityProbeTest {

    @Test
    fun `info de encoder cq preserva nome e faixa real`() {
        val info = EncoderCapabilityProbe.CqEncoderInfo(
            encoderName = "codec.teste",
            qualityRangeLower = 1,
            qualityRangeUpper = 100,
        )

        assertEquals("codec.teste", info.encoderName)
        assertEquals(1, info.qualityRangeLower)
        assertEquals(100, info.qualityRangeUpper)
        assertTrue(info.qualityRangeLower <= info.qualityRangeUpper)
    }
}
