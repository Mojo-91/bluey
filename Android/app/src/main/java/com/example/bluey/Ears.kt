package com.example.bluey

import android.content.Context
import android.content.Intent
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.speech.RecognitionListener
import android.speech.RecognizerIntent
import android.speech.SpeechRecognizer

/** Hold-to-talk speech to text. Delivers one string, only after release. Never plays audio. */
class Ears(private val ctx: Context, private val onText: (String) -> Unit) {
    private val main = Handler(Looper.getMainLooper())
    private var rec: SpeechRecognizer? = null
    private var partial = ""
    private var finished: String? = null
    private var released = false
    private var delivered = false
    private var session = 0

    fun start() {
        session++
        partial = ""; finished = null; released = false; delivered = false
        rec?.destroy()
        if (!SpeechRecognizer.isRecognitionAvailable(ctx)) { deliver(""); return }
        val r = SpeechRecognizer.createSpeechRecognizer(ctx)
        rec = r
        r.setRecognitionListener(object : RecognitionListener {
            override fun onPartialResults(b: Bundle?) { first(b)?.let { partial = it } }
            override fun onResults(b: Bundle?) { finish(first(b) ?: partial) }
            override fun onError(e: Int) { finish(partial) }
            override fun onReadyForSpeech(p: Bundle?) {}
            override fun onBeginningOfSpeech() {}
            override fun onRmsChanged(v: Float) {}
            override fun onBufferReceived(b: ByteArray?) {}
            override fun onEndOfSpeech() {}
            override fun onEvent(t: Int, p: Bundle?) {}
        })
        r.startListening(
            Intent(RecognizerIntent.ACTION_RECOGNIZE_SPEECH)
                .putExtra(RecognizerIntent.EXTRA_LANGUAGE_MODEL, RecognizerIntent.LANGUAGE_MODEL_FREE_FORM)
                .putExtra(RecognizerIntent.EXTRA_PARTIAL_RESULTS, true)
                .putExtra(RecognizerIntent.EXTRA_PREFER_OFFLINE, true)
        )
    }

    fun stop() {
        released = true
        finished?.let { deliver(it); return }
        rec?.stopListening()
        val id = session
        main.postDelayed({ if (id == session) deliver(partial) }, 2500)   // safety net
    }

    private fun first(b: Bundle?) = b?.getStringArrayList(SpeechRecognizer.RESULTS_RECOGNITION)?.firstOrNull()
    private fun finish(t: String) { finished = t; if (released) deliver(t) }
    private fun deliver(t: String) { if (delivered) return; delivered = true; onText(t) }
}
