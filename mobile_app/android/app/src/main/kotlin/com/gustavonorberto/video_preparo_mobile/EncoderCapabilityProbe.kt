package com.gustavonorberto.video_preparo_mobile

import android.media.MediaCodecInfo
import android.media.MediaCodecList
import android.os.Build

/**
 * Consulta os encoders reais do aparelho (via [MediaCodecList], sem qualquer camada do Media3)
 * para descobrir se algum deles suporta modo de qualidade constante (CQ) e, quando suporta, qual
 * e a faixa real de valores de qualidade aceita por aquele encoder especifico.
 *
 * Isso existe porque o Media3 Transformer bloqueia CQ na propria API publica: o
 * `VideoEncoderSettings.Builder.setBitrateMode()` so aceita `BITRATE_MODE_VBR` ou
 * `BITRATE_MODE_CBR` (confirmado no codigo-fonte de `androidx.media3.transformer`). Para saber se
 * vale a pena contornar essa limitacao com um `Codec.EncoderFactory` proprio, primeiro precisamos
 * confirmar se o hardware do aparelho realmente anuncia suporte a CQ — nao e garantido, e varia
 * muito por fabricante/SoC. E, quando anuncia, o significado de um valor como "70" NAO e portavel
 * entre aparelhos: cada encoder declara sua propria `qualityRange` (API 28+), entao qualquer numero
 * usado como alvo de qualidade precisa ser calculado dentro dessa faixa real, nunca assumido fixo.
 */
object EncoderCapabilityProbe {

    /**
     * Encoder de hardware/software que anuncia suporte real a modo de qualidade constante (CQ),
     * junto com a faixa de valores de qualidade que ELE especificamente aceita
     * (`MediaCodecInfo.EncoderCapabilities.getQualityRange()`, disponivel desde a API 28).
     */
    data class CqEncoderInfo(
        val encoderName: String,
        val qualityRangeLower: Int,
        val qualityRangeUpper: Int,
    )

    /**
     * Retorna o primeiro encoder encontrado para [mimeType] que anuncia suporte ao modo de
     * qualidade constante e do qual conseguimos ler uma `qualityRange` valida, ou nulo se nenhum
     * encoder disponivel no aparelho atender aos dois requisitos (ou se a API para consultar a
     * faixa nao existir nesta versao do Android).
     */
    fun findCqEncoder(mimeType: String): CqEncoderInfo? {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.P) {
            // getQualityRange() so existe a partir da API 28 (Android P). Sem ela, nao ha como
            // saber o significado do valor de qualidade naquele aparelho, entao nao arriscamos.
            return null
        }

        val codecList = MediaCodecList(MediaCodecList.REGULAR_CODECS)

        for (codecInfo in codecList.codecInfos) {
            if (!codecInfo.isEncoder) {
                continue
            }
            if (!codecInfo.supportedTypes.any { it.equals(mimeType, ignoreCase = true) }) {
                continue
            }

            val encoderCapabilities = try {
                codecInfo.getCapabilitiesForType(mimeType).encoderCapabilities
            } catch (_: IllegalArgumentException) {
                null
            } ?: continue

            if (!encoderCapabilities.isBitrateModeSupported(MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CQ)) {
                continue
            }

            val qualityRange = try {
                encoderCapabilities.qualityRange
            } catch (_: Exception) {
                null
            } ?: continue

            if (qualityRange.lower == null || qualityRange.upper == null) {
                continue
            }

            return CqEncoderInfo(
                encoderName = codecInfo.name,
                qualityRangeLower = qualityRange.lower,
                qualityRangeUpper = qualityRange.upper,
            )
        }

        return null
    }

    /**
     * Relatorio de diagnostico com todos os encoders encontrados para [mimeType] e quais modos de
     * bitrate cada um anuncia suportar. Usado apenas para log durante o teste manual no aparelho
     * real — nao e consumido pela UI.
     */
    fun describeEncoders(mimeType: String): String {
        val codecList = MediaCodecList(MediaCodecList.REGULAR_CODECS)
        val lines = mutableListOf<String>()

        for (codecInfo in codecList.codecInfos) {
            if (!codecInfo.isEncoder) {
                continue
            }
            if (!codecInfo.supportedTypes.any { it.equals(mimeType, ignoreCase = true) }) {
                continue
            }

            val encoderCapabilities = try {
                codecInfo.getCapabilitiesForType(mimeType).encoderCapabilities
            } catch (_: IllegalArgumentException) {
                null
            }

            if (encoderCapabilities == null) {
                lines.add("${codecInfo.name}: capacidades indisponiveis")
                continue
            }

            val modes = mutableListOf<String>()
            if (encoderCapabilities.isBitrateModeSupported(MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CQ)) {
                modes.add("CQ")
            }
            if (encoderCapabilities.isBitrateModeSupported(MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_VBR)) {
                modes.add("VBR")
            }
            if (encoderCapabilities.isBitrateModeSupported(MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CBR)) {
                modes.add("CBR")
            }

            lines.add("${codecInfo.name}: ${if (modes.isEmpty()) "nenhum modo anunciado" else modes.joinToString(", ")}")
        }

        return if (lines.isEmpty()) "Nenhum encoder encontrado para $mimeType" else lines.joinToString("\n")
    }
}
