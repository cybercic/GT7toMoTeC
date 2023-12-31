from stm.sampler import BaseSampler
import socket
import time
from logging import getLogger
l = getLogger(__name__)

DEFAULT_PORT = 33740
DEFAULT_HEARTBEAT_PORT = 33739
PACKETSIZE = 1500


class GT7Sampler(BaseSampler):

    def __init__(self, addr=None, port=DEFAULT_PORT, hb_port=DEFAULT_HEARTBEAT_PORT, freq=None):
        super().__init__(freq=freq)
        port = int(port)
        if port != DEFAULT_PORT:
            # do not send heartbeats if we are not running on the default ports
            # as GT7 will ignore them anyway
            self.hb_addr = None
            l.info("Redirecionando os pacotes UDP.")
        else:
            self.hb_addr = (addr, hb_port)

        # Create a UDP socket for the inbound packets
        self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, )

        # Set the SO_REUSEADDR option to allow immediate reuse of the port
        self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

        # Bind to any address
        self.socket.bind(('0.0.0.0', port))
        self.socket.settimeout(1)

    def run(self):

        self.running = True  # this is set to False in BaseSampler when we are done
        #
        self.send_hb()
        pkt_count = 0

        while self.running:
            try:

                data, _ = self.socket.recvfrom(PACKETSIZE)
                ts = time.time()
                pkt_count += 1

                if (pkt_count % 100) == 0:
                    # send a heartbeat about every 6 seconds
                    self.send_hb()

                self.put((ts, data))

            except socket.timeout:
                self.send_hb()

    def send_hb(self):
        if not self.hb_addr:
            return

        send_data = b'A'
        try:
            self.socket.sendto(send_data, self.hb_addr)
        except Exception as e:
            # l.error(e)
            pass
