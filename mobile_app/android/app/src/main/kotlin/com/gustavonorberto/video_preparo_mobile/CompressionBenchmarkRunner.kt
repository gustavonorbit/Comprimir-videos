package com.gustavonorberto.video_preparo_mobile

import android.content.ContentValues
import android.content.Context
import android.media.MediaExtractor
import android.media.MediaFormat
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.util.Log
import androidx.core.content.FileProvider
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Codec
import androidx.media3.transformer.Composition
import androidx.media3.transformer.DefaultEncoderFactory
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.Transformer
import androidx.media3.transformer.VideoEncoderSettings
import java.io.File

/**
 * Ferramenta de benchmark controlado, DEBUG-ONLY (o chamador em [MainActivity] verifica
 * `BuildConfig.DEBUG` antes de instanciar isto). Roda uma unica exportacao por chamada, num de 4
 * modos (VBR atual em producao ou uma das 3 configuracoes internas de CQ), medindo e registrando
 * os mesmos dados tecnicos honestamente para os 4 casos, para permitir comparacao direta no
 * mesmo aparelho com o mesmo video de entrada.
 *
 * Este runner NUNCA e usado no pipeline de producao (ver `MainActivity.startCompression`, que
 * permanece exclusivamente em VBR). Ele existe apenas para reunir evidencia empirica sobre se vale
 * a pena, no futuro, considerar CQ como alternativa — decisao que so pode ser tomada apos os testes
 * fisicos registrados em `BENCHMARK_CQ_FOLD6.md`.
 *
 * Privacidade: os logs com tag [TAG] contem apenas metricas numericas/tecnicas (tamanhos,
 * duracoes, resolucao, fps, bitrate, nomes de encoder, codigos de erro). Nunca incluem a URI, o
 * caminho do arquivo, o nome de exibicao do video ou qualquer conteudo do video.
 */
@UnstableApi
class CompressionBenchmarkRunner(private val context: Context) {

    enum class Mode(val label: String, val qualityFraction: Double?) {
        VBR_ATUAL("vbr_atual", null),
        CQ_CONSERVADOR("cq_conservador", 0.85),
        CQ_AGRESSIVO("cq_agressivo", 0.5),
        CQ_EXTREMO("cq_extremo", 0.15),
    }

    companion object {
        private const val TAG = "CompressionBenchmark"
        private const val BENCHMARK_RELATIVE_PATH = "Preparo de Videos/Benchmark"
    }

    private val mainHandler = Handler(Looper.getMainLooper())
    private var isRunning = false

    fun run(
        inputUri: Uri,
        originalSizeBytes: Long,
        baseVbrBitrate: Int,
        mode: Mode,
        onComplete: (Map<String, Any?>) -> Unit,
    ) {
        if (isRunning) {
            val result = errorResult(mode, "busy", "Ja existe um benchmark em andamento.", originalSizeBytes)
            logResult(result)
            onComplete(result)
            return
        }

        val probe = probeVideoTrack(inputUri)
        if (probe == null) {
            val result = errorResult(mode, "probe_failed", "Nao foi possivel ler as informacoes tecnicas do video de entrada.", originalSizeBytes)
            logResult(result)
            onComplete(result)
            return
        }

        isRunning = true

        // Consultado sempre (mesmo no modo VBR de controle) para que a tabela de comparacao
        // registre, de forma consistente nas 4 linhas, se o aparelho declara suporte a CQ e qual
        // e a faixa real de qualidade dele — nunca assumindo que um numero fixo e portavel entre
        // aparelhos.
        val cqProbe = EncoderCapabilityProbe.findCqEncoder(MimeTypes.VIDEO_H264)

        val bitrate = baseVbrBitrate.coerceIn(500_000, 8_000_000)
        val fallbackEncoderFactory = DefaultEncoderFactory.Builder(context)
            .setRequestedVideoEncoderSettings(VideoEncoderSettings.Builder().setBitrate(bitrate).build())
            .build()

        var decision: CqAwareEncoderFactory.Decision? = null
        val encoderFactory: Codec.EncoderFactory = if (mode == Mode.VBR_ATUAL) {
            fallbackEncoderFactory
        } else {
            CqAwareEncoderFactory(
                context = context,
                fallback = fallbackEncoderFactory,
                qualityFraction = mode.qualityFraction ?: 0.5,
                listener = { d -> decision = d },
            )
        }

        val tempFile = File(context.cacheDir, "benchmark_${mode.label}_${System.nanoTime()}.mp4")
        val startNanos = System.nanoTime()

        val transformer = Transformer.Builder(context)
            .setVideoMimeType(MimeTypes.VIDEO_H264)
            .setAudioMimeType(MimeTypes.AUDIO_AAC)
            .setEncoderFactory(encoderFactory)
            .addListener(object : Transformer.Listener {
                override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                    val elapsedMs = (System.nanoTime() - startNanos) / 1_000_000
                    Thread {
                        try {
                            val saved = saveBenchmarkFile(tempFile)
                            val result = buildSuccessResult(
                                mode = mode,
                                probe = probe,
                                cqProbe = cqProbe,
                                decision = decision,
                                originalSizeBytes = originalSizeBytes,
                                saved = saved,
                                elapsedMs = elapsedMs,
                            )
                            mainHandler.post {
                                isRunning = false
                                logResult(result)
                                onComplete(result)
                            }
                        } catch (error: Exception) {
                            tempFile.delete()
                            mainHandler.post {
                                isRunning = false
                                val result = errorResult(mode, "storage_failed", error.message ?: "Falha ao salvar o arquivo de benchmark.", originalSizeBytes)
                                logResult(result)
                                onComplete(result)
                            }
                        }
                    }.start()
                }

                override fun onError(
                    composition: Composition,
                    exportResult: ExportResult,
                    exportException: ExportException,
                ) {
                    tempFile.delete()
                    isRunning = false
                    val result = errorResult(mode, "compression_failed", exportException.message ?: "Falha na exportacao.", originalSizeBytes)
                    logResult(result)
                    onComplete(result)
                }
            })
            .build()

