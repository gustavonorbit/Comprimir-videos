package com.gustavonorberto.video_preparo_mobile

import android.content.Intent
import android.net.Uri
import android.os.Build

/**
 * Extrai a referencia de video de uma Intent de compartilhamento (ACTION_SEND), sem
 * depender de Context/ContentResolver. O enriquecimento com nome/tamanho/mime continua
 * responsabilidade da Activity, que tem acesso ao ContentResolver.
 */
object SharedVideoIntent {

    /** Retorna a Uri do video compartilhado, ou nulo se a Intent nao for um compartilhamento de video valido. */
    fun extractVideoUri(intent: Intent?): Uri? {
        if (intent == null || intent.action != Intent.ACTION_SEND) {
            return null
        }

        val type = intent.type
        if (type.isNullOrBlank() || !type.startsWith("video/")) {
            return null
        }

        return if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.TIRAMISU) {
            intent.getParcelableExtra(Intent.EXTRA_STREAM, Uri::class.java)
        } else {
            @Suppress("DEPRECATION")
            intent.getParcelableExtra(Intent.EXTRA_STREAM) as? Uri
        }
    }

    /**
     * Neutraliza a Intent apos o consumo, para que a mesma Intent nao seja reprocessada
     * quando a Activity for recriada (rotacao, dobra/desdobra do aparelho) sem que uma
     * nova Intent seja entregue via onNewIntent.
     */
    fun markConsumed(intent: Intent?) {
        intent?.removeExtra(Intent.EXTRA_STREAM)
        intent?.action = Intent.ACTION_MAIN
    }
}
