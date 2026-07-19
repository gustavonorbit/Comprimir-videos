package com.gustavonorberto.video_preparo_mobile

import android.database.Cursor
import android.content.ContentValues
import android.content.Intent
import android.media.MediaMetadataRetriever
import android.net.Uri
import android.os.Build
import android.os.Environment
import android.os.Handler
import android.os.Looper
import android.provider.MediaStore
import android.provider.OpenableColumns
import android.webkit.MimeTypeMap
import androidx.annotation.OptIn
import androidx.core.content.FileProvider
import androidx.media3.common.MediaItem
import androidx.media3.common.MimeTypes
import androidx.media3.common.util.UnstableApi
import androidx.media3.transformer.Composition
import androidx.media3.transformer.DefaultEncoderFactory
import androidx.media3.transformer.EditedMediaItem
import androidx.media3.transformer.ExportException
import androidx.media3.transformer.ExportResult
import androidx.media3.transformer.ProgressHolder
import androidx.media3.transformer.Transformer
import androidx.media3.transformer.VideoEncoderSettings
import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.EventChannel
import io.flutter.plugin.common.MethodChannel
import java.io.File

@OptIn(UnstableApi::class)
class MainActivity : FlutterActivity() {
    private val infoChannelName = "video_preparo_mobile/video_info"
    private val processingChannelName = "video_preparo_mobile/video_processing"
    private val progressChannelName = "video_preparo_mobile/video_processing_progress"
    private val sharedIntentChannelName = "video_preparo_mobile/shared_intent"
    private val sharedIntentStreamChannelName = "video_preparo_mobile/shared_intent_stream"
    // Canal experimental, debug-only: existe apenas para a ferramenta interna de benchmark CQ
    // (ver CompressionBenchmarkRunner). O handler abaixo recusa qualquer chamada quando
    // BuildConfig.DEBUG for false, entao isto nunca executa em build release, mesmo que o canal
    // permaneca declarado no binario.
    private val benchmarkChannelName = "video_preparo_mobile/compression_benchmark"
    private val benchmarkRunner: CompressionBenchmarkRunner by lazy { CompressionBenchmarkRunner(applicationContext) }
    private val mainHandler = Handler(Looper.getMainLooper())
    private var progressSink: EventChannel.EventSink? = null
    private var sharedVideoSink: EventChannel.EventSink? = null
    private var pendingSharedVideo: Map<String, Any?>? = null
    private var activeTransformer: Transformer? = null
    private var activeResult: MethodChannel.Result? = null
    private var activeTempFile: File? = null
    private var activeOriginalSizeBytes: Long = 0L
    private var isCancelling = false

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, infoChannelName).setMethodCallHandler { call, result ->
            when (call.method) {
                "getVideoInfo" -> {
                    val uriText = call.argument<String>("uri")
                    val path = call.argument<String>("path")
                    val displayName = call.argument<String>("displayName")

                    try {
                        result.success(readVideoInfo(uriText, path, displayName))
                    } catch (error: SecurityException) {
                        result.error("permission_denied", error.message, null)
                    } catch (error: IllegalArgumentException) {
                        result.error("unsupported", error.message, null)
                    } catch (error: Exception) {
                        result.error("metadata_failed", error.message, null)
                    }
                }
                else -> result.notImplemented()
            }
        }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, processingChannelName).setMethodCallHandler { call, result ->
            when (call.method) {
                "compressVideo" -> {
                    val uriText = call.argument<String>("uri")
                    val path = call.argument<String>("path")
                    val displayName = call.argument<String>("displayName") ?: "video.mp4"
                    val outputName = call.argument<String>("outputName") ?: buildOutputName(displayName)
                    val originalSizeBytes = call.argument<Number>("originalSizeBytes")?.toLong() ?: 0L
                    val strategyName = call.argument<String>("strategyName")
                    val videoBitrate = call.argument<Number>("videoBitrate")?.toInt() ?: 2_500_000
                    val resolutionPolicy = call.argument<String>("resolutionPolicy")
                    val rotationPolicy = call.argument<String>("rotationPolicy")
                    val keepAudio = call.argument<Boolean>("keepAudio") ?: true

                    if (
                        strategyName != "maximumCompression" ||
                        resolutionPolicy != "Original" ||
                        rotationPolicy != "Original" ||
                        !keepAudio
                    ) {
                        result.error("unsupported_settings", "Only automatic maximum compression is available.", null)
                        return@setMethodCallHandler
                    }

                    startCompression(uriText, path, displayName, outputName, originalSizeBytes, videoBitrate, result)
                }
                "cancelCompression" -> {
                    cancelCompression()
                    result.success(null)
                }
                "shareResult" -> {
                    shareResult(
                        call.argument<String>("uri"),
                        call.argument<String>("mimeType") ?: "video/mp4",
                        result,
                    )
                }
                "openResult" -> {
                    openResult(
                        call.argument<String>("uri"),
                        call.argument<String>("mimeType") ?: "video/mp4",
                        result,
                    )
                }
                else -> result.notImplemented()
            }
        }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, benchmarkChannelName).setMethodCallHandler { call, result ->
            if (!BuildConfig.DEBUG) {
                // Nunca executa fora de build debug: nem a Dart side deveria chamar isto em
                // release (o widget de acesso e kDebugMode-gated), mas a checagem aqui e a
                // garantia final, no lado nativo, independente do que o Flutter fizer.
                result.error("debug_only", "Benchmark CQ disponivel apenas em build debug.", null)
                return@setMethodCallHandler
            }

            when (call.method) {
                "runBenchmark" -> {
                    val uriText = call.argument<String>("uri")
                    val path = call.argument<String>("path")
                    val mode = call.argument<String>("mode")
                    val baseVbrBitrate = call.argument<Number>("baseVbrBitrate")?.toInt()
                    val originalSizeBytes = call.argument<Number>("originalSizeBytes")?.toLong() ?: 0L

                    val resolvedMode = when (mode) {
                        "vbr_atual" -> CompressionBenchmarkRunner.Mode.VBR_ATUAL
                        "cq_conservador" -> CompressionBenchmarkRunner.Mode.CQ_CONSERVADOR
                        "cq_agressivo" -> CompressionBenchmarkRunner.Mode.CQ_AGRESSIVO
                        "cq_extremo" -> CompressionBenchmarkRunner.Mode.CQ_EXTREMO
                        else -> null
                    }

                    val inputUri = InputUriResolver.resolve(uriText, path)
                    if (resolvedMode == null || baseVbrBitrate == null || inputUri == null) {
                        result.error("invalid_arguments", "Parametros invalidos para o benchmark.", null)
                        return@setMethodCallHandler
                    }

                    val resolvedOriginalSize = originalSizeBytes.takeIf { it > 0 } ?: queryInputSize(inputUri)

                    benchmarkRunner.run(
                        inputUri = inputUri,
                        originalSizeBytes = resolvedOriginalSize,
                        baseVbrBitrate = baseVbrBitrate,
                        mode = resolvedMode,
                    ) { benchmarkResult ->
                        result.success(benchmarkResult)
                    }
                }
                else -> result.notImplemented()
            }
        }

        MethodChannel(flutterEngine.dartExecutor.binaryMessenger, sharedIntentChannelName).setMethodCallHandler { call, result ->
            when (call.method) {
                "consumeInitialSharedVideo" -> {
                    val video = pendingSharedVideo
                    pendingSharedVideo = null
                    result.success(video)
                }
                else -> result.notImplemented()
            }
        }

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, progressChannelName).setStreamHandler(
            object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    progressSink = events
                }

                override fun onCancel(arguments: Any?) {
                    progressSink = null
                }
            }
        )

        EventChannel(flutterEngine.dartExecutor.binaryMessenger, sharedIntentStreamChannelName).setStreamHandler(
            object : EventChannel.StreamHandler {
                override fun onListen(arguments: Any?, events: EventChannel.EventSink?) {
                    sharedVideoSink = events
                }

                override fun onCancel(arguments: Any?) {
                    sharedVideoSink = null
                }
            }
        )

        // Intent que iniciou o processo (cold start), incluindo um possivel compartilhamento
        // recebido antes de o Flutter estar pronto para escutar o EventChannel.
        handleIncomingIntent(intent, isInitial = true)
    }

    override fun onNewIntent(intent: Intent) {
        super.onNewIntent(intent)
        setIntent(intent)
        handleIncomingIntent(intent, isInitial = false)
    }

    private fun handleIncomingIntent(intent: Intent?, isInitial: Boolean) {
        val videoUri = SharedVideoIntent.extractVideoUri(intent) ?: return
        // Neutraliza a Intent assim que identificamos um video valido para nao reprocessar
        // a mesma Intent em uma futura recriacao da Activity (rotacao, dobra do aparelho).
        SharedVideoIntent.markConsumed(intent)

        val video = buildSharedVideoPayload(videoUri) ?: return

        if (isInitial) {
            pendingSharedVideo = video
        } else {
            sharedVideoSink?.success(video)
        }
    }

    private fun buildSharedVideoPayload(uri: Uri): Map<String, Any?>? {
        return try {
            val metadata = queryOpenableMetadata(uri)
            val displayName = (metadata["displayName"] as? String) ?: uri.lastPathSegment ?: "video.mp4"
            val mimeType = contentResolver.getType(uri) ?: "video/mp4"

            mapOf(
                "uri" to uri.toString(),
                "displayName" to displayName,
                "mimeType" to mimeType,
                "sizeBytes" to metadata["sizeBytes"],
            )
        } catch (_: Exception) {
            null
        }
    }

    private fun readVideoInfo(uriText: String?, path: String?, fallbackName: String?): Map<String, Any?> {
        val retriever = MediaMetadataRetriever()
        val resolvedUri = InputUriResolver.resolve(uriText, path)
            ?: throw IllegalArgumentException("No uri or path provided.")

        try {
            retriever.setDataSource(applicationContext, resolvedUri)

            val metadata = if (resolvedUri.scheme == "content") {
                queryOpenableMetadata(resolvedUri)
            } else {
                emptyMap()
            }
            val durationMs = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_DURATION)?.toLongOrNull()
            val width = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_WIDTH)?.toIntOrNull()
            val height = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_HEIGHT)?.toIntOrNull()
            val rotation = retriever.extractMetadata(MediaMetadataRetriever.METADATA_KEY_VIDEO_ROTATION)?.toIntOrNull()
            val mimeType = if (resolvedUri.scheme == "content") {
                contentResolver.getType(resolvedUri)
            } else {
                guessMimeType(resolvedUri.toString())
            }

            return mapOf(
                "displayName" to (metadata["displayName"] ?: fallbackName),
                "mimeType" to mimeType,
                "sizeBytes" to metadata["sizeBytes"],
                "durationMs" to durationMs,
                "width" to width,
                "height" to height,
                "rotation" to rotation,
            )
        } finally {
            retriever.release()
        }
    }

    private fun queryOpenableMetadata(uri: Uri): Map<String, Any?> {
        if (uri.scheme != "content") {
            return emptyMap()
        }

        val values = mutableMapOf<String, Any?>()
        var cursor: Cursor? = null

        try {
            cursor = contentResolver.query(
                uri,
                arrayOf(OpenableColumns.DISPLAY_NAME, OpenableColumns.SIZE),
                null,
                null,
                null,
            )

            if (cursor != null && cursor.moveToFirst()) {
                val nameIndex = cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME)
                val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)

                if (nameIndex >= 0 && !cursor.isNull(nameIndex)) {
                    values["displayName"] = cursor.getString(nameIndex)
                }
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                    values["sizeBytes"] = cursor.getLong(sizeIndex)
                }
            }
        } finally {
            cursor?.close()
        }

        return values
    }

    private fun guessMimeType(value: String): String? {
        val extension = MimeTypeMap.getFileExtensionFromUrl(value)
        if (extension.isNullOrBlank()) {
            return null
        }
        return MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension.lowercase())
    }

    private fun startCompression(
        uriText: String?,
        path: String?,
        displayName: String,
        outputName: String,
        providedOriginalSizeBytes: Long,
        requestedVideoBitrate: Int,
        result: MethodChannel.Result,
    ) {
        if (activeTransformer != null || activeResult != null) {
            result.error("busy", "Compression already running.", null)
            return
        }

        val inputUri = InputUriResolver.resolve(uriText, path)
        if (inputUri == null) {
            result.error("file_not_found", "No readable input uri.", null)
            return
        }

        val tempFile = File(cacheDir, "compressed_${System.currentTimeMillis()}.mp4")
        activeTempFile = tempFile
        activeOriginalSizeBytes = providedOriginalSizeBytes.takeIf { it > 0 } ?: queryInputSize(inputUri)
        activeResult = result
        isCancelling = false
        sendProgress("preparing", null, "Preparando video...")

        val bitrate = requestedVideoBitrate.coerceIn(500_000, 8_000_000)
        // Pipeline de producao: sempre VBR via DefaultEncoderFactory do Media3. O modo de
        // qualidade constante (CQ) e experimental e roda apenas na ferramenta de benchmark
        // (debug-only, ver CompressionBenchmarkRunner/CqAwareEncoderFactory). Nao substituir
        // este encoder ate que o benchmark no aparelho real confirme ganho consistente.
        val encoderFactory = DefaultEncoderFactory.Builder(applicationContext)
            .setRequestedVideoEncoderSettings(
                VideoEncoderSettings.Builder()
                    .setBitrate(bitrate)
                    .build()
            )
            .build()

        val transformer = Transformer.Builder(applicationContext)
            .setVideoMimeType(MimeTypes.VIDEO_H264)
            .setAudioMimeType(MimeTypes.AUDIO_AAC)
            .setEncoderFactory(encoderFactory)
            .addListener(object : Transformer.Listener {
                override fun onCompleted(composition: Composition, exportResult: ExportResult) {
                    sendProgress("saving", null, "Salvando arquivo...")
                    Thread {
                        try {
                            val saved = saveOutputFile(tempFile, outputName)
                            mainHandler.post {
                                sendProgress("completed", 100, "Compressao concluida.")
                                finishSuccess(saved)
                            }
                        } catch (error: Exception) {
                            mainHandler.post {
                                finishError("storage_failed", error.message ?: "Could not save output.")
                            }
                        }
                    }.start()
                }

                override fun onError(
                    composition: Composition,
                    exportResult: ExportResult,
                    exportException: ExportException,
                ) {
                    if (isCancelling) {
                        finishError("cancelled", "Compression cancelled.")
                    } else {
                        finishError("compression_failed", exportException.message ?: "Export failed.")
                    }
                }
            })
            .build()

        activeTransformer = transformer

        try {
            val mediaItem = MediaItem.fromUri(inputUri)
            val editedMediaItem = EditedMediaItem.Builder(mediaItem).build()
            transformer.start(editedMediaItem, tempFile.absolutePath)
            pollProgress(transformer)
        } catch (error: Exception) {
            finishError("compression_failed", error.message ?: "Could not start compression.")
        }
    }

    private fun pollProgress(transformer: Transformer) {
        val progressHolder = ProgressHolder()
        mainHandler.postDelayed(object : Runnable {
            override fun run() {
                if (activeTransformer !== transformer || isCancelling) {
                    return
                }

                val state = transformer.getProgress(progressHolder)
                when (state) {
                    Transformer.PROGRESS_STATE_AVAILABLE -> {
                        sendProgress("processing", progressHolder.progress, "Comprimindo video...")
                    }
                    Transformer.PROGRESS_STATE_UNAVAILABLE -> {
                        sendProgress("processing", null, "Comprimindo video...")
                    }
                }

                if (state != Transformer.PROGRESS_STATE_NOT_STARTED) {
                    mainHandler.postDelayed(this, 500)
                }
            }
        }, 300)
    }

    private fun cancelCompression() {
        isCancelling = true
        sendProgress("cancelled", null, "Cancelando...")
        activeTransformer?.cancel()
        activeTempFile?.delete()
        finishError("cancelled", "Compression cancelled.")
    }

    private fun saveOutputFile(tempFile: File, outputName: String): SavedOutput {
        val originalSize = activeOriginalSizeBytes
        val finalOutputName = uniqueOutputName(outputName)
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.Q) {
            val values = ContentValues().apply {
                put(MediaStore.Video.Media.DISPLAY_NAME, finalOutputName)
                put(MediaStore.Video.Media.MIME_TYPE, "video/mp4")
                put(MediaStore.Video.Media.RELATIVE_PATH, "${Environment.DIRECTORY_MOVIES}/Preparo de Videos")
                put(MediaStore.Video.Media.IS_PENDING, 1)
            }
            val uri = contentResolver.insert(MediaStore.Video.Media.EXTERNAL_CONTENT_URI, values)
                ?: throw IllegalStateException("Could not create MediaStore item.")

            contentResolver.openOutputStream(uri)?.use { output ->
                tempFile.inputStream().use { input -> input.copyTo(output) }
            } ?: throw IllegalStateException("Could not open MediaStore output stream.")

            val doneValues = ContentValues().apply {
                put(MediaStore.Video.Media.IS_PENDING, 0)
            }
            contentResolver.update(uri, doneValues, null, null)

            val outputSize = tempFile.length()
            tempFile.delete()
            return SavedOutput(
                outputName = finalOutputName,
                outputUri = uri.toString(),
                outputLocationLabel = "Movies/Preparo de Videos",
                originalSizeBytes = originalSize,
                outputSizeBytes = outputSize,
            )
        }

        // Android anterior ao 10: sem MediaStore com RELATIVE_PATH. Salva na pasta
        // especifica do app (nao exige permissao legada) e expoe via FileProvider em vez
        // de uma URI file:// crua, para nao vazar o caminho privado ao compartilhar/abrir.
        val moviesDir = getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: filesDir
        val outputFile = File(moviesDir, finalOutputName)
        tempFile.copyTo(outputFile, overwrite = false)
        val outputSize = outputFile.length()
        tempFile.delete()

        val authority = "$packageName.fileprovider"
        val outputUri = FileProvider.getUriForFile(this, authority, outputFile)

        return SavedOutput(
            outputName = finalOutputName,
            outputUri = outputUri.toString(),
            outputLocationLabel = "Pasta do app",
            originalSizeBytes = originalSize,
            outputSizeBytes = outputSize,
        )
    }

    private fun uniqueOutputName(requestedName: String): String {
        var candidate = requestedName.ifBlank { "video_comprimido.mp4" }
        if (!outputNameExists(candidate)) {
            return candidate
        }

        val (stem, extension) = splitNameAndExtension(candidate)
        var suffix = 2
        do {
            candidate = "${stem}_${suffix}${extension}"
            suffix += 1
        } while (outputNameExists(candidate))

        return candidate
    }

    private fun splitNameAndExtension(fileName: String): Pair<String, String> {
        val dotIndex = fileName.lastIndexOf('.')
        if (dotIndex <= 0 || dotIndex == fileName.lastIndex) {
            return fileName to ""
        }
        return fileName.substring(0, dotIndex) to fileName.substring(dotIndex)
    }

    private fun outputNameExists(fileName: String): Boolean {
        if (Build.VERSION.SDK_INT < Build.VERSION_CODES.Q) {
            val moviesDir = getExternalFilesDir(Environment.DIRECTORY_MOVIES) ?: filesDir
            return File(moviesDir, fileName).exists()
        }

        var cursor: Cursor? = null
        return try {
            cursor = contentResolver.query(
                MediaStore.Video.Media.EXTERNAL_CONTENT_URI,
                arrayOf(MediaStore.Video.Media._ID),
                "${MediaStore.Video.Media.DISPLAY_NAME}=? AND ${MediaStore.Video.Media.RELATIVE_PATH}=?",
                arrayOf(fileName, "${Environment.DIRECTORY_MOVIES}/Preparo de Videos/"),
                null,
            )
            cursor?.moveToFirst() == true
        } finally {
            cursor?.close()
        }
    }

    private fun queryInputSize(uri: Uri): Long {
        return when (uri.scheme) {
            "content" -> queryContentSize(uri)
            "file" -> uri.path?.let { File(it).length() } ?: 0L
            else -> 0L
        }
    }

    private fun queryContentSize(uri: Uri): Long {
        var cursor: Cursor? = null
        try {
            cursor = contentResolver.query(uri, arrayOf(OpenableColumns.SIZE), null, null, null)
            if (cursor != null && cursor.moveToFirst()) {
                val sizeIndex = cursor.getColumnIndex(OpenableColumns.SIZE)
                if (sizeIndex >= 0 && !cursor.isNull(sizeIndex)) {
                    return cursor.getLong(sizeIndex)
                }
            }
        } finally {
            cursor?.close()
        }
        return 0L
    }

    private fun finishSuccess(saved: SavedOutput) {
        activeResult?.success(
            mapOf(
                "outputName" to saved.outputName,
                "outputUri" to saved.outputUri,
                "outputLocationLabel" to saved.outputLocationLabel,
                "originalSizeBytes" to saved.originalSizeBytes,
                "outputSizeBytes" to saved.outputSizeBytes,
                "format" to "MP4",
            )
        )
        clearActiveCompression()
    }

    private fun finishError(code: String, message: String) {
        activeTempFile?.delete()
        activeResult?.error(code, message, null)
        clearActiveCompression()
    }

    private fun clearActiveCompression() {
        activeTransformer = null
        activeResult = null
        activeTempFile = null
        activeOriginalSizeBytes = 0L
        isCancelling = false
    }

    private fun sendProgress(stage: String, percent: Int?, message: String) {
        progressSink?.success(
            mapOf(
                "stage" to stage,
                "percent" to percent,
                "message" to message,
            )
        )
    }

    private fun shareResult(uriText: String?, mimeType: String, result: MethodChannel.Result) {
        val uri = uriText?.takeIf { it.isNotBlank() }?.let { Uri.parse(it) }
        if (uri == null) {
            result.error("invalid_uri", "URI de resultado invalida.", null)
            return
        }

        val sendIntent = Intent(Intent.ACTION_SEND).apply {
            type = mimeType
            putExtra(Intent.EXTRA_STREAM, uri)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }

        if (sendIntent.resolveActivity(packageManager) == null) {
            result.error("no_app", "Nenhum aplicativo compativel foi encontrado.", null)
            return
        }

        try {
            startActivity(Intent.createChooser(sendIntent, "Compartilhar video"))
            result.success(null)
        } catch (error: Exception) {
            result.error("share_failed", "Nao foi possivel compartilhar o video.", error.message)
        }
    }

    private fun openResult(uriText: String?, mimeType: String, result: MethodChannel.Result) {
        val uri = uriText?.takeIf { it.isNotBlank() }?.let { Uri.parse(it) }
        if (uri == null) {
            result.error("invalid_uri", "URI de resultado invalida.", null)
            return
        }

        val viewIntent = Intent(Intent.ACTION_VIEW).apply {
            setDataAndType(uri, mimeType)
            addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
        }

        if (viewIntent.resolveActivity(packageManager) == null) {
            result.error("no_app", "Nenhum aplicativo compativel foi encontrado.", null)
            return
        }

        try {
            startActivity(viewIntent)
            result.success(null)
        } catch (error: Exception) {
            result.error("open_failed", "Nao foi possivel abrir o video.", error.message)
        }
    }

    private fun buildOutputName(displayName: String): String {
        val dotIndex = displayName.lastIndexOf('.')
        val stem = if (dotIndex > 0) displayName.substring(0, dotIndex) else displayName
        return "${stem.ifBlank { "video" }}_comprimido.mp4"
    }

    private data class SavedOutput(
        val outputName: String,
        val outputUri: String,
        val outputLocationLabel: String,
        val originalSizeBytes: Long,
        val outputSizeBytes: Long,
    )
}