        try {
            val mediaItem = MediaItem.fromUri(inputUri)
            val editedMediaItem = EditedMediaItem.Builder(mediaItem).build()
            transformer.start(editedMediaItem, tempFile.absolutePath)
        } catch (error: Exception) {
            isRunning = false
            tempFile.delete()
            val result = errorResult(mode, "compression_failed", error.message ?: "Nao foi possivel iniciar o benchmark.", originalSizeBytes)
            logResult(result)
            onComplete(result)
        }
    }

    private data class VideoProbe(
        val widthPx: Int,
        val heightPx: Int,
        val durationMs: Long,
        val frameRate: Double?,
    )

    private fun probeVideoTrack(uri: Uri): VideoProbe? {
        if (uri.scheme == "file" && uri.path?.let { File(it).canRead() } != true) {
            return null
        }

        val extractor = MediaExtractor()
        return try {
            extractor.setDataSource(context, uri, null)
            for (i in 0 until extractor.trackCount) {
                val format = extractor.getTrackFormat(i)
                val mime = format.getString(MediaFormat.KEY_MIME) ?: continue
                if (!mime.startsWith("video/")) {
                    continue
                }

                val width = if (format.containsKey(MediaFormat.KEY_WIDTH)) format.getInteger(MediaFormat.KEY_WIDTH) else 0
                val height = if (format.containsKey(MediaFormat.KEY_HEIGHT)) format.getInteger(MediaFormat.KEY_HEIGHT) else 0
                val durationUs = if (format.containsKey(MediaFormat.KEY_DURATION)) format.getLong(MediaFormat.KEY_DURATION) else 0L
                val frameRate = if (format.containsKey(MediaFormat.KEY_FRAME_RATE)) {
                    try {
                        format.getInteger(MediaFormat.KEY_FRAME_RATE).toDouble()
                    } catch (_: Exception) {
                        try {
                            format.getFloat(MediaFormat.KEY_FRAME_RATE).toDouble()
                        } catch (_: Exception) {
                            null
                        }
                    }
                } else {
                    null
                }

                return VideoProbe(width, height, durationUs / 1000, frameRate)
            }
            null
        } catch (_: Exception) {
            null
        } finally {
            extractor.release()
        }
    }

    private data class SavedBenchmarkOutput(
        val outputName: String,
        val outputUri: String,
        val outputSizeBytes: Long,
    )

    private fun saveBenchmarkFile(tempFile: File): SavedBenchmarkOutput {
        // O nome ja e unico (label do modo + nanoTime), entao nunca sobrescreve uma execucao
        // anterior nem o pipeline de producao, que grava em "Preparo de Videos" (sem subpasta).
        val finalName = tempFile.name

        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.Video.Media.DISPLAY_NAME, finalName)
                put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                put(MediaStore.Video.Media.RELATIVE_PATH, "${Environment.DIRECTORY_MOVIES}/$BENCHMARK_RELATIVE_PATH")
                put(MediaStore.Video.Media.IS_PENDING, 1)
            }
            val uri = context.contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException("Could not create MediaStore item for benchmark output.")

            context.contentResolver.openOutputStream(uri)?.use { output ->
                tempFile.inputStream().use { input -> input.copyTo(output) }
            } ?: throw IllegalStateException("Could not open MediaStore output stream for benchmark output.")

            context.contentResolver.update(
                uri,
                ContentValues().apply { put(MediaStore.Video.Media.IS_PENDING, 0) },
                null,
                null,
            )

            val outputSize = tempFile.length()
            tempFile.delete()
            return SavedBenchmarkOutput(finalName, uri.toString(), outputSize)
        }

        val benchmarkDir = File(context.getExternalFilesDir(Environment.DIRECTORY_MOVIES), "Benchmark").apply { mkdirs() }
        val outputFile = File(benchmarkDir, finalName)
        tempFile.copyTo(outputFile, overwrite = false)
        val outputSize = outputFile.length()
        tempFile.delete()

        val authority = "${context.packageName}.fileprovider"
        val uri = FileProvider.getUriForFile(context, authority, outputFile)
        return SavedBenchmarkOutput(finalName, uri.toString(), outputSize)
    }

    private fun buildSuccessResult(
        mode: Mode,
        probe: VideoProbe,
        cqProbe: EncoderCapabilityProbe.CqEncoderInfo?,
        decision: CqAwareEncoderFactory.Decision?,
        originalSizeBytes: Long,
        saved: SavedBenchmarkOutput,
        elapsedMs: Long,
    ): Map<String, Any?> {
        val usedCq = decision?.usedCq == true
        val fallbackExecuted = mode != Mode.VBR_ATUAL && !usedCq
        val modoUtilizado = if (usedCq) "cq" else "vbr"
        val reduction = if (originalSizeBytes > 0) {
            ((originalSizeBytes - saved.outputSizeBytes).toDouble() / originalSizeBytes.toDouble()) * 100.0
        } else {
            null
        }
        val bitrateFinalBps = if (probe.durationMs > 0) {
            (saved.outputSizeBytes * 8L * 1000L) / probe.durationMs
        } else {
            null
        }

        val notes = mutableListOf<String>()
        if (mode == Mode.VBR_ATUAL) {
            notes.add("Nome do encoder de video nao exposto publicamente pelo DefaultEncoderFactory do Media3 em modo VBR.")
        }
        notes.add("Qualidade efetiva (apos a codificacao) nao e legivel via API publica do Android; reportamos apenas a qualidade solicitada.")
        if (fallbackExecuted) {
            notes.add("CQ foi solicitado mas o pipeline caiu para VBR: ${decision?.fallbackReason ?: "motivo nao identificado"}.")
        }

        return mapOf(
            "modoSolicitado" to mode.label,
            "modoUtilizado" to modoUtilizado,
            "nomeEncoder" to (decision?.encoderName),
            "mimeSaida" to MimeTypes.VIDEO_H264,
            "suporteDeclaradoCq" to (cqProbe != null),
            "qualityRangeMin" to cqProbe?.qualityRangeLower,
            "qualityRangeMax" to cqProbe?.qualityRangeUpper,
            "qualidadeSolicitada" to decision?.requestedQuality,
            "qualidadeEfetiva" to null,
            "fallbackExecutado" to fallbackExecuted,
            "tamanhoOriginalBytes" to originalSizeBytes,
            "tamanhoFinalBytes" to saved.outputSizeBytes,
            "percentualReducao" to reduction,
            "duracaoVideoMs" to probe.durationMs,
            "tempoProcessamentoMs" to elapsedMs,
            "resolucao" to "${probe.widthPx}x${probe.heightPx}",
            "fps" to probe.frameRate,
            "bitrateMedioFinalBps" to bitrateFinalBps,
            "sucesso" to true,
            "mensagemErro" to null,
            "notaTecnica" to notes.joinToString(" "),
            "outputName" to saved.outputName,
            "outputUri" to saved.outputUri,
        )
    }

    private fun errorResult(mode: Mode, code: String, message: String, originalSizeBytes: Long): Map<String, Any?> {
        return mapOf(
            "modoSolicitado" to mode.label,
            "modoUtilizado" to null,
            "nomeEncoder" to null,
            "mimeSaida" to MimeTypes.VIDEO_H264,
            "suporteDeclaradoCq" to null,
            "qualityRangeMin" to null,
            "qualityRangeMax" to null,
            "qualidadeSolicitada" to null,
            "qualidadeEfetiva" to null,
            "fallbackExecutado" to null,
            "tamanhoOriginalBytes" to originalSizeBytes,
            "tamanhoFinalBytes" to null,
            "percentualReducao" to null,
            "duracaoVideoMs" to null,
            "tempoProcessamentoMs" to null,
            "resolucao" to null,
            "fps" to null,
            "bitrateMedioFinalBps" to null,
            "sucesso" to false,
            "mensagemErro" to "$code: $message",
            "notaTecnica" to null,
            "outputName" to null,
            "outputUri" to null,
        )
    }

    /**
     * Registra uma unica linha estruturada por execucao, com a tag [TAG]. Exclui
     * deliberadamente `outputUri` e `outputName` (podem revelar caminho/local de armazenamento)
     * e qualquer outro campo que nao seja puramente tecnico/numerico — nunca dados pessoais ou
     * conteudo do video.
     */
    private fun logResult(result: Map<String, Any?>) {
        val safeFields = result.filterKeys { it != "outputUri" && it != "outputName" }
        val line = safeFields.entries.joinToString(separator = "; ") { "${it.key}=${it.value}" }
        Log.i(TAG, line)
    }
}
