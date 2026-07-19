package com.gustavonorberto.video_preparo_mobile

import org.junit.Assert.assertEquals
import org.junit.Assert.assertNull
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config

@RunWith(RobolectricTestRunner::class)
@Config(sdk = [33])
class InputUriResolverTest {

    @Test
    fun `content uri e usada como esta`() {
        val resolved = InputUriResolver.resolve("content://media/external/video/media/42", null)

        assertEquals("content", resolved?.scheme)
        assertEquals("content://media/external/video/media/42", resolved.toString())
    }

    @Test
    fun `file uri e usada como esta`() {
        val resolved = InputUriResolver.resolve("file:///storage/emulated/0/Movies/video.mp4", null)

        assertEquals("file", resolved?.scheme)
        assertEquals("/storage/emulated/0/Movies/video.mp4", resolved?.path)
    }

    @Test
    fun `caminho local sem esquema vira uri de arquivo`() {
        val resolved = InputUriResolver.resolve("/data/user/0/app/cache/video.mp4", null)

        assertEquals("file", resolved?.scheme)
        assertEquals("/data/user/0/app/cache/video.mp4", resolved?.path)
    }

    @Test
    fun `usa path como fallback quando nao ha uri`() {
        val resolved = InputUriResolver.resolve(null, "/data/user/0/app/cache/outro.mp4")

        assertEquals("file", resolved?.scheme)
        assertEquals("/data/user/0/app/cache/outro.mp4", resolved?.path)
    }

    @Test
    fun `retorna nulo quando nao ha uri nem path`() {
        assertNull(InputUriResolver.resolve(null, null))
        assertNull(InputUriResolver.resolve("", ""))
    }

    @Test
    fun `nomes com espacos sao preservados`() {
        val resolved = InputUriResolver.resolve("/storage/emulated/0/Movies/meu video.mp4", null)

        assertEquals("/storage/emulated/0/Movies/meu video.mp4", resolved?.path)
    }

    @Test
    fun `nomes com acentos sao preservados`() {
        val resolved = InputUriResolver.resolve(
            "/storage/emulated/0/Movies/vídeo em português.mp4",
            null,
        )

        assertEquals("/storage/emulated/0/Movies/vídeo em português.mp4", resolved?.path)
    }

    @Test
    fun `nomes com cerquilha nao truncam o caminho`() {
        // Uri.parse() direto sobre este caminho interpretaria tudo apos "#" como
        // fragmento e perderia o restante do nome do arquivo. Uri.fromFile() nao tem
        // esse problema porque faz o percent-encoding correto.
        val resolved = InputUriResolver.resolve("/storage/emulated/0/Movies/clipe #1.mp4", null)

        assertEquals("/storage/emulated/0/Movies/clipe #1.mp4", resolved?.path)
    }

    @Test
    fun `nomes com porcentagem sao preservados`() {
        val resolved = InputUriResolver.resolve(
            "/storage/emulated/0/Movies/desconto 50% off.mp4",
            null,
        )

        assertEquals("/storage/emulated/0/Movies/desconto 50% off.mp4", resolved?.path)
    }

    @Test
    fun `nomes com parenteses sao preservados`() {
        val resolved = InputUriResolver.resolve("/storage/emulated/0/Movies/ferias (2026).mp4", null)

        assertEquals("/storage/emulated/0/Movies/ferias (2026).mp4", resolved?.path)
    }

    @Test
    fun `nomes com caracteres unicode diversos sao preservados`() {
        val resolved = InputUriResolver.resolve(
            "/storage/emulated/0/Movies/日本語のビデオ 🎬.mp4",
            null,
        )

        assertEquals("/storage/emulated/0/Movies/日本語のビデオ 🎬.mp4", resolved?.path)
    }
}
