package com.gustavonorberto.video_preparo_mobile

import android.net.Uri
import java.io.File

/**
 * Centraliza a resolucao de referencias de video de entrada (selecionadas pelo picker,
 * recebidas por compartilhamento ou vindas de um caminho local de fallback) em uma unica
 * Uri consistente, usada tanto para leitura de metadados quanto para compressao.
 *
 * Regras:
 * - `content://` -> usada como esta.
 * - `file://` -> usada como esta.
 * - Texto sem esquema (caminho local bruto, ex.: `/data/user/0/app/cache/video.mp4`) ->
 *   envolvido com [Uri.fromFile], que faz o escapamento correto de espacos, acentos e
 *   caracteres especiais (#, %, parenteses, emojis etc). Nunca usar [Uri.parse] direto
 *   sobre um caminho de arquivo bruto: ele nao faz percent-encoding e caracteres como
 *   `#` truncam o restante do caminho por serem interpretados como fragmento da URI.
 */
object InputUriResolver {

    fun resolve(uriText: String?, path: String?): Uri? {
        val candidate = uriText?.takeIf { it.isNotBlank() }
        if (candidate != null) {
            val parsed = Uri.parse(candidate)
            return when (parsed.scheme) {
                "content", "file" -> parsed
                else -> Uri.fromFile(File(candidate))
            }
        }

        val fallbackPath = path?.takeIf { it.isNotBlank() }
        if (fallbackPath != null) {
            return Uri.fromFile(File(fallbackPath))
        }

        return null
    }
}
