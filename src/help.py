COMMAND_HELP = {
    "birras": "!birras - Muestra las proximas AdminBirras y eventos de Sysarmy.",
    "caucho": "!caucho - Muestra la tasa de caucion actual.",
    "clima": "!clima <ciudad> - Muestra el clima de una ciudad. Ejemplo: !clima Buenos Aires",
    "cripto": "!cripto - Muestra precios actuales de criptomonedas.",
    "dolar": "!dolar [pesos] - Muestra cotizaciones del dolar. Opcionalmente convierte un monto. Ejemplo: !dolar 50000",
    "euro": "!euro - Muestra la cotizacion actual del euro.",
    "feriadoar": "!feriadoar - Muestra los proximos feriados de Argentina.",
    "feriadocl": "!feriadocl - Muestra los proximos feriados de Chile.",
    "feriadoes": "!feriadoes - Muestra los proximos feriados de Espana.",
    "feriadomx": "!feriadomx - Muestra los proximos feriados de Mexico.",
    "feriadouy": "!feriadouy - Muestra los proximos feriados de Uruguay.",
    "fulbo": "!fulbo <liga> - Muestra resultados de futbol. Ligas: PL, BL1, PD, FL1 y SA. Ejemplo: !fulbo PL",
    "rank": "!rank - Muestra el ranking general de karma.",
    "karma": "!karma <palabra o usuario> - Consulta su karma. Ejemplo: !karma nachi",
    "kgivers": "!kgivers - Muestra quienes dieron mas karma.",
    "kgiven": "!kgiven <usuario> - Consulta cuanto karma dio un usuario. Ejemplo: !kgiven nachi",
    "pesos": "!pesos <monto> - Convierte pesos argentinos a dolares. Ejemplo: !pesos 10000",
    "q": "!q - Devuelve una cita aleatoria del historial.",
    "qadd": "!qadd <cita> - Agrega una cita al historial. Ejemplo: !qadd <nachi> esto queda para la posteridad",
    "qsearch": "!qsearch <texto> - Busca citas por texto o usuario. Ejemplo: !qsearch kubernetes",
    "subte": "!subte - Muestra el estado del Subte de Buenos Aires.",
    "status": "!status <servicio> - Muestra el estado actual y uptime estimado de los ultimos 30 dias (90 en Auth0). Servicios: atlassian, auth0, claude, cloudflare, datadog (US1), digitalocean, discord, donweb, github, npm, openai. Ejemplo: !status github",
    "underground": "!underground - Muestra el estado del Underground de Londres.",
    "ping": "!ping - Comprueba si el bot esta respondiendo.",
    "flip": "!flip - Tira una mesa. No requiere argumentos.",
    "shrug": "!shrug - Responde con el clasico encogimiento de hombros.",
    "help": "!help [comando] - Muestra la lista de comandos o ayuda detallada. Ejemplo: !help clima",
}

REQUIRED_ARGUMENTS = {
    "clima": "ciudad",
    "fulbo": "liga",
    "karma": "palabra o usuario",
    "kgiven": "usuario",
    "pesos": "monto",
    "qadd": "cita",
    "qsearch": "texto",
    "status": "servicio",
}


GENERAL_HELP = """Estos son los comandos disponibles en el bot de Sysarmy:
!rank !karma !kgivers !kgiven | !q !qadd !qsearch | !caucho !cripto !dolar !euro !pesos | !clima !fulbo !subte !underground !status | !feriadoar !feriadocl !feriadoes !feriadomx !feriadouy | !birras | !ping !flip !shrug
Ejecuta !help <comando> para ver mas informacion. Ejemplo: !help karma"""


def help_message(argument: str = "") -> str:
    command = argument.strip().lower().removeprefix("!")
    if not command:
        return GENERAL_HELP
    detail = COMMAND_HELP.get(command)
    if detail:
        return detail
    return f"No hay ayuda para '{command}'. Ejecuta !help para ver los comandos disponibles."


def missing_argument_message(command: str) -> str:
    argument = REQUIRED_ARGUMENTS.get(command, "argumento")
    return f"Falta el argumento <{argument}>. Uso: !{command} <{argument}>"
