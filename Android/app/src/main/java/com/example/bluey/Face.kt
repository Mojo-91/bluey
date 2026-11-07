package com.example.bluey

import android.os.Build
import android.view.RoundedCorner
import androidx.compose.animation.core.animateDpAsState
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.waitForUpOrCancellation
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.BasicTextField
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Rect
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.Path
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.clipPath
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.platform.LocalDensity
import androidx.compose.ui.platform.LocalUriHandler
import androidx.compose.ui.platform.LocalView
import androidx.compose.ui.text.TextStyle
import androidx.compose.ui.text.drawText
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.text.rememberTextMeasurer
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlinx.coroutines.delay
import kotlin.math.cos
import kotlin.math.sin

data class Ring(val color: Color, val width: Int, val label: String)

/** Solid borders, no glow. Listening is the thick blue one; holding to ask makes it thicker. */
fun ringFor(s: String, held: Boolean): Ring? = when (s) {
    "listening"   -> Ring(Color(0xFF1F47FF), if (held) 26 else 14, "I'm all ears")
    "thinking"    -> Ring(Color(0xFFA855F7), 8, "Thinking")
    "researching" -> Ring(Color(0xFFF59E0B), 8, "Researching")
    "replying"    -> Ring(Color(0xFFEC4899), 8, "Replying")
    "pointing"    -> Ring(Color(0xFF22C55E), 8, "Pointing")
    else -> null
}

@Composable
fun FaceScreen(m: Model) {
    val view = LocalView.current
    val density = LocalDensity.current
    LaunchedEffect(Unit) {
        delay(400)
        if (Build.VERSION.SDK_INT >= 31) {
            m.cornerPx = view.rootWindowInsets?.getRoundedCorner(RoundedCorner.POSITION_TOP_LEFT)?.radius?.toFloat() ?: 0f
        }
    }
    val corner = with(density) { (if (m.cornerPx > 0f) m.cornerPx else 48.dp.toPx()).toDp() }   // border follows the phone's corners
    val ring = if (m.connected) ringFor(m.state, m.held) else null
    val ringW by animateDpAsState((ring?.width ?: 0).dp, tween(150), label = "ring")
    LaunchedEffect(m.connected) {
        if (m.connected) m.showManual = false else { delay(8000); m.showManual = true }
    }

    Box(
        Modifier.fillMaxSize().background(Color.Black).pointerInput(Unit) {
            awaitEachGesture {
                awaitFirstDown()
                if (m.showTranscript) { waitForUpOrCancellation(); return@awaitEachGesture }
                m.hold(); waitForUpOrCancellation(); m.release()
            }
        }
    ) {
        Face(m, forceAsleep = !m.connected)

        if (ring != null && ringW > 0.dp) Box(Modifier.fillMaxSize().border(ringW, ring.color, RoundedCornerShape(corner)))

        if (m.connected && m.state != "sleeping") {
            Pill(Modifier.align(Alignment.TopStart).padding(26.dp), ring?.color ?: Color(0xFF2A3A8C), ring?.label ?: "")
        }
        if (m.connected && !m.showTranscript) {
            Box(
                Modifier.align(Alignment.TopEnd).padding(26.dp).size(34.dp)
                    .background(Color(0xFF141A33), CircleShape).clickable { m.showTranscript = true },
                contentAlignment = Alignment.Center
            ) { Text("≡", color = Color.White, fontSize = 18.sp) }
        }

        // pairing screen
        if (!m.connected) {
            Column(
                Modifier.align(Alignment.BottomCenter).padding(24.dp)
                    .background(Color(0xFF141A33), RoundedCornerShape(14.dp)).padding(14.dp),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                if (m.needsCode) {
                    Text(
                        if (m.wrongCode) "Wrong code. Check the Bluey window on your PC." else "Type the 6-digit code shown in Bluey on your PC",
                        color = if (m.wrongCode) Color(0xFFFF8A8A) else Color(0xFFDFE6FF), fontSize = 13.sp
                    )
                    var code by remember { mutableStateOf("") }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        BasicTextField(
                            code, { v -> code = v.filter { it.isDigit() }.take(6) }, singleLine = true,
                            textStyle = TextStyle(color = Color.White, fontSize = 22.sp, letterSpacing = 4.sp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.NumberPassword),
                            modifier = Modifier.width(150.dp).padding(8.dp)
                        )
                        TextButton({ if (code.length == 6) m.submitCode(code) }) { Text("Connect") }
                    }
                } else {
                    Text("Looking for your PC… same Wi-Fi", color = Color(0xFF8FA0D8), fontSize = 13.sp)
                }
                if (m.showManual) {
                    var ip by remember { mutableStateOf(m.link.manualHost) }
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        BasicTextField(
                            ip, { ip = it }, singleLine = true,
                            textStyle = TextStyle(color = Color.White, fontSize = 14.sp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Uri),
                            decorationBox = { inner ->
                                if (ip.isEmpty()) Text("Can't find it? PC IP from the Bluey window", color = Color.Gray, fontSize = 13.sp)
                                inner()
                            },
                            modifier = Modifier.width(260.dp).padding(8.dp)
                        )
                        TextButton({ m.link.manualHost = ip }) { Text("Use") }
                    }
                }
            }
        }

        if (m.showTranscript) Transcript(m)
    }
}

