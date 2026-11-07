package com.example.bluey

import android.content.Context
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Handler
import android.os.Looper
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.setValue
import org.json.JSONObject

/** One line of the session transcript. */
sealed class Entry {
    data class Ask(val text: String) : Entry()
    data class Say(val text: String) : Entry()
    data class Report(val title: String, val text: String, val sources: List<Pair<String, String>>) : Entry()
}

/** Tiny UI sounds. Bluey never speaks; these are just a chime on connect and a ding on a reply. */
private class Sounds {
    private val tg = try { ToneGenerator(AudioManager.STREAM_MUSIC, 35) } catch (_: Exception) { null }
    fun connected() { tg?.startTone(ToneGenerator.TONE_PROP_ACK, 160) }
    fun ding() { tg?.startTone(ToneGenerator.TONE_PROP_BEEP, 70) }
}

class Model(ctx: Context) {
    var state by mutableStateOf("idle")        // idle listening thinking researching replying pointing sleeping
    var lx by mutableFloatStateOf(0.5f)        // where the eyes look, 0..1
    var ly by mutableFloatStateOf(0.5f)
    var connected by mutableStateOf(false)
    var showManual by mutableStateOf(false)
    var held by mutableStateOf(false)          // finger down: the listening border gets thicker
    var showTranscript by mutableStateOf(false)
    var needsCode by mutableStateOf(false)     // show the 6-digit code box
    var wrongCode by mutableStateOf(false)
    var cornerPx by mutableFloatStateOf(0f)    // the phone's own screen corner radius
    val transcript = mutableStateListOf<Entry>()

    private val main = Handler(Looper.getMainLooper())
    private val sounds = Sounds()

    val link = Link(ctx,
        onMsg = { m -> main.post { receive(m) } },
        onConn = { ok ->
            main.post {
                if (ok && !connected) sounds.connected()
                connected = ok
                if (!ok) { state = "idle"; held = false }
            }
        },
        onDenied = { main.post { wrongCode = true; needsCode = true; connected = false } })

    init { needsCode = link.code.isEmpty() }

    fun submitCode(c: String) { wrongCode = false; needsCode = false; link.code = c }

    private val ears = Ears(ctx) { text ->
        held = false
        if (text.isBlank()) state = "listening"
        else {
            state = "thinking"
            transcript.add(Entry.Ask(text))
            link.send(JSONObject().put("t", "ask").put("text", text))
        }
    }

    private fun receive(m: JSONObject) {
        when (m.optString("t")) {
            "state" -> state = m.optString("s", "idle")
            "look" -> { lx = m.optDouble("x", 0.5).toFloat(); ly = m.optDouble("y", 0.5).toFloat() }
            "say" -> { transcript.add(Entry.Say(m.optString("text"))); sounds.ding() }
            "report" -> {
                val src = mutableListOf<Pair<String, String>>()
                m.optJSONArray("sources")?.let { a ->
                    for (i in 0 until a.length()) a.optJSONArray(i)?.let { p -> src.add(p.optString(0) to p.optString(1)) }
                }
                transcript.add(Entry.Report(m.optString("title"), m.optString("text"), src))
            }
        }
    }

    /** Finger down: start listening. Nothing is sent until release. */
    fun hold() {
        if (!connected) return
        held = true
        link.send(JSONObject().put("t", "wake"))
        state = "listening"
        ears.start()
    }

    /** Finger up: finish transcribing, then ask the PC. */
    fun release() { if (connected) ears.stop() else held = false }
}
