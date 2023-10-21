from threading import Thread
from queue import Empty
from .motec import MotecLog, MotecLogExtra, MotecEvent
from .channels import get_channel_definition
import os

from azure.storage.blob import BlobServiceClient
import re
import sqlite3
from pathlib import Path
from datetime import datetime
from logging import getLogger

l = getLogger(__name__)


class BaseLogger(Thread):

    def __init__(self, sampler=None, filetemplate=None, rawfile=None):
        super().__init__()
        self.sampler = sampler
        self.filetemplate = filetemplate
        self.filename = None
        self.blobname = None
        self.log = None
        self.rawfile = rawfile
        self.lap_samples = 0

    def run(self):

        l.info("Iniciando a captura ...")

        cur = None
        con = None

        # sort out the raw db
        if self.rawfile:
            l.info(f"Salvando RAW Data em {self.rawfile}")
            os.makedirs(os.path.dirname(self.rawfile), exist_ok=True)
            con = sqlite3.connect(self.rawfile, isolation_level="IMMEDIATE")
            cur = con.cursor()
            cur.execute("CREATE TABLE samples(timestamp float, data blob)")
            cur.execute("CREATE TABLE settings(name, value)")
            cur.execute("INSERT INTO settings(name, value) values (?, ?)",
                        ("freq", self.sampler.freq))
            con.commit()

        # start the sampler
        self.sampler.start()

        last_sample = b''

        while self.sampler.is_alive():

            # wait for new samples
            try:
                timestamp, sample = self.sampler.get(
                    timeout=1)  # to allow windows to use CTRL+C
                if cur:
                    to_save = sample if sample != last_sample else None
                    cur.execute(
                        "INSERT INTO samples(timestamp, data) VALUES (?, ?)", (timestamp, to_save))
                self.process_sample(timestamp, sample)
                last_sample = sample

            except Empty:
                pass

            except Exception as e:
                # might have been something in the processing that triggered the exception
                # so let's see if we can save it for later
                if con:
                    con.commit()

                # keep going?
                raise e

        if con:
            con.commit()
        self.save_log()
        self.sampler.join()

    def active_log(self):
        return self.log is not None

    def new_log(self, event=None, channels=None):
        if self.log:
            self.save_log()

        self.log = MotecLog()
        self.update_event(event)

        l.info(f"Salvando novo log {self.filename}")

        self.logx = MotecLogExtra()
        # add the channels

        for channel in channels:
            cd = get_channel_definition(channel, self.sampler.freq)
            self.log.add_channel(cd)

    def update_event(self, event=None):
        if not event or not self.log:
            return

        # convert the event datetime to MoTeC format
        dt = datetime.fromisoformat(event.datetime)
        self.log.date = dt.strftime('%d/%m/%Y')
        self.log.time = dt.strftime('%H:%M:%S')

        self.log.datetime = event.datetime
        self.log.driver = event.driver
        self.log.vehicle = event.vehicle
        self.log.venue = event.venue
        self.log.comment = event.shortcomment
        self.log.event = MotecEvent({
            "name": event.name,
            "session": event.session,
            "comment": event.comment,
            "venuepos": 0
        })

        template_vars = {}
        for k, v in vars(event).items():
            if v is not None:
                v = str(v).replace(' ', '_')
                v = re.sub(r'(?u)[^-\w.]', '', v)
            else:
                v = ""

            template_vars[k] = v

        filepath = Path(self.filetemplate).parts
        filepath = [p.format(**template_vars) for p in filepath]
        filepath = [re.sub(r'_+', '_', p) for p in filepath]
        filepath = [re.sub(r'^_|_$', '', p) for p in filepath]
        filepath = [p for p in filepath if p]
        self.filename = os.path.join(*filepath)

        print(f"Variável filename: {self.filename} ...")

        self.blobname = f"{event.driver}_{event.venue}_{event.session}_{event.datetime}"

        print(f"Variável blobname: {self.blobname} ...")

    def add_samples(self, samples):
        self.log.add_samples(samples)
        self.lap_samples += 1

    def add_lap(self, laptime=0.0, lap=None):

        samples = self.lap_samples
        freq = self.sampler.freq
        sample_time = samples / freq

        # vCS: Removendo a verificação de tempo de volta

        if abs(sample_time - laptime) > (3 / freq):
            l.warning(
                f"Lap {lap}: Descartado o tempo {laptime:.3f} pela diferença para o tempo capturado {sample_time:.3f}")
            laptime = sample_time

        l.info(f"Adicionando a volta {lap}, LapTime: {laptime:.3f},"
               f" Pacotes: {samples}, SampleTime: {sample_time:.3f}")

        self.logx.add_lap(laptime)
        self.lap_samples = 0

    def stop(self):
        if self.sampler:
            self.sampler.stop()

    def save_log(self):

        self.lap_samples = 0

        if not self.log:
            return

        # check if have at least 2 laps? out + pace
        if self.logx.valid_laps():

            os.makedirs(os.path.dirname(self.filename), exist_ok=True)

            # dump the ldx
            ldxfilename = f"{self.filename}.ldx"
            l.info(f"Salvando as voltas em {ldxfilename}")
            with open(ldxfilename, "w") as fout:
                fout.write(self.logx.to_string())

            # dump the log
            ldfilename = f"{self.filename}.ld"
            l.info(f"Salvando o log MoTeC em {ldfilename}")
            with open(ldfilename, "wb") as fout:
                fout.write(self.log.to_string())

            connection_string = "BlobEndpoint=https://stogtml.blob.core.windows.net/;QueueEndpoint=https://stogtml.queue.core.windows.net/;FileEndpoint=https://stogtml.file.core.windows.net/;TableEndpoint=https://stogtml.table.core.windows.net/;SharedAccessSignature=sv=2022-11-02&ss=b&srt=sco&sp=rwlacitfx&se=2024-02-01T02:59:59Z&st=2023-02-01T03:00:01Z&spr=https&sig=DYFOWFwgh2uGrpD82h%2BQFheDNfLyWgKb8Pza1IWjZIc%3D"
            blob_service_client = BlobServiceClient.from_connection_string(
                connection_string)

            # vCS: Subindo o arquivo ldx para o BLOB
            blob_client_ldx = blob_service_client.get_blob_client(
                container="motec-aliens", blob=f"{self.log.driver}\\{self.blobname}.ldx")
            with open(ldxfilename, "rb") as data_to_upload_ldx:
                blob_client_ldx.upload_blob(data_to_upload_ldx, overwrite=True)

            # vCS: Subindo o arquivo ld para o BLOB
            blob_client_ld = blob_service_client.get_blob_client(
                container="motec-aliens", blob=f"{self.log.driver}\\{self.blobname}.ld")
            with open(ldfilename, "rb") as data_to_upload_ld:
                blob_client_ld.upload_blob(data_to_upload_ld, overwrite=True)

        else:
            l.warning(f"Abortando o log {self.filename}. Menos de 2 voltas!")

        self.log = None

    def get_venue(self):
        if self.log:
            return self.log.venue
        else:
            return "Não Identificada!"

    def get_vehicle(self):
        if self.log:
            return self.log.vehicle
        else:
            return "Não Identificado!"