@Composable
fun Pill(modifier: Modifier, color: Color, label: String) {
    Row(
        modifier.background(color, CircleShape).padding(horizontal = 9.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Canvas(Modifier.size(14.dp)) {      // the small eye icon
            drawCircle(Color.White)
            drawCircle(Color(0xFF141F8C), size.minDimension * 0.28f, center + Offset(size.width * 0.08f, 0f))
        }
        if (label.isNotEmpty()) {
            Text(label, color = Color.White, fontSize = 11.sp, fontWeight = FontWeight.Bold, modifier = Modifier.padding(start = 6.dp))
        }
    }
}

/** This session: what you asked, Bluey's one-liners, and reports as cards you can expand. */
@Composable
fun Transcript(m: Model) {
    val uri = LocalUriHandler.current
    Box(Modifier.fillMaxSize().background(Color(0xF2000000)).padding(horizontal = 56.dp, vertical = 24.dp)) {
        LazyColumn(Modifier.fillMaxSize(), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            if (m.transcript.isEmpty()) item { Text("Nothing yet. Hold the screen and ask.", color = Color.Gray) }
            itemsIndexed(m.transcript) { _, e ->
                when (e) {
                    is Entry.Ask -> Text(
                        e.text, color = Color.White,
                        modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.End)
                            .background(Color(0xFF2A2F45), RoundedCornerShape(14.dp)).padding(12.dp)
                    )
                    is Entry.Say -> Text(
                        e.text, color = Color.White,
                        modifier = Modifier.fillMaxWidth().wrapContentWidth(Alignment.Start)
                            .background(Color(0xFF2347E6), RoundedCornerShape(14.dp)).padding(12.dp)
                    )
                    is Entry.Report -> {
                        var open by remember { mutableStateOf(false) }
                        Column(
                            Modifier.fillMaxWidth().background(Color(0xFF181C2C), RoundedCornerShape(14.dp))
                                .clickable { open = !open }.padding(14.dp)
                        ) {
                            Text(e.title, color = Color.White, fontWeight = FontWeight.Bold, fontSize = 15.sp)
                            val body = if (open || e.text.length <= 180) e.text else e.text.take(180).trimEnd() + "…"
                            if (body.isNotEmpty()) Text(body, color = Color(0xFFDFE6FF), fontSize = 13.sp, modifier = Modifier.padding(top = 6.dp))
                            if (open) e.sources.filter { it.second.startsWith("http") }.forEach { (t, u) ->
                                Text(t, color = Color(0xFF8FB4FF), fontSize = 12.sp, maxLines = 1,
                                    modifier = Modifier.padding(top = 6.dp).clickable { uri.openUri(u) })
                            }
                        }
                    }
                }
            }
        }
        TextButton({ m.showTranscript = false }, Modifier.align(Alignment.TopEnd)) { Text("Close") }
    }
}

