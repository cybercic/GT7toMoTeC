import time

import os
import argparse

import appdirs
import platform

from stm.gt7 import GT7Logger, GT7Sampler
from stm.sampler import RawSampler

from logging import getLogger, basicConfig, DEBUG
basicConfig(
    level=DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
l = getLogger(__name__)


def main():

    parser = argparse.ArgumentParser(
        description="Converter os pacotes do GT7 para o MoTeC i2")
    parser.add_argument(
        "addr", type=str, help="Endereço IP do PlayStation ou arquivo RAW")
    parser.add_argument("--driver", type=str, default="",
                        help="Nome do piloto")
    parser.add_argument("--session", type=str, default="",
                        help="Sessão (Treino, Classificação, Corrida)")
    parser.add_argument("--vehicle", type=str, default="",
                        help="Substituir o nome do carro")
    parser.add_argument("--venue", type=str, default="",
                        help="Nome da pista, o MoTeC não gerará o mapa sem o nome")
    parser.add_argument("--replay", action="store_true",
                        help="Gravar dados do replay")
    parser.add_argument("--freq", type=int, default=60,
                        help="Frequência dos pacotes")
    parser.add_argument(
        "--saveraw", help="Salvar os pacotes em um banco SQLite3 (RAW)", action="store_true")
    parser.add_argument(
        "--loadraw", help="Carregar os pacotes de um banco SQLite3 (RAW)", action="store_true")
    args = parser.parse_args()

    if platform.system() == "Windows":
        logs_dir = os.path.join("logs", "gt7")
        logs_raw = os.path.join("logs", "raw")
    else:
        config_dir = appdirs.user_config_dir(appname="LaudaGT")
        os.makedirs(config_dir, exist_ok=True)
        logs_dir = config_dir
        logs_raw = config_dir

    filetemplate = os.path.join(
        logs_dir, "{driver}_{venue}_{session}_{datetime}")

    if args.saveraw:
        rawfile = os.path.join(logs_raw, f"{time.time():.0f}.db")
    else:
        rawfile = None

    if args.loadraw:
        sampler = RawSampler(rawfile=args.addr)
    else:
        sampler = GT7Sampler(addr=args.addr, freq=args.freq)

    logger = GT7Logger(
        rawfile=rawfile,
        sampler=sampler,
        filetemplate=filetemplate,
        replay=args.replay,
        driver=args.driver,
        session=args.session,
        vehicle=args.vehicle,
        venue=args.venue
    )

    try:
        logger.start()
        while logger.is_alive():
            logger.join(0.1)
    except KeyboardInterrupt:
        l.warning("Finalizando")
        logger.stop()
        logger.join()


if __name__ == '__main__':
    main()
