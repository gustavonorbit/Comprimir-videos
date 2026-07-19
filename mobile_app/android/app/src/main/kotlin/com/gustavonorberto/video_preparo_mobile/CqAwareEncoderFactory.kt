package com.gustavonorberto.video_preparo_mobile

import android.content.Context
import android.media.MediaCodecInfo
import android.media.MediaFormat
import android.media.metrics.LogSessionId
import android.util.Log
import androidx.media3.common.Format
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Codec
import androidx.media3.transformer.DefaultCodec
import androidx.media3.transformer.ExportException
import kotlin.math.roundToInt

/**
 * `Codec.EncoderFactory` experimental para testar modo de qualidade constante (CQ) no encoder de
 * video, contornando o bloqueio do `DefaultEncoderFactory`/`VideoEncoderSettings` do Media3 (que
 * so aceita VBR ou CBR).
 *
 * Estrategia:
 * - Audio: delegado inteiramente para [fallback] (nenhuma mudanca de comportamento).
 * - Video: se [EncoderCapabilityProbe] encontrar um encoder no aparelho que anuncia suporte real a
 *   CQ e do qual conseguimos ler a `qualityRange` real, calcula o valor de qualidade DENTRO dessa
 *   faixa (nunca um numero fixo — o mesmo "70" nao significa o mesmo em aparelhos diferentes),
 *   monta o `MediaFormat` manualmente com `KEY_BITRATE_MODE = BITRATE_MODE_CQ` e `KEY_QUALITY`, e
 *   usa `DefaultCodec` do proprio Media3 para toda a maquina de buffers (fila de entrada/saida,
 *   superficie, etc.) — so a configuracao do formato e diferente. Se o aparelho nao anunciar
 *   suporte, ou a configuracao falhar, delega para [fallback] (VBR).
 * - [listener], se fornecido, recebe um [Decision] por chamada de encoding de video, com os dados
 *   necessarios para o chamador registrar honestamente qual caminho foi realmente seguido (nunca
 *   declarar CQ se o pipeline caiu para VBR).
 *
 * Isto e codigo experimental/pesquisa: nao suportado oficialmente pelo Media3, e o comportamento
 * de CQ pode variar entre fabricantes mesmo quando anunciado. Uso restrito a ferramenta de
 * benchmark (debug-only) ate que uma validacao no aparelho real justifique substituir o pipeline
 * de producao, que permanece em VBR.
 */
