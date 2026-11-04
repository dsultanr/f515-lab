import android.os.Binder;
import android.os.IBinder;
import android.os.Parcel;
import android.os.RemoteException;
import android.os.SystemClock;
import java.util.concurrent.LinkedBlockingQueue;
import java.util.concurrent.TimeUnit;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

/** Passive, bounded observer for the verified F515 radio AIDL (2026-11-04).
 * No tune, seek, playback, settings, signal-request or power transactions.
 * stdout is drained outside Binder threads; dropped records are reported.
 */
public final class RadioWatch extends Binder {
    private static final String SERVICE = "com.ts.base.aidl.IRadioServiceBase";
    private static final String LISTENER = "com.ts.base.aidl.IRadioListener";
    private final LinkedBlockingQueue<String> events = new LinkedBlockingQueue<>(512);
    private final AtomicLong dropped = new AtomicLong();
    private final AtomicBoolean alive = new AtomicBoolean(true);
    private final AtomicBoolean registered = new AtomicBoolean();
    private final IBinder service;

    private RadioWatch(IBinder service) {
        this.service = service;
        attachInterface(null, LISTENER);
    }

    private void record(String event) {
        if (!events.offer(System.currentTimeMillis() + " " + event)) dropped.incrementAndGet();
    }

    @Override public boolean onTransact(int code, Parcel data, Parcel reply, int flags)
            throws RemoteException {
        if (code == INTERFACE_TRANSACTION) {
            if (reply != null) reply.writeString(LISTENER);
            return true;
        }
        if (code < 1 || code > 19) return super.onTransact(code, data, reply, flags);
        data.enforceInterface(LISTENER);
        try {
            switch (code) {
                case 1:
                case 2:
                    record("announcement event=" + code + " source=" + data.readInt()
                           + " type=" + data.readInt());
                    break;
                case 3:
                    if (data.readInt() == 0) {
                        record("radio_info null");
                    } else {
                        int index = data.readInt();
                        int radioType = data.readInt();
                        int pty = data.readInt();
                        int frequency = data.readInt();
                        record("radio_info index=" + index + " radioType=" + radioType
                               + " pty=" + pty + " frequencyId=" + frequency);
                    }
                    break;
                case 13:
                    record("signal frequency=" + data.readInt() + " level=" + data.readInt()
                           + " usn=" + data.readInt() + " wam=" + data.readInt()
                           + " offset=" + data.readInt() + " snr=" + data.readInt());
                    break;
                case 18:
                    record("AF_CHANGE pastFreq=" + data.readInt() + " newFreq=" + data.readInt());
                    break;
                case 19:
                    record("chip_ready=" + (data.readInt() != 0));
                    break;
                default:
                    // Other notifications are intentionally consumed without parsing.
                    break;
            }
        } catch (RuntimeException e) {
            record("parse_error code=" + code + " error=" + e);
        }
        return true; // Verified listener methods are oneway, with no reply payload.
    }

    private void listenerCall(int code) throws RemoteException {
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(SERVICE);
            data.writeStrongBinder(this);
            if (!service.transact(code, data, reply, 0)) throw new RemoteException("transaction rejected");
            reply.readException();
        } finally { data.recycle(); reply.recycle(); }
    }

    private boolean readFlag(int code) throws RemoteException {
        Parcel data = Parcel.obtain();
        Parcel reply = Parcel.obtain();
        try {
            data.writeInterfaceToken(SERVICE);
            if (!service.transact(code, data, reply, 0)) throw new RemoteException("getter rejected");
            reply.readException();
            return reply.readInt() != 0;
        } finally { data.recycle(); reply.recycle(); }
    }

    private void unregister() {
        if (registered.compareAndSet(true, false)) {
            try { listenerCall(17); record("unregistered"); }
            catch (RemoteException e) { record("unregister_error " + e); }
        }
    }

    public static void main(String[] args) throws Exception {
        int seconds = args.length == 1 ? Integer.parseInt(args[0]) : 3;
        if (seconds < 1 || seconds > 3600) throw new IllegalArgumentException("duration must be 1..3600 seconds");
        IBinder binder = (IBinder) Class.forName("android.os.ServiceManager")
                .getMethod("getService", String.class).invoke(null, "ts_radiomanager");
        if (binder == null) throw new IllegalStateException("ts_radiomanager unavailable");
        RadioWatch watch = new RadioWatch(binder);
        binder.linkToDeath(() -> { watch.alive.set(false); watch.record("service_died"); }, 0);
        Runtime.getRuntime().addShutdownHook(new Thread(watch::unregister));
        long end = SystemClock.elapsedRealtime() + seconds * 1000L;
        try {
            watch.record("start duration_seconds=" + seconds + " af=" + watch.readFlag(30)
                         + " traffic_announcement=" + watch.readFlag(34));
            watch.listenerCall(16);
            watch.registered.set(true);
            watch.record("registered");
            while (watch.alive.get() && SystemClock.elapsedRealtime() < end) {
                String event = watch.events.poll(500, TimeUnit.MILLISECONDS);
                if (event != null) System.out.println(event);
                if (System.out.checkError()) break;
            }
        } finally {
            watch.unregister();
            String event;
            while ((event = watch.events.poll()) != null) System.out.println(event);
            System.out.println(System.currentTimeMillis() + " stop dropped=" + watch.dropped.get());
        }
        System.exit(0); // app_process Binder threads must not outlive the bounded capture.
    }
}
