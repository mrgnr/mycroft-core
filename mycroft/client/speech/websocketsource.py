from queue import Queue, Empty

from speech_recognition import AudioSource
from tornado import web, ioloop
from tornado.websocket import WebSocketHandler

from mycroft.util import create_daemon
from mycroft.util.log import LOG


class AudioWebSocketHandler(WebSocketHandler):
    def open(self):
        LOG.debug("WebSocket opened")

    def on_message(self, message):
        try:
            self.app.source.stream.write(message)
        except Exception as e:
            LOG.debug("Failed to write websocket data to audio stream")

    def on_close(self):
        LOG.debug("WebSocket closed")


class WebSocketAudioSource(AudioSource):
    class WebSocketAudioStream(Queue):
        def __init__(self, source):
            self.source = source

        def read(self, chunk_size, overflow_exc):
            chunks = chunk_size / self.source.CHUNK

            for _ in range(chunks):
                try:
                    yield self.pop()
                except Empty as e:
                    if overflow_exc:
                        raise IOError

        def write(self, data):
            if not self.source.muted:
                self.push(data)


    server_thread = None

    def __init__(self, route="/speech", host="0.0.0.0", port=6969,
                 sample_rate=16000, chunk_size=1024, mute=False):

        self.route = route
        self.host = host
        self.port = port
        self.SAMPLE_RATE = sample_rate
        self.CHUNK = chunk_size
        self.muted = False
        self.stream = None

        if mute:
            self.mute()

        self.app = web.Application([(self.route, AudioWebSocketHandler)],
                                   debug=True)
        self.app.source = self
        self.app.listen(self.port, self.host)

        if not WebSocketAudioSource.server_thread:
            WebSocketAudioSource.server_thread = create_daemon(
                ioloop.IOLoop.instance().start)
        LOG.debug('IOLoop started @ '
                  'ws://{}:{}{}'.format(self.host, self.port, self.route))


    def __enter__(self):
        return self._start()

    def __exit__(self, exc_type, exc_value, traceback):
        return self._stop()

    def _start(self):
        self.stream = WebSocketAudioSource.WebSocketAudioStream(self)
        return self

    def _stop(self):
        self.stream = None

    def restart(self):
        self._stop()
        self._start()

    def mute(self):
        self.muted = True

    def unmute(self):
        self.muted = False

    def is_muted(self):
        return self.muted