@UnstableApi
class CqAwareEncoderFactory(
    private val context: Context,
    private val fallback: Codec.EncoderFactory,
    private val qualityFraction: Double,
    private val listener: Listener? = null,
    private val cqEncoderFinder: (String) -> EncoderCapabilityProbe.CqEncoderInfo? =
        EncoderCapabilityProbe::findCqEncoder,
) : Codec.EncoderFactory {

    /**
     * Resultado da decisao tomada para um encoding de video especifico: se o aparelho anuncia CQ
     * com qualityRange legivel, qual encoder/faixa/valor foram usados, se realmente usou CQ ou
     * caiu para VBR, e por que (quando aplicavel).
     */
    data class Decision(
        val mimeType: String,
        val cqSupportedByDevice: Boolean,
        val encoderName: String?,
        val qualityRangeLower: Int?,
        val qualityRangeUpper: Int?,
        val requestedQuality: Int?,
        val usedCq: Boolean,
        val fallbackReason: String?,
    )

    fun interface Listener {
        fun onDecision(decision: Decision)
    }

    companion object {
        private const val TAG = "CqAwareEncoderFactory"
    }

    override fun createForAudioEncoding(
        format: Format,
        logSessionId: LogSessionId?,
    ): Codec = fallback.createForAudioEncoding(format, logSessionId)

    override fun createForVideoEncoding(format: Format, logSessionId: LogSessionId?): Codec {
        val mimeType = format.sampleMimeType
        val cqEncoder = mimeType?.let { cqEncoderFinder(it) }

        if (mimeType == null || cqEncoder == null) {
            val reason = "Nenhum encoder do aparelho anuncia suporte real a CQ com qualityRange legivel para ${format.sampleMimeType}."
            Log.i(TAG, "$reason Usando bitrate VBR atual.")
            listener?.onDecision(
                Decision(
                    mimeType = mimeType ?: "desconhecido",
                    cqSupportedByDevice = false,
                    encoderName = null,
                    qualityRangeLower = null,
                    qualityRangeUpper = null,
                    requestedQuality = null,
                    usedCq = false,
                    fallbackReason = reason,
                )
            )
            return fallback.createForVideoEncoding(format, logSessionId)
        }

        val requestedQuality = qualityWithinRange(cqEncoder, qualityFraction)
        Log.i(TAG, "Usando modo de qualidade constante (CQ=$requestedQuality, faixa ${cqEncoder.qualityRangeLower}-${cqEncoder.qualityRangeUpper}) no encoder '${cqEncoder.encoderName}' para $mimeType.")

        val frameRate = if (format.frameRate != Format.NO_VALUE.toFloat()) {
            format.frameRate.roundToInt()
        } else {
            30
        }

        val mediaFormat = MediaFormat.createVideoFormat(mimeType, format.width, format.height).apply {
            setInteger(MediaFormat.KEY_COLOR_FORMAT, MediaCodecInfo.CodecCapabilities.COLOR_FormatSurface)
            setInteger(MediaFormat.KEY_FRAME_RATE, frameRate)
            setFloat(MediaFormat.KEY_I_FRAME_INTERVAL, 1.0f)
            setInteger(MediaFormat.KEY_BITRATE_MODE, MediaCodecInfo.EncoderCapabilities.BITRATE_MODE_CQ)
            setInteger(MediaFormat.KEY_QUALITY, requestedQuality)
        }

        return try {
            val codec = DefaultCodec(
                context,
                format,
                mediaFormat,
                cqEncoder.encoderName,
                /* isDecoder= */ false,
                /* outputSurface= */ null,
            )
            listener?.onDecision(
                Decision(
                    mimeType = mimeType,
                    cqSupportedByDevice = true,
                    encoderName = cqEncoder.encoderName,
                    qualityRangeLower = cqEncoder.qualityRangeLower,
                    qualityRangeUpper = cqEncoder.qualityRangeUpper,
                    requestedQuality = requestedQuality,
                    usedCq = true,
                    fallbackReason = null,
                )
            )
            codec
        } catch (error: ExportException) {
            // Alguns aparelhos anunciam suporte a CQ mas falham ao configurar de fato. Cai para o
            // caminho atual (VBR) em vez de derrubar a compressao inteira — e registra o motivo
            // real, nunca declarando CQ quando o resultado final foi VBR.
            val reason = "Falha ao configurar o encoder '${cqEncoder.encoderName}' em modo CQ: ${error.message}"
            Log.w(TAG, "$reason Caindo para bitrate VBR atual.", error)
            listener?.onDecision(
                Decision(
                    mimeType = mimeType,
                    cqSupportedByDevice = true,
                    encoderName = cqEncoder.encoderName,
                    qualityRangeLower = cqEncoder.qualityRangeLower,
                    qualityRangeUpper = cqEncoder.qualityRangeUpper,
                    requestedQuality = requestedQuality,
                    usedCq = false,
                    fallbackReason = reason,
                )
            )
            fallback.createForVideoEncoding(format, logSessionId)
        }
    }

    override fun audioNeedsEncoding(): Boolean = fallback.audioNeedsEncoding()

    override fun videoNeedsEncoding(): Boolean = fallback.videoNeedsEncoding()

    /**
     * Calcula um valor de qualidade dentro da `qualityRange` REAL de [encoder] a partir de uma
     * fracao 0.0 (extremo inferior da faixa, mais compressao) a 1.0 (extremo superior, mais
     * qualidade). Nunca assume que um numero absoluto como 70 tem o mesmo significado em
     * aparelhos diferentes.
     */
    private fun qualityWithinRange(encoder: EncoderCapabilityProbe.CqEncoderInfo, fraction: Double): Int {
        val clampedFraction = fraction.coerceIn(0.0, 1.0)
        val span = encoder.qualityRangeUpper - encoder.qualityRangeLower
        val value = encoder.qualityRangeLower + (span * clampedFraction).roundToInt()
        return value.coerceIn(encoder.qualityRangeLower, encoder.qualityRangeUpper)
    }
}