@Composable
fun Face(m: Model, forceAsleep: Boolean) {
    val asleep = forceAsleep || m.state == "sleeping"
    var blink by remember { mutableStateOf(false) }
    LaunchedEffect(Unit) { while (true) { delay((2500..5000).random().toLong()); blink = true; delay(120); blink = false } }

    val lid by animateFloatAsState(if (asleep || blink) 1f else if (m.state == "idle") 0.35f else 0f, tween(120), label = "lid")
    val lx by animateFloatAsState(m.lx, tween(120), label = "lx")
    val ly by animateFloatAsState(m.ly, tween(120), label = "ly")
    val lift by animateFloatAsState(if (m.state in listOf("listening", "thinking", "researching")) 0.06f else 0f, label = "lift")
    val mouth by animateFloatAsState(if (m.state == "replying") 0.13f else 0.07f, label = "mouth")
    val measurer = rememberTextMeasurer()

    BoxWithConstraints(Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
        val w = maxWidth * 0.94f
        val h = minOf(maxHeight * 0.9f, w / 2)
        Canvas(Modifier.size(w, h)) {
            val W = size.width
            val H = size.height
            val sky = Brush.verticalGradient(listOf(Color(0xFFC7E0FF), Color(0xFF5C85FF), Color(0xFF1A33E6)), 0f, H)
            val ink = Color(0xFF141F8C)

            // dome: top half of an ellipse, flat edge at the bottom
            drawPath(Path().apply { arcTo(Rect(0f, 0f, W, 2 * H), 180f, 180f, true); close() }, sky)

            val star = Path().apply {
                for (i in 0 until 10) {
                    val a = Math.toRadians(-90.0 + 36 * i)
                    val r = if (i % 2 == 0) H * 0.11f else H * 0.045f
                    val x = W / 2 + r * cos(a).toFloat()
                    val y = H * 0.10f + r * sin(a).toFloat()
                    if (i == 0) moveTo(x, y) else lineTo(x, y)
                }
                close()
            }
            drawPath(star, ink)

            for (fx in listOf(0.30f, 0.70f)) {
                val cx = W * fx
                val cy = H * 0.57f
                val d = H * 0.46f
                val r = d / 2

                val by = H * (0.36f - lift)
                drawPath(
                    Path().apply { moveTo(cx - W * 0.05f, by + H * 0.03f); quadraticBezierTo(cx, by - H * 0.07f, cx + W * 0.05f, by + H * 0.02f) },
                    ink, style = Stroke(H * 0.03f, cap = StrokeCap.Round)
                )

                clipPath(Path().apply { addOval(Rect(Offset(cx, cy), r)) }) {
                    drawCircle(Color.White, r, Offset(cx, cy))
                    val pr = r * 0.5f
                    val po = Offset(cx + (lx - 0.5f) * d * 0.5f, cy + (ly - 0.5f) * d * 0.5f)
                    drawCircle(ink, pr, po)
                    drawCircle(Color.White, pr * 0.28f, po + Offset(-pr * 0.32f, -pr * 0.32f))
                    drawRect(sky, Offset(cx - r, cy - r), Size(d, d * lid))
                }
                if (asleep) {
                    drawPath(
                        Path().apply { moveTo(cx - r * 0.9f, cy); quadraticBezierTo(cx, cy + r * 0.5f, cx + r * 0.9f, cy) },
                        ink, style = Stroke(d * 0.07f, cap = StrokeCap.Round)
                    )
                }
            }

            for (fx in listOf(0.20f, 0.80f)) {
                drawOval(Color(0xFFFF7AC8).copy(alpha = 0.35f), Offset(W * fx - W * 0.03f, H * 0.78f - H * 0.05f), Size(W * 0.06f, H * 0.10f))
            }
            drawOval(ink, Offset(W / 2 - W * 0.015f, H * 0.82f - H * mouth / 2), Size(W * 0.03f, H * mouth))

            if (asleep) {
                drawText(measurer, "z Z", Offset(W * 0.86f, H * 0.08f),
                    style = TextStyle(color = Color.White.copy(alpha = 0.8f), fontSize = (H * 0.1f).toSp(), fontWeight = FontWeight.Bold))
            }
        }
    }
}
