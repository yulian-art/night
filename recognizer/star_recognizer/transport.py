"""Ordered gRPC producer; camera, inference and reset reception remain independent."""
from dataclasses import dataclass, field
import queue
import threading
import ipaddress
from .types import InputEvent

def validate_address(address):
    host,separator,port=address.rpartition(":")
    host=host.strip("[]")
    if not separator or not port.isdecimal() or not 1<=int(port)<=65535:
        raise ValueError("address must be loopback-host:port")
    if host!="localhost":
        try:
            valid=ipaddress.ip_address(host).is_loopback
        except ValueError:
            valid=False
        if not valid:
            raise ValueError("recognizer connects only to a loopback Go service")

@dataclass
class _Session:
    events: queue.Queue
    generation: int = 0
    call: object = None
    channel: object = None
    closed: threading.Event = field(default_factory=threading.Event)
    failure: str = ""

class GrpcBridge:
    def __init__(self,address,on_reset,on_disconnect,capacity=64):
        validate_address(address)
        if capacity<1:
            raise ValueError("capacity must be positive")
        self.address,self.on_reset,self.on_disconnect=address,on_reset,on_disconnect
        self.capacity=capacity
        self._lock=threading.Lock()
        self._stop=threading.Event()
        self._session=None
        self._thread=None
        self.connected=False
        self.last_error="Not connected"

    @staticmethod
    def _drain(session):
        while True:
            try:
                session.events.get_nowait()
            except queue.Empty:
                return

    def start(self):
        if self._thread:
            raise RuntimeError("bridge already started")
        self._thread=threading.Thread(target=self._loop,name="recognizer-grpc",daemon=True)
        self._thread.start()

    def send(self,event:InputEvent):
        call=None
        with self._lock:
            session=self._session
            if session is None or session.closed.is_set() or event.generation!=session.generation:
                return
            try:
                session.events.put_nowait(event)
            except queue.Full:
                session.failure="Action queue overflow; input discarded and stream closed"
                session.closed.set()
                self._drain(session)
                call=session.call
        if call:
            call.cancel()

    def _requests(self,session,pb):
        while not self._stop.is_set() and not session.closed.is_set():
            try:
                event=session.events.get(timeout=0.1)
            except queue.Empty:
                continue
            with self._lock:
                if session is not self._session or session.closed.is_set() or event.generation!=session.generation:
                    continue
            if event.state is not None:
                yield pb.InputEvent(tracking=pb.TrackingEvent(generation=event.generation,state=int(event.state)))
            else:
                yield pb.InputEvent(action=pb.ActionEvent(generation=event.generation,action=int(event.action),phase=int(event.phase)))

    def _loop(self):
        import grpc
        from .generated.star.v1 import star_pb2 as pb
        delay=0.25
        fatal={grpc.StatusCode.ALREADY_EXISTS,grpc.StatusCode.INVALID_ARGUMENT,grpc.StatusCode.FAILED_PRECONDITION,
               grpc.StatusCode.UNIMPLEMENTED,grpc.StatusCode.PERMISSION_DENIED}
        while not self._stop.is_set():
            session=_Session(queue.Queue(self.capacity))
            code=None
            with self._lock:
                self._session=session
            try:
                session.channel=grpc.insecure_channel(self.address,options=(("grpc.enable_retries",0),))
                connect=session.channel.stream_stream("/star.v1.RecognizerService/Connect",
                       request_serializer=pb.InputEvent.SerializeToString,response_deserializer=pb.ResetInput.FromString)
                session.call=connect(self._requests(session,pb))
                if session.closed.is_set():
                    session.call.cancel()
                for reset in session.call:
                    with self._lock:
                        if session is not self._session or session.closed.is_set() or self._stop.is_set():
                            break
                        session.generation=reset.generation
                        self._drain(session)
                        self.connected=True
                        self.last_error=""
                    # Never hold transport lock while invoking application callbacks.
                    self.on_reset(reset.generation)
                    delay=0.25
                reason=session.failure or "Go input stream closed"
            except grpc.RpcError as exc:
                code=exc.code()
                reason=session.failure or f"{code.name}: {exc.details()}"
            except Exception as exc:
                reason=f"Bridge error: {exc}"
                code=grpc.StatusCode.INVALID_ARGUMENT
            finally:
                session.closed.set()
                if session.call:
                    session.call.cancel()
                if session.channel:
                    session.channel.close()
                with self._lock:
                    if self._session is session:
                        self._session=None
                    self.connected=False
                    self._drain(session)
            self.last_error=reason
            self.on_reset(0)
            if not self._stop.is_set():
                self.on_disconnect(reason)
            if code in fatal or self._stop.wait(delay):
                return
            delay=min(delay*2,5)

    def close(self):
        self._stop.set()
        with self._lock:
            session=self._session
            if session:
                session.closed.set()
                self._drain(session)
        if session and session.call:
            session.call.cancel()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
            if self._thread.is_alive():
                raise RuntimeError("gRPC worker did not stop in time")
