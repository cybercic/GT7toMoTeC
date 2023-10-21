import json
import time

from logging import getLogger, basicConfig, DEBUG

import PySimpleGUI as sg

import sys
import os

import appdirs
import platform

from stm.gt7 import GT7Logger, GT7Sampler
from stm.version import __version__

# Diretório de configuração
config_dir = appdirs.user_config_dir(appname="LaudaGT")
os.makedirs(config_dir, exist_ok=True)
print(f"Diretório de configuração: {config_dir} ...")

STATE_FILE = os.path.join(config_dir, "LaudaGT.cfg")
state = {
    "IP": "192.168.0.100",
    "PORT": 33740,
    "REPLAY": False,
    "DRIVER": "",
    "SESSION": ""
}

try:
    with open(STATE_FILE) as f:
        state.update(json.load(f))
except Exception as e:
    pass

sg.change_look_and_feel('DarkRed1')
sg.set_options(font="Calibri 10")

BUTTON_DISABLED = ('grey', sg.theme_background_color())
BUTTON_ENABLED = ('white', sg.theme_background_color())

labels1 = [
    [sg.Text("PlayStation IP: ")],
    [sg.Text("Porta UDP: ")],
    [sg.Text("Capturar Replays: ")],
    [sg.Text("Piloto: ")],
    [sg.Text("Sessão: ")],
]

labels2 = [
    [sg.Text("Arquivo Log: ")],
    [sg.Text("Carro: ")],
    [sg.Text("Pista: ")],
    [sg.Text("Pacote: ")],
    [sg.Text("Volta: ")],
]

values1 = [
    [sg.Input(state["IP"], key="IP", size=(15, 1), enable_events=True, justification="center"),
     sg.Text("Deve estar na mesma rede local!", font="Calibri 8 italic")],
    [sg.Input(state["PORT"], key="PORT", size=(8, 1), enable_events=True, justification="center"),
     sg.Text("Se estiver redirecionando os pacotes UDP ...", font="Calibri 8 italic")],
    [sg.Checkbox("", state["REPLAY"], key="REPLAY", enable_events=True), sg.Text(
        "ATENÇÃO: Consome muito espaço no disco rígido!", font="Calibri 8 italic")],
    [sg.Input(state["DRIVER"], key="DRIVER", size=(15, 1), enable_events=True)],
    [sg.Input(state["SESSION"], key="SESSION",
              size=(30, 1), enable_events=True)],
]

values2 = [
    [sg.Text("Não Iniciado", key="LOGFILE")],
    [sg.Text("Não Identificado", key="VEHICLE")],
    [sg.Text("Não Identificada", key="VENUE")],
    [sg.Text("Não Disponível", key="TICK")],
    [sg.Text("Não Disponível", key="LAP")],
]

# Caminho do executável usando a função sys._MEIPASS
executable_path = sys._MEIPASS if hasattr(
    sys, '_MEIPASS') else os.path.abspath(".")
print(f"Caminho do executável: {executable_path} ...")

# Concatenando o caminho do executável com os caminhos relativos
logo_path = os.path.join(executable_path, 'stm/gt7/db/logo.png')
partners_path = os.path.join(executable_path, 'stm/gt7/db/partners.png')
icon_path = os.path.join(executable_path, 'stm/gt7/db/laudagt.ico')

layout = [
    [sg.Column(labels1, element_justification='r'), sg.Column(
        values1), sg.Image(logo_path, pad=(10, 0))],
    [sg.HorizontalSeparator()],
    [sg.Column(labels2, element_justification='r'), sg.Column(values2)],
    [
        sg.Button('Iniciar', key="START"),
        sg.Button("Parar", key="STOP", disabled=True,
                  button_color=BUTTON_DISABLED),
        sg.Button('Sair', key="QUIT"),
        sg.Checkbox("Salvar Pacotes", key="RAWFILE")
    ],
    [sg.HorizontalSeparator()],
    [sg.Output(size=(120, 12), echo_stdout_stderr=True)],
    [sg.Image(partners_path)]
]

window = sg.Window(f"GT7 logger v{__version__}", layout, size=(
    750, 610), icon=icon_path, finalize=True)

# Iniciando o logger
basicConfig(
    level=DEBUG,
    format="%(asctime)s.%(msecs)03d [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S"
)

l = getLogger(__name__)

logger = None

while True:
    event, values = window.read(timeout=500)
    if event in (sg.WINDOW_CLOSED, "QUIT"):
        break

    if event == "IP" and len(values['IP']) and values['IP'][-1] not in ('.1234567890'):
        window["IP"].update(values['IP'][:-1])

    if event == "PORT" and len(values['PORT']) and values['PORT'][-1] not in ('1234567890'):
        window["PORT"].update(values['PORT'][:-1])

    if event in state:
        state[event] = values[event]

    if event == "START":

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
        print(f"Variável filetemplate: {filetemplate} ...")

        if values["RAWFILE"]:
            rawfile = os.path.join(logs_raw, f"{time.time():.0f}.db")
            print(f"Variável rawfile: {rawfile} ...")
        else:
            rawfile = None

        logger = GT7Logger(
            rawfile=rawfile,
            sampler=GT7Sampler(
                addr=values["IP"], port=values["PORT"], freq=60),
            filetemplate=filetemplate,
            replay=values["REPLAY"],
            driver=values["DRIVER"],
            session=values["SESSION"]
        )
        logger.start()

    if event == "STOP" and logger:
        logger.stop()
        logger.join()
        logger = None

    if logger:
        window["QUIT"].update(disabled=True, button_color=BUTTON_DISABLED)
        window["START"].update(disabled=True, button_color=BUTTON_DISABLED)
        window["STOP"].update(disabled=False, button_color=BUTTON_ENABLED)
        window["LOGFILE"].update(logger.filename)

        if logger.last_packet:
            p = logger.last_packet
            window["LAP"].update(f"{p.current_lap}/{p.laps}")
            window["TICK"].update(f"{p.tick}")
            window["VEHICLE"].update(logger.get_vehicle())
            window["VENUE"].update(logger.get_venue())

    else:
        window["QUIT"].update(disabled=False, button_color=BUTTON_ENABLED)
        window["START"].update(disabled=False, button_color=BUTTON_ENABLED)
        window["STOP"].update(disabled=True, button_color=BUTTON_DISABLED)
        window["LOGFILE"].update("Não Iniciado")
        window["LAP"].update("Não Disponível")
        window["TICK"].update("Não Disponível")
        window["VEHICLE"].update("Não Identificado")
        window["VENUE"].update("Não Identificada")

try:
    with open(STATE_FILE, "w") as f:
        json.dump(state, f)
except Exception as e:
    print(e)
    pass

window.close()
