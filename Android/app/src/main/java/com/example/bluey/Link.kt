package com.example.bluey

import android.content.Context
import android.net.nsd.NsdManager
import android.net.nsd.NsdServiceInfo
import org.json.JSONObject
import java.io.OutputStream
import java.net.Inet4Address
import java.net.InetSocketAddress
import java.net.NetworkInterface
import java.net.Socket
import java.util.concurrent.Executors
import java.util.concurrent.TimeUnit
import java.util.concurrent.atomic.AtomicReference
import kotlin.concurrent.thread

const val PORT = 47474

/** Finds the PC (Bonjour, or a typed IP) and keeps one TCP connection alive. One JSON object per line. */
class Link(
    ctx: Context,
    private val onMsg: (JSONObject) -> Unit,
    private val onConn: (Boolean) -> Unit,
    private val onDenied: () -> Unit
) {
    private val nsd = ctx.getSystemService(Context.NSD_SERVICE) as NsdManager
    private val prefs = ctx.getSharedPreferences("bluey", Context.MODE_PRIVATE)
    private val io = Executors.newSingleThreadExecutor()
    @Volatile private var running = false
    @Volatile private var out: OutputStream? = null
    @Volatile private var socket: Socket? = null
    @Volatile private var found: String? = null
    @Volatile private var denied = false
    private var discovery: NsdManager.DiscoveryListener? = null

    var manualHost: String
        get() = prefs.getString("mac_ip", "") ?: ""
        set(v) { prefs.edit().putString("mac_ip", v.trim()).apply(); runCatching { socket?.close() } }

    /** The 6-digit code shown in the Bluey window on the PC. */
    var code: String
        get() = prefs.getString("code", "") ?: ""
        set(v) { prefs.edit().putString("code", v.trim()).apply(); denied = false; runCatching { socket?.close() } }

    fun start() {
        if (running) return
        running = true
        discover()
        scanLoop()
        thread(isDaemon = true) {
            while (running) {
                val host = manualHost.ifEmpty { found }
                if (host != null && code.isNotEmpty() && !denied) session(host)
                Thread.sleep(1500)
            }
        }
    }

    fun stop() {
        running = false
        discovery?.let { runCatching { nsd.stopServiceDiscovery(it) } }
        discovery = null
        runCatching { socket?.close() }
    }

    fun send(o: JSONObject) {
        val w = out ?: return
        io.execute { runCatching { w.write((o.toString() + "\n").toByteArray()); w.flush() } }
    }

    private fun session(host: String) {
        try {
            Socket().use { sock ->
                socket = sock
                sock.connect(InetSocketAddress(host, PORT), 4000)
                val o = sock.getOutputStream()
                o.write((JSONObject().put("t", "hello").put("code", code).toString() + "\n").toByteArray())
                o.flush()
                val r = sock.getInputStream().bufferedReader()
                val first = r.readLine() ?: return@use
                when (JSONObject(first).optString("t")) {
                    "denied" -> { denied = true; onDenied() }
                    "ok" -> {
                        out = o
                        onConn(true)
                        r.forEachLine { line -> runCatching { onMsg(JSONObject(line)) } }
                    }
                }
            }
        } catch (_: Exception) { if (manualHost.isEmpty()) found = null }
        out = null
        socket = null
        onConn(false)
    }

    /** If Bonjour finds nothing, look for the PC on the phone's own Wi-Fi (same /24) by trying the port. */
    private fun scanLoop() = thread(isDaemon = true) {
        while (running) {
            Thread.sleep(4000)
            if (running && found == null && manualHost.isEmpty() && socket == null) runCatching { scan() }
        }
    }

    private fun scan() {
        val me = NetworkInterface.getNetworkInterfaces().toList()
            .filter { it.isUp && !it.isLoopback }
            .flatMap { it.interfaceAddresses }
            .map { it.address }
            .filterIsInstance<Inet4Address>()
            .firstOrNull { it.isSiteLocalAddress }?.hostAddress ?: return
        val prefix = me.substringBeforeLast('.')
        val hit = AtomicReference<String?>(null)
        val pool = Executors.newFixedThreadPool(48)
        for (i in 1..254) {
            val ip = "$prefix.$i"
            if (ip == me) continue
            pool.execute {
                if (hit.get() == null) {
                    try { Socket().use { it.connect(InetSocketAddress(ip, PORT), 300) }; hit.compareAndSet(null, ip) } catch (_: Exception) { }
                }
            }
        }
        pool.shutdown()
        pool.awaitTermination(15, TimeUnit.SECONDS)
        hit.get()?.let { found = it }
    }

    private fun discover() {
        val l = object : NsdManager.DiscoveryListener {
            override fun onDiscoveryStarted(t: String) {}
            override fun onDiscoveryStopped(t: String) {}
            override fun onStartDiscoveryFailed(t: String, c: Int) {}
            override fun onStopDiscoveryFailed(t: String, c: Int) {}
            override fun onServiceLost(s: NsdServiceInfo) {}
            override fun onServiceFound(s: NsdServiceInfo) {
                nsd.resolveService(s, object : NsdManager.ResolveListener {
                    override fun onResolveFailed(i: NsdServiceInfo, c: Int) {}
                    override fun onServiceResolved(i: NsdServiceInfo) { found = i.host?.hostAddress }
                })
            }
        }
        discovery = l
        nsd.discoverServices("_bluey._tcp.", NsdManager.PROTOCOL_DNS_SD, l)
    }
}
